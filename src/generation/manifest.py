"""Asset manifest for tracking generated assets."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id
from src.common.models import Asset, AssetType, ShotVisualSpec, VisualFidelityLevel


class ManifestStatus(str, Enum):
    """Status of the asset manifest."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"  # Some assets failed
    FAILED = "failed"


class AssetRequirement(BaseModel):
    """A required asset to be generated."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("req"))
    shot_id: str
    scene_id: str
    asset_type: AssetType
    priority: int = 1  # 1 = highest

    # Generation spec
    prompt: str = ""
    style_hints: list[str] = Field(default_factory=list)
    reference_image_path: str | None = None

    # Visual specification (for ShotVisualSpec-driven generation)
    visual_spec: ShotVisualSpec | None = None
    shot_type: str = "medium"  # Shot type for framing

    # Fidelity level (PLACEHOLDER or REFERENCE)
    fidelity_level: VisualFidelityLevel = VisualFidelityLevel.PLACEHOLDER

    # Image-specific
    target_width: int = 1920
    target_height: int = 1080

    # Audio-specific
    duration_seconds: float | None = None
    voice_id: str | None = None

    # Status
    generated: bool = False
    asset_id: str | None = None
    error: str | None = None


class AssetManifest(BaseModel):
    """Manifest tracking all assets for a video."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("manifest"))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Target
    story_id: str
    video_id: str | None = None

    # Status
    status: ManifestStatus = ManifestStatus.PENDING
    total_requirements: int = 0
    completed_count: int = 0
    failed_count: int = 0

    # Requirements
    requirements: list[AssetRequirement] = Field(default_factory=list)

    # Generated assets
    assets: list[Asset] = Field(default_factory=list)

    # Output
    output_directory: str = "outputs/assets"

    # Cost tracking
    total_generation_cost: float = 0.0
    total_generation_time_seconds: float = 0.0

    def add_requirement(
        self,
        shot_id: str,
        scene_id: str,
        asset_type: AssetType,
        prompt: str = "",
        **kwargs,
    ) -> "AssetManifest":
        """Add an asset requirement."""
        req = AssetRequirement(
            shot_id=shot_id,
            scene_id=scene_id,
            asset_type=asset_type,
            prompt=prompt,
            **kwargs,
        )
        new_reqs = list(self.requirements) + [req]
        return self.model_copy(update={
            "requirements": new_reqs,
            "total_requirements": len(new_reqs),
            "updated_at": datetime.utcnow(),
        })

    def mark_completed(self, req_id: str, asset: Asset) -> "AssetManifest":
        """Mark a requirement as completed."""
        new_reqs = []
        for req in self.requirements:
            if req.id == req_id:
                req = req.model_copy(update={
                    "generated": True,
                    "asset_id": asset.id,
                })
            new_reqs.append(req)

        new_assets = list(self.assets) + [asset]
        new_completed = self.completed_count + 1

        status = ManifestStatus.IN_PROGRESS
        if new_completed == self.total_requirements:
            status = ManifestStatus.COMPLETED
        elif self.failed_count > 0:
            status = ManifestStatus.PARTIAL

        return self.model_copy(update={
            "requirements": new_reqs,
            "assets": new_assets,
            "completed_count": new_completed,
            "status": status,
            "updated_at": datetime.utcnow(),
            "total_generation_cost": self.total_generation_cost + asset.generation_cost,
            "total_generation_time_seconds": self.total_generation_time_seconds + asset.generation_time_seconds,
        })

    def mark_failed(self, req_id: str, error: str) -> "AssetManifest":
        """Mark a requirement as failed."""
        new_reqs = []
        for req in self.requirements:
            if req.id == req_id:
                req = req.model_copy(update={"error": error})
            new_reqs.append(req)

        status = ManifestStatus.PARTIAL
        if self.completed_count == 0 and self.failed_count + 1 == self.total_requirements:
            status = ManifestStatus.FAILED

        return self.model_copy(update={
            "requirements": new_reqs,
            "failed_count": self.failed_count + 1,
            "status": status,
            "updated_at": datetime.utcnow(),
        })

    def get_pending_requirements(self) -> list[AssetRequirement]:
        """Get all pending requirements."""
        return [r for r in self.requirements if not r.generated and r.error is None]

    def get_asset_for_shot(self, shot_id: str, asset_type: AssetType) -> Asset | None:
        """Get the generated asset for a shot."""
        for req in self.requirements:
            if req.shot_id == shot_id and req.asset_type == asset_type and req.asset_id:
                for asset in self.assets:
                    if asset.id == req.asset_id:
                        return asset
        return None

    def progress_percent(self) -> float:
        """Return completion percentage."""
        if self.total_requirements == 0:
            return 100.0
        return (self.completed_count / self.total_requirements) * 100

    def summary(self) -> dict:
        """Return summary for logging."""
        # Count by fidelity
        placeholder_count = sum(
            1 for r in self.requirements
            if r.asset_type == AssetType.IMAGE and r.fidelity_level == VisualFidelityLevel.PLACEHOLDER
        )
        reference_count = sum(
            1 for r in self.requirements
            if r.asset_type == AssetType.IMAGE and r.fidelity_level == VisualFidelityLevel.REFERENCE
        )

        return {
            "id": self.id,
            "story_id": self.story_id,
            "status": self.status.value,
            "progress": f"{self.progress_percent():.1f}%",
            "completed": self.completed_count,
            "failed": self.failed_count,
            "total": self.total_requirements,
            "placeholder_count": placeholder_count,
            "reference_count": reference_count,
            "cost": f"${self.total_generation_cost:.2f}",
        }

    def get_fidelity_breakdown(self) -> dict:
        """Return detailed breakdown of assets by fidelity level.

        Useful for review packs to clearly label which shots are
        REFERENCE vs PLACEHOLDER.
        """
        breakdown = {
            "placeholder": [],
            "reference": [],
        }

        for req in self.requirements:
            if req.asset_type == AssetType.IMAGE:
                entry = {
                    "req_id": req.id,
                    "shot_id": req.shot_id,
                    "scene_id": req.scene_id,
                    "generated": req.generated,
                    "asset_id": req.asset_id,
                    "shot_role": req.visual_spec.role.value if req.visual_spec else None,
                }
                if req.fidelity_level == VisualFidelityLevel.REFERENCE:
                    breakdown["reference"].append(entry)
                else:
                    breakdown["placeholder"].append(entry)

        return breakdown


