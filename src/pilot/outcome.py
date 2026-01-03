"""Pilot outcome report generator.

Generates post-pilot analysis reports for internal use.
This is for us, not the founder.

Key concepts:
- Founder Satisfaction: What the founder thinks (derived from feedback)
- System Health: What the system measured (SLA, iterations, cost)
- Outcome: The final recommendation considering both perspectives
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from src.pilot.run import (
    PilotRun,
    PilotStatus,
    ApprovalOutcome,
    FeedbackDecision,
    FEEDBACK_FLAGS,
)


# =============================================================================
# OUTCOME STATES
# =============================================================================

class Recommendation(str, Enum):
    """Final outcome recommendation.

    These states explicitly separate founder satisfaction from system concerns.
    """

    APPROVED_FOR_PUBLISH = "approved_for_publish"
    """Founder approved AND system health is good. Safe to publish."""

    APPROVED_WITH_RISK = "approved_with_risk"
    """Founder approved BUT system has concerns (SLA, cost, iterations).
    The video can be published, but we should investigate internally."""

    REVISE_REQUIRED = "revise_required"
    """Founder not satisfied OR repeated issues indicate process problems.
    Do not run more pilots until we revise our approach."""

    STOP_PILOT = "stop_pilot"
    """Fundamental misalignment or no convergence.
    Stop this pilot type entirely and reassess viability."""

    # Legacy aliases for backward compatibility
    PROCEED = "approved_for_publish"
    REVISE = "revise_required"
    STOP = "stop_pilot"


class FounderSatisfactionLevel(str, Enum):
    """Founder's satisfaction derived from feedback."""

    SATISFIED = "satisfied"
    """Founder approved the video."""

    CLOSE = "close"
    """Founder requested minor changes - almost there."""

    UNSATISFIED = "unsatisfied"
    """Founder requested major changes."""

    ABANDONED = "abandoned"
    """Founder dropped the pilot."""

    UNKNOWN = "unknown"
    """No feedback received or pilot ongoing."""


class SystemHealthLevel(str, Enum):
    """System health assessment based on operational metrics."""

    HEALTHY = "healthy"
    """All metrics within acceptable ranges."""

    CONCERNING = "concerning"
    """Some metrics outside ideal ranges but workable."""

    UNHEALTHY = "unhealthy"
    """Multiple metrics indicate systemic issues."""


# =============================================================================
# ASSESSMENT DATA CLASSES
# =============================================================================

@dataclass
class FounderSatisfaction:
    """Assessment of founder satisfaction from their perspective.

    This represents what the FOUNDER cares about:
    - Did the video meet their creative vision?
    - Does it represent their brand correctly?
    - Would they publish it?
    """

    level: FounderSatisfactionLevel
    latest_decision: FeedbackDecision | None
    approval_count: int
    major_changes_count: int
    minor_changes_count: int
    persistent_objections: list[str]
    resolved_objections: list[str]
    trajectory: str  # "improving", "stable", "declining", "unknown"

    @property
    def is_approved(self) -> bool:
        """Founder explicitly approved."""
        return self.level == FounderSatisfactionLevel.SATISFIED

    @property
    def has_concerns(self) -> bool:
        """Founder has ongoing concerns."""
        return len(self.persistent_objections) > 0


@dataclass
class SystemHealth:
    """Assessment of system health from operational perspective.

    This represents what the SYSTEM is worried about:
    - Did we meet SLA commitments?
    - Was the cost reasonable?
    - Did we converge efficiently?
    """

    level: SystemHealthLevel
    sla_pass_rate: float
    final_sla_passed: bool
    total_attempts: int
    total_iterations: int
    average_iterations_per_attempt: float
    total_cost_dollars: float
    concerns: list[str]  # Specific system concerns

    @property
    def is_healthy(self) -> bool:
        """System metrics are all acceptable."""
        return self.level == SystemHealthLevel.HEALTHY

    @property
    def has_sla_issues(self) -> bool:
        """SLA was not fully met."""
        return self.sla_pass_rate < 1.0 or not self.final_sla_passed


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

    # Enhanced feedback metrics
    feedback_decisions: list[FeedbackDecision | None] = field(default_factory=list)
    recurring_flags: dict[str, int] = field(default_factory=dict)  # flag -> count
    flags_resolved: list[str] = field(default_factory=list)  # Flags that appeared then disappeared
    flags_persistent: list[str] = field(default_factory=list)  # Flags that kept recurring
    major_changes_count: int = 0
    minor_changes_count: int = 0
    approve_count: int = 0


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
            feedback_decisions=[],
            recurring_flags={},
            flags_resolved=[],
            flags_persistent=[],
            major_changes_count=0,
            minor_changes_count=0,
            approve_count=0,
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

    # Feedback analysis - enhanced
    feedback_received = sum(1 for r in pilot.runs if r.has_feedback)

    # Extract themes from feedback (legacy method)
    themes = _extract_feedback_themes(pilot)

    # Collect feedback decisions
    feedback_decisions = [r.feedback_decision for r in pilot.runs]

    # Count decision types
    major_changes_count = sum(1 for d in feedback_decisions if d == FeedbackDecision.MAJOR_CHANGES)
    minor_changes_count = sum(1 for d in feedback_decisions if d == FeedbackDecision.MINOR_CHANGES)
    approve_count = sum(1 for d in feedback_decisions if d == FeedbackDecision.APPROVE)

    # Analyze flags across attempts
    recurring_flags, flags_resolved, flags_persistent = _analyze_feedback_flags(pilot)

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
        feedback_decisions=feedback_decisions,
        recurring_flags=recurring_flags,
        flags_resolved=flags_resolved,
        flags_persistent=flags_persistent,
        major_changes_count=major_changes_count,
        minor_changes_count=minor_changes_count,
        approve_count=approve_count,
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


