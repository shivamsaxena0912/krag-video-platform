"""Scene and related models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id


class TimeOfDay(str, Enum):
    """Time of day for a scene."""

    DAWN = "dawn"
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    UNSPECIFIED = "unspecified"


class EmotionalArc(str, Enum):
    """Direction of emotional intensity."""

    RISING = "rising"
    FALLING = "falling"
    PEAK = "peak"
    VALLEY = "valley"
    STABLE = "stable"


class SceneSetting(BaseModel):
    """The setting/context of a scene."""

    model_config = ConfigDict(frozen=True)

    location_name: str
    location_description: str
    time_of_day: TimeOfDay = TimeOfDay.UNSPECIFIED
    era: str = ""
    atmosphere: str = ""  # e.g., "tense", "peaceful", "chaotic"
    weather: str | None = None
    interior_exterior: Literal["interior", "exterior", "mixed"] = "mixed"


class EmotionalBeat(BaseModel):
    """The emotional arc/beat of a scene."""

    model_config = ConfigDict(frozen=True)

    primary_emotion: str  # e.g., "tension", "joy", "sorrow"
    intensity: float = Field(ge=0, le=1, default=0.5)  # 0-1
    arc: EmotionalArc = EmotionalArc.STABLE
    narrative_function: str = ""  # e.g., "inciting incident", "climax"


class Scene(BaseModel):
    """A discrete narrative unit within a story."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("scene"))
    story_id: str
    sequence: int  # Order within story
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Content
    raw_text: str
    summary: str = ""
    setting: SceneSetting
    emotional_beat: EmotionalBeat

    # Entities present (IDs)
    characters: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)

    # Derived metadata
    word_count: int = 0
    estimated_duration_seconds: float = 0.0
    complexity_score: float = Field(ge=0, le=1, default=0.5)

    # Continuity
    continuity_score: float = Field(ge=0, le=1, default=1.0)
    continuity_notes: list[str] = Field(default_factory=list)

    # Planning status
    has_shot_plan: bool = False
    shot_plan_id: str | None = None

    def summary_dict(self) -> dict:
        """Return summary for logging."""
        return {
            "id": self.id,
            "story_id": self.story_id,
            "sequence": self.sequence,
            "characters": len(self.characters),
            "has_shot_plan": self.has_shot_plan,
        }
