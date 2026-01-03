"""Pilot operations layer for founder engagements.

This module provides infrastructure for running real founder pilots
safely, predictably, and repeatably.
"""

from src.pilot.run import (
    PilotRun,
    PilotRunAttempt,
    PilotStatus,
    ApprovalOutcome,
    PilotStore,
    create_pilot,
)
from src.pilot.runbook import (
    PilotRunbookBuilder,
    RunbookConfig,
    generate_pilot_runbook,
)
from src.pilot.artifacts import (
    FounderArtifacts,
    generate_founder_artifacts,
    generate_founder_instructions,
    generate_what_to_expect,
    generate_approval_criteria,
)
from src.pilot.outcome import (
    PilotMetrics,
    Recommendation,
    compute_pilot_metrics,
    determine_recommendation,
    generate_pilot_outcome_report,
    generate_multi_pilot_report,
)

__all__ = [
    # Run
    "PilotRun",
    "PilotRunAttempt",
    "PilotStatus",
    "ApprovalOutcome",
    "PilotStore",
    "create_pilot",
    # Runbook
    "PilotRunbookBuilder",
    "RunbookConfig",
    "generate_pilot_runbook",
    # Artifacts
    "FounderArtifacts",
    "generate_founder_artifacts",
    "generate_founder_instructions",
    "generate_what_to_expect",
    "generate_approval_criteria",
    # Outcome
    "PilotMetrics",
    "Recommendation",
    "compute_pilot_metrics",
    "determine_recommendation",
    "generate_pilot_outcome_report",
    "generate_multi_pilot_report",
]
