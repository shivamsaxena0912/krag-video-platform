# Data Models & Schemas

## Overview

This document defines the complete data models used throughout the KRAG video platform. All models are implemented as Pydantic classes for validation, serialization, and type safety.

## Core Principles

1. **Immutability**: Data models are immutable after creation (frozen=True)
2. **Versioning**: All entities have version tracking
3. **Provenance**: Origin and transformation history is tracked
4. **Validation**: Strict type checking and value constraints

---

## Scene Graph Schema

The Scene Graph represents the structured understanding of a narrative text.

### Story

```python
class Story(BaseModel):
    """Root entity representing a complete narrative."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"story_{uuid4().hex[:12]}")
    title: str
    source_type: SourceType
    source_metadata: SourceMetadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1
    status: StoryStatus = StoryStatus.DRAFT

    # Derived from parsing
    total_scenes: int = 0
    total_characters: int = 0
    total_locations: int = 0
    estimated_duration_minutes: float = 0.0


class SourceType(str, Enum):
    BOOK = "book"
    SCRIPT = "script"
    NARRATIVE = "narrative"
    ARTICLE = "article"
    CUSTOM = "custom"


class SourceMetadata(BaseModel):
    """Metadata about the source material."""
    title: str
    author: str | None = None
    publication_year: int | None = None
    genre: str | None = None
    era: str | None = None  # Historical period depicted
    language: str = "en"
    license: str | None = None
    source_url: str | None = None
    word_count: int = 0


class StoryStatus(str, Enum):
    DRAFT = "draft"
    PARSING = "parsing"
    PARSED = "parsed"
    PLANNING = "planning"
    PLANNED = "planned"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    COMPLETE = "complete"
    FAILED = "failed"
```

### Scene

```python
class Scene(BaseModel):
    """A discrete narrative unit within a story."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"scene_{uuid4().hex[:12]}")
    story_id: str
    sequence: int  # Order within story
    version: int = 1

    # Content
    raw_text: str
    summary: str
    setting: SceneSetting
    emotional_beat: EmotionalBeat

    # Entities present
    characters: list[str] = []  # Character IDs
    locations: list[str] = []  # Location IDs
    events: list[str] = []  # Event IDs
    props: list[str] = []  # Prop IDs

    # Derived metadata
    word_count: int = 0
    estimated_duration_seconds: float = 0.0
    complexity_score: float = 0.0  # 0-1

    # Continuity
    continuity_score: float = 1.0
    continuity_notes: list[str] = []

    # Planning status
    has_shot_plan: bool = False
    shot_plan_id: str | None = None


class SceneSetting(BaseModel):
    """The setting/context of a scene."""
    location_name: str
    location_description: str
    time_of_day: TimeOfDay
    era: str
    atmosphere: str  # e.g., "tense", "peaceful", "chaotic"
    weather: str | None = None
    interior_exterior: Literal["interior", "exterior", "mixed"]


class TimeOfDay(str, Enum):
    DAWN = "dawn"
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    UNSPECIFIED = "unspecified"


class EmotionalBeat(BaseModel):
    """The emotional arc/beat of a scene."""
    primary_emotion: str  # e.g., "tension", "joy", "sorrow"
    intensity: float  # 0-1
    arc: EmotionalArc
    narrative_function: str  # e.g., "inciting incident", "climax"


class EmotionalArc(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    PEAK = "peak"
    VALLEY = "valley"
    STABLE = "stable"
```

### Character

```python
class Character(BaseModel):
    """A character entity within the story."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"char_{uuid4().hex[:12]}")
    story_id: str
    name: str
    aliases: list[str] = []

    # Description
    physical_description: str
    personality_traits: list[str] = []
    role: CharacterRole
    importance: CharacterImportance

    # Visual generation
    visual_prompt: str  # Stable prompt for consistency
    visual_reference_id: str | None = None  # Reference image ID
    voice_profile: VoiceProfile | None = None

    # Timeline
    introduction_scene_id: str | None = None
    scenes_appeared: list[str] = []


class CharacterRole(str, Enum):
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"
    NARRATOR = "narrator"


class CharacterImportance(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    BACKGROUND = "background"


class VoiceProfile(BaseModel):
    """Voice characteristics for voiceover/dialogue."""
    voice_id: str  # ElevenLabs or other provider ID
    gender: str
    age_range: str
    accent: str | None = None
    tone: str  # e.g., "authoritative", "warm", "grave"
```

