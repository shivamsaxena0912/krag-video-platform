"""Story and source metadata models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.common.models.base import generate_id


class SourceType(str, Enum):
    """Type of source material."""

    BOOK = "book"
    SCRIPT = "script"
    NARRATIVE = "narrative"
    ARTICLE = "article"
    CUSTOM = "custom"


class StoryStatus(str, Enum):
    """Status of story processing."""

    DRAFT = "draft"
    PARSING = "parsing"
    PARSED = "parsed"
    PLANNING = "planning"
    PLANNED = "planned"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    COMPLETE = "complete"
    FAILED = "failed"


class SourceMetadata(BaseModel):
    """Metadata about the source material."""

    model_config = ConfigDict(frozen=True)

    title: str
    author: str | None = None
    publication_year: int | None = None
    genre: str | None = None
    era: str | None = None  # Historical period depicted
    language: str = "en"
    license: str | None = None
    source_url: str | None = None
    word_count: int = 0


class Story(BaseModel):
    """Root entity representing a complete narrative."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: generate_id("story"))
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

    # Raw content
    raw_text: str = ""

    def summary(self) -> dict:
        """Return summary for logging."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "scenes": self.total_scenes,
        }
