"""Unit tests for generation module (manifest, placeholder, renderer)."""

import pytest
from pathlib import Path
import tempfile

from src.generation.manifest import (
    AssetManifest,
    AssetRequirement,
    ManifestStatus,
    create_manifest_from_shots,
)
from src.generation.placeholder import (
    PlaceholderGenerator,
    create_placeholder_image,
    get_mood_colors,
)
from src.generation.renderer import (
    VideoRenderer,
    RenderConfig,
    RenderResult,
    KenBurnsParams,
    KenBurnsDirection,
    motion_to_ken_burns,
)
from src.common.models import (
    Asset,
    AssetType,
    Shot,
    ShotType,
    Composition,
    MotionSpec,
    CameraMotion,
)


class TestAssetManifest:
    """Tests for AssetManifest."""

    def test_create_empty_manifest(self):
        """Test creating an empty manifest."""
        manifest = AssetManifest(story_id="story_001")

        assert manifest.story_id == "story_001"
        assert manifest.status == ManifestStatus.PENDING
        assert len(manifest.requirements) == 0
        assert len(manifest.assets) == 0

    def test_add_requirement(self):
        """Test adding requirements."""
        manifest = AssetManifest(story_id="story_001")

        manifest = manifest.add_requirement(
            shot_id="shot_001",
            scene_id="scene_001",
            asset_type=AssetType.IMAGE,
            prompt="Test prompt",
        )

        assert len(manifest.requirements) == 1
        assert manifest.total_requirements == 1
        assert manifest.requirements[0].shot_id == "shot_001"
        assert manifest.requirements[0].prompt == "Test prompt"

    def test_mark_completed(self):
        """Test marking requirements as completed."""
        manifest = AssetManifest(story_id="story_001")
        manifest = manifest.add_requirement(
            shot_id="shot_001",
            scene_id="scene_001",
            asset_type=AssetType.IMAGE,
        )

        req_id = manifest.requirements[0].id
        asset = Asset(
            asset_type=AssetType.IMAGE,
            shot_id="shot_001",
            scene_id="scene_001",
            file_path="/path/to/image.png",
            generation_cost=0.05,
        )

        manifest = manifest.mark_completed(req_id, asset)

        assert manifest.completed_count == 1
        assert manifest.requirements[0].generated is True
        assert manifest.requirements[0].asset_id == asset.id
        assert len(manifest.assets) == 1
        assert manifest.total_generation_cost == 0.05

    def test_mark_failed(self):
        """Test marking requirements as failed."""
        manifest = AssetManifest(story_id="story_001")
        manifest = manifest.add_requirement(
            shot_id="shot_001",
            scene_id="scene_001",
            asset_type=AssetType.IMAGE,
        )

        req_id = manifest.requirements[0].id
        manifest = manifest.mark_failed(req_id, "Generation failed")

        assert manifest.failed_count == 1
        assert manifest.requirements[0].error == "Generation failed"
        assert manifest.status == ManifestStatus.PARTIAL

    def test_progress_percent(self):
        """Test progress calculation."""
        manifest = AssetManifest(story_id="story_001")

        # Add 4 requirements
        for i in range(4):
            manifest = manifest.add_requirement(
                shot_id=f"shot_{i}",
                scene_id="scene_001",
                asset_type=AssetType.IMAGE,
            )

        assert manifest.progress_percent() == 0.0

        # Complete 2
        for i in range(2):
            req_id = manifest.requirements[i].id
            asset = Asset(
                asset_type=AssetType.IMAGE,
                shot_id=f"shot_{i}",
                scene_id="scene_001",
                file_path=f"/path/{i}.png",
            )
            manifest = manifest.mark_completed(req_id, asset)

        assert manifest.progress_percent() == 50.0

    def test_get_pending_requirements(self):
        """Test getting pending requirements."""
        manifest = AssetManifest(story_id="story_001")

        for i in range(3):
            manifest = manifest.add_requirement(
                shot_id=f"shot_{i}",
                scene_id="scene_001",
                asset_type=AssetType.IMAGE,
            )

        # Complete first one
        asset = Asset(
            asset_type=AssetType.IMAGE,
            shot_id="shot_0",
            scene_id="scene_001",
            file_path="/path/0.png",
        )
        manifest = manifest.mark_completed(manifest.requirements[0].id, asset)

        pending = manifest.get_pending_requirements()
        assert len(pending) == 2


class TestCreateManifestFromShots:
    """Tests for create_manifest_from_shots."""

    def test_creates_image_requirements(self):
        """Test manifest creation from shots."""
        shots = [
            Shot(
                shot_plan_id="plan_001",
                sequence=1,
                shot_type=ShotType.WIDE,
                duration_seconds=4.0,
                subject="Test",
                mood="epic",
                visual_description="Wide shot of scene",
                composition=Composition(),
                motion=MotionSpec(),
            ),
            Shot(
                shot_plan_id="plan_001",
                sequence=2,
                shot_type=ShotType.CLOSE_UP,
                duration_seconds=3.0,
                subject="Character",
                mood="tension",
                visual_description="Close up",
                narration_text="Narration here",
                composition=Composition(),
                motion=MotionSpec(),
            ),
        ]

        manifest = create_manifest_from_shots("story_001", shots)

        # Should have 2 images + 1 voiceover (for shot with narration)
        assert manifest.total_requirements == 3

        image_reqs = [r for r in manifest.requirements if r.asset_type == AssetType.IMAGE]
        voice_reqs = [r for r in manifest.requirements if r.asset_type == AssetType.VOICEOVER]

        assert len(image_reqs) == 2
        assert len(voice_reqs) == 1


