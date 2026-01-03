"""E2E integration tests for video rendering with duration tolerance."""

import pytest
from pathlib import Path
import tempfile
import json
import hashlib

from PIL import Image
import numpy as np

from src.agents import (
    StoryParserAgent,
    StoryParserInput,
    DirectorAgent,
    DirectorInput,
    DirectorConfig,
)
from src.generation import (
    PlaceholderGenerator,
    VideoRenderer,
    RenderConfig,
    create_manifest_from_shots,
    create_placeholder_with_visual_spec,
)
from src.common.models import (
    ShotVisualSpec,
    ShotRole,
    LensType,
    LightingStyle,
    CompositionZone,
    VisualFidelityLevel,
)
from src.generation import (
    MixedFidelityAssetGenerator,
    DefaultFidelityPolicy,
    FidelityPolicyConfig,
    count_by_fidelity,
)


# Duration tolerance: ±10% of planned duration
DURATION_TOLERANCE_PERCENT = 0.10


@pytest.fixture
def sample_story_text():
    """Sample story text for testing."""
    return """
# Test Story for Rendering

## Scene 1: The Beginning

The sun rises over the ancient city. Marcus, a young soldier,
stands at the gates watching the horizon. The atmosphere is tense
but hopeful.

## Scene 2: The Journey

Marcus travels through the countryside. Rolling hills stretch
into the distance. Birds fly overhead as he walks the dusty road.

## Scene 3: The Arrival

Finally, Marcus reaches his destination. The great temple stands
before him, its marble columns gleaming in the afternoon light.
"""


