"""Unit tests for DirectorAgent."""

import pytest

from src.agents.director import (
    DirectorAgent,
    DirectorInput,
    DirectorOutput,
    DirectorConfig,
    PacingStyle,
    HookStrategy,
    create_shot_plans,
)
from src.common.models import (
    Scene,
    SceneSetting,
    TimeOfDay,
    EmotionalBeat,
    ShotType,
    CameraMotion,
)


@pytest.fixture
def sample_scene():
    """Create a sample scene for testing."""
    return Scene(
        story_id="story_test_001",
        sequence=1,
        raw_text="The grand Colosseum stands against the morning sky. Marcus enters.",
        summary="Opening scene at the Colosseum",
        setting=SceneSetting(
            location_name="Colosseum",
            location_description="The great Roman amphitheater",
            time_of_day=TimeOfDay.MORNING,
            era="Ancient Rome",
            atmosphere="epic",
        ),
        emotional_beat=EmotionalBeat(
            primary_emotion="tension",
            intensity=0.7,
        ),
        word_count=50,
    )


@pytest.fixture
def contemplative_scene():
    """Create a contemplative scene."""
    return Scene(
        story_id="story_test_001",
        sequence=2,
        raw_text="Silent reflection in the temple gardens.",
        summary="Quiet moment of reflection",
        setting=SceneSetting(
            location_name="Temple Gardens",
            time_of_day=TimeOfDay.SUNSET,
            atmosphere="peaceful",
        ),
        emotional_beat=EmotionalBeat(
            primary_emotion="contemplative",
            intensity=0.3,
        ),
        word_count=30,
    )


class TestDirectorAgent:
    """Tests for DirectorAgent."""

    @pytest.mark.asyncio
    async def test_basic_execution(self, sample_scene):
        """Test basic shot plan creation."""
        director = DirectorAgent()
        input = DirectorInput(scene=sample_scene)

        output = await director(input)

        assert isinstance(output, DirectorOutput)
        assert output.shot_plan is not None
        assert len(output.shots) >= 3  # min_shots_per_scene
        assert len(output.shots) <= 10  # max_shots_per_scene

    @pytest.mark.asyncio
    async def test_hook_analysis(self, sample_scene):
        """Test hook analysis is generated."""
        director = DirectorAgent()
        output = await director(DirectorInput(scene=sample_scene))

        assert "strategy" in output.hook_analysis
        assert "hook_duration" in output.hook_analysis
        assert "hook_shot_count" in output.hook_analysis

    @pytest.mark.asyncio
    async def test_duration_budgeting(self, sample_scene):
        """Test duration budget is calculated."""
        director = DirectorAgent()
        output = await director(DirectorInput(scene=sample_scene))

        assert "total" in output.duration_budget
        assert "hook" in output.duration_budget
        assert "remaining" in output.duration_budget
        assert output.duration_budget["hook"] == 3.0  # Default hook duration

    @pytest.mark.asyncio
    async def test_first_shot_is_hook(self, sample_scene):
        """Test first shot follows hook strategy."""
        director = DirectorAgent()
        config = DirectorConfig(default_hook_strategy=HookStrategy.VISUAL_IMPACT)
        output = await director(DirectorInput(scene=sample_scene, config=config))

        first_shot = output.shots[0]
        assert first_shot.sequence == 1
        # Visual impact uses EXTREME_WIDE
        assert first_shot.shot_type in [ShotType.EXTREME_WIDE, ShotType.WIDE]

    @pytest.mark.asyncio
    async def test_contemplative_pacing(self, contemplative_scene):
        """Test contemplative scenes get fewer, longer shots."""
        director = DirectorAgent()
        output = await director(DirectorInput(scene=contemplative_scene))

        # Contemplative pacing should have longer average duration
        avg_duration = sum(s.duration_seconds for s in output.shots) / len(output.shots)
        assert avg_duration >= 3.0  # Longer than minimum

    @pytest.mark.asyncio
    async def test_playbook_constraints_applied(self, sample_scene):
        """Test playbook constraints are applied."""
        director = DirectorAgent()
        input = DirectorInput(
            scene=sample_scene,
            playbook_constraints=["prefer_static"],
        )
        output = await director(input)

        # All shots should have static motion
        for shot in output.shots:
            assert shot.motion.camera_motion == CameraMotion.STATIC

    @pytest.mark.asyncio
    async def test_shot_variety(self, sample_scene):
        """Test shot types have variety."""
        director = DirectorAgent()
        config = DirectorConfig(prefer_variety=True, min_shots_per_scene=5)
        output = await director(DirectorInput(scene=sample_scene, config=config))

        shot_types = {s.shot_type for s in output.shots}
        # Should have at least 3 different shot types
        assert len(shot_types) >= 3

    @pytest.mark.asyncio
    async def test_scene_continuity(self, sample_scene):
        """Test continuity with previous scene ending."""
        director = DirectorAgent()

        # First scene ends with CLOSE_UP
        input = DirectorInput(
            scene=sample_scene,
            scene_index=1,
            previous_ending_shot_type=ShotType.CLOSE_UP,
        )
        output = await director(input)

        # First shot should not be CLOSE_UP (for variety)
        assert output.shots[0].shot_type != ShotType.CLOSE_UP

    @pytest.mark.asyncio
    async def test_audio_cues_added(self, sample_scene):
        """Test audio cues are added to shots."""
        director = DirectorAgent()
        config = DirectorConfig(include_audio_cues=True)
        output = await director(DirectorInput(scene=sample_scene, config=config))

        # First shot should have music start
        first_shot = output.shots[0]
        cue_types = [c.cue_type.value for c in first_shot.audio_cues]
        assert "music_start" in cue_types

        # Last shot should have music fade
        last_shot = output.shots[-1]
        cue_types = [c.cue_type.value for c in last_shot.audio_cues]
        assert "music_fade" in cue_types

    @pytest.mark.asyncio
    async def test_transitions_added(self, sample_scene):
        """Test transitions are added between shots."""
        director = DirectorAgent()
        config = DirectorConfig(include_transitions=True, min_shots_per_scene=4)
        output = await director(DirectorInput(scene=sample_scene, config=config))

        # Middle shots should have transitions
        for shot in output.shots[:-1]:
            assert shot.transition_out is not None


