"""Shot plan and shot-related models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id
from src.common.models.scene import TimeOfDay


# ============================================================================
# Enums
# ============================================================================


class ShotPlanStatus(str, Enum):
    """Status of a shot plan."""

    DRAFT = "draft"
    APPROVED = "approved"
    GENERATING = "generating"
    GENERATED = "generated"
    ASSEMBLED = "assembled"


class ShotType(str, Enum):
    """Type of camera shot."""

    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM_WIDE = "medium_wide"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE = "extreme_close"
    CUTAWAY = "cutaway"
    POV = "pov"


class Framing(str, Enum):
    """Subject framing within the shot."""

    CENTERED = "centered"
    LEFT_THIRD = "left_third"
    RIGHT_THIRD = "right_third"
    LOWER_THIRD = "lower_third"
    UPPER_THIRD = "upper_third"


class CameraAngle(str, Enum):
    """Camera angle relative to subject."""

    EYE_LEVEL = "eye_level"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"
    BIRDS_EYE = "birds_eye"
    WORMS_EYE = "worms_eye"
    DUTCH = "dutch"


class DepthOfField(str, Enum):
    """Depth of field setting."""

    DEEP = "deep"
    SHALLOW = "shallow"
    RACK = "rack"


class CameraMotion(str, Enum):
    """Camera motion type."""

    STATIC = "static"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    TILT_UP = "tilt_up"
    TILT_DOWN = "tilt_down"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    DOLLY_IN = "dolly_in"
    DOLLY_OUT = "dolly_out"
    TRACK_LEFT = "track_left"
    TRACK_RIGHT = "track_right"
    CRANE_UP = "crane_up"
    CRANE_DOWN = "crane_down"


class MotionSpeed(str, Enum):
    """Speed of camera motion."""

    VERY_SLOW = "very_slow"
    SLOW = "slow"
    MODERATE = "moderate"
    FAST = "fast"
    VERY_FAST = "very_fast"


class TransitionType(str, Enum):
    """Type of transition between shots."""

    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE_TO_BLACK = "fade_to_black"
    FADE_FROM_BLACK = "fade_from_black"
    WIPE = "wipe"
    CROSSFADE = "crossfade"


class AudioCueType(str, Enum):
    """Type of audio cue."""

    MUSIC_START = "music_start"
    MUSIC_SWELL = "music_swell"
    MUSIC_FADE = "music_fade"
    SFX = "sfx"
    AMBIENT = "ambient"
    SILENCE = "silence"


# ============================================================================
# Component Models
# ============================================================================


class Composition(BaseModel):
    """Shot composition details."""

    model_config = ConfigDict(frozen=True)

    framing: Framing = Framing.CENTERED
    angle: CameraAngle = CameraAngle.EYE_LEVEL
    depth_of_field: DepthOfField = DepthOfField.DEEP
    rule_of_thirds_position: str | None = None


class MotionSpec(BaseModel):
    """Camera/subject motion specification."""

    model_config = ConfigDict(frozen=True)

    camera_motion: CameraMotion = CameraMotion.STATIC
    motion_speed: MotionSpeed = MotionSpeed.MODERATE
    motion_direction: str | None = None
    subject_motion: str | None = None


class Transition(BaseModel):
    """Transition between shots."""

    model_config = ConfigDict(frozen=True)

    type: TransitionType = TransitionType.CUT
    duration_seconds: float = Field(default=0.5, ge=0)


class DialogueLine(BaseModel):
    """A line of dialogue."""

    model_config = ConfigDict(frozen=True)

    character_id: str
    text: str
    emotion: str = ""
    timing_hint: str | None = None


class AudioCue(BaseModel):
    """Audio cue for a shot."""

    model_config = ConfigDict(frozen=True)

    cue_type: AudioCueType
    description: str = ""
    timing: str = "start"  # "start", "middle", "end", or timestamp


# ============================================================================
# Shot
# ============================================================================


class Shot(BaseModel):
    """A single shot within a shot plan."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("shot"))
    shot_plan_id: str
    sequence: int

    # Shot specification
    shot_type: ShotType = ShotType.MEDIUM
    duration_seconds: float = Field(default=3.0, ge=0.1)
    subject: str  # What/who is the focus
    composition: Composition = Field(default_factory=Composition)
    motion: MotionSpec = Field(default_factory=MotionSpec)

    # Context
    mood: str = ""
    lighting: str = ""
    time_of_day: TimeOfDay = TimeOfDay.UNSPECIFIED

    # Content
    narration_text: str | None = None
    dialogue: list[DialogueLine] = Field(default_factory=list)
    visual_description: str = ""

    # Generation
    image_prompt: str | None = None
    negative_prompt: str | None = None
    style_reference: str | None = None

    # Transitions
    transition_in: Transition | None = None
    transition_out: Transition | None = None

    # Audio cues
    audio_cues: list[AudioCue] = Field(default_factory=list)

    # Assets (populated after generation)
    generated_asset_ids: list[str] = Field(default_factory=list)


# ============================================================================
# Shot Plan
# ============================================================================


class ShotPlan(BaseModel):
    """Complete shot plan for a scene."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("plan"))
    scene_id: str
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Shots
    shots: list[Shot] = Field(default_factory=list)

    @property
    def total_shots(self) -> int:
        return len(self.shots)

    # Audio (imported to avoid circular import)
    audio_plan_id: str | None = None

    # Metadata
    estimated_duration_seconds: float = 0.0
    complexity_score: float = Field(ge=0, le=1, default=0.5)
    generation_cost_estimate: float = 0.0

    # Rationale
    creative_direction: str = ""
    pacing_rationale: str = ""
    style_notes: list[str] = Field(default_factory=list)

    # Status
    status: ShotPlanStatus = ShotPlanStatus.DRAFT

    def summary(self) -> dict:
        """Return summary for logging."""
        return {
            "id": self.id,
            "scene_id": self.scene_id,
            "shots": len(self.shots),
            "duration": self.estimated_duration_seconds,
            "status": self.status.value,
        }
