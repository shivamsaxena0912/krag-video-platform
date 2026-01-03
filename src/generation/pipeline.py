"""Real video generation pipeline with high-fidelity support.

This module provides the complete video generation pipeline that:
1. Generates story structure from scenario
2. Creates shots with fidelity policy
3. Generates assets (DALL-E for REFERENCE, placeholder for others)
4. Renders final video with proper folder structure
5. Validates fidelity proof

This is the REAL pipeline - no simulation, no stubs for REFERENCE shots.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.agents import (
    StoryParserAgent,
    StoryParserInput,
    DirectorAgent,
    DirectorInput,
    DirectorConfig,
)
from src.common.logging import get_logger
from src.common.models import Shot, VisualFidelityLevel, AssetType
from src.generation import (
    MixedFidelityAssetGenerator,
    DefaultFidelityPolicy,
    FidelityPolicyConfig,
    create_manifest_from_shots,
    VideoRenderer,
    RenderConfig,
    RenderQuality,
    get_quality_preset,
    count_by_fidelity,
)
from src.founder import get_scenario

logger = get_logger(__name__)


@dataclass
class FidelityProof:
    """Proof that high-fidelity images were actually generated."""

    reference_shots: list[int]  # Shot indices that are REFERENCE
    reference_images_generated: bool
    reference_image_paths: list[str]
    image_backend: str
    image_cost_usd: float
    placeholder_count: int
    fallback_count: int

    def to_dict(self) -> dict:
        return {
            "reference_shots": self.reference_shots,
            "reference_images_generated": self.reference_images_generated,
            "reference_image_paths": self.reference_image_paths,
            "image_backend": self.image_backend,
            "image_cost_usd": round(self.image_cost_usd, 4),
            "placeholder_count": self.placeholder_count,
            "fallback_count": self.fallback_count,
        }

    def validate(self, render_quality: RenderQuality) -> tuple[bool, list[str]]:
        """Validate fidelity proof against requirements.

        Returns:
            (is_valid, list of error messages)
        """
        errors = []

        if render_quality == RenderQuality.FOUNDER_PREVIEW:
            # Must have at least one reference image if there are reference shots
            if len(self.reference_shots) > 0 and not self.reference_images_generated:
                errors.append(
                    f"FIDELITY_VIOLATION: {len(self.reference_shots)} reference shots "
                    "defined but no reference images generated"
                )

            # Cost must be non-zero if using real backend
            if self.image_backend != "stub" and self.image_cost_usd == 0.0:
                if len(self.reference_shots) > 0:
                    errors.append(
                        f"COST_VIOLATION: Using {self.image_backend} backend but "
                        "image_cost_usd is 0.0 - images may not have been generated"
                    )

            # Reference image files must exist
            for path in self.reference_image_paths:
                if not Path(path).exists():
                    errors.append(f"FILE_MISSING: Reference image not found: {path}")

        return len(errors) == 0, errors


@dataclass
class PipelineResult:
    """Result of running the video generation pipeline."""

    success: bool
    output_dir: Path
    video_path: Path | None
    manifest_path: Path | None
    render_report_path: Path | None
    cost_breakdown_path: Path | None

    # Stats
    total_shots: int = 0
    reference_count: int = 0
    placeholder_count: int = 0
    total_cost_usd: float = 0.0
    generation_time_seconds: float = 0.0

    # Fidelity proof
    fidelity_proof: FidelityProof | None = None

    # Errors
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def generate_story_from_scenario(
    scenario_id: str,
    company_name: str,
    founder_name: str,
) -> str:
    """Generate a story text from a scenario.

    Creates a structured story that the pipeline can parse into scenes and shots.
    """
    scenario = get_scenario(scenario_id)

    if scenario_id == "feature_launch":
        story = f"""# {company_name} Feature Launch Video

## Scene 1: The Problem

Every day, teams struggle with the same frustrating challenge.
Time is wasted. Progress is slow. {founder_name} knows this pain firsthand.
There had to be a better way.

## Scene 2: Introducing the Solution

{company_name} built something different. A new approach that changes everything.
With our latest feature, what used to take hours now takes minutes.
The interface is intuitive. The results are immediate.