class TestPlaceholderGenerator:
    """Tests for PlaceholderGenerator."""

    def test_get_mood_colors(self):
        """Test mood color mapping."""
        tension_colors = get_mood_colors("tension")
        assert "bg" in tension_colors
        assert "fg" in tension_colors
        assert "accent" in tension_colors

        # Unknown mood should return neutral
        unknown_colors = get_mood_colors("unknown_mood")
        neutral_colors = get_mood_colors("neutral")
        assert unknown_colors == neutral_colors

    def test_create_placeholder_image(self):
        """Test placeholder image creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"

            img = create_placeholder_image(
                width=1920,
                height=1080,
                text="Test placeholder",
                mood="tension",
                shot_type="wide",
                output_path=str(output_path),
            )

            assert img.size == (1920, 1080)
            assert output_path.exists()

    @pytest.mark.asyncio
    async def test_placeholder_generator(self):
        """Test PlaceholderGenerator.generate()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = PlaceholderGenerator(output_dir=tmpdir)

            req = AssetRequirement(
                shot_id="shot_001",
                scene_id="scene_001",
                asset_type=AssetType.IMAGE,
                prompt="Wide shot of the Colosseum",
                style_hints=["epic", "dramatic"],
            )

            asset = await generator.generate(req)

            assert asset.asset_type == AssetType.IMAGE
            assert asset.shot_id == "shot_001"
            assert Path(asset.file_path).exists()
            assert asset.generation_model == "placeholder_generator"
            assert asset.generation_cost == 0.0


class TestKenBurnsMotionMapping:
    """Tests for Ken Burns motion mapping."""

    def test_zoom_in_mapping(self):
        """Test ZOOM_IN motion mapping."""
        params = motion_to_ken_burns(CameraMotion.ZOOM_IN)

        assert params.direction == KenBurnsDirection.ZOOM_IN
        assert params.start_scale == 1.0
        assert params.end_scale > params.start_scale

    def test_zoom_out_mapping(self):
        """Test ZOOM_OUT motion mapping."""
        params = motion_to_ken_burns(CameraMotion.ZOOM_OUT)

        assert params.direction == KenBurnsDirection.ZOOM_OUT
        assert params.start_scale > params.end_scale

    def test_pan_left_mapping(self):
        """Test PAN_LEFT motion mapping."""
        params = motion_to_ken_burns(CameraMotion.PAN_LEFT)

        assert params.direction == KenBurnsDirection.PAN_LEFT
        assert params.start_x_offset > params.end_x_offset

    def test_pan_right_mapping(self):
        """Test PAN_RIGHT motion mapping."""
        params = motion_to_ken_burns(CameraMotion.PAN_RIGHT)

        assert params.direction == KenBurnsDirection.PAN_RIGHT
        assert params.end_x_offset > params.start_x_offset

    def test_static_mapping(self):
        """Test STATIC motion mapping."""
        params = motion_to_ken_burns(CameraMotion.STATIC)

        assert params.direction == KenBurnsDirection.STATIC
        assert params.start_scale == params.end_scale

    def test_none_defaults_to_zoom_in(self):
        """Test None motion defaults to zoom in."""
        params = motion_to_ken_burns(None)

        assert params.direction == KenBurnsDirection.ZOOM_IN


class TestRenderConfig:
    """Tests for RenderConfig."""

    def test_default_values(self):
        """Test default render configuration."""
        config = RenderConfig()

        assert config.output_width == 1920
        assert config.output_height == 1080
        assert config.fps == 30
        assert config.video_codec == "libx264"

    def test_custom_values(self):
        """Test custom render configuration."""
        config = RenderConfig(
            output_width=1280,
            output_height=720,
            fps=24,
            crf=18,
        )

        assert config.output_width == 1280
        assert config.output_height == 720
        assert config.fps == 24
        assert config.crf == 18


class TestVideoRenderer:
    """Tests for VideoRenderer."""

    def test_renderer_initialization(self):
        """Test renderer initializes correctly."""
        renderer = VideoRenderer()

        assert renderer.config.output_width == 1920
        assert renderer.output_dir.exists()

    def test_ken_burns_filter_generation(self):
        """Test Ken Burns filter string generation."""
        renderer = VideoRenderer()

        params = KenBurnsParams(
            direction=KenBurnsDirection.ZOOM_IN,
            start_scale=1.0,
            end_scale=1.3,
        )

        filter_str = renderer._generate_ken_burns_filter(
            params,
            duration=4.0,
            input_w=1920,
            input_h=1080,
        )

        assert "zoompan" in filter_str
        assert "1920x1080" in filter_str
        assert "120" in filter_str  # 4s * 30fps
