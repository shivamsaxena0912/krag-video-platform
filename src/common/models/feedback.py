"""Feedback and quality evaluation models."""

from __future__ import annotations

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


class TimeRange(BaseModel):
    """A time range within a video."""

    model_config = ConfigDict(frozen=True)

    start_seconds: float = Field(ge=0)
    end_seconds: float | None = None

    @property
    def duration(self) -> float | None:
        """Calculate duration if end is specified."""
        if self.end_seconds is not None:
            return self.end_seconds - self.start_seconds
        return None


class FeedbackIssue(BaseModel):
    """A specific issue identified during evaluation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("issue"))
    dimension: str
    severity: IssueSeverity = IssueSeverity.MINOR
    description: str
    fix_category: FixCategory = FixCategory.OTHER
    taxonomy_labels: list[str] = Field(default_factory=list)  # Arbitrary labels
    suggested_fix: str | None = None
    time_range: TimeRange | None = None  # Where in video this issue occurs


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


class PacingFeedback(str, Enum):
    """Pacing assessment for a shot or sequence."""

    TOO_FAST = "too_fast"  # Shot duration too short
    TOO_SLOW = "too_slow"  # Shot duration too long
    APPROPRIATE = "appropriate"  # Duration is good
    NEEDS_BREATHING_ROOM = "needs_breathing_room"  # Add pause before/after
    JARRING_TRANSITION = "jarring_transition"  # Cut feels abrupt


class ShotIntentAssessment(str, Enum):
    """Assessment of whether shot achieves its intended purpose."""

    EFFECTIVE = "effective"  # Shot achieves its role
    PARTIALLY_EFFECTIVE = "partially_effective"  # Room for improvement
    INEFFECTIVE = "ineffective"  # Shot doesn't achieve its role
    WRONG_CHOICE = "wrong_choice"  # Different shot type needed


class ShotFeedback(BaseModel):
    """Detailed feedback for a single shot.

    Allows experts to comment on pacing, shot intent, and duration
    adjustments at the shot level.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("sfb"))
    shot_id: str
    shot_sequence: int = 0

    # Pacing assessment
    pacing: PacingFeedback = PacingFeedback.APPROPRIATE
    pacing_comment: str = ""
    suggested_duration_seconds: float | None = None  # Expert's preferred duration

    # Shot intent assessment
    intent_assessment: ShotIntentAssessment = ShotIntentAssessment.EFFECTIVE
    intent_comment: str = ""  # Why it does/doesn't work
    intended_role: str = ""  # What role was this shot supposed to play

    # Duration adjustments
    duration_delta_seconds: float = 0.0  # +/- seconds from current
    extend_reason: str = ""  # Why extend (emotional beat, let moment breathe)
    shorten_reason: str = ""  # Why shorten (loses momentum, redundant)

    # Visual composition feedback
    composition_score: int = Field(ge=1, le=5, default=3)
    composition_comment: str = ""
    framing_suggestion: str = ""  # e.g., "Subject should be in right third"
    motion_suggestion: str = ""  # e.g., "Use static instead of pan"

    # Transition feedback
    transition_in_comment: str = ""
    transition_out_comment: str = ""
    suggested_transition_type: str | None = None

    # General notes
    expert_notes: str = ""
    priority: int = Field(ge=1, le=5, default=3)  # How important is this feedback

    # Playbook constraint suggestions
    suggested_constraints: list[str] = Field(default_factory=list)
    # e.g., ["prefer_static", "min_duration:4.0", "longer_establishing"]


class SequenceFeedback(BaseModel):
    """Feedback on a sequence of shots (scene-level pacing)."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("seqfb"))
    scene_id: str
    shot_ids: list[str] = Field(default_factory=list)

    # Sequence pacing
    overall_pacing: PacingFeedback = PacingFeedback.APPROPRIATE
    rhythm_comment: str = ""  # e.g., "Shot lengths too uniform, needs variety"

    # Shot order feedback
    reorder_suggestion: list[int] | None = None  # Suggested sequence order
    reorder_reason: str = ""

    # Shot count feedback
    too_many_shots: bool = False
    too_few_shots: bool = False
    shot_count_comment: str = ""

    # Suggested additions/removals
    shots_to_remove: list[str] = Field(default_factory=list)
    shots_to_add: list[str] = Field(default_factory=list)  # Descriptions of new shots
    remove_reasons: dict[str, str] = Field(default_factory=dict)
    add_reasons: list[str] = Field(default_factory=list)

    # Playbook constraints for this sequence
    suggested_constraints: list[str] = Field(default_factory=list)


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
    target_time_range: TimeRange | None = None  # Optional time scope within target

    # Scores (rubric-based)
    dimension_scores: DimensionScores = Field(default_factory=DimensionScores)
    overall_score: float = Field(ge=1, le=10, default=5.0)

    # Taxonomy labels for classification
    taxonomy_labels: list[str] = Field(default_factory=list)

    # Details
    issues: list[FeedbackIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    timestamped_notes: list[TimestampedNote] = Field(default_factory=list)

    # Shot-level feedback (for expert review of individual shots)
    shot_feedbacks: list[ShotFeedback] = Field(default_factory=list)

    # Sequence-level feedback (for scene pacing review)
    sequence_feedbacks: list[SequenceFeedback] = Field(default_factory=list)

    # Action
    recommendation: FeedbackRecommendation = FeedbackRecommendation.MINOR_FIXES
    fix_requests: list[FixRequest] = Field(default_factory=list)

    # Playbook constraints derived from this feedback
    derived_constraints: list[str] = Field(default_factory=list)

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