### Location

```python
class Location(BaseModel):
    """A location entity within the story."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"loc_{uuid4().hex[:12]}")
    story_id: str
    name: str

    # Description
    description: str
    era: str
    region: str | None = None
    location_type: LocationType

    # Visual generation
    visual_prompt: str
    visual_reference_id: str | None = None

    # Usage
    scenes_used: list[str] = []


class LocationType(str, Enum):
    BUILDING = "building"
    OUTDOOR = "outdoor"
    INTERIOR = "interior"
    LANDSCAPE = "landscape"
    URBAN = "urban"
    RURAL = "rural"
    ABSTRACT = "abstract"
```

### Event

```python
class Event(BaseModel):
    """A significant event within the narrative."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"event_{uuid4().hex[:12]}")
    story_id: str
    scene_id: str

    name: str
    description: str
    event_type: EventType
    significance: EventSignificance

    # Participants
    characters_involved: list[str] = []
    location_id: str | None = None

    # Causality
    caused_by_event_id: str | None = None
    causes_event_ids: list[str] = []


class EventType(str, Enum):
    ACTION = "action"
    DIALOGUE = "dialogue"
    REVELATION = "revelation"
    DECISION = "decision"
    TRANSITION = "transition"
    CONFLICT = "conflict"
    RESOLUTION = "resolution"


class EventSignificance(str, Enum):
    CRITICAL = "critical"  # Plot-essential
    MAJOR = "major"
    MINOR = "minor"
    ATMOSPHERIC = "atmospheric"
```

---

## Shot Plan Schema

The Shot Plan represents the cinematic translation of a scene.

### ShotPlan

```python
class ShotPlan(BaseModel):
    """Complete shot plan for a scene."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"plan_{uuid4().hex[:12]}")
    scene_id: str
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Shots
    shots: list[Shot]
    total_shots: int = 0

    # Audio
    audio_plan: AudioPlan

    # Metadata
    estimated_duration_seconds: float = 0.0
    complexity_score: float = 0.0
    generation_cost_estimate: float = 0.0

    # Rationale
    creative_direction: str
    pacing_rationale: str
    style_notes: list[str] = []

    # Status
    status: ShotPlanStatus = ShotPlanStatus.DRAFT


class ShotPlanStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    GENERATING = "generating"
    GENERATED = "generated"
    ASSEMBLED = "assembled"
```

### Shot