def _analyze_feedback_flags(pilot: PilotRun) -> tuple[dict[str, int], list[str], list[str]]:
    """Analyze feedback flags across attempts.

    Returns:
        Tuple of (recurring_flags count, resolved flags, persistent flags).
    """
    # Count occurrences of each flag
    flag_counts: Counter[str] = Counter()
    flag_first_seen: dict[str, int] = {}
    flag_last_seen: dict[str, int] = {}

    for run in pilot.runs:
        for flag in run.feedback_flags:
            flag_counts[flag] += 1
            if flag not in flag_first_seen:
                flag_first_seen[flag] = run.attempt_number
            flag_last_seen[flag] = run.attempt_number

    recurring_flags = dict(flag_counts.most_common())

    # Identify resolved flags (appeared early, not in later attempts)
    flags_resolved = []
    flags_persistent = []

    if pilot.runs and len(pilot.runs) >= 2:
        final_attempt = pilot.runs[-1].attempt_number

        for flag, count in flag_counts.items():
            last_seen = flag_last_seen[flag]

            # If flag was last seen before the final attempt, it's resolved
            if last_seen < final_attempt:
                flags_resolved.append(flag)
            elif count >= 2:
                # If seen in multiple attempts including the last, it's persistent
                flags_persistent.append(flag)

    return recurring_flags, flags_resolved, flags_persistent


# =============================================================================
# ASSESSMENT FUNCTIONS
# =============================================================================

def assess_founder_satisfaction(
    pilot: PilotRun,
    metrics: PilotMetrics,
) -> FounderSatisfaction:
    """Assess founder satisfaction from their feedback.

    This answers: "Is the founder happy with what we delivered?"
    """
    # Get latest feedback decision
    latest_decision = None
    if pilot.runs and pilot.runs[-1].feedback_decision:
        latest_decision = pilot.runs[-1].feedback_decision

    # Determine satisfaction level
    if pilot.approval_outcome == ApprovalOutcome.DROPPED:
        level = FounderSatisfactionLevel.ABANDONED
    elif latest_decision == FeedbackDecision.APPROVE:
        level = FounderSatisfactionLevel.SATISFIED
    elif latest_decision == FeedbackDecision.MINOR_CHANGES:
        level = FounderSatisfactionLevel.CLOSE
    elif latest_decision == FeedbackDecision.MAJOR_CHANGES:
        level = FounderSatisfactionLevel.UNSATISFIED
    elif pilot.approval_outcome == ApprovalOutcome.APPROVED:
        level = FounderSatisfactionLevel.SATISFIED
    else:
        level = FounderSatisfactionLevel.UNKNOWN

    # Determine trajectory
    trajectory = _determine_feedback_trajectory(pilot)

    return FounderSatisfaction(
        level=level,
        latest_decision=latest_decision,
        approval_count=metrics.approve_count,
        major_changes_count=metrics.major_changes_count,
        minor_changes_count=metrics.minor_changes_count,
        persistent_objections=metrics.flags_persistent,
        resolved_objections=metrics.flags_resolved,
        trajectory=trajectory,
    )


