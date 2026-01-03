"""Shot plan and shot-related models."""

from __future__ import annotations

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


class ShotRole(str, Enum):
    """Narrative role of a shot within a scene."""

    ESTABLISHING = "establishing"  # Sets location/context
    ACTION = "action"  # Shows main activity
    REACTION = "reaction"  # Character response
    DETAIL = "detail"  # Close-up on significant object
    TRANSITION = "transition"  # Bridges scenes
    MONTAGE = "montage"  # Part of rapid sequence
    CLIMAX = "climax"  # Peak dramatic moment
    RESOLUTION = "resolution"  # Closing/calming shot


class VisualFidelityLevel(str, Enum):
    """Visual fidelity level for asset generation.

    PLACEHOLDER: Fast, low-cost placeholder images for iteration
    REFERENCE: Higher-quality AI-generated images for look-dev
    """

    PLACEHOLDER = "placeholder"
    REFERENCE = "reference"


class ShotPurpose(str, Enum):
    """Editorial purpose of a shot - mandatory for editorial authority.

    Every shot MUST declare exactly one purpose. Shots without a declared
    purpose are automatically removed during the trimming pass.

    INFORMATION: Delivers facts, context, or exposition
    EMOTION: Creates or amplifies emotional response
    ATMOSPHERE: Establishes mood, tone, or environment
    TRANSITION: Bridges scenes or shifts narrative beats
    """

    INFORMATION = "information"
    EMOTION = "emotion"
    ATMOSPHERE = "atmosphere"
    TRANSITION = "transition"


class BeatIntensity(str, Enum):
    """Rhythmic intensity of a shot - controls tempo and contrast.

    The system enforces variation: no long runs of identical intensity.
    This is how rhythm is created.

    LOW: Breathing room, contemplation, stillness
    MEDIUM: Normal narrative flow, neutral energy
    HIGH: Peak moments, urgency, maximum engagement
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EndingIntent(str, Enum):
    """Explicit intent for the final shot - no neutral endings allowed.

    The system biases duration and intensity to support this intent.

    RESOLUTION: Emotional closure, catharsis, peace
    PROVOCATION: Lingering question, tension, "what now?"
    TRANSITION: Continuation implied, story goes on
    """

    RESOLUTION = "resolution"
    PROVOCATION = "provocation"
    TRANSITION = "transition"


class LensType(str, Enum):
    """Camera lens type affecting perspective."""

    ULTRA_WIDE = "ultra_wide"  # 14-24mm, expansive, distortion
    WIDE = "wide"  # 24-35mm, environmental
    NORMAL = "normal"  # 35-50mm, natural perspective
    SHORT_TELE = "short_tele"  # 85-135mm, portraits, compression
    TELEPHOTO = "telephoto"  # 200mm+, extreme compression, isolation
    MACRO = "macro"  # Extreme close-up


class LightingStyle(str, Enum):
    """Lighting style/mood."""

    NATURAL = "natural"  # Realistic daylight
    HIGH_KEY = "high_key"  # Bright, low contrast, optimistic
    LOW_KEY = "low_key"  # Dark, high contrast, dramatic
    REMBRANDT = "rembrandt"  # Classic portrait, triangle shadow
    SILHOUETTE = "silhouette"  # Backlit, subject in shadow
    GOLDEN_HOUR = "golden_hour"  # Warm, soft, romantic
    BLUE_HOUR = "blue_hour"  # Cool, ethereal, melancholy
    DRAMATIC = "dramatic"  # Strong shadows, tension
    DIFFUSED = "diffused"  # Soft, even, dreamlike


class CompositionZone(str, Enum):
    """Precise composition zone based on rule of thirds grid."""

    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
    FULL_FRAME = "full_frame"  # Subject fills frame


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


class SubjectEntity(BaseModel):
    """An entity visible in the shot."""

    model_config = ConfigDict(frozen=True)

    entity_id: str = ""  # Reference to character/location/prop ID
    entity_type: str = "character"  # character, location, prop, symbol
    name: str = ""
    screen_position: CompositionZone = CompositionZone.CENTER
    prominence: str = "primary"  # primary, secondary, background
    action: str = ""  # What the entity is doing


class VisualSymbol(BaseModel):
    """Visual symbolism or motif in the shot."""

    model_config = ConfigDict(frozen=True)

    symbol: str  # e.g., "broken sword", "setting sun", "closed door"
    meaning: str  # What it represents narratively
    visual_treatment: str = ""  # How to emphasize it (focus, framing, lighting)


class ShotVisualSpec(BaseModel):
    """Complete visual specification for a shot.

    This model provides deterministic, explicit visual parameters
    that the renderer and image generator can consume directly.
    """

    model_config = ConfigDict(frozen=True)

    # Visual fidelity level (PLACEHOLDER default, REFERENCE for look-dev)
    fidelity_level: VisualFidelityLevel = VisualFidelityLevel.PLACEHOLDER

    # Shot role in the narrative
    role: ShotRole = ShotRole.ACTION

    # Camera setup
    lens_type: LensType = LensType.NORMAL
    camera_height: str = "eye_level"  # ground, low, eye_level, high, aerial

    # Composition
    primary_zone: CompositionZone = CompositionZone.CENTER
    secondary_zone: CompositionZone | None = None
    negative_space: str = ""  # Where empty space should be (left, right, top, bottom)

    # Lighting
    lighting_style: LightingStyle = LightingStyle.NATURAL
    key_light_direction: str = "front"  # front, side, back, top, bottom
    fill_ratio: str = "balanced"  # balanced, high_contrast, minimal_fill
    practical_lights: list[str] = Field(default_factory=list)  # e.g., ["candles", "fireplace"]

    # Subjects in frame
    subjects: list[SubjectEntity] = Field(default_factory=list)

    # Color and mood
    color_palette: list[str] = Field(default_factory=list)  # e.g., ["warm earth tones", "desaturated"]
    color_temperature: str = "neutral"  # warm, neutral, cool

    # Symbolism
    symbols: list[VisualSymbol] = Field(default_factory=list)

    # Ken Burns / animation hints for renderer
    ken_burns_start_zone: CompositionZone = CompositionZone.CENTER
    ken_burns_end_zone: CompositionZone = CompositionZone.CENTER
    zoom_direction: str = "none"  # in, out, none

    # Prompt generation helpers
    style_keywords: list[str] = Field(default_factory=list)  # e.g., ["cinematic", "film grain"]
    reference_films: list[str] = Field(default_factory=list)  # e.g., ["Gladiator", "Rome HBO"]


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

    # MANDATORY: Editorial purpose - shots without purpose are removed
    purpose: ShotPurpose | None = None  # None = will be removed in trimming pass

    # Rhythmic intensity - controls tempo and contrast
    intensity: BeatIntensity = BeatIntensity.MEDIUM

    # Ending intent (only for final shot) - no neutral endings
    ending_intent: EndingIntent | None = None

    # Visual specification (populated by DirectorAgent)
    visual_spec: ShotVisualSpec | None = None

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