```python
class Shot(BaseModel):
    """A single shot within a shot plan."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"shot_{uuid4().hex[:12]}")
    shot_plan_id: str
    sequence: int

    # Shot specification
    shot_type: ShotType
    duration_seconds: float
    subject: str  # What/who is the focus
    composition: Composition
    motion: MotionSpec

    # Context
    mood: str
    lighting: str
    time_of_day: TimeOfDay

    # Content
    narration_text: str | None = None
    dialogue: list[DialogueLine] = []
    visual_description: str

    # Generation
    image_prompt: str | None = None
    negative_prompt: str | None = None
    style_reference: str | None = None

    # Transitions
    transition_in: Transition | None = None
    transition_out: Transition | None = None

    # Audio cues
    audio_cues: list[AudioCue] = []

    # Assets (populated after generation)
    generated_asset_ids: list[str] = []


class ShotType(str, Enum):
    EXTREME_WIDE = "extreme_wide"  # Establishing, landscapes
    WIDE = "wide"  # Full scene context
    MEDIUM_WIDE = "medium_wide"  # Group shots
    MEDIUM = "medium"  # Waist up
    MEDIUM_CLOSE = "medium_close"  # Chest up
    CLOSE_UP = "close_up"  # Face/object detail
    EXTREME_CLOSE = "extreme_close"  # Eyes, small details
    CUTAWAY = "cutaway"  # Reaction, detail insert
    POV = "pov"  # Point of view


class Composition(BaseModel):
    """Shot composition details."""
    framing: Framing
    angle: CameraAngle
    depth_of_field: DepthOfField
    rule_of_thirds_position: str | None = None


class Framing(str, Enum):
    CENTERED = "centered"
    LEFT_THIRD = "left_third"
    RIGHT_THIRD = "right_third"
    LOWER_THIRD = "lower_third"
    UPPER_THIRD = "upper_third"


class CameraAngle(str, Enum):
    EYE_LEVEL = "eye_level"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"
    BIRDS_EYE = "birds_eye"
    WORMS_EYE = "worms_eye"
    DUTCH = "dutch"


class DepthOfField(str, Enum):
    DEEP = "deep"  # Everything in focus
    SHALLOW = "shallow"  # Subject isolated
    RACK = "rack"  # Focus shift


class MotionSpec(BaseModel):
    """Camera/subject motion specification."""
    camera_motion: CameraMotion
    motion_speed: MotionSpeed
    motion_direction: str | None = None
    subject_motion: str | None = None


class CameraMotion(str, Enum):
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
    VERY_SLOW = "very_slow"
    SLOW = "slow"
    MODERATE = "moderate"
    FAST = "fast"
    VERY_FAST = "very_fast"


class Transition(BaseModel):
    """Transition between shots."""
    type: TransitionType
    duration_seconds: float = 0.5


class TransitionType(str, Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE_TO_BLACK = "fade_to_black"
    FADE_FROM_BLACK = "fade_from_black"
    WIPE = "wipe"
    CROSSFADE = "crossfade"


class DialogueLine(BaseModel):
    """A line of dialogue."""
    character_id: str
    text: str
    emotion: str
    timing_hint: str | None = None


class AudioCue(BaseModel):
    """Audio cue for a shot."""
    cue_type: AudioCueType
    description: str
    timing: str  # "start", "middle", "end", or timestamp


class AudioCueType(str, Enum):
    MUSIC_START = "music_start"
    MUSIC_SWELL = "music_swell"
    MUSIC_FADE = "music_fade"
    SFX = "sfx"
    AMBIENT = "ambient"
    SILENCE = "silence"
```

### AudioPlan

```python
class AudioPlan(BaseModel):
    """Complete audio plan for a scene."""
    voiceover: VoiceoverPlan
    music: MusicPlan
    sound_effects: list[SoundEffect] = []
    ambient: AmbientAudio | None = None


class VoiceoverPlan(BaseModel):
    """Voiceover specifications."""
    narrator_voice_id: str
    full_text: str
    segments: list[VoiceoverSegment]
    style: str  # e.g., "documentary", "dramatic"
    pacing: str  # "slow", "moderate", "fast"


class VoiceoverSegment(BaseModel):
    """A segment of voiceover tied to shots."""
    text: str
    shot_ids: list[str]
    emotion: str
    emphasis_words: list[str] = []


class MusicPlan(BaseModel):
    """Music specifications."""
    mood: str
    genre: str
    tempo: str  # "slow", "moderate", "fast"
    intensity_curve: list[tuple[float, float]]  # (timestamp, intensity 0-1)
    track_id: str | None = None  # If using licensed track


class SoundEffect(BaseModel):
    """Sound effect specification."""
    description: str
    timing_seconds: float
    duration_seconds: float
    volume: float = 0.8


class AmbientAudio(BaseModel):
    """Ambient audio layer."""
    description: str
    volume: float = 0.3
```

---

## Feedback Schema

Structured feedback for quality improvement.

### FeedbackAnnotation

