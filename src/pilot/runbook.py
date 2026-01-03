"""Pilot runbook generator.

Generates human-readable runbook files that document
what we're testing, what success looks like, and our
commitments to the founder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pilot.run import PilotRun


@dataclass
class RunbookConfig:
    """Configuration for runbook generation."""

    # Testing goals
    primary_goal: str = "Validate video generation quality for real founder use case"
    secondary_goals: list[str] | None = None

    # Success criteria
    success_criteria: list[str] | None = None

    # Feedback focus areas
    feedback_areas: list[str] | None = None

    # Promises
    promises: list[str] | None = None
    non_promises: list[str] | None = None


def generate_pilot_runbook(
    pilot: PilotRun,
    config: RunbookConfig | None = None,
    output_path: Path | str | None = None,
) -> str:
    """Generate a pilot runbook document.

    The runbook is founder trust infrastructure - it documents
    what we're testing, what success looks like, and our commitments.

    Args:
        pilot: The pilot run to generate runbook for.
        config: Optional configuration for runbook content.
        output_path: Optional path to write the runbook file.

    Returns:
        The runbook content as a string.
    """
    config = config or RunbookConfig()

    # Build default values
    secondary_goals = config.secondary_goals or [
        "Measure time-to-first-cut for this scenario type",
        "Identify common feedback patterns for playbook improvement",
        "Validate SLA constraints for the target platform",
    ]

    success_criteria = config.success_criteria or [
        "Founder approves at least one video for publishing",
        "Time-to-first-cut under 2 minutes",
        "No more than 3 iterations needed for approval",
        "SLA constraints met (duration, shot count, pacing)",
    ]

    feedback_areas = config.feedback_areas or [
        "Overall video quality and professionalism",
        "Pacing - too fast, too slow, or just right",
        "Hook effectiveness - does it grab attention?",
        "Ending clarity - is the call-to-action clear?",
        "Tone alignment - does it match the brand voice?",
        "Key message - does the main point come through?",
    ]

    promises = config.promises or [
        f"Up to {pilot.max_attempts} video attempts",
        f"Up to {pilot.max_iterations_per_attempt} refinement iterations per attempt",
        "Review pack with each video for easy feedback",
        "Plain-English marketing summary (no jargon)",
        "Director notes explaining creative decisions",
        "Response to feedback within 24 hours",
    ]

    non_promises = config.non_promises or [
        "Final production-quality video (this is draft quality)",
        "Custom music or voice-over (using placeholders)",
        "Unlimited revisions (we have defined limits)",
        "Guaranteed approval (we're testing, not selling)",
        "Timeline commitments (this is a pilot)",
    ]

    # Generate runbook content
    lines = [
        "=" * 60,
        "PILOT RUNBOOK",
        "=" * 60,
        "",
        f"Pilot ID:     {pilot.pilot_id}",
        f"Founder:      {pilot.founder_name}",
        f"Company:      {pilot.company_name}",
        f"Scenario:     {pilot.scenario_type}",
        f"Created:      {pilot.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "-" * 60,
        "WHAT WE ARE TESTING",
        "-" * 60,
        "",
        f"Primary Goal:",
        f"  {config.primary_goal}",
        "",
        "Secondary Goals:",
    ]

    for goal in secondary_goals:
        lines.append(f"  - {goal}")

    lines.extend([
        "",
        "-" * 60,
        "WHAT SUCCESS LOOKS LIKE",
        "-" * 60,
        "",
    ])

    for criterion in success_criteria:
        lines.append(f"  [_] {criterion}")

    lines.extend([
        "",
        "-" * 60,
        "ITERATION LIMITS",
        "-" * 60,
        "",
        f"  Maximum video attempts:         {pilot.max_attempts}",
        f"  Max iterations per attempt:     {pilot.max_iterations_per_attempt}",
        f"  Total possible iterations:      {pilot.max_attempts * pilot.max_iterations_per_attempt}",
        "",
        "  If we hit these limits without approval, we will:",
        "    1. Analyze feedback patterns",
        "    2. Update our playbook",
        "    3. Discuss next steps with founder",
        "",
        "-" * 60,
        "FEEDBACK WE WANT FROM THE FOUNDER",
        "-" * 60,
        "",
    ])

    for i, area in enumerate(feedback_areas, 1):
        lines.append(f"  {i}. {area}")

    lines.extend([
        "",
        "  Feedback format:",
        "    - APPROVE: Ready to publish as-is",
        "    - MINOR CHANGES: Small tweaks needed (specify what)",
        "    - MAJOR CHANGES: Significant rework needed (specify issues)",
        "",
        "-" * 60,
        "WHAT WE PROMISE",
        "-" * 60,
        "",
    ])

    for promise in promises:
        lines.append(f"  [x] {promise}")

    lines.extend([
        "",
        "-" * 60,
        "WHAT WE DON'T PROMISE",
        "-" * 60,
        "",
    ])

    for non_promise in non_promises:
        lines.append(f"  [ ] {non_promise}")

    lines.extend([
        "",
        "-" * 60,
        "PILOT TIMELINE",
        "-" * 60,
        "",
        "  Day 1:    Initial video generation",
        "  Day 1-2:  Founder review and feedback",
        "  Day 2-3:  Iterations based on feedback",
        "  Day 3-5:  Final approval or decision to stop",
        "",
        "  Note: Timeline is approximate and depends on founder availability.",
        "",
        "-" * 60,
        "CONTACT & SUPPORT",
        "-" * 60,
        "",
        "  For questions or issues:",
        "    - Reply to the email that sent this pilot",
        "    - Include the Pilot ID in all communications",
        "",
        "=" * 60,
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 60,
        "",
    ])

    content = "\n".join(lines)

    # Write to file if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

    return content


class PilotRunbookBuilder:
    """Builder for pilot runbooks with fluent API."""

    def __init__(self, pilot: PilotRun):
        """Initialize the builder.

        Args:
            pilot: The pilot to build a runbook for.
        """
        self.pilot = pilot
        self.config = RunbookConfig()

    def with_primary_goal(self, goal: str) -> "PilotRunbookBuilder":
        """Set the primary testing goal."""
        self.config.primary_goal = goal
        return self

    def with_secondary_goals(self, goals: list[str]) -> "PilotRunbookBuilder":
        """Set secondary testing goals."""
        self.config.secondary_goals = goals
        return self

    def with_success_criteria(self, criteria: list[str]) -> "PilotRunbookBuilder":
        """Set success criteria."""
        self.config.success_criteria = criteria
        return self

    def with_feedback_areas(self, areas: list[str]) -> "PilotRunbookBuilder":
        """Set feedback focus areas."""
        self.config.feedback_areas = areas
        return self

    def with_promises(self, promises: list[str]) -> "PilotRunbookBuilder":
        """Set what we promise."""
        self.config.promises = promises
        return self

    def with_non_promises(self, non_promises: list[str]) -> "PilotRunbookBuilder":
        """Set what we don't promise."""
        self.config.non_promises = non_promises
        return self

    def build(self, output_path: Path | str | None = None) -> str:
        """Build the runbook.

        Args:
            output_path: Optional path to write the runbook file.

        Returns:
            The runbook content as a string.
        """
        return generate_pilot_runbook(
            self.pilot,
            self.config,
            output_path,
        )