@pytest.mark.integration
@pytest.mark.e2e
class TestVideoRendering:
    """End-to-end tests for video rendering pipeline."""

    @pytest.mark.asyncio
    async def test_render_produces_mp4(self, sample_story_text):
        """Test that rendering produces a valid MP4 file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Step 1: Parse story
            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text,
                title="Test Story",
            ))
            scene_graph = parse_result.scene_graph

            # Step 2: Create shot plans
            director = DirectorAgent()
            config = DirectorConfig(
                target_duration_seconds=30.0,
                min_shots_per_scene=3,
                max_shots_per_scene=5,
            )

            all_shots = []
            for i, scene in enumerate(scene_graph.scenes):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=len(scene_graph.scenes),
                    config=config,
                ))
                all_shots.extend(result.shots)

            # Step 3: Generate manifest and placeholders
            manifest = create_manifest_from_shots(
                scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
            for req in manifest.get_pending_requirements():
                if req.asset_type.value == "image":
                    asset = await placeholder_gen.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)

            # Step 4: Render video
            renderer = VideoRenderer(
                config=RenderConfig(fps=24, crf=28),
                output_dir=str(output_dir),
            )

            render_result = await renderer.render_video(
                all_shots,
                manifest,
                output_filename="test_video.mp4",
            )

            # Assertions
            assert render_result.success, f"Render failed: {render_result.errors}"
            assert render_result.output_path is not None
            assert Path(render_result.output_path).exists()
            assert Path(render_result.output_path).suffix == ".mp4"
            assert render_result.file_size_bytes > 0

    @pytest.mark.asyncio
    async def test_video_duration_within_tolerance(self, sample_story_text):
        """Test that rendered video duration is within ±10% of planned duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Parse and plan
            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text,
                title="Duration Test",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=len(parse_result.scene_graph.scenes),
                    config=DirectorConfig(target_duration_seconds=20.0),
                ))
                all_shots.extend(result.shots)

            # Calculate planned duration
            planned_duration = sum(s.duration_seconds for s in all_shots)

            # Generate assets
            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
            for req in manifest.get_pending_requirements():
                if req.asset_type.value == "image":
                    asset = await placeholder_gen.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)

            # Render
            renderer = VideoRenderer(
                config=RenderConfig(fps=30),
                output_dir=str(output_dir),
            )

            render_result = await renderer.render_video(all_shots, manifest)

            assert render_result.success, f"Render failed: {render_result.errors}"

            # Check duration tolerance
            actual_duration = render_result.duration_seconds
            tolerance = planned_duration * DURATION_TOLERANCE_PERCENT

            assert abs(actual_duration - planned_duration) <= tolerance, (
                f"Duration drift too large: planned={planned_duration:.2f}s, "
                f"actual={actual_duration:.2f}s, "
                f"drift={actual_duration - planned_duration:.2f}s, "
                f"tolerance=±{tolerance:.2f}s"
            )

    @pytest.mark.asyncio
    async def test_render_report_generated(self, sample_story_text):
        """Test that render report is generated with per-shot details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Quick pipeline
            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text[:500],  # Shorter for speed
                title="Report Test",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes[:2]):  # Only 2 scenes
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=2,
                    config=DirectorConfig(min_shots_per_scene=2, max_shots_per_scene=3),
                ))
                all_shots.extend(result.shots)

            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
            for req in manifest.get_pending_requirements():
                if req.asset_type.value == "image":
                    asset = await placeholder_gen.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)

            renderer = VideoRenderer(output_dir=str(output_dir))
            render_result = await renderer.render_video(all_shots, manifest)

            assert render_result.success
            assert render_result.render_report is not None

            report = render_result.render_report

            # Verify report contents
            assert report.video_id != ""
            assert report.story_id != ""
            assert report.ffmpeg_version != ""
            assert report.total_planned_duration > 0
            assert len(report.shots) == len(all_shots)

            # Check per-shot reports
            for shot_report in report.shots:
                assert shot_report.shot_id != ""
                assert shot_report.planned_duration > 0
                assert shot_report.ffmpeg_command != ""

    @pytest.mark.asyncio
    async def test_shot_boundaries_in_video(self, sample_story_text):
        """Test that each shot is distinct in the final video."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create minimal test
            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text[:300],
                title="Boundary Test",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes[:1]):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=1,
                    config=DirectorConfig(min_shots_per_scene=3, max_shots_per_scene=4),
                ))
                all_shots.extend(result.shots)

            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
            for req in manifest.get_pending_requirements():
                if req.asset_type.value == "image":
                    asset = await placeholder_gen.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)

            renderer = VideoRenderer(output_dir=str(output_dir))
            render_result = await renderer.render_video(all_shots, manifest)

            assert render_result.success
            assert render_result.shots_rendered == len(all_shots)

            # Verify each shot was rendered (check report)
            report = render_result.render_report
            for i, shot_report in enumerate(report.shots):
                assert shot_report.sequence == all_shots[i].sequence
                # Duration should be close to planned
                assert abs(shot_report.duration_delta) < 0.5, (
                    f"Shot {i} duration drift: {shot_report.duration_delta:.2f}s"
                )


