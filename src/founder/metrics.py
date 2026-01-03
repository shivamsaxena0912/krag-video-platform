"""Time-to-value metrics for founder validation.

This module tracks the metrics that matter for pitching and pricing:
- time_to_first_cut: How fast can we deliver something?
- time_to_approved_cut: How fast can we get to "yes"?
- number_of_iterations: How much back-and-forth?

These metrics drive the value proposition.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.logging import get_logger
from src.founder.scenario import FounderScenario
from src.founder.feedback import FounderFeedbackLevel

logger = get_logger(__name__)


@dataclass
class TimeToValueMetrics:
    """Metrics tracking time-to-value for a single run.

    These are the numbers that matter for founders and for pricing.
    """

    # Timestamps
    run_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    first_cut_at: datetime | None = None
    approved_at: datetime | None = None

    # Iteration tracking
    iterations: list[dict[str, Any]] = field(default_factory=list)
    current_version: int = 0

    # Computed metrics (in seconds)
    @property
    def time_to_first_cut_seconds(self) -> float | None:
        """Time from start to first cut, in seconds."""
        if self.first_cut_at is None:
            return None
        delta = self.first_cut_at - self.run_started_at
        return delta.total_seconds()

    @property
    def time_to_approved_cut_seconds(self) -> float | None:
        """Time from start to approval, in seconds."""
        if self.approved_at is None:
            return None
        delta = self.approved_at - self.run_started_at
        return delta.total_seconds()

    @property
    def number_of_iterations(self) -> int:
        """Total number of iterations."""
        return len(self.iterations)

    def record_first_cut(self) -> None:
        """Record when the first cut was delivered."""
        self.first_cut_at = datetime.now(timezone.utc)
        self.current_version = 1
        self.iterations.append({
            "version": 1,
            "timestamp": self.first_cut_at.isoformat(),
            "type": "first_cut",
            "feedback": None,
        })
        logger.info(
            "first_cut_delivered",
            time_seconds=self.time_to_first_cut_seconds,
        )

    def record_iteration(
        self,
        feedback_level: FounderFeedbackLevel,
        changes_made: list[str],
    ) -> None:
        """Record an iteration based on founder feedback."""
        now = datetime.now(timezone.utc)
        self.current_version += 1

        self.iterations.append({
            "version": self.current_version,
            "timestamp": now.isoformat(),
            "type": "revision",
            "feedback_level": feedback_level.value,
            "changes_made": changes_made,
        })

        if feedback_level == FounderFeedbackLevel.APPROVE:
            self.approved_at = now
            logger.info(
                "cut_approved",
                version=self.current_version,
                total_iterations=self.number_of_iterations,
                time_to_approved_seconds=self.time_to_approved_cut_seconds,
            )
        else:
            logger.info(
                "revision_requested",
                version=self.current_version,
                feedback_level=feedback_level.value,
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_started_at": self.run_started_at.isoformat(),
            "first_cut_at": self.first_cut_at.isoformat() if self.first_cut_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "time_to_first_cut_seconds": self.time_to_first_cut_seconds,
            "time_to_approved_cut_seconds": self.time_to_approved_cut_seconds,
            "number_of_iterations": self.number_of_iterations,
            "current_version": self.current_version,
            "iterations": self.iterations,
        }


@dataclass
class RunReport:
    """Complete run report for a founder session.

    This is what we show at the end and use for pitch/pricing.
    """

    # Identity
    run_id: str
    scenario: FounderScenario

    # Metrics
    metrics: TimeToValueMetrics

    # Outcomes
    final_status: str  # "approved", "pending", "abandoned"
    final_duration_seconds: float = 0.0
    final_shot_count: int = 0

    # Cost tracking
    total_cost_dollars: float = 0.0

    # Paths
    output_dir: Path | None = None
    review_pack_path: Path | None = None

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            "=" * 60,
            "📊 RUN REPORT",
            "=" * 60,
            "",
            f"Scenario: {self.scenario.scenario_name}",
            f"Run ID: {self.run_id}",
            f"Status: {self.final_status.upper()}",
            "",
            "--- TIME TO VALUE ---",
        ]

        if self.metrics.time_to_first_cut_seconds is not None:
            ttfc = self.metrics.time_to_first_cut_seconds
            if ttfc < 60:
                ttfc_str = f"{ttfc:.1f} seconds"
            else:
                ttfc_str = f"{ttfc / 60:.1f} minutes"
            lines.append(f"Time to first cut: {ttfc_str}")
        else:
            lines.append("Time to first cut: N/A")

        if self.metrics.time_to_approved_cut_seconds is not None:
            ttac = self.metrics.time_to_approved_cut_seconds
            if ttac < 60:
                ttac_str = f"{ttac:.1f} seconds"
            else:
                ttac_str = f"{ttac / 60:.1f} minutes"
            lines.append(f"Time to approved cut: {ttac_str}")
        else:
            lines.append("Time to approved cut: N/A (not yet approved)")

        lines.extend([
            f"Number of iterations: {self.metrics.number_of_iterations}",
            "",
            "--- FINAL OUTPUT ---",
            f"Duration: {self.final_duration_seconds:.1f}s",
            f"Shots: {self.final_shot_count}",
            f"Cost: ${self.total_cost_dollars:.2f}",
            "",
            "--- ITERATION HISTORY ---",
        ])

        for it in self.metrics.iterations:
            version = it["version"]
            it_type = it["type"]
            feedback = it.get("feedback_level", "-")
            lines.append(f"  v{version}: {it_type} | feedback: {feedback}")

        lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(lines)

    def save(self, path: Path | None = None) -> Path:
        """Save the run report to a file."""
        if path is None:
            if self.output_dir is None:
                raise ValueError("No output path specified")
            path = self.output_dir / "run_report.json"

        data = {
            "run_id": self.run_id,
            "scenario_id": self.scenario.scenario_id,
            "scenario_name": self.scenario.scenario_name,
            "final_status": self.final_status,
            "final_duration_seconds": self.final_duration_seconds,
            "final_shot_count": self.final_shot_count,
            "total_cost_dollars": self.total_cost_dollars,
            "metrics": self.metrics.to_dict(),
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        # Also save human-readable summary
        summary_path = path.parent / "run_report.txt"
        with open(summary_path, "w") as f:
            f.write(self.summary())

        logger.info("run_report_saved", path=str(path))
        return path


def create_run_report(
    run_id: str,
    scenario: FounderScenario,
    metrics: TimeToValueMetrics,
    final_duration_seconds: float = 0.0,
    final_shot_count: int = 0,
    total_cost_dollars: float = 0.0,
    output_dir: Path | None = None,
) -> RunReport:
    """Create a run report from collected metrics."""
    # Determine final status
    if metrics.approved_at is not None:
        final_status = "approved"
    elif metrics.number_of_iterations > 0:
        final_status = "pending"
    else:
        final_status = "not_started"

    return RunReport(
        run_id=run_id,
        scenario=scenario,
        metrics=metrics,
        final_status=final_status,
        final_duration_seconds=final_duration_seconds,
        final_shot_count=final_shot_count,
        total_cost_dollars=total_cost_dollars,
        output_dir=output_dir,
    )