def assess_system_health(
    pilot: PilotRun,
    metrics: PilotMetrics,
) -> SystemHealth:
    """Assess system health from operational metrics.

    This answers: "Did our system perform well operationally?"
    """
    concerns = []

    # Check SLA
    if metrics.sla_pass_rate < 1.0:
        concerns.append(f"SLA pass rate only {metrics.sla_pass_rate:.0%}")
    if not metrics.final_attempt_sla_passed:
        concerns.append("Final attempt failed SLA")

    # Check attempts
    if metrics.total_attempts > 3:
        concerns.append(f"Required {metrics.total_attempts} attempts (ideal: ≤3)")

    # Check iterations
    if metrics.average_iterations_per_attempt > 2.5:
        concerns.append(f"High iteration count ({metrics.average_iterations_per_attempt:.1f} avg)")

    # Check cost (example threshold - could be configurable)
    if metrics.total_cost_dollars > 10.0:
        concerns.append(f"High cost (${metrics.total_cost_dollars:.2f})")

    # Determine health level
    if len(concerns) == 0:
        level = SystemHealthLevel.HEALTHY
    elif len(concerns) <= 2:
        level = SystemHealthLevel.CONCERNING
    else:
        level = SystemHealthLevel.UNHEALTHY

    return SystemHealth(
        level=level,
        sla_pass_rate=metrics.sla_pass_rate,
        final_sla_passed=metrics.final_attempt_sla_passed,
        total_attempts=metrics.total_attempts,
        total_iterations=metrics.total_iterations,
        average_iterations_per_attempt=metrics.average_iterations_per_attempt,
        total_cost_dollars=metrics.total_cost_dollars,
        concerns=concerns,
    )


def _determine_feedback_trajectory(pilot: PilotRun) -> str:
    """Determine if feedback is improving, stable, or declining."""
    if len(pilot.runs) < 2:
        return "unknown"

    decision_values = {
        FeedbackDecision.MAJOR_CHANGES: 0,
        FeedbackDecision.MINOR_CHANGES: 1,
        FeedbackDecision.APPROVE: 2,
    }

    # Get decisions for runs that have feedback
    decisions = [
        decision_values.get(r.feedback_decision, -1)
        for r in pilot.runs
        if r.feedback_decision is not None
    ]

    if len(decisions) < 2:
        return "unknown"

    # Compare first half to second half
    mid = len(decisions) // 2
    first_half_avg = sum(decisions[:mid]) / mid if mid > 0 else 0
    second_half_avg = sum(decisions[mid:]) / (len(decisions) - mid)

    if second_half_avg > first_half_avg + 0.3:
        return "improving"
    elif second_half_avg < first_half_avg - 0.3:
        return "declining"
    else:
        return "stable"


def _generate_founder_safe_explanation(
    recommendation: Recommendation,
    founder_satisfaction: FounderSatisfaction,
    system_health: SystemHealth,
    metrics: PilotMetrics,
) -> list[str]:
    """Generate a simple, founder-safe explanation of the decision.

    This is one paragraph explaining the outcome in plain language,
    suitable for sharing with external stakeholders.
    """
    lines = [
        "### Founder-Safe Explanation",
        "",
    ]

    if recommendation == Recommendation.APPROVED_FOR_PUBLISH:
        explanation = (
            f"This pilot was a success. The founder reviewed the video and approved it for publication. "
            f"We delivered efficiently with {metrics.total_attempts} attempt(s), and all our quality "
            f"checks passed. The video is ready to publish."
        )
    elif recommendation == Recommendation.APPROVED_WITH_RISK:
        concerns_text = " and ".join(system_health.concerns[:2]) if system_health.concerns else "some operational metrics"
        explanation = (
            f"The founder approved the video and it's ready to publish. However, internally we noted "
            f"that {concerns_text} didn't meet our ideal targets. This doesn't affect the video quality "
            f"the founder sees, but we should review our process before similar pilots."
        )
    elif recommendation == Recommendation.REVISE_REQUIRED:
        if founder_satisfaction.major_changes_count >= 2:
            explanation = (
                f"After {metrics.total_attempts} attempts, we haven't fully aligned with what the founder wants. "
                f"We received 'major changes' feedback {founder_satisfaction.major_changes_count} times. "
                f"Before running similar pilots, we need to adjust our approach to better match founder expectations."
            )
        elif founder_satisfaction.level == FounderSatisfactionLevel.ABANDONED:
            explanation = (
                f"The founder decided not to continue with this pilot. We should understand their concerns "
                f"and adjust our approach before attempting similar engagements."
            )
        else:
            explanation = (
                f"This pilot is still in progress or needs more iteration. "
                f"We're working to address the founder's feedback and improve the output."
            )
    else:  # STOP_PILOT
        if founder_satisfaction.persistent_objections:
            issues = ", ".join(o.replace("_", " ") for o in founder_satisfaction.persistent_objections[:2])
            explanation = (
                f"This pilot encountered fundamental challenges. Despite {metrics.total_attempts} attempts, "
                f"we couldn't resolve issues around {issues}. This suggests this type of video may not be "
                f"a good fit for our current capabilities with this founder type."
            )
        else:
            explanation = (
                f"This pilot didn't work out. We encountered significant challenges that prevented us "
                f"from delivering what the founder needed. We recommend pausing similar pilots while we "
                f"investigate the root cause."
            )

    lines.append(f"> {explanation}")
    lines.append("")

    return lines