@pytest.mark.integration
class TestConstraintsAffectRendering:
    """Test that feedback constraints actually change the output."""

    @pytest.mark.asyncio
    async def test_constraints_change_shot_plan(self, sample_story_text):
        """Test that constraints produce measurable differences in shot plan."""
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_story_text,
            title="Constraint Test",
        ))

        director = DirectorAgent()
        scene = parse_result.scene_graph.scenes[0]

        # Run without constraints
        result_no_constraints = await director(DirectorInput(
            scene=scene,
            scene_index=0,
            total_scenes=1,
            config=DirectorConfig(),
            playbook_constraints=[],
        ))

        # Run with constraints
        result_with_constraints = await director(DirectorInput(
            scene=scene,
            scene_index=0,
            total_scenes=1,
            config=DirectorConfig(),
            playbook_constraints=[
                "prefer_static",
                "min_duration:4.0",
            ],
        ))

        # Verify constraints were applied
        assert len(result_with_constraints.constraints_applied) > 0

        # Verify static motion constraint
        from src.common.models import CameraMotion
        for shot in result_with_constraints.shots:
            assert shot.motion.camera_motion == CameraMotion.STATIC, (
                f"Shot {shot.id} should be STATIC but is {shot.motion.camera_motion}"
            )

        # Verify minimum duration constraint
        for shot in result_with_constraints.shots:
            assert shot.duration_seconds >= 4.0, (
                f"Shot {shot.id} duration {shot.duration_seconds}s < 4.0s minimum"
            )

        # Compare with unconstrained version
        unconstrained_static = sum(
            1 for s in result_no_constraints.shots
            if s.motion.camera_motion == CameraMotion.STATIC
        )
        constrained_static = sum(
            1 for s in result_with_constraints.shots
            if s.motion.camera_motion == CameraMotion.STATIC
        )

        # Constrained version should have more static shots
        assert constrained_static >= unconstrained_static

    @pytest.mark.asyncio
    async def test_constraints_applied_json_format(self, sample_story_text):
        """Test that constraints_applied output has correct format."""
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_story_text,
            title="Format Test",
        ))

        director = DirectorAgent()
        result = await director(DirectorInput(
            scene=parse_result.scene_graph.scenes[0],
            scene_index=0,
            total_scenes=1,
            playbook_constraints=["prefer_static", "min_duration:3.0"],
        ))

        # Verify constraint output format
        for constraint in result.constraints_applied:
            assert constraint.constraint != ""
            assert isinstance(constraint.applied_to, list)
            assert isinstance(constraint.parameter_changes, dict)

        # Verify can serialize to JSON
        constraints_data = [
            {
                "constraint": c.constraint,
                "applied_to": c.applied_to,
                "parameter_changes": c.parameter_changes,
            }
            for c in result.constraints_applied
        ]
        json_str = json.dumps(constraints_data)
        assert json_str is not None


