"""Feedback and quality evaluation models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id


class FeedbackSource(str, Enum):
    """Source of feedback."""

    AI_CRITIC = "ai_critic"
    HUMAN_EXPERT = "human_expert"
    HUMAN_DIRECTOR = "human_director"
    HUMAN_EDITOR = "human_editor"
    AUTOMATED_QA = "automated_qa"


class FeedbackTargetType(str, Enum):
    """Type of entity being evaluated."""

    STORY = "story"
    SCENE = "scene"
    SHOT = "shot"
    ASSET = "asset"
    VIDEO_DRAFT = "video_draft"
    FINAL_VIDEO = "final_video"


class IssueSeverity(str, Enum):
    """Severity of an identified issue."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"


class FixCategory(str, Enum):
    """Category of fix required."""

    # Image/Visual
    REGENERATE_IMAGE = "regenerate_image"
    ADJUST_COMPOSITION = "adjust_composition"
    FIX_CONSISTENCY = "fix_consistency"
    CHANGE_SHOT_TYPE = "change_shot_type"

    # Timing/Pacing
    ADJUST_DURATION = "adjust_duration"
    CHANGE_TRANSITION = "change_transition"
    REORDER_SHOTS = "reorder_shots"

    # Audio
    REGENERATE_VOICEOVER = "regenerate_voiceover"
    ADJUST_AUDIO_MIX = "adjust_audio_mix"
    CHANGE_MUSIC = "change_music"
    ADD_SFX = "add_sfx"

    # Content
    REWRITE_NARRATION = "rewrite_narration"
    ADD_SHOT = "add_shot"
    REMOVE_SHOT = "remove_shot"

    # Other
    OTHER = "other"


class FeedbackRecommendation(str, Enum):
    """Overall recommendation from feedback."""

    APPROVE = "approve"
    APPROVE_WITH_NOTES = "approve_with_notes"
    MINOR_FIXES = "minor_fixes"
    MAJOR_REVISION = "major_revision"
    REJECT = "reject"


class DimensionScores(BaseModel):
    """Scores across quality dimensions."""

    model_config = ConfigDict(frozen=True)

    narrative_clarity: int = Field(ge=1, le=5, default=3)
    hook_strength: int = Field(ge=1, le=5, default=3)
    pacing: int = Field(ge=1, le=5, default=3)
    shot_composition: int = Field(ge=1, le=5, default=3)
    continuity: int = Field(ge=1, le=5, default=3)
    audio_mix: int = Field(ge=1, le=5, default=3)

    def average(self) -> float:
        """Calculate average score across dimensions."""
        return (
            self.narrative_clarity
            + self.hook_strength
            + self.pacing
            + self.shot_composition
            + self.continuity
            + self.audio_mix
        ) / 6

    def to_overall_score(self) -> float:
        """Convert to 1-10 scale."""
        return self.average() * 2


class FeedbackIssue(BaseModel):
    """A specific issue identified during evaluation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("issue"))
    dimension: str
    severity: IssueSeverity = IssueSeverity.MINOR
    description: str
    fix_category: FixCategory = FixCategory.OTHER
    suggested_fix: str | None = None


class TimestampedNote(BaseModel):
    """A note tied to a specific timestamp."""

    model_config = ConfigDict(frozen=True)

    timestamp_seconds: float = Field(ge=0)
    end_timestamp_seconds: float | None = None
    note: str
    severity: IssueSeverity = IssueSeverity.SUGGESTION


class FixRequest(BaseModel):
    """A specific fix request from feedback."""

    model_config = ConfigDict(frozen=True)

    issue_id: str
    fix_category: FixCategory
    target_shot_id: str | None = None
    instructions: str
    priority: int = Field(default=1, ge=1, le=5)


class FeedbackAnnotation(BaseModel):
    """Complete structured feedback on a video/scene/shot."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("fb"))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Source
    source: FeedbackSource
    reviewer_id: str | None = None

    # Target
    target_type: FeedbackTargetType
    target_id: str

    # Scores
    dimension_scores: DimensionScores = Field(default_factory=DimensionScores)
    overall_score: float = Field(ge=1, le=10, default=5.0)

    # Details
    issues: list[FeedbackIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    timestamped_notes: list[TimestampedNote] = Field(default_factory=list)

    # Action
    recommendation: FeedbackRecommendation = FeedbackRecommendation.MINOR_FIXES
    fix_requests: list[FixRequest] = Field(default_factory=list)

    def summary(self) -> dict:
        """Return summary for logging."""
        return {
            "id": self.id,
            "source": self.source.value,
            "target": f"{self.target_type.value}:{self.target_id}",
            "score": self.overall_score,
            "recommendation": self.recommendation.value,
            "issues": len(self.issues),
        }
