"""Base model class for all entities."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a given prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


class BaseEntity(BaseModel):
    """Base class for all domain entities."""

    model_config = ConfigDict(
        frozen=True,
        use_enum_values=True,
        validate_assignment=True,
        extra="forbid",
    )

    id: str = Field(default_factory=lambda: generate_id("entity"))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1)

    def summary(self) -> dict[str, Any]:
        """Return a summary dict for logging."""
        return {
            "id": self.id,
            "type": self.__class__.__name__,
        }

    def with_updated_at(self) -> "BaseEntity":
        """Return a copy with updated timestamp."""
        return self.model_copy(update={"updated_at": datetime.utcnow()})

    def with_version_bump(self) -> "BaseEntity":
        """Return a copy with incremented version."""
        return self.model_copy(
            update={
                "version": self.version + 1,
                "updated_at": datetime.utcnow(),
            }
        )