def _generate_founder_call_summary(
    pilot: PilotRun,
    metrics: PilotMetrics,
) -> list[str]:
    """Generate a 'What the founder would likely say on a call' section.

    This predicts how the founder would describe their experience
    if asked about the pilot on a call.
    """
    lines = [
        "---",
        "",
        "## What the Founder Would Likely Say on a Call",
        "",
    ]

    # Determine overall sentiment
    latest_decision = None
    if pilot.runs and pilot.runs[-1].feedback_decision:
        latest_decision = pilot.runs[-1].feedback_decision

    # Build the narrative
    if latest_decision == FeedbackDecision.APPROVE:
        lines.append(_get_approve_narrative(pilot, metrics))
    elif latest_decision == FeedbackDecision.MINOR_CHANGES:
        lines.append(_get_minor_changes_narrative(pilot, metrics))
    elif latest_decision == FeedbackDecision.MAJOR_CHANGES:
        lines.append(_get_major_changes_narrative(pilot, metrics))
    elif pilot.approval_outcome == ApprovalOutcome.DROPPED:
        lines.append(_get_dropped_narrative(pilot, metrics))
    else:
        lines.append(_get_ongoing_narrative(pilot, metrics))

    lines.append("")
    return lines


def _get_approve_narrative(pilot: PilotRun, metrics: PilotMetrics) -> str:
    """Generate narrative for approved pilots."""
    base = f"> \"Yeah, we got a good video out of this."

    if metrics.total_attempts == 1:
        base += " First try, actually. Pretty impressed.\""
    elif metrics.total_attempts == 2:
        base += " Took a couple of rounds but we got there.\""
    elif metrics.total_attempts <= 3:
        base += f" It took {metrics.total_attempts} attempts, but the final result works for us.\""
    else:
        base += f" Not gonna lie, took {metrics.total_attempts} attempts. But in the end, we got something we can use.\""

    return base


def _get_minor_changes_narrative(pilot: PilotRun, metrics: PilotMetrics) -> str:
    """Generate narrative for minor changes status."""
    base = "> \"We're close."

    if metrics.flags_persistent:
        top_issue = metrics.flags_persistent[0].replace("_", " ")
        base += f" Still have some {top_issue} issues to work out."
    elif metrics.recurring_flags:
        top_issue = list(metrics.recurring_flags.keys())[0].replace("_", " ")
        base += f" The {top_issue} thing keeps coming up, but it's getting better."

    base += " One more round should do it.\""
    return base


def _get_major_changes_narrative(pilot: PilotRun, metrics: PilotMetrics) -> str:
    """Generate narrative for major changes status."""
    if metrics.major_changes_count >= 2:
        base = "> \"We've been going back and forth on this."

        if metrics.flags_persistent:
            issues = ", ".join(f.replace("_", " ") for f in metrics.flags_persistent[:2])
            base += f" The {issues} keeps being a problem."
        base += " Starting to wonder if we need a different approach.\""
    else:
        base = "> \"This isn't quite what we're looking for."

        if metrics.recurring_flags:
            top_issue = list(metrics.recurring_flags.keys())[0].replace("_", " ")
            base += f" The main issue is {top_issue}."
        base += " Needs significant rework.\""

    return base


def _get_dropped_narrative(pilot: PilotRun, metrics: PilotMetrics) -> str:
    """Generate narrative for dropped pilots."""
    if metrics.total_attempts == 1:
        return "> \"It wasn't what we expected at all. We decided not to continue after the first video.\""

    if metrics.flags_persistent:
        issues = ", ".join(f.replace("_", " ") for f in metrics.flags_persistent[:2])
        return f"> \"We tried {metrics.total_attempts} times but kept running into the same {issues} issues. Had to walk away.\""

    return f"> \"After {metrics.total_attempts} attempts, we just couldn't get it right. Decided to put this on hold.\""


