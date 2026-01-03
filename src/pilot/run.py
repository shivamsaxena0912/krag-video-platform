"""Pilot run abstraction for founder engagements.

A PilotRun represents a real customer engagement, tracking
multiple video generation attempts and their outcomes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
import uuid

from src.common.logging import get_logger

logger = get_logger(__name__)


class PilotStatus(str, Enum):
    """Status of a pilot engagement."""

    ACTIVE = "active"
    """Pilot is ongoing, runs are being made."""

    PAUSED = "paused"
    """Pilot is temporarily paused (founder busy, etc.)."""

    COMPLETED = "completed"
    """Pilot has concluded (approved or dropped)."""


class ApprovalOutcome(str, Enum):
    """Outcome of founder approval."""

    PENDING = "pending"
    """Awaiting founder decision."""

    APPROVED = "approved"
    """Founder approved - video is ready to publish."""

    DROPPED = "dropped"
    """Founder decided not to proceed."""


@dataclass
class PilotRunAttempt:
    """A single video generation attempt within a pilot."""

    attempt_id: str
    attempt_number: int
    created_at: datetime

    # Outputs
    video_path: str | None = None
    review_pack_path: str | None = None

    # Metrics
    time_to_first_cut_seconds: float | None = None
    iteration_count: int = 0
    total_cost_dollars: float = 0.0

    # SLA
    sla_passed: bool = False
    sla_violations: list[str] = field(default_factory=list)

    # Founder feedback (if received)
    founder_feedback: str | None = None
    feedback_received_at: datetime | None = None
    feedback_level: str | None = None  # "approve", "minor_changes", "major_changes"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "created_at": self.created_at.isoformat(),
            "video_path": self.video_path,
            "review_pack_path": self.review_pack_path,
            "time_to_first_cut_seconds": self.time_to_first_cut_seconds,
            "iteration_count": self.iteration_count,
            "total_cost_dollars": self.total_cost_dollars,
            "sla_passed": self.sla_passed,
            "sla_violations": self.sla_violations,
            "founder_feedback": self.founder_feedback,
            "feedback_received_at": self.feedback_received_at.isoformat() if self.feedback_received_at else None,
            "feedback_level": self.feedback_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PilotRunAttempt":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now(timezone.utc)

        feedback_received_at = data.get("feedback_received_at")
        if isinstance(feedback_received_at, str):
            feedback_received_at = datetime.fromisoformat(feedback_received_at)

        return cls(
            attempt_id=data["attempt_id"],
            attempt_number=data["attempt_number"],
            created_at=created_at,
            video_path=data.get("video_path"),
            review_pack_path=data.get("review_pack_path"),
            time_to_first_cut_seconds=data.get("time_to_first_cut_seconds"),
            iteration_count=data.get("iteration_count", 0),
            total_cost_dollars=data.get("total_cost_dollars", 0.0),
            sla_passed=data.get("sla_passed", False),
            sla_violations=data.get("sla_violations", []),
            founder_feedback=data.get("founder_feedback"),
            feedback_received_at=feedback_received_at,
            feedback_level=data.get("feedback_level"),
        )


@dataclass
class PilotRun:
    """A pilot engagement with a founder.

    Represents a real customer engagement, potentially spanning
    multiple video generation attempts over days or weeks.
    """

    # Identity
    pilot_id: str
    founder_name: str
    company_name: str

    # Configuration
    scenario_type: str  # e.g., "feature_launch", "funding_announcement"
    brand_context: dict[str, Any] = field(default_factory=dict)
    playbook_version: str | None = None

    # Attempts
    runs: list[PilotRunAttempt] = field(default_factory=list)

    # Status
    status: PilotStatus = PilotStatus.ACTIVE
    approval_outcome: ApprovalOutcome = ApprovalOutcome.PENDING

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""

    # Constraints
    max_attempts: int = 5
    max_iterations_per_attempt: int = 3

    def add_attempt(
        self,
        video_path: str | None = None,
        review_pack_path: str | None = None,
        time_to_first_cut_seconds: float | None = None,
        iteration_count: int = 0,
        total_cost_dollars: float = 0.0,
        sla_passed: bool = False,
        sla_violations: list[str] | None = None,
    ) -> PilotRunAttempt:
        """Add a new attempt to this pilot."""
        attempt = PilotRunAttempt(
            attempt_id=f"attempt_{len(self.runs) + 1}_{uuid.uuid4().hex[:8]}",
            attempt_number=len(self.runs) + 1,
            created_at=datetime.now(timezone.utc),
            video_path=video_path,
            review_pack_path=review_pack_path,
            time_to_first_cut_seconds=time_to_first_cut_seconds,
            iteration_count=iteration_count,
            total_cost_dollars=total_cost_dollars,
            sla_passed=sla_passed,
            sla_violations=sla_violations or [],
        )
        self.runs.append(attempt)
        self.updated_at = datetime.now(timezone.utc)

        logger.info(
            "pilot_attempt_added",
            pilot_id=self.pilot_id,
            attempt_number=attempt.attempt_number,
            founder=self.founder_name,
        )

        return attempt

    def record_feedback(
        self,
        attempt_number: int,
        feedback: str,
        level: str,
    ) -> None:
        """Record founder feedback for an attempt."""
        for attempt in self.runs:
            if attempt.attempt_number == attempt_number:
                attempt.founder_feedback = feedback
                attempt.feedback_received_at = datetime.now(timezone.utc)
                attempt.feedback_level = level
                self.updated_at = datetime.now(timezone.utc)

                logger.info(
                    "pilot_feedback_recorded",
                    pilot_id=self.pilot_id,
                    attempt_number=attempt_number,
                    level=level,
                )
                return

        raise ValueError(f"Attempt {attempt_number} not found")

    def mark_approved(self) -> None:
        """Mark the pilot as approved."""
        self.approval_outcome = ApprovalOutcome.APPROVED
        self.status = PilotStatus.COMPLETED
        self.updated_at = datetime.now(timezone.utc)

        logger.info(
            "pilot_approved",
            pilot_id=self.pilot_id,
            founder=self.founder_name,
            attempts=len(self.runs),
        )

    def mark_dropped(self, reason: str = "") -> None:
        """Mark the pilot as dropped."""
        self.approval_outcome = ApprovalOutcome.DROPPED
        self.status = PilotStatus.COMPLETED
        if reason:
            self.notes = f"{self.notes}\nDropped: {reason}".strip()
        self.updated_at = datetime.now(timezone.utc)

        logger.info(
            "pilot_dropped",
            pilot_id=self.pilot_id,
            founder=self.founder_name,
            reason=reason,
        )

    def pause(self, reason: str = "") -> None:
        """Pause the pilot."""
        self.status = PilotStatus.PAUSED
        if reason:
            self.notes = f"{self.notes}\nPaused: {reason}".strip()
        self.updated_at = datetime.now(timezone.utc)

    def resume(self) -> None:
        """Resume a paused pilot."""
        if self.status == PilotStatus.PAUSED:
            self.status = PilotStatus.ACTIVE
            self.updated_at = datetime.now(timezone.utc)

    @property
    def attempt_count(self) -> int:
        """Number of attempts made."""
        return len(self.runs)

    @property
    def can_add_attempt(self) -> bool:
        """Whether more attempts are allowed."""
        return (
            self.status == PilotStatus.ACTIVE
            and self.attempt_count < self.max_attempts
        )

    @property
    def latest_attempt(self) -> PilotRunAttempt | None:
        """Get the most recent attempt."""
        return self.runs[-1] if self.runs else None

    @property
    def total_cost(self) -> float:
        """Total cost across all attempts."""
        return sum(r.total_cost_dollars for r in self.runs)

    @property
    def average_time_to_first_cut(self) -> float | None:
        """Average time to first cut across attempts."""
        times = [r.time_to_first_cut_seconds for r in self.runs if r.time_to_first_cut_seconds]
        return sum(times) / len(times) if times else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "pilot_id": self.pilot_id,
            "founder_name": self.founder_name,
            "company_name": self.company_name,
            "scenario_type": self.scenario_type,
            "brand_context": self.brand_context,
            "playbook_version": self.playbook_version,
            "runs": [r.to_dict() for r in self.runs],
            "status": self.status.value,
            "approval_outcome": self.approval_outcome.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "notes": self.notes,
            "max_attempts": self.max_attempts,
            "max_iterations_per_attempt": self.max_iterations_per_attempt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PilotRun":
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
            pilot_id=data["pilot_id"],
            founder_name=data["founder_name"],
            company_name=data["company_name"],
            scenario_type=data["scenario_type"],
            brand_context=data.get("brand_context", {}),
            playbook_version=data.get("playbook_version"),
            runs=[PilotRunAttempt.from_dict(r) for r in data.get("runs", [])],
            status=PilotStatus(data.get("status", "active")),
            approval_outcome=ApprovalOutcome(data.get("approval_outcome", "pending")),
            created_at=created_at,
            updated_at=updated_at,
            notes=data.get("notes", ""),
            max_attempts=data.get("max_attempts", 5),
            max_iterations_per_attempt=data.get("max_iterations_per_attempt", 3),
        )


def create_pilot(
    founder_name: str,
    company_name: str,
    scenario_type: str,
    brand_context: dict[str, Any] | None = None,
    playbook_version: str | None = None,
    max_attempts: int = 5,
    max_iterations_per_attempt: int = 3,
) -> PilotRun:
    """Create a new pilot run.

    Args:
        founder_name: Name of the founder.
        company_name: Name of the company.
        scenario_type: Type of scenario (e.g., "feature_launch").
        brand_context: Brand configuration dict.
        playbook_version: Version of playbook to use.
        max_attempts: Maximum video generation attempts.
        max_iterations_per_attempt: Max refinement iterations per attempt.

    Returns:
        New PilotRun instance.
    """
    pilot_id = f"pilot_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"

    pilot = PilotRun(
        pilot_id=pilot_id,
        founder_name=founder_name,
        company_name=company_name,
        scenario_type=scenario_type,
        brand_context=brand_context or {},
        playbook_version=playbook_version,
        max_attempts=max_attempts,
        max_iterations_per_attempt=max_iterations_per_attempt,
    )

    logger.info(
        "pilot_created",
        pilot_id=pilot_id,
        founder=founder_name,
        company=company_name,
        scenario=scenario_type,
    )

    return pilot


class PilotStore:
    """Persistent storage for pilot runs.

    Stores pilot metadata as JSON files in a directory.
    """

    def __init__(self, storage_dir: Path | str):
        """Initialize the store.

        Args:
            storage_dir: Directory to store pilot JSON files.
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _pilot_path(self, pilot_id: str) -> Path:
        """Get the path for a pilot's JSON file."""
        return self.storage_dir / f"{pilot_id}.json"

    def save(self, pilot: PilotRun) -> Path:
        """Save a pilot to disk.

        Args:
            pilot: The pilot to save.

        Returns:
            Path to the saved file.
        """
        path = self._pilot_path(pilot.pilot_id)
        with open(path, "w") as f:
            json.dump(pilot.to_dict(), f, indent=2)

        logger.debug("pilot_saved", pilot_id=pilot.pilot_id, path=str(path))
        return path

    def load(self, pilot_id: str) -> PilotRun | None:
        """Load a pilot from disk.

        Args:
            pilot_id: The pilot ID to load.

        Returns:
            PilotRun if found, None otherwise.
        """
        path = self._pilot_path(pilot_id)
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        return PilotRun.from_dict(data)

    def list_pilots(
        self,
        status: PilotStatus | None = None,
        founder_name: str | None = None,
    ) -> list[PilotRun]:
        """List all pilots, optionally filtered.

        Args:
            status: Filter by status.
            founder_name: Filter by founder name.

        Returns:
            List of matching pilots.
        """
        pilots = []
        for path in self.storage_dir.glob("pilot_*.json"):
            with open(path) as f:
                data = json.load(f)
            pilot = PilotRun.from_dict(data)

            # Apply filters
            if status and pilot.status != status:
                continue
            if founder_name and pilot.founder_name.lower() != founder_name.lower():
                continue

            pilots.append(pilot)

        # Sort by created_at descending (newest first)
        pilots.sort(key=lambda p: p.created_at, reverse=True)
        return pilots

    def get_active_pilots(self) -> list[PilotRun]:
        """Get all active pilots."""
        return self.list_pilots(status=PilotStatus.ACTIVE)

    def get_pilot_by_founder(self, founder_name: str) -> PilotRun | None:
        """Get the most recent pilot for a founder."""
        pilots = self.list_pilots(founder_name=founder_name)
        return pilots[0] if pilots else None