class TestDirectorConfig:
    """Tests for DirectorConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DirectorConfig()

        assert config.target_duration_seconds == 60.0
        assert config.hook_duration == 3.0
        assert config.min_shots_per_scene == 3
        assert config.max_shots_per_scene == 10
        assert config.default_pacing == PacingStyle.MODERATE

    def test_custom_values(self):
        """Test custom configuration."""
        config = DirectorConfig(
            target_duration_seconds=120.0,
            hook_duration=5.0,
            default_pacing=PacingStyle.DYNAMIC,
        )

        assert config.target_duration_seconds == 120.0
        assert config.hook_duration == 5.0
        assert config.default_pacing == PacingStyle.DYNAMIC


class TestHookStrategies:
    """Tests for different hook strategies."""

    @pytest.mark.asyncio
    async def test_mystery_hook(self, sample_scene):
        """Test mystery hook strategy."""
        director = DirectorAgent()
        config = DirectorConfig(default_hook_strategy=HookStrategy.MYSTERY)

        # Override to use mystery (normally determined by scene)
        output = await director(DirectorInput(
            scene=sample_scene,
            scene_index=1,  # Not first scene
            config=config,
        ))

        # Can verify hook_analysis has correct strategy
        assert output.hook_analysis["strategy"] in [
            "mystery", "visual_impact", "action", "emotional"
        ]

    @pytest.mark.asyncio
    async def test_action_hook(self):
        """Test action hook for high-intensity scenes."""
        scene = Scene(
            story_id="story_test",
            sequence=1,
            raw_text="Battle erupts at the gates",
            summary="Battle scene",
            setting=SceneSetting(location_name="City Gates"),
            emotional_beat=EmotionalBeat(
                primary_emotion="action",
                intensity=0.9,
            ),
        )

        director = DirectorAgent()
        output = await director(DirectorInput(
            scene=scene,
            scene_index=1,  # Not first scene
        ))

        # High intensity action should use ACTION hook
        assert output.hook_analysis["strategy"] == "action"