## Scene 3: See It In Action

Watch as complex tasks become simple. One click, and it's done.
Real users are already seeing the difference.
Teams are moving faster than ever before.

## Scene 4: The Call to Action

Ready to experience the future? Try {company_name} today.
Join thousands of teams who've already made the switch.
Your productivity transformation starts now.
"""
    elif scenario_id == "funding_announcement":
        story = f"""# {company_name} Funding Announcement

## Scene 1: The Vision

{founder_name} started {company_name} with a bold vision.
A world where technology serves people, not the other way around.
Today, that vision takes a giant leap forward.

## Scene 2: The Announcement

We're thrilled to announce our latest funding round.
This investment validates everything we've been building.
More importantly, it enables what comes next.

## Scene 3: What This Enables

With this funding, we're accelerating our roadmap.
New features. New markets. New possibilities.
Our team is growing, and so is our impact.

## Scene 4: Thank You and Next Steps

Thank you to our investors who believe in our mission.
Thank you to our team who makes it all possible.
The best is yet to come. Join us on this journey.
"""
    else:  # problem_solution
        story = f"""# {company_name} Problem/Solution Video

## Scene 1: The Pain Point

You know the feeling. Another deadline. Another bottleneck.
The tools you have weren't built for how you work.
Something has to change.

## Scene 2: The Cost of Inaction

Every day without a solution costs you time and money.
Your competitors are moving faster. Your team is burning out.
This can't continue.

## Scene 3: A Better Way

{company_name} was built for exactly this moment.
We understand your challenge because we've lived it.
Our solution works the way you think.

## Scene 4: Take Action Now

