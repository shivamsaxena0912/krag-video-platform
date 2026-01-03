"""Batch report generation for validation results.

This module generates batch_report.md summarizing:
- Approval rate
- Common feedback flags
- Time-to-value statistics
- Where defaults fail repeatedly
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.logging import get_logger
from src.validation.batch import BatchResult, ScenarioResult

logger = get_logger(__name__)


@dataclass
class BatchStatistics:
    """Computed statistics from a batch run."""

    # Overall
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0

    # SLA
    sla_pass_rate: float = 0.0
    sla_violation_rate: float = 0.0

    # Time to value
    avg_time_to_first_cut: float = 0.0
    min_time_to_first_cut: float = 0.0
    max_time_to_first_cut: float = 0.0
    avg_iterations: float = 0.0

    # Output quality
    avg_duration: float = 0.0
    avg_shot_count: float = 0.0

    # Common issues
    top_sla_violations: list[tuple[str, int, float]] = field(default_factory=list)
    top_feedback_flags: list[tuple[str, int, float]] = field(default_factory=list)

    # Per-scenario breakdown
    scenario_stats: dict[str, dict[str, Any]] = field(default_factory=dict)


def compute_statistics(result: BatchResult) -> BatchStatistics:
    """Compute detailed statistics from batch results."""
    stats = BatchStatistics()

    if not result.results:
        return stats

    # Overall counts
    stats.total_runs = result.total_runs
    stats.successful_runs = result.successful_runs
    stats.failed_runs = result.failed_runs
    stats.success_rate = result.successful_runs / result.total_runs if result.total_runs > 0 else 0.0

    # SLA rates
    sla_passed = sum(1 for r in result.results if r.sla_passed)
    stats.sla_pass_rate = sla_passed / result.total_runs if result.total_runs > 0 else 0.0
    stats.sla_violation_rate = 1.0 - stats.sla_pass_rate

    # Time to value
    ttfc_values = [r.time_to_first_cut_seconds for r in result.results if r.time_to_first_cut_seconds]
    if ttfc_values:
        stats.avg_time_to_first_cut = sum(ttfc_values) / len(ttfc_values)
        stats.min_time_to_first_cut = min(ttfc_values)
        stats.max_time_to_first_cut = max(ttfc_values)

    iterations = [r.iterations for r in result.results if r.iterations > 0]
    if iterations:
        stats.avg_iterations = sum(iterations) / len(iterations)

    # Output quality
    durations = [r.duration_seconds for r in result.results if r.duration_seconds > 0]
    if durations:
        stats.avg_duration = sum(durations) / len(durations)

    shots = [r.shot_count for r in result.results if r.shot_count > 0]
    if shots:
        stats.avg_shot_count = sum(shots) / len(shots)

    # Top violations
    total = result.total_runs
    stats.top_sla_violations = [
        (violation, count, count / total)
        for violation, count in sorted(
            result.common_sla_violations.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
    ]

    stats.top_feedback_flags = [
        (flag, count, count / total)
        for flag, count in sorted(
            result.common_feedback_flags.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
    ]

    # Per-scenario breakdown
    scenario_results: dict[str, list[ScenarioResult]] = {}
    for r in result.results:
        if r.scenario_id not in scenario_results:
            scenario_results[r.scenario_id] = []
        scenario_results[r.scenario_id].append(r)

    for scenario_id, results in scenario_results.items():
        runs = len(results)
        successes = sum(1 for r in results if r.success)
        sla_passes = sum(1 for r in results if r.sla_passed)
        ttfc_list = [r.time_to_first_cut_seconds for r in results if r.time_to_first_cut_seconds]

        stats.scenario_stats[scenario_id] = {
            "runs": runs,
            "success_rate": successes / runs if runs > 0 else 0.0,
            "sla_pass_rate": sla_passes / runs if runs > 0 else 0.0,
            "avg_time_to_first_cut": sum(ttfc_list) / len(ttfc_list) if ttfc_list else 0.0,
            "violations": list(set(v for r in results for v in r.sla_violations)),
        }

    return stats


def generate_batch_report(
    result: BatchResult,
    output_path: Path | str | None = None,
) -> str:
    """Generate a markdown batch report.

    Args:
        result: The batch result to report on.
        output_path: Optional path to save the report.

    Returns:
        The markdown report as a string.
    """
    stats = compute_statistics(result)

    lines = [
        "# Batch Validation Report",
        "",
        f"**Batch ID:** {result.batch_id}",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Runs | {stats.total_runs} |",
        f"| Success Rate | {stats.success_rate:.0%} |",
        f"| SLA Pass Rate | {stats.sla_pass_rate:.0%} |",
        f"| Avg Time to First Cut | {stats.avg_time_to_first_cut:.1f}s |",
        f"| Avg Iterations | {stats.avg_iterations:.1f} |",
        "",
    ]

    # Health indicator
    if stats.sla_pass_rate >= 0.9:
        lines.append("**Status:** ✅ Healthy - defaults working well")
    elif stats.sla_pass_rate >= 0.7:
        lines.append("**Status:** ⚠️ Attention Needed - some scenarios failing")
    else:
        lines.append("**Status:** ❌ Critical - defaults need adjustment")

    lines.extend([
        "",
        "---",
        "",
        "## Time to Value",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Average | {stats.avg_time_to_first_cut:.1f}s |",
        f"| Minimum | {stats.min_time_to_first_cut:.1f}s |",
        f"| Maximum | {stats.max_time_to_first_cut:.1f}s |",
        f"| Avg Iterations | {stats.avg_iterations:.1f} |",
        "",
    ])

    # Common failures
    if stats.top_sla_violations:
        lines.extend([
            "---",
            "",
            "## Where Defaults Fail",
            "",
            "These SLA violations occur repeatedly and indicate where defaults need adjustment:",
            "",
            "| Violation | Count | Rate |",
            "|-----------|-------|------|",
        ])
        for violation, count, rate in stats.top_sla_violations:
            lines.append(f"| `{violation}` | {count} | {rate:.0%} |")

        lines.extend([
            "",
            "### Recommended Adjustments",
            "",
        ])

        for violation, count, rate in stats.top_sla_violations:
            if rate >= 0.5:
                if violation == "duration_exceeded":
                    lines.append(
                        "- **Duration Exceeded:** Increase trimming aggressiveness or reduce target duration"
                    )
                elif violation == "shot_count_exceeded":
                    lines.append(
                        "- **Shot Count Exceeded:** Reduce shots per scene or increase consolidation"
                    )
                elif violation == "iteration_exceeded":
                    lines.append(
                        "- **Iteration Exceeded:** Improve first-cut quality or relax iteration limits"
                    )

        lines.append("")

    # Common feedback flags
    if stats.top_feedback_flags:
        lines.extend([
            "---",
            "",
            "## Common Feedback Flags",
            "",
            "| Flag | Count | Rate |",
            "|------|-------|------|",
        ])
        for flag, count, rate in stats.top_feedback_flags:
            lines.append(f"| `{flag}` | {count} | {rate:.0%} |")
        lines.append("")

    # Per-scenario breakdown
    lines.extend([
        "---",
        "",
        "## Scenario Breakdown",
        "",
        "| Scenario | Runs | Success | SLA Pass | Avg TTFC |",
        "|----------|------|---------|----------|----------|",
    ])

    for scenario_id, s in stats.scenario_stats.items():
        status = "✅" if s["sla_pass_rate"] >= 0.8 else "⚠️" if s["sla_pass_rate"] >= 0.5 else "❌"
        lines.append(
            f"| {scenario_id} | {s['runs']} | {s['success_rate']:.0%} | "
            f"{status} {s['sla_pass_rate']:.0%} | {s['avg_time_to_first_cut']:.1f}s |"
        )

    lines.append("")

    # Detailed failures by scenario
    failing_scenarios = [
        (sid, s) for sid, s in stats.scenario_stats.items()
        if s["sla_pass_rate"] < 0.8
    ]

    if failing_scenarios:
        lines.extend([
            "### Failing Scenarios Detail",
            "",
        ])
        for scenario_id, s in failing_scenarios:
            lines.extend([
                f"#### {scenario_id}",
                "",
                f"- SLA Pass Rate: {s['sla_pass_rate']:.0%}",
                f"- Violations: {', '.join(s['violations']) if s['violations'] else 'None'}",
                "",
            ])

    # Recommendations
    lines.extend([
        "---",
        "",
        "## Recommendations",
        "",
    ])

    recommendations = []

    if stats.sla_pass_rate < 0.8:
        recommendations.append(
            "1. **Tighten editorial trimming:** Current defaults produce content that's too long for platform constraints."
        )

    if stats.avg_time_to_first_cut > 30:
        recommendations.append(
            "2. **Optimize pipeline:** First cut taking >30s may indicate processing bottlenecks."
        )

    if any("duration_exceeded" in v for v, _, _ in stats.top_sla_violations):
        recommendations.append(
            "3. **Reduce target duration:** Story content may be too long for selected intents."
        )

    if not recommendations:
        recommendations.append(
            "- No critical issues detected. Continue monitoring."
        )

    lines.extend(recommendations)

    lines.extend([
        "",
        "---",
        "",
        f"*Report generated from {stats.total_runs} runs across {len(stats.scenario_stats)} scenarios.*",
    ])

    report = "\n".join(lines)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(report)
        logger.info("batch_report_generated", path=str(path))

    return report