def _get_ongoing_narrative(pilot: PilotRun, metrics: PilotMetrics) -> str:
    """Generate narrative for ongoing pilots."""
    if metrics.total_attempts == 0:
        return "> \"We haven't seen anything yet. Still waiting for the first draft.\""

    if not metrics.feedback_received_count:
        return "> \"We got a video but haven't had time to review it yet.\""

    return f"> \"We're {metrics.total_attempts} videos in. Still working on it.\""


def determine_recommendation(
    pilot: PilotRun,
    metrics: PilotMetrics,
    founder_satisfaction: FounderSatisfaction | None = None,
    system_health: SystemHealth | None = None,
) -> Recommendation:
    """Determine recommendation based on pilot outcome.

    Decision matrix:
    - Founder APPROVE + System HEALTHY → APPROVED_FOR_PUBLISH
    - Founder APPROVE + System CONCERNING/UNHEALTHY → APPROVED_WITH_RISK
    - Repeated MAJOR_CHANGES (≥2) → REVISE_REQUIRED
    - No convergence after max attempts OR persistent flags → STOP_PILOT

    Args:
        pilot: The pilot run.
        metrics: Computed metrics.
        founder_satisfaction: Pre-computed satisfaction (optional, will compute if not provided).
        system_health: Pre-computed health (optional, will compute if not provided).

    Returns:
        One of: APPROVED_FOR_PUBLISH, APPROVED_WITH_RISK, REVISE_REQUIRED, STOP_PILOT
    """
    # Compute assessments if not provided
    if founder_satisfaction is None:
        founder_satisfaction = assess_founder_satisfaction(pilot, metrics)
    if system_health is None:
        system_health = assess_system_health(pilot, metrics)

    # =========================================================================
    # STOP_PILOT: Fundamental problems - don't continue this pilot type
    # =========================================================================

    # No convergence after max attempts
    if metrics.total_attempts >= pilot.max_attempts:
        if not founder_satisfaction.is_approved:
            return Recommendation.STOP_PILOT

    # Repeated MAJOR_CHANGES with same persistent issues = not converging
    if metrics.major_changes_count >= 2 and founder_satisfaction.persistent_objections:
        return Recommendation.STOP_PILOT

    # 3+ MAJOR_CHANGES = fundamental misalignment
    if metrics.major_changes_count >= 3:
        return Recommendation.STOP_PILOT

    # Dropped after first attempt = major misalignment
    if pilot.approval_outcome == ApprovalOutcome.DROPPED and metrics.total_attempts == 1:
        return Recommendation.STOP_PILOT

    # Dropped with persistent issues = we couldn't solve it
    if pilot.approval_outcome == ApprovalOutcome.DROPPED and founder_satisfaction.persistent_objections:
        return Recommendation.STOP_PILOT

    # =========================================================================
    # APPROVED_FOR_PUBLISH / APPROVED_WITH_RISK: Founder approved
    # =========================================================================

    if founder_satisfaction.is_approved:
        # Founder is happy - but check system health
        if system_health.is_healthy:
            return Recommendation.APPROVED_FOR_PUBLISH
        else:
            # Founder approved but system has concerns
            return Recommendation.APPROVED_WITH_RISK

    # =========================================================================
    # REVISE_REQUIRED: Process needs adjustment
    # =========================================================================

    # Repeated MAJOR_CHANGES (even without persistent flags)
    if metrics.major_changes_count >= 2:
        return Recommendation.REVISE_REQUIRED

    # Dropped but not immediately (founder tried but gave up)
    if pilot.approval_outcome == ApprovalOutcome.DROPPED:
        return Recommendation.REVISE_REQUIRED

    # Declining trajectory
    if founder_satisfaction.trajectory == "declining":
        return Recommendation.REVISE_REQUIRED

    # Default: still working, but not ideal
    return Recommendation.REVISE_REQUIRED