Stop struggling. Start succeeding.
Try {company_name} free for 14 days.
Your future self will thank you.
"""

    return story


def add_reference_watermark(
    image_path: Path,
    output_path: Path | None = None,
) -> Path:
    """Add a 'REFERENCE SHOT' watermark to an image.

    This is for internal verification only - controlled by debug flag.
    """
    output_path = output_path or image_path

    with Image.open(image_path) as img:
        # Create drawing context
        draw = ImageDraw.Draw(img)

        # Use a simple font (fallback to default if not available)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        except (IOError, OSError):
            font = ImageFont.load_default()

        text = "REFERENCE SHOT"

        # Get text size
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Position in bottom-right corner with padding
        padding = 10
        x = img.width - text_width - padding
        y = img.height - text_height - padding

        # Draw semi-transparent background
        bg_padding = 5
        draw.rectangle(
            [x - bg_padding, y - bg_padding,
             x + text_width + bg_padding, y + text_height + bg_padding],
            fill=(0, 0, 0, 180)
        )

        # Draw text
        draw.text((x, y), text, fill=(255, 255, 0), font=font)

        # Save
        img.save(output_path)

    return output_path


async def run_real_pipeline(
    scenario_id: str,
    company_name: str,
    founder_name: str,
    output_dir: Path,
    render_quality: RenderQuality = RenderQuality.FOUNDER_PREVIEW,
    debug_visual_fidelity: bool = False,
) -> PipelineResult:
    """Run the real video generation pipeline.

    This is NOT a simulation. It will:
    1. Generate story structure from scenario
    2. Create shots with fidelity policy
    3. Call real DALL-E API for REFERENCE shots
    4. Render actual video with FFmpeg
    5. Validate fidelity proof

    Args:
        scenario_id: Which scenario to use (feature_launch, etc.)
        company_name: Company name for story generation
        founder_name: Founder name for story generation
        output_dir: Where to save all outputs
        render_quality: Quality preset (determines backend and cost cap)
        debug_visual_fidelity: If True, add watermark to REFERENCE shots

    Returns:
        PipelineResult with all outputs and validation
    """
    import time
    start_time = time.time()

    result = PipelineResult(
        success=False,
        output_dir=output_dir,
        video_path=None,
        manifest_path=None,
        render_report_path=None,
        cost_breakdown_path=None,
    )

    # Get quality preset
    preset = get_quality_preset(render_quality)
    reference_backend = preset.get("reference_backend", "stub")
    cost_cap = preset.get("reference_cost_cap", 0.5)
    max_reference_shots = preset.get("max_reference_shots", 5)

    logger.info(
        "pipeline_starting",
        scenario=scenario_id,
        quality=render_quality.value,
        backend=reference_backend,
        cost_cap=cost_cap,
    )

    # Create directory structure
    output_dir = Path(output_dir)
    assets_dir = output_dir / "assets"
    placeholder_dir = assets_dir / "placeholder"
    reference_dir = assets_dir / "reference"

    placeholder_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Generate story from scenario
        logger.info("generating_story", scenario=scenario_id)
        story_text = generate_story_from_scenario(
            scenario_id, company_name, founder_name
        )

        # Step 2: Parse story into scenes
        logger.info("parsing_story")
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=story_text,
            title=f"{company_name} - {scenario_id}",
        ))
        scene_graph = parse_result.scene_graph

        # Step 3: Create shot plans for each scene
        logger.info("planning_shots", scenes=len(scene_graph.scenes))
        director = DirectorAgent()
        config = DirectorConfig(
            target_duration_seconds=40.0,  # 30-45s target
            min_shots_per_scene=2,
            max_shots_per_scene=4,
        )

        all_shots: list[Shot] = []
        for i, scene in enumerate(scene_graph.scenes):
            scene_result = await director(DirectorInput(
                scene=scene,
                scene_index=i,
                total_scenes=len(scene_graph.scenes),
                config=config,
            ))
            all_shots.extend(scene_result.shots)

        result.total_shots = len(all_shots)
        logger.info("shots_planned", count=len(all_shots))

        # Step 4: Apply fidelity policy
        logger.info("applying_fidelity_policy", max_reference=max_reference_shots)
        policy_config = FidelityPolicyConfig(
            max_reference_shots=max_reference_shots,
            cost_cap_usd=cost_cap,
            include_hook=True,
            include_climax=True,
            include_resolution=True,
            include_establishing=True,
        )
        policy = DefaultFidelityPolicy(policy_config)
        all_shots = policy.apply(all_shots)

        # Count fidelity breakdown
        reference_indices = [
            i for i, shot in enumerate(all_shots)
            if shot.visual_spec and shot.visual_spec.fidelity_level == VisualFidelityLevel.REFERENCE
        ]

        logger.info(
            "fidelity_applied",
            reference_shots=len(reference_indices),
            reference_indices=reference_indices,
        )

        # Step 5: Create asset manifest
        logger.info("creating_manifest")
        manifest = create_manifest_from_shots(
            scene_graph.story.id,
            all_shots,
            output_dir=str(assets_dir),
        )

        # Count expected fidelity
        fidelity_counts = count_by_fidelity(manifest)

        # Step 6: Generate assets with real backend
        logger.info(
            "generating_assets",
            backend=reference_backend,
            expected_reference=fidelity_counts["reference"],
            expected_placeholder=fidelity_counts["placeholder"],
        )

        generator = MixedFidelityAssetGenerator(
            output_dir=str(assets_dir),
            reference_backend=reference_backend,
            reference_cost_cap=cost_cap,
        )

        manifest = await generator.generate_all(manifest)

        # Get generation report
        gen_report = generator.get_generation_report()
        result.reference_count = gen_report["reference_count"]
        result.placeholder_count = gen_report["placeholder_count"]
        result.total_cost_usd = gen_report["reference_cost"].get("total_cost_usd", 0.0)

        logger.info(
            "assets_generated",
            reference=gen_report["reference_count"],
            placeholder=gen_report["placeholder_count"],
            fallback=gen_report["fallback_count"],
            cost=gen_report["reference_cost"],
        )

        # Step 6.5: Add watermarks if debug mode
        reference_image_paths = []
        for asset in manifest.assets:
            if asset.generation_params.get("fidelity_level") == "reference":
                reference_image_paths.append(asset.file_path)
                if debug_visual_fidelity:
                    add_reference_watermark(Path(asset.file_path))
                    logger.debug("watermark_added", path=asset.file_path)

        # Step 7: Save manifest
        manifest_path = assets_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest.model_dump(), f, indent=2, default=str)
        result.manifest_path = manifest_path

        # Step 8: Render video
        logger.info("rendering_video")
        render_config = RenderConfig(
            fps=preset.get("fps", 30),
            crf=preset.get("crf", 23),
            preset=preset.get("preset", "medium"),
            enable_music_bed=preset.get("enable_music_bed", True),
        )

        renderer = VideoRenderer(
            config=render_config,
            output_dir=str(output_dir),
        )

        render_result = await renderer.render_video(
            all_shots,
            manifest,
            output_filename="final_video.mp4",
        )

        if render_result.success:
            result.video_path = Path(render_result.output_path)
            logger.info("video_rendered", path=render_result.output_path)
        else:
            result.errors.extend(render_result.errors)
            logger.error("video_render_failed", errors=render_result.errors)

        # Step 9: Save render report with fidelity proof
        fidelity_proof = FidelityProof(
            reference_shots=reference_indices,
            reference_images_generated=gen_report["reference_count"] > 0,
            reference_image_paths=reference_image_paths,
            image_backend=reference_backend,
            image_cost_usd=result.total_cost_usd,
            placeholder_count=gen_report["placeholder_count"],
            fallback_count=gen_report["fallback_count"],
        )
        result.fidelity_proof = fidelity_proof

        render_report = {
            "video_id": scene_graph.story.id,
            "scenario": scenario_id,
            "render_quality": render_quality.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_shots": result.total_shots,
            "total_duration": render_result.duration_seconds if render_result.success else 0.0,
            "generation_stats": gen_report,
            "fidelity_proof": fidelity_proof.to_dict(),
            "render_success": render_result.success,
            "errors": result.errors,
        }

        render_report_path = output_dir / "render_report.json"
        with open(render_report_path, "w") as f:
            json.dump(render_report, f, indent=2)
        result.render_report_path = render_report_path

        # Step 10: Save cost breakdown
        cost_breakdown = {
            "image_generation_cost": round(result.total_cost_usd, 4),
            "llm_cost": 0.0,  # Would track LLM calls if needed
            "audio_cost": 0.0,  # Procedural audio is free
            "total_cost": round(result.total_cost_usd, 4),
            "breakdown_by_shot": [
                {
                    "shot_index": i,
                    "shot_id": shot.id,
                    "fidelity": (
                        "reference" if i in reference_indices else "placeholder"
                    ),
                    "cost": (
                        result.total_cost_usd / len(reference_indices)
                        if i in reference_indices and len(reference_indices) > 0
                        else 0.0
                    ),
                }
                for i, shot in enumerate(all_shots)
            ],
        }

        cost_breakdown_path = output_dir / "video_cost_breakdown.json"
        with open(cost_breakdown_path, "w") as f:
            json.dump(cost_breakdown, f, indent=2)
        result.cost_breakdown_path = cost_breakdown_path

        # Step 11: Validate fidelity proof
        is_valid, validation_errors = fidelity_proof.validate(render_quality)
        if not is_valid:
            result.errors.extend(validation_errors)
            logger.error("fidelity_validation_failed", errors=validation_errors)

        # Calculate total time
        result.generation_time_seconds = time.time() - start_time

        # Success if video rendered and validation passed
        result.success = render_result.success and is_valid

        logger.info(
            "pipeline_complete",
            success=result.success,
            duration=result.generation_time_seconds,
            cost=result.total_cost_usd,
            reference_count=result.reference_count,
        )

    except Exception as e:
        result.errors.append(f"PIPELINE_ERROR: {str(e)}")
        logger.exception("pipeline_failed", error=str(e))

    return result


def generate_cost_summary_for_founder(
    reference_count: int,
    total_cost: float,
) -> str:
    """Generate a founder-facing cost summary line.

    Returns a non-technical sentence for marketing_summary.txt
    """
    if reference_count == 0:
        return "This video uses placeholder visuals for rapid iteration."

    return (
        f"This video includes {reference_count} high-fidelity AI-generated "
        f"visuals. Total cost: ${total_cost:.2f}."
    )
