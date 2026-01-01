"""Audio plan models."""

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id


class VoiceoverSegment(BaseModel):
    """A segment of voiceover tied to shots."""

    model_config = ConfigDict(frozen=True)

    text: str
    shot_ids: list[str] = Field(default_factory=list)
    emotion: str = ""
    emphasis_words: list[str] = Field(default_factory=list)


class VoiceoverPlan(BaseModel):
    """Voiceover specifications."""

    model_config = ConfigDict(frozen=True)

    narrator_voice_id: str
    full_text: str = ""
    segments: list[VoiceoverSegment] = Field(default_factory=list)
    style: str = "documentary"  # e.g., "documentary", "dramatic"
    pacing: str = "moderate"  # "slow", "moderate", "fast"


class MusicPlan(BaseModel):
    """Music specifications."""

    model_config = ConfigDict(frozen=True)

    mood: str
    genre: str = ""
    tempo: str = "moderate"  # "slow", "moderate", "fast"
    intensity_curve: list[tuple[float, float]] = Field(
        default_factory=list
    )  # (timestamp, intensity 0-1)
    track_id: str | None = None  # If using licensed track


class SoundEffect(BaseModel):
    """Sound effect specification."""

    model_config = ConfigDict(frozen=True)

    description: str
    timing_seconds: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    volume: float = Field(default=0.8, ge=0, le=1)


class AmbientAudio(BaseModel):
    """Ambient audio layer."""

    model_config = ConfigDict(frozen=True)

    description: str
    volume: float = Field(default=0.3, ge=0, le=1)


class AudioPlan(BaseModel):
    """Complete audio plan for a scene."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("audio"))
    scene_id: str

    voiceover: VoiceoverPlan | None = None
    music: MusicPlan | None = None
    sound_effects: list[SoundEffect] = Field(default_factory=list)
    ambient: AmbientAudio | None = None