def _get_recommendation_reasoning(
    recommendation: Recommendation,
    founder_satisfaction: FounderSatisfaction,
    system_health: SystemHealth,
) -> str:
    """Generate human-readable reasoning for the recommendation."""

    if recommendation == Recommendation.APPROVED_FOR_PUBLISH:
        return (
            "The founder approved the video AND our system metrics are healthy. "
            "This pilot succeeded on both fronts - the founder got what they wanted, "
            "and we delivered it efficiently."
        )

    elif recommendation == Recommendation.APPROVED_WITH_RISK:
        concerns = ", ".join(system_health.concerns[:2]) if system_health.concerns else "operational issues"
        return (
            f"The founder approved the video, but our system flagged concerns: {concerns}. "
            "The video can be published, but we should investigate why we had these issues "
            "before running similar pilots."
        )

    elif recommendation == Recommendation.REVISE_REQUIRED:
        if founder_satisfaction.major_changes_count >= 2:
            return (
                f"We received MAJOR_CHANGES feedback {founder_satisfaction.major_changes_count} times. "
                "This indicates a pattern - our approach isn't meeting founder expectations. "
                "Revise the playbook before running more pilots."
            )
        elif founder_satisfaction.level == FounderSatisfactionLevel.ABANDONED:
            return (
                "The founder dropped the pilot. We need to understand why and adjust "
                "our approach before attempting similar engagements."
            )
        else:
            return (
                "The pilot hasn't reached a successful conclusion. "
                "Review feedback patterns and adjust approach."
            )

    else:  # STOP_PILOT
        if founder_satisfaction.persistent_objections:
            issues = ", ".join(o.replace("_", " ") for o in founder_satisfaction.persistent_objections[:2])
            return (
                f"Persistent issues ({issues}) were never resolved despite multiple attempts. "
                "This suggests a fundamental mismatch between what we can deliver and what "
                "this founder type needs. Stop this pilot category and reassess viability."
            )
        else:
            return (
                "This pilot failed significantly - either due to immediate misalignment, "
                "repeated rejection, or inability to converge. Do not run similar pilots "
                "until the root cause is identified and addressed."
            )


