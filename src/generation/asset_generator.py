"""Unified asset generator with mixed fidelity support.

This module provides a single entry point for asset generation that
dispatches between PlaceholderGenerator and VisualReferenceGenerator
based on the fidelity_level specified in each AssetRequirement.

The edit/timing/sequencing remain unchanged - only visual content varies.
"""

from __future__ import annotations

from pathlib import Path

from src.common.logging import get_logger
from src.common.models import Asset, AssetType, VisualFidelityLevel
from src.generation.manifest import AssetRequirement, AssetManifest
from src.generation.placeholder import PlaceholderGenerator
from src.generation.reference_generator import (
    VisualReferenceGenerator,
    create_reference_generator,
)

logger = get_logger(__name__)


class MixedFidelityAssetGenerator:
    """Asset generator supporting mixed PLACEHOLDER/REFERENCE fidelity.

    This generator acts as a unified entry point that:
    1. Routes PLACEHOLDER requirements to PlaceholderGenerator
    2. Routes REFERENCE requirements to VisualReferenceGenerator
    3. Tracks costs across both generators
    4. Ensures edit/timing remains unchanged regardless of fidelity

    Design principles:
    - Same shot timing whether PLACEHOLDER or REFERENCE
    - Only visual content changes
    - Cost tracking for budget control
    - Graceful fallback to PLACEHOLDER if REFERENCE fails
    """

    def __init__(
        self,
        output_dir: str = "outputs/assets",
        reference_backend: str = "stub",
        reference_cost_cap: float = 1.0,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize generators
        self.placeholder_generator = PlaceholderGenerator(
            output_dir=str(self.output_dir / "placeholder")
        )
        self.reference_generator = create_reference_generator(
            backend_name=reference_backend,
            output_dir=str(self.output_dir / "reference"),
            cost_cap_usd=reference_cost_cap,
        )

        # Tracking
        self.placeholder_count = 0
        self.reference_count = 0
        self.fallback_count = 0  # REFERENCE failed, fell back to PLACEHOLDER

    async def generate(self, requirement: AssetRequirement) -> Asset:
        """Generate an asset based on its fidelity level.

        Args:
            requirement: Asset requirement with fidelity_level

        Returns:
            Generated Asset
        """
        # Only images support fidelity levels (audio is always "real")
        if requirement.asset_type != AssetType.IMAGE:
            return await self.placeholder_generator.generate(requirement)

        fidelity = requirement.fidelity_level

        if fidelity == VisualFidelityLevel.REFERENCE:
            try:
                asset = await self.reference_generator.generate(requirement)
                self.reference_count += 1
                return asset
            except ValueError as e:
                # Cost cap exceeded or other error - fall back to placeholder
                logger.warning(
                    "reference_fallback_to_placeholder",
                    shot_id=requirement.shot_id,
                    error=str(e),
                )
                self.fallback_count += 1
                # Fall through to placeholder generation

        # Default: PLACEHOLDER
        asset = await self.placeholder_generator.generate(requirement)
        self.placeholder_count += 1
        return asset

    async def generate_all(
        self,
        manifest: AssetManifest,
    ) -> AssetManifest:
        """Generate all pending assets in the manifest.

        Args:
            manifest: Asset manifest with requirements

        Returns:
            Updated manifest with generated assets
        """
        pending = manifest.get_pending_requirements()

        logger.info(
            "generating_assets",
            total=len(pending),
            image_count=sum(1 for r in pending if r.asset_type == AssetType.IMAGE),
        )

        for req in pending:
            if req.asset_type == AssetType.IMAGE:
                try:
                    asset = await self.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)
                except Exception as e:
                    logger.error(
                        "asset_generation_failed",
                        requirement_id=req.id,
                        shot_id=req.shot_id,
                        error=str(e),
                    )
                    manifest = manifest.mark_failed(req.id, str(e))

        return manifest

    def get_generation_report(self) -> dict:
        """Get report on generation statistics."""
        return {
            "placeholder_count": self.placeholder_count,
            "reference_count": self.reference_count,
            "fallback_count": self.fallback_count,
            "total_generated": self.placeholder_count + self.reference_count,
            "reference_cost": self.reference_generator.get_cost_report(),
        }

    def reset_tracking(self) -> None:
        """Reset generation counters and cost tracking."""
        self.placeholder_count = 0
        self.reference_count = 0
        self.fallback_count = 0
        self.reference_generator.reset_cost_tracking()


def count_by_fidelity(manifest: AssetManifest) -> dict:
    """Count requirements by fidelity level.

    Useful for planning and cost estimation.
    """
    counts = {
        "placeholder": 0,
        "reference": 0,
        "total": 0,
    }

    for req in manifest.requirements:
        if req.asset_type == AssetType.IMAGE:
            if req.fidelity_level == VisualFidelityLevel.REFERENCE:
                counts["reference"] += 1
            else:
                counts["placeholder"] += 1
            counts["total"] += 1

    return counts