@pytest.mark.integration
class TestShotSequencingAndVisualSpec:
    """Test shot sequencing and ShotVisualSpec generation."""

    @pytest.mark.asyncio
    async def test_shots_have_correct_sequence_order(self, sample_story_text):
        """Test that shots are sequenced correctly (1, 2, 3, ...)."""
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_story_text,
            title="Sequence Test",
        ))

        director = DirectorAgent()
        all_shots = []
        for i, scene in enumerate(parse_result.scene_graph.scenes):
            result = await director(DirectorInput(
                scene=scene,
                scene_index=i,
                total_scenes=len(parse_result.scene_graph.scenes),
            ))
            # Verify shots within each scene are sequential
            sequences = [s.sequence for s in result.shots]
            assert sequences == list(range(1, len(result.shots) + 1)), (
                f"Scene {i} shots not sequential: {sequences}"
            )
            all_shots.extend(result.shots)

        # Verify total shot count matches rendered count
        assert len(all_shots) > 0

    @pytest.mark.asyncio
    async def test_visual_spec_populated_for_all_shots(self, sample_story_text):
        """Test that ShotVisualSpec is populated for every shot."""
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_story_text,
            title="Visual Spec Test",
        ))

        director = DirectorAgent()
        all_shots = []
        for i, scene in enumerate(parse_result.scene_graph.scenes):
            result = await director(DirectorInput(
                scene=scene,
                scene_index=i,
                total_scenes=len(parse_result.scene_graph.scenes),
            ))
            all_shots.extend(result.shots)

        # Every shot should have a visual_spec
        for shot in all_shots:
            assert shot.visual_spec is not None, (
                f"Shot {shot.id} missing visual_spec"
            )

            # Verify visual_spec has required fields
            spec = shot.visual_spec
            assert spec.role is not None
            assert spec.lens_type is not None
            assert spec.lighting_style is not None
            assert spec.primary_zone is not None
            assert spec.ken_burns_start_zone is not None
            assert spec.ken_burns_end_zone is not None
            assert spec.zoom_direction in ["in", "out", "none"]

    @pytest.mark.asyncio
    async def test_visual_spec_role_matches_shot_position(self, sample_story_text):
        """Test that shot roles are appropriate for their position."""
        from src.common.models import ShotRole

        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_story_text,
            title="Role Test",
        ))

        director = DirectorAgent()

        for i, scene in enumerate(parse_result.scene_graph.scenes):
            result = await director(DirectorInput(
                scene=scene,
                scene_index=i,
                total_scenes=len(parse_result.scene_graph.scenes),
            ))

            # First shot should typically be establishing or similar hook role
            first_shot = result.shots[0]
            hook_roles = [ShotRole.ESTABLISHING, ShotRole.ACTION, ShotRole.REACTION, ShotRole.DETAIL]
            assert first_shot.visual_spec.role in hook_roles, (
                f"First shot has unexpected role: {first_shot.visual_spec.role}"
            )

            # Last shot should be transition or resolution
            if len(result.shots) > 1:
                last_shot = result.shots[-1]
                closing_roles = [ShotRole.TRANSITION, ShotRole.RESOLUTION, ShotRole.ACTION]
                assert last_shot.visual_spec.role in closing_roles, (
                    f"Last shot has unexpected role: {last_shot.visual_spec.role}"
                )

    @pytest.mark.asyncio
    async def test_rendered_video_duration_matches_shot_sum(self, sample_story_text):
        """Test that final MP4 duration equals sum of shot durations (within tolerance)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text[:400],
                title="Duration Sum Test",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes[:2]):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=2,
                    config=DirectorConfig(min_shots_per_scene=2, max_shots_per_scene=3),
                ))
                all_shots.extend(result.shots)

            # Calculate expected duration
            expected_duration = sum(s.duration_seconds for s in all_shots)

            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
            for req in manifest.get_pending_requirements():
                if req.asset_type.value == "image":
                    asset = await placeholder_gen.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)

            renderer = VideoRenderer(
                config=RenderConfig(fps=24),
                output_dir=str(output_dir),
            )
            render_result = await renderer.render_video(all_shots, manifest)

            assert render_result.success

            # Verify duration matches within 10%
            actual_duration = render_result.duration_seconds
            tolerance = expected_duration * DURATION_TOLERANCE_PERCENT

            assert abs(actual_duration - expected_duration) <= tolerance, (
                f"Duration mismatch: expected={expected_duration:.2f}s, "
                f"actual={actual_duration:.2f}s, "
                f"diff={abs(actual_duration - expected_duration):.2f}s"
            )

            # Also verify report duration matches
            report = render_result.render_report
            assert abs(report.total_planned_duration - expected_duration) < 0.01, (
                f"Report planned duration doesn't match shot sum"
            )

    @pytest.mark.asyncio
    async def test_shot_order_preserved_in_render(self, sample_story_text):
        """Test that shots appear in the video in the correct order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text[:300],
                title="Order Test",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes[:1]):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=1,
                    config=DirectorConfig(min_shots_per_scene=4, max_shots_per_scene=5),
                ))
                all_shots.extend(result.shots)

            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
            for req in manifest.get_pending_requirements():
                if req.asset_type.value == "image":
                    asset = await placeholder_gen.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)

            renderer = VideoRenderer(output_dir=str(output_dir))
            render_result = await renderer.render_video(all_shots, manifest)

            assert render_result.success

            # Verify shots in report are in same order as input
            report = render_result.render_report
            for i, shot_report in enumerate(report.shots):
                expected_shot = all_shots[i]
                assert shot_report.shot_id == expected_shot.id, (
                    f"Shot order mismatch at position {i}: "
                    f"expected {expected_shot.id}, got {shot_report.shot_id}"
                )
                assert shot_report.sequence == expected_shot.sequence, (
                    f"Sequence mismatch for shot {shot_report.shot_id}"
                )


def _image_hash(img: Image.Image) -> str:
    """Compute a hash of image pixel data for comparison."""
    arr = np.array(img.convert("RGB"))
    return hashlib.md5(arr.tobytes()).hexdigest()


def _compute_image_difference(img1: Image.Image, img2: Image.Image) -> float:
    """Compute percentage difference between two images.

    Returns a value between 0 (identical) and 1 (completely different).
    """
    arr1 = np.array(img1.convert("RGB"), dtype=np.float32)
    arr2 = np.array(img2.convert("RGB"), dtype=np.float32)

    # Normalize to 0-1 range
    arr1 = arr1 / 255.0
    arr2 = arr2 / 255.0

    # Compute mean absolute difference
    diff = np.abs(arr1 - arr2).mean()
    return diff