```python
class FeedbackAnnotation(BaseModel):
    """Structured feedback on a video/scene/shot."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"fb_{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Source
    source: FeedbackSource
    reviewer_id: str | None = None

    # Target
    target_type: FeedbackTargetType
    target_id: str

    # Scores
    dimension_scores: DimensionScores
    overall_score: float  # 1-10

    # Details
    issues: list[FeedbackIssue] = []
    strengths: list[str] = []
    timestamped_notes: list[TimestampedNote] = []

    # Action
    recommendation: FeedbackRecommendation
    fix_requests: list[FixRequest] = []


class FeedbackSource(str, Enum):
    AI_CRITIC = "ai_critic"
    HUMAN_EXPERT = "human_expert"
    HUMAN_DIRECTOR = "human_director"
    HUMAN_EDITOR = "human_editor"
    AUTOMATED_QA = "automated_qa"


class FeedbackTargetType(str, Enum):
    STORY = "story"
    SCENE = "scene"
    SHOT = "shot"
    ASSET = "asset"
    VIDEO_DRAFT = "video_draft"
    FINAL_VIDEO = "final_video"


class DimensionScores(BaseModel):
    """Scores across quality dimensions."""
    narrative_clarity: int = Field(ge=1, le=5)
    hook_strength: int = Field(ge=1, le=5)
    pacing: int = Field(ge=1, le=5)
    shot_composition: int = Field(ge=1, le=5)
    continuity: int = Field(ge=1, le=5)
    audio_mix: int = Field(ge=1, le=5)

    def average(self) -> float:
        return (
            self.narrative_clarity +
            self.hook_strength +
            self.pacing +
            self.shot_composition +
            self.continuity +
            self.audio_mix
        ) / 6


class FeedbackIssue(BaseModel):
    """A specific issue identified."""
    id: str = Field(default_factory=lambda: f"issue_{uuid4().hex[:8]}")
    dimension: str
    severity: IssueSeverity
    description: str
    fix_category: FixCategory
    suggested_fix: str | None = None


class IssueSeverity(str, Enum):
    CRITICAL = "critical"  # Must fix before approval
    MAJOR = "major"  # Should fix
    MINOR = "minor"  # Nice to fix
    SUGGESTION = "suggestion"  # Optional improvement


class FixCategory(str, Enum):
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


class TimestampedNote(BaseModel):
    """A note tied to a timestamp."""
    timestamp_seconds: float
    end_timestamp_seconds: float | None = None
    note: str
    severity: IssueSeverity = IssueSeverity.SUGGESTION


class FixRequest(BaseModel):
    """A specific fix request."""
    issue_id: str
    fix_category: FixCategory
    target_shot_id: str | None = None
    instructions: str
    priority: int = 1  # 1 = highest


class FeedbackRecommendation(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_NOTES = "approve_with_notes"
    MINOR_FIXES = "minor_fixes"
    MAJOR_REVISION = "major_revision"
    REJECT = "reject"
```

---

## Asset Schema

Generated assets and their metadata.

```python
class Asset(BaseModel):
    """A generated asset."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"asset_{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Type and source
    asset_type: AssetType
    shot_id: str
    scene_id: str

    # Storage
    file_path: str
    file_size_bytes: int
    mime_type: str
    checksum: str

    # Generation
    generation_model: str
    generation_params: dict
    generation_prompt: str | None = None
    generation_time_seconds: float
    generation_cost: float

    # Quality
    quality_score: float = 0.0  # 0-1
    quality_notes: list[str] = []

    # Usage
    used_in_video_ids: list[str] = []


class AssetType(str, Enum):
    IMAGE = "image"
    VOICEOVER = "voiceover"
    MUSIC = "music"
    SFX = "sfx"
    AMBIENT = "ambient"
    VIDEO_CLIP = "video_clip"
```

---

## Pipeline State Schema

```python
class PipelineRun(BaseModel):
    """State of a pipeline execution."""
    id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    story_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Status
    status: PipelineStatus
    current_stage: PipelineStage
    progress_percent: float = 0.0

    # Stage outputs
    stage_outputs: dict[str, Any] = {}

    # Costs
    costs: CostBreakdown

    # Iteration
    refinement_iterations: int = 0
    max_iterations: int = 3

    # Error handling
    errors: list[PipelineError] = []
    warnings: list[str] = []


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(str, Enum):
    INGESTION = "ingestion"
    PARSING = "parsing"
    SCENE_GRAPH = "scene_graph"
    CONTINUITY = "continuity"
    SHOT_PLANNING = "shot_planning"
    ASSET_GENERATION = "asset_generation"
    ASSEMBLY = "assembly"
    CRITIQUE = "critique"
    REFINEMENT = "refinement"
    HUMAN_REVIEW = "human_review"
    FINALIZATION = "finalization"


class CostBreakdown(BaseModel):
    """Cost tracking for a pipeline run."""
    total_cost: float = 0.0
    llm_cost: float = 0.0
    image_generation_cost: float = 0.0
    voice_synthesis_cost: float = 0.0
    music_cost: float = 0.0
    storage_cost: float = 0.0
    compute_cost: float = 0.0


class PipelineError(BaseModel):
    """An error during pipeline execution."""
    stage: PipelineStage
    error_type: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recoverable: bool = True
    stack_trace: str | None = None
```