def create_manifest_from_shots(
    story_id: str,
    shots: list,
    output_dir: str = "outputs/assets",
    include_voiceover: bool = True,
) -> AssetManifest:
    """Create an asset manifest from a list of shots.

    Includes ShotVisualSpec for visually-differentiated placeholder generation.
    """
    manifest = AssetManifest(
        story_id=story_id,
        output_directory=output_dir,
    )

    for shot in shots:
        # Determine fidelity level from visual spec (default PLACEHOLDER)
        fidelity = VisualFidelityLevel.PLACEHOLDER
        if shot.visual_spec and shot.visual_spec.fidelity_level:
            fidelity = shot.visual_spec.fidelity_level

        # Every shot needs an image - include visual_spec for differentiation
        manifest = manifest.add_requirement(
            shot_id=shot.id,
            scene_id=shot.shot_plan_id.replace("plan_", "scene_"),
            asset_type=AssetType.IMAGE,
            prompt=shot.visual_description,
            style_hints=[shot.mood, shot.lighting] if shot.lighting else [shot.mood],
            visual_spec=shot.visual_spec,  # Pass through for visual differentiation
            shot_type=shot.shot_type.value if hasattr(shot.shot_type, 'value') else str(shot.shot_type),
            fidelity_level=fidelity,
        )

        # Add voiceover if narration exists
        if include_voiceover and shot.narration_text:
            manifest = manifest.add_requirement(
                shot_id=shot.id,
                scene_id=shot.shot_plan_id.replace("plan_", "scene_"),
                asset_type=AssetType.VOICEOVER,
                prompt=shot.narration_text,
                duration_seconds=shot.duration_seconds,
            )

    return manifest