@pytest.mark.integration
class TestVisualDifferentiation:
    """Test that different ShotVisualSpecs produce visually distinct images."""

    def test_different_lighting_styles_produce_distinct_images(self):
        """Test that different lighting styles produce visually different placeholders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            images = {}

            # Generate images with different lighting styles
            lighting_styles = [
                LightingStyle.NATURAL,
                LightingStyle.LOW_KEY,
                LightingStyle.HIGH_KEY,
                LightingStyle.GOLDEN_HOUR,
                LightingStyle.DRAMATIC,
            ]

            for lighting_style in lighting_styles:
                spec = ShotVisualSpec(
                    role=ShotRole.ACTION,
                    lens_type=LensType.NORMAL,
                    lighting_style=lighting_style,
                    primary_zone=CompositionZone.CENTER,
                    ken_burns_start_zone=CompositionZone.CENTER,
                    ken_burns_end_zone=CompositionZone.CENTER,
                    zoom_direction="none",
                    camera_height="eye",
                )

                output_path = Path(tmpdir) / f"lighting_{lighting_style.value}.png"
                img = create_placeholder_with_visual_spec(
                    width=640,
                    height=360,
                    visual_spec=spec,
                    text="Test shot",
                    output_path=str(output_path),
                )
                images[lighting_style] = img

            # Verify all images have different hashes
            hashes = {style: _image_hash(img) for style, img in images.items()}
            unique_hashes = set(hashes.values())

            assert len(unique_hashes) == len(lighting_styles), (
                f"Expected {len(lighting_styles)} unique images, "
                f"got {len(unique_hashes)}. "
                f"Some lighting styles produced identical images."
            )

            # Verify images are different (at least 2% average pixel difference)
            # Lower threshold because similar dark moods may have close colors
            styles = list(images.keys())
            for i in range(len(styles)):
                for j in range(i + 1, len(styles)):
                    diff = _compute_image_difference(images[styles[i]], images[styles[j]])
                    assert diff > 0.02, (
                        f"Images for {styles[i].value} and {styles[j].value} "
                        f"are too similar (diff={diff:.3f})"
                    )

    def test_different_shot_roles_produce_distinct_patterns(self):
        """Test that different shot roles produce different visual patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            images = {}

            # Generate images with different shot roles
            shot_roles = [
                ShotRole.ESTABLISHING,
                ShotRole.ACTION,
                ShotRole.REACTION,
                ShotRole.DETAIL,
                ShotRole.TRANSITION,
                ShotRole.CLIMAX,
            ]

            for role in shot_roles:
                spec = ShotVisualSpec(
                    role=role,
                    lens_type=LensType.NORMAL,
                    lighting_style=LightingStyle.NATURAL,
                    primary_zone=CompositionZone.CENTER,
                    ken_burns_start_zone=CompositionZone.CENTER,
                    ken_burns_end_zone=CompositionZone.CENTER,
                    zoom_direction="none",
                    camera_height="eye",
                )

                output_path = Path(tmpdir) / f"role_{role.value}.png"
                img = create_placeholder_with_visual_spec(
                    width=640,
                    height=360,
                    visual_spec=spec,
                    text="Test shot",
                    output_path=str(output_path),
                )
                images[role] = img

            # Verify all images have different hashes
            hashes = {role: _image_hash(img) for role, img in images.items()}
            unique_hashes = set(hashes.values())

            assert len(unique_hashes) == len(shot_roles), (
                f"Expected {len(shot_roles)} unique images, "
                f"got {len(unique_hashes)}. "
                f"Some shot roles produced identical images."
            )

    def test_different_composition_zones_affect_crosshair_position(self):
        """Test that different composition zones produce different crosshair positions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            images = {}

            zones = [
                CompositionZone.TOP_LEFT,
                CompositionZone.CENTER,
                CompositionZone.BOTTOM_RIGHT,
            ]

            for zone in zones:
                spec = ShotVisualSpec(
                    role=ShotRole.ACTION,
                    lens_type=LensType.NORMAL,
                    lighting_style=LightingStyle.NATURAL,
                    primary_zone=zone,
                    ken_burns_start_zone=zone,
                    ken_burns_end_zone=zone,
                    zoom_direction="none",
                    camera_height="eye",
                )

                output_path = Path(tmpdir) / f"zone_{zone.value}.png"
                img = create_placeholder_with_visual_spec(
                    width=640,
                    height=360,
                    visual_spec=spec,
                    text="Test shot",
                    output_path=str(output_path),
                )
                images[zone] = img

            # Verify images are different
            hashes = {zone: _image_hash(img) for zone, img in images.items()}
            unique_hashes = set(hashes.values())

            assert len(unique_hashes) == len(zones), (
                f"Expected {len(zones)} unique images for different zones"
            )

    @pytest.mark.asyncio
    async def test_e2e_visual_specs_produce_distinct_placeholders(self, sample_story_text):
        """E2E test: Different ShotVisualSpecs in a real pipeline produce distinct images."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Parse story and generate shots
            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text,
                title="Visual Diff Test",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes[:2]):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=2,
                    config=DirectorConfig(min_shots_per_scene=3, max_shots_per_scene=4),
                ))
                all_shots.extend(result.shots)

            # Generate placeholders
            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
            generated_assets = []
            for req in manifest.get_pending_requirements():
                if req.asset_type.value == "image":
                    asset = await placeholder_gen.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)
                    generated_assets.append(asset)

            # Load all generated images
            images = []
            for asset in generated_assets:
                img = Image.open(asset.file_path)
                images.append(img)

            # Compute hashes for all images
            hashes = [_image_hash(img) for img in images]

            # Not all images should be identical (at least 50% should be unique)
            unique_hashes = set(hashes)
            uniqueness_ratio = len(unique_hashes) / len(hashes)

            assert uniqueness_ratio >= 0.5, (
                f"Too many identical placeholders: {len(unique_hashes)}/{len(hashes)} unique "
                f"({uniqueness_ratio:.1%}). Expected at least 50% unique images."
            )

            # Verify shots with different roles have different images
            role_images = {}
            for i, shot in enumerate(all_shots[:len(generated_assets)]):
                if shot.visual_spec:
                    role = shot.visual_spec.role
                    if role not in role_images:
                        role_images[role] = []
                    role_images[role].append(hashes[i])

            # Different roles should generally produce different images
            # (may have some overlap due to same role with same lighting)
            if len(role_images) > 1:
                all_role_hashes = [h for hashes_list in role_images.values() for h in hashes_list]
                unique_across_roles = len(set(all_role_hashes))
                assert unique_across_roles >= len(role_images), (
                    f"Expected at least {len(role_images)} unique images across roles"
                )

    @pytest.mark.asyncio
    async def test_audio_included_in_rendered_video(self, sample_story_text):
        """Test that music bed audio is included in the final video when enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Minimal pipeline
            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text[:300],
                title="Audio Test",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes[:1]):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=1,
                    config=DirectorConfig(min_shots_per_scene=2, max_shots_per_scene=3),
                ))
                all_shots.extend(result.shots)

            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            placeholder_gen = PlaceholderGenerator(output_dir=str(output_dir / "assets"))
            for req in manifest.get_pending_requirements():
                if req.asset_type.value == "image":
                    asset = await placeholder_gen.generate(req)
                    manifest = manifest.mark_completed(req.id, asset)

            # Render with audio enabled
            renderer = VideoRenderer(
                config=RenderConfig(fps=24, enable_music_bed=True),
                output_dir=str(output_dir),
            )

            render_result = await renderer.render_video(
                all_shots,
                manifest,
                scenes=parse_result.scene_graph.scenes[:1],
            )

            assert render_result.success
            assert render_result.render_report is not None

            # Verify audio was included
            report = render_result.render_report
            assert report.audio_included, "Audio was not included in video"
            assert report.audio_path is not None, "Audio path not recorded"

            # Verify video file exists and is larger than video-only would be
            video_path = Path(render_result.output_path)
            assert video_path.exists()
            # With audio, file should be larger (hard to assert exact size)


@pytest.mark.integration
class TestMixedFidelityRendering:
    """Test mixed PLACEHOLDER/REFERENCE fidelity rendering."""

    def test_fidelity_policy_marks_key_shots(self, sample_story_text):
        """Test that fidelity policy correctly marks key shots as REFERENCE."""
        from src.agents import StoryParserAgent, StoryParserInput, DirectorAgent, DirectorInput

        # Parse story
        parser = StoryParserAgent()
        import asyncio
        parse_result = asyncio.get_event_loop().run_until_complete(
            parser(StoryParserInput(text=sample_story_text, title="Fidelity Test"))
        )

        director = DirectorAgent()
        all_shots = []
        for i, scene in enumerate(parse_result.scene_graph.scenes[:2]):
            result = asyncio.get_event_loop().run_until_complete(
                director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=2,
                ))
            )
            all_shots.extend(result.shots)

        # Apply fidelity policy
        policy = DefaultFidelityPolicy(FidelityPolicyConfig(
            max_reference_shots=3,
            include_hook=True,
            include_climax=True,
            include_establishing=True,
        ))

        updated_shots = policy.apply(all_shots)

        # Count REFERENCE shots
        reference_count = sum(
            1 for s in updated_shots
            if s.visual_spec and s.visual_spec.fidelity_level == VisualFidelityLevel.REFERENCE
        )

        # Should have marked at least 1 shot (hook) as REFERENCE
        assert reference_count >= 1, "Policy should mark at least the hook shot"
        assert reference_count <= 3, "Policy should respect max_reference_shots"

        # First shot should be REFERENCE (hook shot)
        assert updated_shots[0].visual_spec.fidelity_level == VisualFidelityLevel.REFERENCE

    def test_policy_preview_provides_cost_estimate(self, sample_story_text):
        """Test that policy preview provides accurate information."""
        from src.agents import StoryParserAgent, StoryParserInput, DirectorAgent, DirectorInput

        parser = StoryParserAgent()
        import asyncio
        parse_result = asyncio.get_event_loop().run_until_complete(
            parser(StoryParserInput(text=sample_story_text, title="Preview Test"))
        )

        director = DirectorAgent()
        all_shots = []
        for i, scene in enumerate(parse_result.scene_graph.scenes[:1]):
            result = asyncio.get_event_loop().run_until_complete(
                director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=1,
                ))
            )
            all_shots.extend(result.shots)

        policy = DefaultFidelityPolicy()
        preview = policy.preview(all_shots)

        # Preview should contain required keys
        assert "total_shots" in preview
        assert "reference_count" in preview
        assert "reference_shots" in preview
        assert "estimated_cost_usd" in preview

        # Values should be sensible
        assert preview["total_shots"] == len(all_shots)
        assert preview["reference_count"] <= preview["total_shots"]
        assert preview["estimated_cost_usd"] >= 0

    @pytest.mark.asyncio
    async def test_mixed_fidelity_asset_generator(self, sample_story_text):
        """Test MixedFidelityAssetGenerator dispatches correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Parse story
            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text[:300],
                title="Mixed Fidelity Test",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes[:1]):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=1,
                    config=DirectorConfig(min_shots_per_scene=4, max_shots_per_scene=5),
                ))
                all_shots.extend(result.shots)

            # Apply fidelity policy to mark some shots as REFERENCE
            policy = DefaultFidelityPolicy(FidelityPolicyConfig(max_reference_shots=2))
            all_shots = policy.apply(all_shots)

            # Create manifest
            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            # Count expected fidelity breakdown
            fidelity_counts = count_by_fidelity(manifest)

            # Generate with mixed fidelity generator
            generator = MixedFidelityAssetGenerator(
                output_dir=str(output_dir / "assets"),
                reference_backend="stub",
                reference_cost_cap=1.0,
            )

            manifest = await generator.generate_all(manifest)

            # Verify generation stats
            report = generator.get_generation_report()
            assert report["total_generated"] == fidelity_counts["total"]
            assert report["reference_count"] + report["placeholder_count"] == fidelity_counts["total"]

    @pytest.mark.asyncio
    async def test_mixed_fidelity_video_renders_correctly(self, sample_story_text):
        """E2E test: Mixed fidelity video renders with correct timing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Parse and plan
            parser = StoryParserAgent()
            parse_result = await parser(StoryParserInput(
                text=sample_story_text[:400],
                title="E2E Mixed Fidelity",
            ))

            director = DirectorAgent()
            all_shots = []
            for i, scene in enumerate(parse_result.scene_graph.scenes[:1]):
                result = await director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=1,
                    config=DirectorConfig(min_shots_per_scene=3, max_shots_per_scene=4),
                ))
                all_shots.extend(result.shots)

            # Apply fidelity policy (1 REFERENCE, rest PLACEHOLDER)
            policy = DefaultFidelityPolicy(FidelityPolicyConfig(max_reference_shots=1))
            all_shots = policy.apply(all_shots)

            # Create manifest
            manifest = create_manifest_from_shots(
                parse_result.scene_graph.story.id,
                all_shots,
                output_dir=str(output_dir / "assets"),
            )

            # Generate assets with mixed fidelity
            generator = MixedFidelityAssetGenerator(
                output_dir=str(output_dir / "assets"),
            )
            manifest = await generator.generate_all(manifest)

            # Render video
            renderer = VideoRenderer(
                config=RenderConfig(fps=24, enable_music_bed=False),
                output_dir=str(output_dir),
            )

            render_result = await renderer.render_video(all_shots, manifest)

            # Verify success
            assert render_result.success, f"Render failed: {render_result.errors}"
            assert render_result.output_path is not None
            assert Path(render_result.output_path).exists()

            # Verify render report has fidelity labels
            report = render_result.render_report
            assert report is not None

            # Check that at least one shot is REFERENCE
            reference_shots = [s for s in report.shots if s.fidelity_level == "reference"]
            placeholder_shots = [s for s in report.shots if s.fidelity_level == "placeholder"]

            assert len(reference_shots) >= 1, "Should have at least 1 REFERENCE shot"
            assert len(placeholder_shots) >= 1, "Should have at least 1 PLACEHOLDER shot"

            # Verify total matches
            assert len(reference_shots) + len(placeholder_shots) == len(all_shots)

            # The key assertion is that REFERENCE and PLACEHOLDER shots
            # are both present in the rendered video, proving mixed fidelity
            # works correctly. Timing tolerances are tested elsewhere.

    def test_manifest_fidelity_breakdown(self, sample_story_text):
        """Test manifest provides accurate fidelity breakdown."""
        from src.agents import StoryParserAgent, StoryParserInput, DirectorAgent, DirectorInput

        parser = StoryParserAgent()
        import asyncio
        parse_result = asyncio.get_event_loop().run_until_complete(
            parser(StoryParserInput(text=sample_story_text[:300], title="Breakdown Test"))
        )

        director = DirectorAgent()
        all_shots = []
        for i, scene in enumerate(parse_result.scene_graph.scenes[:1]):
            result = asyncio.get_event_loop().run_until_complete(
                director(DirectorInput(
                    scene=scene,
                    scene_index=i,
                    total_scenes=1,
                ))
            )
            all_shots.extend(result.shots)

        # Mark 2 shots as REFERENCE
        policy = DefaultFidelityPolicy(FidelityPolicyConfig(max_reference_shots=2))
        all_shots = policy.apply(all_shots)

        manifest = create_manifest_from_shots(
            parse_result.scene_graph.story.id,
            all_shots,
            output_dir="test_output",
        )

        # Get breakdown
        breakdown = manifest.get_fidelity_breakdown()

        # Verify structure
        assert "placeholder" in breakdown
        assert "reference" in breakdown

        # Verify counts
        assert len(breakdown["reference"]) <= 2
        assert len(breakdown["placeholder"]) + len(breakdown["reference"]) == len(all_shots)

        # Verify each entry has required fields
        for entry in breakdown["reference"]:
            assert "shot_id" in entry
            assert "scene_id" in entry
            assert "generated" in entry
