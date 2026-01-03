"""Pilot outcome report generator.

Generates post-pilot analysis reports for internal use.
This is for us, not the founder.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from src.pilot.run import PilotRun, PilotStatus, ApprovalOutcome


class Recommendation(str, Enum):
    """Recommendation for proceeding with the product/process."""

    PROCEED = "proceed"
    """Pilot was successful, proceed with similar engagements."""

    REVISE = "revise"
    """Pilot had issues, revise approach before more pilots."""

    STOP = "stop"
    """Pilot failed significantly, stop and reassess."""


@dataclass
class PilotMetrics:
    """Computed metrics from a pilot."""

    total_attempts: int
    total_iterations: int
    total_cost_dollars: float

    average_time_to_first_cut_seconds: float | None
    average_iterations_per_attempt: float

    sla_pass_rate: float  # 0.0 to 1.0
    approval_rate: float  # 0.0 to 1.0 (for completed pilots)

    first_attempt_sla_passed: bool
    final_attempt_sla_passed: bool

    feedback_received_count: int
    feedback_themes: list[str]


def compute_pilot_metrics(pilot: PilotRun) -> PilotMetrics:
    """Compute metrics from a pilot run.

    Args:
        pilot: The pilot to analyze.

    Returns:
        Computed metrics.
    """
    if not pilot.runs:
        return PilotMetrics(
            total_attempts=0,
            total_iterations=0,
            total_cost_dollars=0.0,
            average_time_to_first_cut_seconds=None,
            average_iterations_per_attempt=0.0,
            sla_pass_rate=0.0,
            approval_rate=0.0,
            first_attempt_sla_passed=False,
            final_attempt_sla_passed=False,
            feedback_received_count=0,
            feedback_themes=[],
        )

    # Basic counts
    total_attempts = len(pilot.runs)
    total_iterations = sum(r.iteration_count for r in pilot.runs)
    total_cost = sum(r.total_cost_dollars for r in pilot.runs)

    # Time to first cut
    ttfc_values = [r.time_to_first_cut_seconds for r in pilot.runs if r.time_to_first_cut_seconds]
    avg_ttfc = sum(ttfc_values) / len(ttfc_values) if ttfc_values else None

    # Average iterations
    avg_iterations = total_iterations / total_attempts if total_attempts > 0 else 0.0

    # SLA pass rate
    sla_passes = sum(1 for r in pilot.runs if r.sla_passed)
    sla_pass_rate = sla_passes / total_attempts if total_attempts > 0 else 0.0

    # Approval rate (1.0 if approved, 0.0 otherwise)
    approval_rate = 1.0 if pilot.approval_outcome == ApprovalOutcome.APPROVED else 0.0

    # First and final SLA status
    first_sla = pilot.runs[0].sla_passed if pilot.runs else False
    final_sla = pilot.runs[-1].sla_passed if pilot.runs else False

    # Feedback analysis
    feedback_received = sum(1 for r in pilot.runs if r.founder_feedback)

    # Extract themes from feedback
    themes = _extract_feedback_themes(pilot)

    return PilotMetrics(
        total_attempts=total_attempts,
        total_iterations=total_iterations,
        total_cost_dollars=total_cost,
        average_time_to_first_cut_seconds=avg_ttfc,
        average_iterations_per_attempt=avg_iterations,
        sla_pass_rate=sla_pass_rate,
        approval_rate=approval_rate,
        first_attempt_sla_passed=first_sla,
        final_attempt_sla_passed=final_sla,
        feedback_received_count=feedback_received,
        feedback_themes=themes,
    )


def _extract_feedback_themes(pilot: PilotRun) -> list[str]:
    """Extract common themes from founder feedback.

    Simple keyword-based extraction.
    """
    themes = []

    # Keywords to look for
    theme_keywords = {
        "too_long": ["too long", "shorten", "shorter", "cut down", "too slow"],
        "too_short": ["too short", "longer", "more detail", "expand"],
        "pacing": ["pacing", "pace", "fast", "slow", "rhythm"],
        "hook": ["hook", "opening", "start", "beginning", "grab"],
        "ending": ["ending", "end", "cta", "call to action", "conclusion"],
        "tone": ["tone", "voice", "feel", "vibe", "mood"],
        "message": ["message", "point", "key", "main", "unclear"],
        "brand": ["brand", "doesn't feel", "not us", "off-brand"],
    }

    # Collect all feedback text
    all_feedback = " ".join(
        r.founder_feedback.lower()
        for r in pilot.runs
        if r.founder_feedback
    )

    # Check for themes
    for theme, keywords in theme_keywords.items():
        for keyword in keywords:
            if keyword in all_feedback:
                themes.append(theme)
                break

    return themes


def determine_recommendation(
    pilot: PilotRun,
    metrics: PilotMetrics,
) -> Recommendation:
    """Determine recommendation based on pilot outcome.

    Args:
        pilot: The pilot run.
        metrics: Computed metrics.

    Returns:
        PROCEED, REVISE, or STOP recommendation.
    """
    # If approved, likely PROCEED
    if pilot.approval_outcome == ApprovalOutcome.APPROVED:
        # But check for warning signs
        if metrics.total_attempts > 3:
            return Recommendation.REVISE  # Took too many attempts
        if metrics.average_iterations_per_attempt > 2.5:
            return Recommendation.REVISE  # Too many iterations
        return Recommendation.PROCEED

    # If dropped, determine severity
    if pilot.approval_outcome == ApprovalOutcome.DROPPED:
        if metrics.total_attempts == 1:
            # Dropped immediately - major issue
            return Recommendation.STOP
        if metrics.feedback_received_count == 0:
            # No feedback received - engagement issue
            return Recommendation.REVISE
        # Some attempts made but ultimately dropped
        return Recommendation.REVISE

    # Still pending - can't determine
    return Recommendation.REVISE


def generate_pilot_outcome_report(
    pilot: PilotRun,
    output_path: Path | str | None = None,
) -> str:
    """Generate a pilot outcome report.

    This report is for internal use, not for the founder.
    It analyzes what happened and recommends next steps.

    Args:
        pilot: The completed (or in-progress) pilot.
        output_path: Optional path to write the report.

    Returns:
        The report content as markdown.
    """
    metrics = compute_pilot_metrics(pilot)
    recommendation = determine_recommendation(pilot, metrics)

    # Build report
    lines = [
        "# Pilot Outcome Report",
        "",
        f"**Pilot ID:** {pilot.pilot_id}",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Founder | {pilot.founder_name} |",
        f"| Company | {pilot.company_name} |",
        f"| Scenario | {pilot.scenario_type} |",
        f"| Status | {pilot.status.value.upper()} |",
        f"| Outcome | {pilot.approval_outcome.value.upper()} |",
        f"| **Recommendation** | **{recommendation.value.upper()}** |",
        "",
        "---",
        "",
        "## Metrics",
        "",
        "### Volume",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total video attempts | {metrics.total_attempts} |",
        f"| Total iterations | {metrics.total_iterations} |",
        f"| Avg iterations/attempt | {metrics.average_iterations_per_attempt:.1f} |",
        f"| Total cost | ${metrics.total_cost_dollars:.2f} |",
        "",
        "### Performance",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
    ]

    if metrics.average_time_to_first_cut_seconds:
        ttfc_formatted = f"{metrics.average_time_to_first_cut_seconds:.1f}s"
    else:
        ttfc_formatted = "N/A"

    lines.extend([
        f"| Avg time to first cut | {ttfc_formatted} |",
        f"| SLA pass rate | {metrics.sla_pass_rate:.0%} |",
        f"| First attempt SLA | {'PASS' if metrics.first_attempt_sla_passed else 'FAIL'} |",
        f"| Final attempt SLA | {'PASS' if metrics.final_attempt_sla_passed else 'FAIL'} |",
        "",
        "### Engagement",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Feedback received | {metrics.feedback_received_count} / {metrics.total_attempts} attempts |",
        f"| Approval rate | {metrics.approval_rate:.0%} |",
        "",
    ])

    # Feedback themes
    if metrics.feedback_themes:
        lines.extend([
            "---",
            "",
            "## Common Feedback Themes",
            "",
        ])
        for theme in metrics.feedback_themes:
            lines.append(f"- **{theme.replace('_', ' ').title()}**")
        lines.append("")

    # Attempt history
    if pilot.runs:
        lines.extend([
            "---",
            "",
            "## Attempt History",
            "",
            "| # | SLA | Iterations | Cost | Feedback Level |",
            "|---|-----|------------|------|----------------|",
        ])

        for run in pilot.runs:
            sla_status = "PASS" if run.sla_passed else "FAIL"
            feedback_level = run.feedback_level or "-"
            lines.append(
                f"| {run.attempt_number} | {sla_status} | {run.iteration_count} | "
                f"${run.total_cost_dollars:.2f} | {feedback_level} |"
            )

        lines.append("")

    # What improved
    if metrics.total_attempts > 1:
        lines.extend([
            "---",
            "",
            "## What Improved vs First Run",
            "",
        ])

        first = pilot.runs[0]
        last = pilot.runs[-1]

        improvements = []

        # SLA improvement
        if not first.sla_passed and last.sla_passed:
            improvements.append("SLA compliance achieved")

        # Iteration reduction
        if last.iteration_count < first.iteration_count:
            diff = first.iteration_count - last.iteration_count
            improvements.append(f"Reduced iterations by {diff}")

        # Feedback level improvement
        level_order = {"major_changes": 0, "minor_changes": 1, "approve": 2}
        if first.feedback_level and last.feedback_level:
            first_level = level_order.get(first.feedback_level, -1)
            last_level = level_order.get(last.feedback_level, -1)
            if last_level > first_level:
                improvements.append("Feedback level improved")

        if improvements:
            for imp in improvements:
                lines.append(f"- {imp}")
        else:
            lines.append("- No significant improvements observed")

        lines.append("")

    # Recommendation details
    lines.extend([
        "---",
        "",
        "## Recommendation Details",
        "",
    ])

    if recommendation == Recommendation.PROCEED:
        lines.extend([
            f"**{recommendation.value.upper()}**: This pilot was successful.",
            "",
            "Next steps:",
            "- Continue with similar founder engagements",
            "- Apply learnings to playbook",
            "- Track aggregate metrics across pilots",
        ])
    elif recommendation == Recommendation.REVISE:
        lines.extend([
            f"**{recommendation.value.upper()}**: This pilot had issues that need addressing.",
            "",
            "Before next pilot:",
            "- Review feedback themes and update playbook",
            "- Analyze why SLA violations occurred" if metrics.sla_pass_rate < 1.0 else "",
            "- Consider adjusting scenario defaults",
            "- Discuss with team what went wrong",
        ])
        # Remove empty lines
        lines = [l for l in lines if l]
    else:  # STOP
        lines.extend([
            f"**{recommendation.value.upper()}**: This pilot failed significantly.",
            "",
            "Critical issues to address:",
            "- Investigate root cause of failure",
            "- Do not run more pilots until issues are resolved",
            "- Consider if scenario type is viable",
            "- Review entire pipeline for this use case",
        ])

    lines.extend([
        "",
        "---",
        "",
        f"*Report generated automatically. Pilot ID: {pilot.pilot_id}*",
        "",
    ])

    content = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

    return content


def generate_multi_pilot_report(
    pilots: list[PilotRun],
    output_path: Path | str | None = None,
) -> str:
    """Generate an aggregate report across multiple pilots.

    Useful for understanding overall pilot program health.

    Args:
        pilots: List of pilots to analyze.
        output_path: Optional path to write the report.

    Returns:
        The report content as markdown.
    """
    if not pilots:
        return "# Multi-Pilot Report\n\nNo pilots to analyze."

    # Compute aggregate metrics
    total_pilots = len(pilots)
    completed = [p for p in pilots if p.status == PilotStatus.COMPLETED]
    approved = [p for p in pilots if p.approval_outcome == ApprovalOutcome.APPROVED]
    dropped = [p for p in pilots if p.approval_outcome == ApprovalOutcome.DROPPED]

    all_metrics = [compute_pilot_metrics(p) for p in pilots]

    total_attempts = sum(m.total_attempts for m in all_metrics)
    total_iterations = sum(m.total_iterations for m in all_metrics)
    total_cost = sum(m.total_cost_dollars for m in all_metrics)

    # Average time to first cut
    ttfc_values = [m.average_time_to_first_cut_seconds for m in all_metrics if m.average_time_to_first_cut_seconds]
    avg_ttfc = sum(ttfc_values) / len(ttfc_values) if ttfc_values else None

    # Feedback themes across all pilots
    all_themes: list[str] = []
    for m in all_metrics:
        all_themes.extend(m.feedback_themes)
    theme_counts = Counter(all_themes)

    # Recommendations
    recommendations = [determine_recommendation(p, m) for p, m in zip(pilots, all_metrics)]
    rec_counts = Counter(r.value for r in recommendations)

    lines = [
        "# Multi-Pilot Aggregate Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Pilots Analyzed:** {total_pilots}",
        "",
        "---",
        "",
        "## Overview",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total pilots | {total_pilots} |",
        f"| Completed | {len(completed)} |",
        f"| Approved | {len(approved)} ({len(approved)/total_pilots:.0%}) |",
        f"| Dropped | {len(dropped)} ({len(dropped)/total_pilots:.0%}) |",
        "",
        "---",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total video attempts | {total_attempts} |",
        f"| Avg attempts/pilot | {total_attempts/total_pilots:.1f} |",
        f"| Total iterations | {total_iterations} |",
        f"| Avg iterations/pilot | {total_iterations/total_pilots:.1f} |",
        f"| Total cost | ${total_cost:.2f} |",
        f"| Avg cost/pilot | ${total_cost/total_pilots:.2f} |",
    ]

    if avg_ttfc:
        lines.append(f"| Avg time to first cut | {avg_ttfc:.1f}s |")

    lines.extend([
        "",
        "---",
        "",
        "## Common Feedback Themes",
        "",
    ])

    if theme_counts:
        for theme, count in theme_counts.most_common(5):
            lines.append(f"- **{theme.replace('_', ' ').title()}**: {count} pilots")
    else:
        lines.append("- No common themes detected")

    lines.extend([
        "",
        "---",
        "",
        "## Recommendation Distribution",
        "",
    ])

    for rec in [Recommendation.PROCEED, Recommendation.REVISE, Recommendation.STOP]:
        count = rec_counts.get(rec.value, 0)
        lines.append(f"- **{rec.value.upper()}**: {count} pilots ({count/total_pilots:.0%})")

    lines.extend([
        "",
        "---",
        "",
        "## Pilot List",
        "",
        "| Pilot ID | Founder | Company | Outcome | Recommendation |",
        "|----------|---------|---------|---------|----------------|",
    ])

    for pilot, rec in zip(pilots, recommendations):
        lines.append(
            f"| {pilot.pilot_id} | {pilot.founder_name} | {pilot.company_name} | "
            f"{pilot.approval_outcome.value} | {rec.value} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "*Report generated automatically.*",
        "",
    ])

    content = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

    return content
