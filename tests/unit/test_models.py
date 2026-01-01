"""Unit tests for data models and schema validation."""

import pytest
from datetime import datetime

from src.common.models import (
    Story,
    SourceType,
    SourceMetadata,
    StoryStatus,
    Scene,
    SceneSetting,
    TimeOfDay,
    EmotionalBeat,
    EmotionalArc,
    Character,
    CharacterRole,
    CharacterImportance,
    Location,
    LocationType,
    Shot,
    ShotType,
    ShotPlan,
    ShotPlanStatus,
    Composition,
    MotionSpec,
    FeedbackAnnotation,
    FeedbackSource,
    FeedbackTargetType,
    FeedbackRecommendation,
    DimensionScores,
    FeedbackIssue,
    IssueSeverity,
    FixCategory,
    TimeRange,
    TimestampedNote,
    FixRequest,
)


class TestStoryModel:
    """Tests for Story model."""

    def test_story_creation(self):
        """Test creating a valid Story."""
        story = Story(
            title="Test Story",
            source_type=SourceType.NARRATIVE,
            source_metadata=SourceMetadata(title="Test Story"),
        )

        assert story.title == "Test Story"
        assert story.source_type == SourceType.NARRATIVE
        assert story.status == StoryStatus.DRAFT
        assert story.id.startswith("story_")
        assert story.version == 1

    def test_story_with_all_fields(self):
        """Test Story with all optional fields."""
        story = Story(
            title="Complete Story",
            source_type=SourceType.BOOK,
            source_metadata=SourceMetadata(
                title="Complete Story",
                author="Test Author",
                publication_year=2024,
                genre="historical",
                era="Ancient Rome",
            ),
            status=StoryStatus.PARSED,
            total_scenes=5,
            total_characters=3,
            raw_text="Sample text content",
        )

        assert story.total_scenes == 5
        assert story.source_metadata.author == "Test Author"

    def test_story_summary(self):
        """Test Story summary method."""
        story = Story(
            title="Summary Test",
            source_type=SourceType.NARRATIVE,
            source_metadata=SourceMetadata(title="Summary Test"),
            total_scenes=3,
        )

        summary = story.summary()
        assert summary["title"] == "Summary Test"
        assert summary["scenes"] == 3


class TestSceneModel:
    """Tests for Scene model."""

    def test_scene_creation(self):
        """Test creating a valid Scene."""
        scene = Scene(
            story_id="story_123",
            sequence=1,
            raw_text="Test scene content",
            setting=SceneSetting(
                location_name="Rome",
                location_description="The eternal city",
            ),
            emotional_beat=EmotionalBeat(
                primary_emotion="tension",
            ),
        )

        assert scene.story_id == "story_123"
        assert scene.sequence == 1
        assert scene.id.startswith("scene_")
        assert scene.setting.location_name == "Rome"

    def test_scene_with_characters(self):
        """Test Scene with character references."""
        scene = Scene(
            story_id="story_123",
            sequence=2,
            raw_text="Marcus speaks",
            setting=SceneSetting(
                location_name="Forum",
                location_description="Roman Forum",
            ),
            emotional_beat=EmotionalBeat(primary_emotion="dialogue"),
            characters=["char_1", "char_2"],
            locations=["loc_1"],
        )

        assert len(scene.characters) == 2
        assert len(scene.locations) == 1


class TestShotModel:
    """Tests for Shot and ShotPlan models."""

    def test_shot_creation(self):
        """Test creating a valid Shot."""
        shot = Shot(
            shot_plan_id="plan_123",
            sequence=1,
            shot_type=ShotType.WIDE,
            duration_seconds=4.0,
            subject="Colosseum exterior",
            mood="epic",
            visual_description="Establishing shot of the Colosseum",
        )

        assert shot.shot_type == ShotType.WIDE
        assert shot.duration_seconds == 4.0
        assert shot.id.startswith("shot_")

    def test_shot_plan_creation(self):
        """Test creating a valid ShotPlan."""
        plan = ShotPlan(
            scene_id="scene_123",
            status=ShotPlanStatus.DRAFT,
            creative_direction="Documentary style",
        )

        assert plan.scene_id == "scene_123"
        assert plan.status == ShotPlanStatus.DRAFT
        assert plan.total_shots == 0


