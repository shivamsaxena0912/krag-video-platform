"""Playbook system for expert feedback aggregation."""

from src.playbook.playbook import (
    Playbook,
    PlaybookEntry,
    PlaybookVersion,
    create_playbook,
    load_playbook,
    save_playbook,
)
from src.playbook.aggregation import (
    aggregate_feedback,
    FeedbackAggregation,
)
from src.playbook.apply import (
    apply_playbook,
    PlaybookApplication,
    describe_application,
)

__all__ = [
    # Playbook
    "Playbook",
    "PlaybookEntry",
    "PlaybookVersion",
    "create_playbook",
    "load_playbook",
    "save_playbook",
    # Aggregation
    "aggregate_feedback",
    "FeedbackAggregation",
    # Application
    "apply_playbook",
    "PlaybookApplication",
    "describe_application",
]
