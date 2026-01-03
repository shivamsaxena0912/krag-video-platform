"""Playbook data structures and persistence.

A Playbook is a versioned collection of expert feedback patterns
that can be applied automatically to subsequent runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib

from src.common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PlaybookEntry:
    """A single entry in a playbook.

    Each entry represents a learned pattern from expert feedback
    that should be applied automatically.
    """

    # Identity
    entry_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Trigger conditions (when to apply)
    trigger_scenario: str | None = None  # Apply only to this scenario
    trigger_intent: str | None = None    # Apply only to this intent
    trigger_condition: str | None = None # Free-form condition description

    # Bias adjustments (what to apply)
    pacing_adjustment: float = 0.0       # -0.5 to +0.5 adjustment
    trimming_adjustment: float = 0.0     # -0.1 to +0.1 adjustment
    hook_strength_adjustment: float = 0.0  # -0.3 to +0.3 adjustment

    # Constraints (hard rules)
    max_duration_override: float | None = None
    min_duration_override: float | None = None
    max_shots_override: int | None = None

    # Director constraints (from feedback)
    director_constraints: list[str] = field(default_factory=list)

    # Source tracking
    source_feedback_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5  # 0.0 to 1.0, based on feedback frequency

    # Description
    description: str = ""
    rationale: str = ""

    def matches(
        self,
        scenario_id: str | None = None,
        intent: str | None = None,
    ) -> bool:
        """Check if this entry matches the given context."""
        if self.trigger_scenario and self.trigger_scenario != scenario_id:
            return False
        if self.trigger_intent and self.trigger_intent != intent:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "created_at": self.created_at.isoformat(),
            "trigger_scenario": self.trigger_scenario,
            "trigger_intent": self.trigger_intent,
            "trigger_condition": self.trigger_condition,
            "pacing_adjustment": self.pacing_adjustment,
            "trimming_adjustment": self.trimming_adjustment,
            "hook_strength_adjustment": self.hook_strength_adjustment,
            "max_duration_override": self.max_duration_override,
            "min_duration_override": self.min_duration_override,
            "max_shots_override": self.max_shots_override,
            "director_constraints": self.director_constraints,
            "source_feedback_ids": self.source_feedback_ids,
            "confidence": self.confidence,
            "description": self.description,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlaybookEntry":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now(timezone.utc)

        return cls(
            entry_id=data["entry_id"],
            created_at=created_at,
            trigger_scenario=data.get("trigger_scenario"),
            trigger_intent=data.get("trigger_intent"),
            trigger_condition=data.get("trigger_condition"),
            pacing_adjustment=data.get("pacing_adjustment", 0.0),
            trimming_adjustment=data.get("trimming_adjustment", 0.0),
            hook_strength_adjustment=data.get("hook_strength_adjustment", 0.0),
            max_duration_override=data.get("max_duration_override"),
            min_duration_override=data.get("min_duration_override"),
            max_shots_override=data.get("max_shots_override"),
            director_constraints=data.get("director_constraints", []),
            source_feedback_ids=data.get("source_feedback_ids", []),
            confidence=data.get("confidence", 0.5),
            description=data.get("description", ""),
            rationale=data.get("rationale", ""),
        )


@dataclass
class PlaybookVersion:
    """Version metadata for a playbook."""

    version: int
    created_at: datetime
    description: str
    entry_count: int
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "entry_count": self.entry_count,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlaybookVersion":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now(timezone.utc)

        return cls(
            version=data["version"],
            created_at=created_at,
            description=data.get("description", ""),
            entry_count=data.get("entry_count", 0),
            content_hash=data.get("content_hash", ""),
        )


@dataclass
class Playbook:
    """A versioned collection of expert feedback patterns."""

    # Identity
    playbook_id: str
    name: str
    description: str = ""

    # Entries
    entries: list[PlaybookEntry] = field(default_factory=list)

    # Versioning
    current_version: int = 1
    versions: list[PlaybookVersion] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_entry(self, entry: PlaybookEntry) -> None:
        """Add an entry to the playbook."""
        self.entries.append(entry)
        self.updated_at = datetime.now(timezone.utc)

    def remove_entry(self, entry_id: str) -> bool:
        """Remove an entry by ID."""
        for i, entry in enumerate(self.entries):
            if entry.entry_id == entry_id:
                self.entries.pop(i)
                self.updated_at = datetime.now(timezone.utc)
                return True
        return False

    def get_matching_entries(
        self,
        scenario_id: str | None = None,
        intent: str | None = None,
    ) -> list[PlaybookEntry]:
        """Get all entries that match the given context."""
        return [
            entry for entry in self.entries
            if entry.matches(scenario_id, intent)
        ]

    def create_version(self, description: str = "") -> PlaybookVersion:
        """Create a new version snapshot."""
        self.current_version += 1

        # Compute content hash
        content = json.dumps([e.to_dict() for e in self.entries], sort_keys=True)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]

        version = PlaybookVersion(
            version=self.current_version,
            created_at=datetime.now(timezone.utc),
            description=description,
            entry_count=len(self.entries),
            content_hash=content_hash,
        )

        self.versions.append(version)
        self.updated_at = datetime.now(timezone.utc)

        logger.info(
            "playbook_version_created",
            playbook_id=self.playbook_id,
            version=self.current_version,
            entries=len(self.entries),
        )

        return version

    def diff_from_version(self, from_version: int) -> dict[str, Any]:
        """Get diff from a previous version.

        Note: This is a simplified diff that shows current state.
        Full diff would require storing historical entries.
        """
        from_v = next(
            (v for v in self.versions if v.version == from_version),
            None
        )

        return {
            "from_version": from_version,
            "to_version": self.current_version,
            "from_entry_count": from_v.entry_count if from_v else 0,
            "to_entry_count": len(self.entries),
            "from_hash": from_v.content_hash if from_v else "",
            "to_hash": self._compute_hash(),
            "current_entries": [e.entry_id for e in self.entries],
        }

    def _compute_hash(self) -> str:
        """Compute content hash."""
        content = json.dumps([e.to_dict() for e in self.entries], sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "playbook_id": self.playbook_id,
            "name": self.name,
            "description": self.description,
            "entries": [e.to_dict() for e in self.entries],
            "current_version": self.current_version,
            "versions": [v.to_dict() for v in self.versions],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Playbook":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now(timezone.utc)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        else:
            updated_at = datetime.now(timezone.utc)

        return cls(
            playbook_id=data["playbook_id"],
            name=data["name"],
            description=data.get("description", ""),
            entries=[PlaybookEntry.from_dict(e) for e in data.get("entries", [])],
            current_version=data.get("current_version", 1),
            versions=[PlaybookVersion.from_dict(v) for v in data.get("versions", [])],
            created_at=created_at,
            updated_at=updated_at,
        )


def create_playbook(
    name: str,
    playbook_id: str | None = None,
    description: str = "",
) -> Playbook:
    """Create a new playbook."""
    if playbook_id is None:
        playbook_id = f"pb_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    playbook = Playbook(
        playbook_id=playbook_id,
        name=name,
        description=description,
    )

    # Create initial version
    playbook.create_version("Initial version")

    return playbook


def load_playbook(path: Path | str) -> Playbook:
    """Load a playbook from file."""
    path = Path(path)
    with open(path) as f:
        data = json.load(f)
    return Playbook.from_dict(data)


def save_playbook(playbook: Playbook, path: Path | str) -> None:
    """Save a playbook to file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(playbook.to_dict(), f, indent=2)
    logger.info("playbook_saved", path=str(path), version=playbook.current_version)