class TestFeedbackModel:
    """Tests for FeedbackAnnotation model."""

    def test_feedback_creation(self):
        """Test creating a valid FeedbackAnnotation."""
        feedback = FeedbackAnnotation(
            source=FeedbackSource.AI_CRITIC,
            target_type=FeedbackTargetType.STORY,
            target_id="story_123",
            overall_score=7.5,
        )

        assert feedback.source == FeedbackSource.AI_CRITIC
        assert feedback.target_type == FeedbackTargetType.STORY
        assert feedback.overall_score == 7.5
        assert feedback.id.startswith("fb_")

    def test_feedback_with_time_range(self):
        """Test FeedbackAnnotation with time range."""
        feedback = FeedbackAnnotation(
            source=FeedbackSource.HUMAN_EXPERT,
            target_type=FeedbackTargetType.VIDEO_DRAFT,
            target_id="video_123",
            target_time_range=TimeRange(
                start_seconds=10.0,
                end_seconds=25.0,
            ),
            overall_score=6.0,
        )

        assert feedback.target_time_range.start_seconds == 10.0
        assert feedback.target_time_range.duration == 15.0

    def test_dimension_scores(self):
        """Test DimensionScores calculations."""
        scores = DimensionScores(
            narrative_clarity=4,
            hook_strength=3,
            pacing=4,
            shot_composition=5,
            continuity=4,
            audio_mix=4,
        )

        assert scores.average() == 4.0
        assert scores.to_overall_score() == 8.0

    def test_feedback_issue_with_taxonomy(self):
        """Test FeedbackIssue with taxonomy labels."""
        issue = FeedbackIssue(
            dimension="pacing",
            severity=IssueSeverity.MINOR,
            description="Shot is too long",
            fix_category=FixCategory.ADJUST_DURATION,
            taxonomy_labels=["pacing", "shot_duration", "viewer_engagement"],
            suggested_fix="Reduce shot duration to 3 seconds",
            time_range=TimeRange(start_seconds=15.0, end_seconds=20.0),
        )

        assert len(issue.taxonomy_labels) == 3
        assert issue.time_range.duration == 5.0

    def test_complete_feedback(self):
        """Test complete FeedbackAnnotation with all fields."""
        feedback = FeedbackAnnotation(
            source=FeedbackSource.AI_CRITIC,
            target_type=FeedbackTargetType.SCENE,
            target_id="scene_123",
            dimension_scores=DimensionScores(
                narrative_clarity=4,
                hook_strength=4,
                pacing=3,
                shot_composition=4,
                continuity=5,
                audio_mix=3,
            ),
            overall_score=7.6,
            taxonomy_labels=["scene_level", "automated"],
            issues=[
                FeedbackIssue(
                    dimension="pacing",
                    description="Slow start",
                    fix_category=FixCategory.ADJUST_DURATION,
                ),
            ],
            strengths=["Good visual clarity", "Strong emotional beat"],
            timestamped_notes=[
                TimestampedNote(
                    timestamp_seconds=5.0,
                    note="Consider cutting here",
                ),
            ],
            recommendation=FeedbackRecommendation.MINOR_FIXES,
            fix_requests=[
                FixRequest(
                    issue_id="issue_123",
                    fix_category=FixCategory.ADJUST_DURATION,
                    instructions="Reduce opening shot",
                ),
            ],
        )

        assert len(feedback.issues) == 1
        assert len(feedback.strengths) == 2
        assert len(feedback.timestamped_notes) == 1
        assert feedback.recommendation == FeedbackRecommendation.MINOR_FIXES


class TestCharacterModel:
    """Tests for Character model."""

    def test_character_creation(self):
        """Test creating a valid Character."""
        character = Character(
            story_id="story_123",
            name="Marcus Aurelius",
            physical_description="Elderly Roman emperor",
            role=CharacterRole.PROTAGONIST,
            importance=CharacterImportance.PRIMARY,
        )

        assert character.name == "Marcus Aurelius"
        assert character.role == CharacterRole.PROTAGONIST


class TestLocationModel:
    """Tests for Location model."""

    def test_location_creation(self):
        """Test creating a valid Location."""
        location = Location(
            story_id="story_123",
            name="Rome",
            description="The eternal city",
            location_type=LocationType.URBAN,
            era="Ancient Rome",
        )

        assert location.name == "Rome"
        assert location.location_type == LocationType.URBAN