def generate_pilot_outcome_report(
    pilot: PilotRun,
    output_path: Path | str | None = None,
) -> str:
    """Generate a pilot outcome report.

    This report is for internal use, not for the founder.
    It separates founder satisfaction from system health concerns.

    Args:
        pilot: The completed (or in-progress) pilot.
        output_path: Optional path to write the report.

    Returns:
        The report content as markdown.
    """
    metrics = compute_pilot_metrics(pilot)
    founder_satisfaction = assess_founder_satisfaction(pilot, metrics)
    system_health = assess_system_health(pilot, metrics)
    recommendation = determine_recommendation(pilot, metrics, founder_satisfaction, system_health)
    reasoning = _get_recommendation_reasoning(recommendation, founder_satisfaction, system_health)

    # Format recommendation for display
    rec_display = recommendation.value.upper().replace("_", " ")

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
        "",
        f"### Final Recommendation: **{rec_display}**",
        "",
    ]

    # Add founder-safe explanation right at the top
    lines.extend(_generate_founder_safe_explanation(recommendation, founder_satisfaction, system_health, metrics))

    # ==========================================================================
    # SECTION: What the Founder Cares About
    # ==========================================================================
    lines.extend([
        "---",
        "",
        "## What the Founder Cares About",
        "",
        "*This section reflects the founder's perspective based on their feedback.*",
        "",
        f"**Satisfaction Level:** {founder_satisfaction.level.value.upper()}",
        "",
    ])

    # Founder satisfaction details
    if founder_satisfaction.latest_decision:
        lines.append(f"**Latest Decision:** {founder_satisfaction.latest_decision.value.upper()}")
    lines.append(f"**Feedback Trajectory:** {founder_satisfaction.trajectory.title()}")
    lines.append("")

    # What founder objected to
    if founder_satisfaction.persistent_objections:
        lines.extend([
            "### Ongoing Objections (Not Resolved)",
            "",
        ])
        for objection in founder_satisfaction.persistent_objections:
            lines.append(f"- {objection.replace('_', ' ').title()}")
        lines.append("")

    if founder_satisfaction.resolved_objections:
        lines.extend([
            "### Resolved Objections",
            "",
        ])
        for objection in founder_satisfaction.resolved_objections:
            lines.append(f"- {objection.replace('_', ' ').title()}")
        lines.append("")

    # Feedback history summary
    lines.extend([
        "### Feedback History",
        "",
        f"| Type | Count |",
        f"|------|-------|",
        f"| APPROVE | {founder_satisfaction.approval_count} |",
        f"| MINOR_CHANGES | {founder_satisfaction.minor_changes_count} |",
        f"| MAJOR_CHANGES | {founder_satisfaction.major_changes_count} |",
        "",
    ])

    # ==========================================================================
    # SECTION: What the System is Worried About
    # ==========================================================================
    lines.extend([
        "---",
        "",
        "## What the System is Worried About",
        "",
        "*This section reflects operational concerns - things the founder doesn't see.*",
        "",
        f"**System Health:** {system_health.level.value.upper()}",
        "",
    ])

    # System metrics
    if metrics.average_time_to_first_cut_seconds:
        ttfc_formatted = f"{metrics.average_time_to_first_cut_seconds:.1f}s"
    else:
        ttfc_formatted = "N/A"

    lines.extend([
        "### Operational Metrics",
        "",
        f"| Metric | Value | Status |",
        f"|--------|-------|--------|",
        f"| SLA Pass Rate | {system_health.sla_pass_rate:.0%} | {'OK' if system_health.sla_pass_rate == 1.0 else 'ISSUE'} |",
        f"| Final SLA | {'PASS' if system_health.final_sla_passed else 'FAIL'} | {'OK' if system_health.final_sla_passed else 'ISSUE'} |",
        f"| Total Attempts | {system_health.total_attempts} | {'OK' if system_health.total_attempts <= 3 else 'HIGH'} |",
        f"| Avg Iterations | {system_health.average_iterations_per_attempt:.1f} | {'OK' if system_health.average_iterations_per_attempt <= 2.5 else 'HIGH'} |",
        f"| Total Cost | ${system_health.total_cost_dollars:.2f} | {'OK' if system_health.total_cost_dollars <= 10.0 else 'HIGH'} |",
        f"| Time to First Cut | {ttfc_formatted} | - |",
        "",
    ])

    # System concerns
    if system_health.concerns:
        lines.extend([
            "### System Concerns",
            "",
        ])
        for concern in system_health.concerns:
            lines.append(f"- {concern}")
        lines.append("")
    else:
        lines.extend([
            "### System Concerns",
            "",
            "*No system concerns. All metrics within acceptable ranges.*",
            "",
        ])

    # Top Recurring Founder Objections (based on flags)
    if metrics.recurring_flags:
        lines.extend([
            "---",
            "",
            "## Top Recurring Founder Objections",
            "",
        ])
        for flag, count in list(metrics.recurring_flags.items())[:5]:
            flag_display = flag.replace("_", " ").title()
            lines.append(f"- **{flag_display}** ({count}x)")
        lines.append("")

        # Show resolution status
        if metrics.flags_resolved:
            lines.extend([
                "### Issues Resolved",
                "",
            ])
            for flag in metrics.flags_resolved:
                lines.append(f"- {flag.replace('_', ' ').title()}")
            lines.append("")

        if metrics.flags_persistent:
            lines.extend([
                "### Issues Still Unresolved",
                "",
            ])
            for flag in metrics.flags_persistent:
                lines.append(f"- {flag.replace('_', ' ').title()}")
            lines.append("")

    # Legacy feedback themes (from text analysis)
    elif metrics.feedback_themes:
        lines.extend([
            "---",
            "",
            "## Common Feedback Themes",
            "",
        ])
        for theme in metrics.feedback_themes:
            lines.append(f"- **{theme.replace('_', ' ').title()}**")
        lines.append("")

    # Attempt history - enhanced with feedback details
    if pilot.runs:
        lines.extend([
            "---",
            "",
            "## Attempt History",
            "",
            "| # | SLA | Iterations | Cost | Decision | Flags |",
            "|---|-----|------------|------|----------|-------|",
        ])

        for run in pilot.runs:
            sla_status = "PASS" if run.sla_passed else "FAIL"
            decision = run.feedback_decision.value.upper() if run.feedback_decision else (run.feedback_level or "-")
            flags = ", ".join(run.feedback_flags[:3]) if run.feedback_flags else "-"
            lines.append(
                f"| {run.attempt_number} | {sla_status} | {run.iteration_count} | "
                f"${run.total_cost_dollars:.2f} | {decision} | {flags} |"
            )

        lines.append("")

        # Detailed feedback per attempt
        lines.extend([
            "### Detailed Feedback by Attempt",
            "",
        ])

        for run in pilot.runs:
            if run.has_feedback:
                decision = run.feedback_decision.value.upper() if run.feedback_decision else run.feedback_level or "N/A"
                mode = f" ({run.feedback_mode.value})" if run.feedback_mode else ""
                lines.append(f"**Attempt {run.attempt_number}** - {decision}{mode}")

                if run.feedback_flags:
                    flags_display = ", ".join(f.replace("_", " ") for f in run.feedback_flags)
                    lines.append(f"- Flags: {flags_display}")

                if run.feedback_notes:
                    # Truncate long notes
                    notes = run.feedback_notes[:200] + "..." if len(run.feedback_notes) > 200 else run.feedback_notes
                    lines.append(f"- Notes: \"{notes}\"")

                lines.append("")
            else:
                lines.append(f"**Attempt {run.attempt_number}** - No feedback received")
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

        # Feedback decision improvement
        decision_order = {
            FeedbackDecision.MAJOR_CHANGES: 0,
            FeedbackDecision.MINOR_CHANGES: 1,
            FeedbackDecision.APPROVE: 2,
        }
        first_decision = first.feedback_decision
        last_decision = last.feedback_decision
        if first_decision and last_decision:
            if decision_order.get(last_decision, -1) > decision_order.get(first_decision, -1):
                improvements.append(f"Feedback improved: {first_decision.value} → {last_decision.value}")

        # Legacy feedback level check
        elif first.feedback_level and last.feedback_level:
            level_order = {"major_changes": 0, "minor_changes": 1, "approve": 2}
            first_level = level_order.get(first.feedback_level, -1)
            last_level = level_order.get(last.feedback_level, -1)
            if last_level > first_level:
                improvements.append("Feedback level improved")

        # Flag resolution
        if metrics.flags_resolved:
            for flag in metrics.flags_resolved:
                improvements.append(f"Resolved: {flag.replace('_', ' ')}")

        if improvements:
            for imp in improvements:
                lines.append(f"- {imp}")
        else:
            lines.append("- No significant improvements observed")

        lines.append("")

    # What the founder would likely say on a call
    lines.extend(_generate_founder_call_summary(pilot, metrics))

    # ==========================================================================
    # SECTION: Why This Recommendation
    # ==========================================================================
    lines.extend([
        "---",
        "",
        "## Why This Recommendation",
        "",
        f"**{rec_display}**",
        "",
        reasoning,
        "",
    ])

    # Decision matrix explanation
    lines.extend([
        "### Decision Matrix Applied",
        "",
        "| Factor | Status | Impact |",
        "|--------|--------|--------|",
        f"| Founder Satisfaction | {founder_satisfaction.level.value.upper()} | "
        f"{'Approved' if founder_satisfaction.is_approved else 'Not approved'} |",
        f"| System Health | {system_health.level.value.upper()} | "
        f"{'No concerns' if system_health.is_healthy else 'Has concerns'} |",
        f"| Persistent Issues | {len(founder_satisfaction.persistent_objections)} | "
        f"{'Blocking' if founder_satisfaction.persistent_objections else 'None'} |",
        f"| MAJOR_CHANGES Count | {founder_satisfaction.major_changes_count} | "
        f"{'Problematic' if founder_satisfaction.major_changes_count >= 2 else 'OK'} |",
        "",
    ])

    # Next steps based on recommendation
    lines.extend([
        "### Next Steps",
        "",
    ])

    if recommendation == Recommendation.APPROVED_FOR_PUBLISH:
        lines.extend([
            "1. Publish the video",
            "2. Continue with similar founder engagements",
            "3. Apply learnings to playbook",
            "4. Track aggregate metrics across pilots",
        ])
    elif recommendation == Recommendation.APPROVED_WITH_RISK:
        lines.extend([
            "1. **Publish the video** (founder approved)",
            "2. **Investigate system concerns** before next pilot:",
        ])
        for concern in system_health.concerns:
            lines.append(f"   - {concern}")
        lines.extend([
            "3. Adjust playbook if needed",
            "4. Monitor next pilot closely",
        ])
    elif recommendation == Recommendation.REVISE_REQUIRED:
        lines.extend([
            "1. **Do not run similar pilots yet**",
            "2. Review feedback patterns:",
        ])
        if founder_satisfaction.persistent_objections:
            for obj in founder_satisfaction.persistent_objections[:3]:
                lines.append(f"   - {obj.replace('_', ' ').title()}")
        lines.extend([
            "3. Update playbook to address issues",
            "4. Discuss with team what went wrong",
            "5. Run a revised pilot after changes",
        ])
    else:  # STOP_PILOT
        lines.extend([
            "1. **Stop this pilot category entirely**",
            "2. Investigate root cause:",
        ])
        if founder_satisfaction.persistent_objections:
            lines.append(f"   - Unresolved issues: {', '.join(founder_satisfaction.persistent_objections)}")
        if founder_satisfaction.major_changes_count >= 3:
            lines.append(f"   - {founder_satisfaction.major_changes_count}x MAJOR_CHANGES = fundamental mismatch")
        if pilot.approval_outcome == ApprovalOutcome.DROPPED:
            lines.append("   - Founder abandoned the pilot")
        lines.extend([
            "3. Reassess if this scenario type is viable",
            "4. Consider if this founder type is a fit",
            "5. Only resume after systemic changes",
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
