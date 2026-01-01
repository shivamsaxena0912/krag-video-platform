"""Data models for the KRAG video platform."""

from src.common.models.base import BaseEntity
from src.common.models.story import (
    Story,
    SourceType,
    SourceMetadata,
    StoryStatus,
)
from src.common.models.scene import (
    Scene,
    SceneSetting,
    TimeOfDay,
    EmotionalBeat,
    EmotionalArc,
)
from src.common.models.entities import (
    Character,
    CharacterRole,
    CharacterImportance,
    VoiceProfile,
    Location,
    LocationType,
    Event,
    EventType,
    EventSignificance,
)
from src.common.models.shot import (
    ShotPlan,
    ShotPlanStatus,
    Shot,
    ShotType,
    Composition,
    Framing,
    CameraAngle,
    DepthOfField,
    MotionSpec,
    CameraMotion,
    MotionSpeed,
    Transition,
    TransitionType,
    DialogueLine,
    AudioCue,
    AudioCueType,
)
from src.common.models.audio import (
    AudioPlan,
    VoiceoverPlan,
    VoiceoverSegment,
    MusicPlan,
    SoundEffect,
    AmbientAudio,
)
from src.common.models.feedback import (
    FeedbackAnnotation,
    FeedbackSource,
    FeedbackTargetType,
    DimensionScores,
    FeedbackIssue,
    IssueSeverity,
    FixCategory,
    TimestampedNote,
    FixRequest,
    FeedbackRecommendation,
)
from src.common.models.asset import (
    Asset,
    AssetType,
)
from src.common.models.pipeline import (
    PipelineRun,
    PipelineStatus,
    PipelineStage,
    CostBreakdown,
    PipelineError,
)

__all__ = [
    # Base
    "BaseEntity",
    # Story
    "Story",
    "SourceType",
    "SourceMetadata",
    "StoryStatus",
    # Scene
    "Scene",
    "SceneSetting",
    "TimeOfDay",
    "EmotionalBeat",
    "EmotionalArc",
    # Entities
    "Character",
    "CharacterRole",
    "CharacterImportance",
    "VoiceProfile",
    "Location",
    "LocationType",
    "Event",
    "EventType",
    "EventSignificance",
    # Shot
    "ShotPlan",
    "ShotPlanStatus",
    "Shot",
    "ShotType",
    "Composition",
    "Framing",
    "CameraAngle",
    "DepthOfField",
    "MotionSpec",
    "CameraMotion",
    "MotionSpeed",
    "Transition",
    "TransitionType",
    "DialogueLine",
    "AudioCue",
    "AudioCueType",
    # Audio
    "AudioPlan",
    "VoiceoverPlan",
    "VoiceoverSegment",
    "MusicPlan",
    "SoundEffect",
    "AmbientAudio",
    # Feedback
    "FeedbackAnnotation",
    "FeedbackSource",
    "FeedbackTargetType",
    "DimensionScores",
    "FeedbackIssue",
    "IssueSeverity",
    "FixCategory",
    "TimestampedNote",
    "FixRequest",
    "FeedbackRecommendation",
    # Asset
    "Asset",
    "AssetType",
    # Pipeline
    "PipelineRun",
    "PipelineStatus",
    "PipelineStage",
    "CostBreakdown",
    "PipelineError",
]
