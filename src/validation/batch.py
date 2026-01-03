"""Batch validation for running multiple founder scenarios.

This module provides tooling to run multiple scenarios in batch,
collecting statistics and identifying where defaults fail repeatedly.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable
import json

from src.common.logging import get_logger
from src.founder import (
    FounderScenario,
    SCENARIOS,
    TimeToValueMetrics,
    FounderFeedbackLevel,
)
from src.marketing import MarketingIntent, get_preset, validate_pipeline_sla, SLAReport

logger = get_logger(__name__)


@dataclass
class BatchConfig:
    """Configuration for batch validation runs."""

    # Scenarios to run
    scenarios: list[str] = field(default_factory=lambda: list(SCENARIOS.keys()))

    # Repeat each scenario N times for consistency testing
    runs_per_scenario: int = 1

    # Output
    output_dir: Path | None = None

    # Simulated feedback for testing iterations
    simulate_feedback: bool = False
    simulated_feedback_level: FounderFeedbackLevel = FounderFeedbackLevel.MINOR_CHANGES


@dataclass
class ScenarioResult:
    """Result of running a single scenario."""

    scenario_id: str
    scenario_name: str
    run_index: int

    # Success
    success: bool
    error: str | None = None

    # Metrics
    time_to_first_cut_seconds: float | None = None
    time_to_approved_cut_seconds: float | None = None
    iterations: int = 0

    # Output
    duration_seconds: float = 0.0
    shot_count: int = 0

    # SLA
    sla_passed: bool = True
    sla_violations: list[str] = field(default_factory=list)
    sla_warnings: list[str] = field(default_factory=list)

    # Feedback flags (if simulated)
    feedback_flags: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "run_index": self.run_index,
            "success": self.success,
            "error": self.error,
            "time_to_first_cut_seconds": self.time_to_first_cut_seconds,
            "time_to_approved_cut_seconds": self.time_to_approved_cut_seconds,
            "iterations": self.iterations,
            "duration_seconds": self.duration_seconds,
            "shot_count": self.shot_count,
            "sla_passed": self.sla_passed,
            "sla_violations": self.sla_violations,
            "sla_warnings": self.sla_warnings,
            "feedback_flags": self.feedback_flags,
        }


@dataclass
class BatchResult:
    """Result of a batch validation run."""

    # Identity
    batch_id: str
    started_at: datetime
    completed_at: datetime | None = None

    # Config
    config: BatchConfig = field(default_factory=BatchConfig)

    # Results
    results: list[ScenarioResult] = field(default_factory=list)

    # Aggregates (computed)
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    sla_pass_rate: float = 0.0

    # Common failures
    common_sla_violations: dict[str, int] = field(default_factory=dict)
    common_feedback_flags: dict[str, int] = field(default_factory=dict)

    def compute_aggregates(self) -> None:
        """Compute aggregate statistics."""
        self.total_runs = len(self.results)
        self.successful_runs = sum(1 for r in self.results if r.success)
        self.failed_runs = self.total_runs - self.successful_runs

        sla_passed = sum(1 for r in self.results if r.sla_passed)
        self.sla_pass_rate = sla_passed / self.total_runs if self.total_runs > 0 else 0.0

        # Count common violations
        for result in self.results:
            for violation in result.sla_violations:
                # Normalize violation message
                key = self._normalize_violation(violation)
                self.common_sla_violations[key] = self.common_sla_violations.get(key, 0) + 1

            for flag, value in result.feedback_flags.items():
                if value:
                    self.common_feedback_flags[flag] = self.common_feedback_flags.get(flag, 0) + 1

    def _normalize_violation(self, violation: str) -> str:
        """Normalize violation message for grouping."""
        # Remove specific numbers for grouping
        if "Duration" in violation and "exceeds" in violation:
            return "duration_exceeded"
        if "Shot count" in violation and "exceeds" in violation:
            return "shot_count_exceeded"
        if "Iteration" in violation:
            return "iteration_exceeded"
        if "Cost" in violation:
            return "cost_exceeded"
        return violation.lower().replace(" ", "_")[:30]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "batch_id": self.batch_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "sla_pass_rate": self.sla_pass_rate,
            "common_sla_violations": self.common_sla_violations,
            "common_feedback_flags": self.common_feedback_flags,
            "results": [r.to_dict() for r in self.results],
        }


# Type for the pipeline runner function
PipelineRunner = Callable[[FounderScenario, Path], Awaitable[tuple[
    bool,  # success
    float,  # duration_seconds
    int,  # shot_count
    TimeToValueMetrics,
    SLAReport,
    str | None,  # error
]]]


class BatchRunner:
    """Runs multiple founder scenarios in batch for consistency testing."""

    def __init__(self, config: BatchConfig):
        self.config = config

    async def run(
        self,
        pipeline_runner: PipelineRunner,
    ) -> BatchResult:
        """Run all configured scenarios.

        Args:
            pipeline_runner: Async function that runs a single scenario.
                Should return (success, duration, shots, metrics, sla_report, error).

        Returns:
            BatchResult with all scenario results.
        """
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = self.config.output_dir or Path(f"outputs/batch_{batch_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

        result = BatchResult(
            batch_id=batch_id,
            started_at=datetime.now(timezone.utc),
            config=self.config,
        )

        logger.info(
            "batch_started",
            batch_id=batch_id,
            scenarios=len(self.config.scenarios),
            runs_per_scenario=self.config.runs_per_scenario,
        )

        for scenario_id in self.config.scenarios:
            scenario = SCENARIOS.get(scenario_id)
            if not scenario:
                logger.warning("scenario_not_found", scenario_id=scenario_id)
                continue

            for run_idx in range(self.config.runs_per_scenario):
                scenario_result = await self._run_scenario(
                    scenario,
                    run_idx,
                    output_dir,
                    pipeline_runner,
                )
                result.results.append(scenario_result)

                logger.info(
                    "scenario_completed",
                    scenario_id=scenario_id,
                    run=run_idx + 1,
                    success=scenario_result.success,
                    sla_passed=scenario_result.sla_passed,
                )

        result.completed_at = datetime.now(timezone.utc)
        result.compute_aggregates()

        # Save batch result
        with open(output_dir / "batch_result.json", "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        logger.info(
            "batch_completed",
            batch_id=batch_id,
            total_runs=result.total_runs,
            successful=result.successful_runs,
            sla_pass_rate=f"{result.sla_pass_rate:.0%}",
        )

        return result

    async def _run_scenario(
        self,
        scenario: FounderScenario,
        run_idx: int,
        output_dir: Path,
        pipeline_runner: PipelineRunner,
    ) -> ScenarioResult:
        """Run a single scenario."""
        run_dir = output_dir / f"{scenario.scenario_id}_run{run_idx + 1}"
        run_dir.mkdir(parents=True, exist_ok=True)

        try:
            success, duration, shots, metrics, sla_report, error = await pipeline_runner(
                scenario, run_dir
            )

            return ScenarioResult(
                scenario_id=scenario.scenario_id,
                scenario_name=scenario.scenario_name,
                run_index=run_idx,
                success=success,
                error=error,
                time_to_first_cut_seconds=metrics.time_to_first_cut_seconds,
                time_to_approved_cut_seconds=metrics.time_to_approved_cut_seconds,
                iterations=metrics.number_of_iterations,
                duration_seconds=duration,
                shot_count=shots,
                sla_passed=sla_report.passed,
                sla_violations=[v.message for v in sla_report.violations],
                sla_warnings=[v.message for v in sla_report.warnings],
            )

        except Exception as e:
            logger.error(
                "scenario_failed",
                scenario_id=scenario.scenario_id,
                error=str(e),
            )
            return ScenarioResult(
                scenario_id=scenario.scenario_id,
                scenario_name=scenario.scenario_name,
                run_index=run_idx,
                success=False,
                error=str(e),
            )


async def run_batch(
    pipeline_runner: PipelineRunner,
    scenarios: list[str] | None = None,
    runs_per_scenario: int = 1,
    output_dir: Path | None = None,
) -> BatchResult:
    """Convenience function to run a batch validation.

    Args:
        pipeline_runner: Function that runs a single scenario.
        scenarios: List of scenario IDs to run (default: all).
        runs_per_scenario: Number of times to run each scenario.
        output_dir: Output directory for results.

    Returns:
        BatchResult with all scenario results.
    """
    config = BatchConfig(
        scenarios=scenarios or list(SCENARIOS.keys()),
        runs_per_scenario=runs_per_scenario,
        output_dir=output_dir,
    )

    runner = BatchRunner(config)
    return await runner.run(pipeline_runner)
