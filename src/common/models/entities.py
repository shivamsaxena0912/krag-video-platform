"""Entity models: Character, Location, Event."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id


# ============================================================================
# Character
# ============================================================================


class CharacterRole(str, Enum):
    """Role of a character in the narrative."""

    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"
    NARRATOR = "narrator"


class CharacterImportance(str, Enum):
    """Importance level of a character."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    BACKGROUND = "background"


class VoiceProfile(BaseModel):
    """Voice characteristics for voiceover/dialogue."""

    model_config = ConfigDict(frozen=True)

    voice_id: str  # Provider voice ID
    gender: str
    age_range: str
    accent: str | None = None
    tone: str = ""  # e.g., "authoritative", "warm", "grave"


class Character(BaseModel):
    """A character entity within the story."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("char"))
    story_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Description
    physical_description: str = ""
    personality_traits: list[str] = Field(default_factory=list)
    role: CharacterRole = CharacterRole.SUPPORTING
    importance: CharacterImportance = CharacterImportance.SECONDARY

    # Visual generation
    visual_prompt: str = ""  # Stable prompt for consistency
    visual_reference_id: str | None = None  # Reference image ID
    voice_profile: VoiceProfile | None = None

    # Timeline
    introduction_scene_id: str | None = None
    scenes_appeared: list[str] = Field(default_factory=list)


# ============================================================================
# Location
# ============================================================================


class LocationType(str, Enum):
    """Type of location."""

    BUILDING = "building"
    OUTDOOR = "outdoor"
    INTERIOR = "interior"
    LANDSCAPE = "landscape"
    URBAN = "urban"
    RURAL = "rural"
    ABSTRACT = "abstract"


class Location(BaseModel):
    """A location entity within the story."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("loc"))
    story_id: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Description
    description: str = ""
    era: str = ""
    region: str | None = None
    location_type: LocationType = LocationType.OUTDOOR

    # Visual generation
    visual_prompt: str = ""
    visual_reference_id: str | None = None

    # Usage
    scenes_used: list[str] = Field(default_factory=list)


# ============================================================================
# Event
# ============================================================================


class EventType(str, Enum):
    """Type of narrative event."""

    ACTION = "action"
    DIALOGUE = "dialogue"
    REVELATION = "revelation"
    DECISION = "decision"
    TRANSITION = "transition"
    CONFLICT = "conflict"
    RESOLUTION = "resolution"


class EventSignificance(str, Enum):
    """Significance level of an event."""

    CRITICAL = "critical"  # Plot-essential
    MAJOR = "major"
    MINOR = "minor"
    ATMOSPHERIC = "atmospheric"


class Event(BaseModel):
    """A significant event within the narrative."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("event"))
    story_id: str
    scene_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    name: str
    description: str = ""
    event_type: EventType = EventType.ACTION
    significance: EventSignificance = EventSignificance.MINOR

    # Participants
    characters_involved: list[str] = Field(default_factory=list)
    location_id: str | None = None

    # Causality
    caused_by_event_id: str | None = None
    causes_event_ids: list[str] = Field(default_factory=list)