---

## JSON Schema Examples

### Scene Graph JSON

```json
{
  "story": {
    "id": "story_abc123",
    "title": "The Fall of Rome",
    "source_type": "book",
    "source_metadata": {
      "title": "The History of the Decline and Fall of the Roman Empire",
      "author": "Edward Gibbon",
      "publication_year": 1776,
      "genre": "history",
      "era": "Ancient Rome"
    }
  },
  "scenes": [
    {
      "id": "scene_001",
      "story_id": "story_abc123",
      "sequence": 1,
      "summary": "Emperor Commodus enters the Colosseum as a gladiator",
      "setting": {
        "location_name": "Colosseum",
        "location_description": "The great amphitheater of Rome, filled with 50,000 spectators",
        "time_of_day": "afternoon",
        "era": "180 AD",
        "atmosphere": "electric anticipation"
      },
      "emotional_beat": {
        "primary_emotion": "tension",
        "intensity": 0.8,
        "arc": "rising",
        "narrative_function": "inciting incident"
      },
      "characters": ["char_commodus", "char_crowd"],
      "locations": ["loc_colosseum"]
    }
  ],
  "characters": [
    {
      "id": "char_commodus",
      "name": "Emperor Commodus",
      "physical_description": "Young Roman emperor, athletic build, arrogant bearing",
      "role": "protagonist",
      "visual_prompt": "young Roman emperor, athletic build, golden laurel wreath, white toga with purple trim, arrogant expression, clean-shaven"
    }
  ]
}
```

### Shot Plan JSON

```json
{
  "id": "plan_xyz789",
  "scene_id": "scene_001",
  "shots": [
    {
      "id": "shot_001",
      "sequence": 1,
      "shot_type": "extreme_wide",
      "duration_seconds": 4.0,
      "subject": "Colosseum exterior",
      "composition": {
        "framing": "centered",
        "angle": "eye_level",
        "depth_of_field": "deep"
      },
      "motion": {
        "camera_motion": "slow_zoom_in",
        "motion_speed": "slow"
      },
      "narration_text": "In the year 180 AD, the greatest empire the world had ever known...",
      "transition_out": {
        "type": "dissolve",
        "duration_seconds": 0.5
      }
    },
    {
      "id": "shot_002",
      "sequence": 2,
      "shot_type": "wide",
      "duration_seconds": 3.0,
      "subject": "Colosseum interior, crowd",
      "composition": {
        "framing": "centered",
        "angle": "high_angle",
        "depth_of_field": "deep"
      },
      "motion": {
        "camera_motion": "static",
        "motion_speed": "moderate"
      }
    }
  ],
  "audio_plan": {
    "voiceover": {
      "narrator_voice_id": "voice_documentary_male",
      "style": "documentary",
      "pacing": "moderate"
    },
    "music": {
      "mood": "epic",
      "genre": "orchestral",
      "tempo": "moderate"
    }
  }
}
```

### Feedback JSON

```json
{
  "id": "fb_review123",
  "source": "ai_critic",
  "target_type": "video_draft",
  "target_id": "draft_001",
  "dimension_scores": {
    "narrative_clarity": 4,
    "hook_strength": 3,
    "pacing": 4,
    "shot_composition": 5,
    "continuity": 4,
    "audio_mix": 3
  },
  "overall_score": 7.5,
  "issues": [
    {
      "id": "issue_001",
      "dimension": "hook_strength",
      "severity": "major",
      "description": "Opening shot holds too long before action begins",
      "fix_category": "adjust_duration",
      "suggested_fix": "Reduce establishing shot from 4s to 2.5s"
    },
    {
      "id": "issue_002",
      "dimension": "audio_mix",
      "severity": "minor",
      "description": "Music slightly overpowers narration at 0:45",
      "fix_category": "adjust_audio_mix",
      "suggested_fix": "Reduce music volume by 3dB during narration segment"
    }
  ],
  "recommendation": "minor_fixes"
}
```

---

*These schemas are implemented in `src/common/models/`.*
