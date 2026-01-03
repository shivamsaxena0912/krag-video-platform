"""Expert feedback aggregation into playbook entries.

This module analyzes patterns in expert feedback and converts
them into reusable playbook entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import hashlib

from src.common.logging import get_logger
from src.common.models import FeedbackAnnotation, FeedbackIssue, FixCategory
from src.founder import FounderFeedback, FounderFeedbackLevel
from src.playbook.playbook import Playbook, PlaybookEntry

logger = get_logger(__name__)


@dataclass
class FeedbackPattern:
    """A detected pattern in feedback."""

    pattern_type: str  # e.g., "too_long", "hook_weak"
    occurrences: int
    scenarios: list[str]
    intents: list[str]
    feedback_ids: list[str]

    @property
    def confidence(self) -> float:
        """Confidence based on occurrence frequency."""
        # More occurrences = higher confidence
        return min(1.0, self.occurrences / 5)  # Max confidence at 5 occurrences


@dataclass
class FeedbackAggregation:
    """Result of feedback aggregation."""

    # Input
    feedback_count: int
    scenarios_covered: list[str]
    intents_covered: list[str]

    # Patterns detected
    patterns: list[FeedbackPattern] = field(default_factory=list)

    # Entries generated
    entries_created: int = 0
    entries_updated: int = 0


def aggregate_feedback(
    playbook: Playbook,
    feedback_list: list[FounderFeedback | FeedbackAnnotation],
    scenario_ids: list[str] | None = None,
    intent_ids: list[str] | None = None,
    min_occurrences: int = 2,
) -> FeedbackAggregation:
    """Aggregate expert feedback into playbook entries.

    Args:
        playbook: The playbook to add entries to.
        feedback_list: List of feedback to analyze.
        scenario_ids: Corresponding scenario IDs for each feedback.
        intent_ids: Corresponding intent IDs for each feedback.
        min_occurrences: Minimum occurrences to create an entry.

    Returns:
        FeedbackAggregation with results.
    """
    if scenario_ids is None:
        scenario_ids = [None] * len(feedback_list)
    if intent_ids is None:
        intent_ids = [None] * len(feedback_list)

    result = FeedbackAggregation(
        feedback_count=len(feedback_list),
        scenarios_covered=list(set(s for s in scenario_ids if s)),
        intents_covered=list(set(i for i in intent_ids if i)),
    )

    # Detect patterns
    patterns = _detect_patterns(feedback_list, scenario_ids, intent_ids)
    result.patterns = patterns

    # Convert patterns to entries
    for pattern in patterns:
        if pattern.occurrences >= min_occurrences:
            entry = _pattern_to_entry(pattern)
            if entry:
                # Check if similar entry exists
                existing = _find_similar_entry(playbook, entry)
                if existing:
                    _merge_entries(existing, entry)
                    result.entries_updated += 1
                else:
                    playbook.add_entry(entry)
                    result.entries_created += 1

    logger.info(
        "feedback_aggregated",
        feedback_count=result.feedback_count,
        patterns_found=len(result.patterns),
        entries_created=result.entries_created,
        entries_updated=result.entries_updated,
    )

    return result


def _detect_patterns(
    feedback_list: list[FounderFeedback | FeedbackAnnotation],
    scenario_ids: list[str | None],
    intent_ids: list[str | None],
) -> list[FeedbackPattern]:
    """Detect patterns in feedback."""
    # Track pattern occurrences
    pattern_data: dict[str, dict[str, Any]] = {}

    for i, feedback in enumerate(feedback_list):
        scenario_id = scenario_ids[i]
        intent_id = intent_ids[i]
        feedback_id = f"fb_{i}"

        # Extract flags from feedback
        flags = _extract_flags(feedback)

        for flag in flags:
            if flag not in pattern_data:
                pattern_data[flag] = {
                    "occurrences": 0,
                    "scenarios": set(),
                    "intents": set(),
                    "feedback_ids": [],
                }

            pattern_data[flag]["occurrences"] += 1
            if scenario_id:
                pattern_data[flag]["scenarios"].add(scenario_id)
            if intent_id:
                pattern_data[flag]["intents"].add(intent_id)
            pattern_data[flag]["feedback_ids"].append(feedback_id)

    # Convert to FeedbackPattern objects
    patterns = []
    for pattern_type, data in pattern_data.items():
        patterns.append(FeedbackPattern(
            pattern_type=pattern_type,
            occurrences=data["occurrences"],
            scenarios=list(data["scenarios"]),
            intents=list(data["intents"]),
            feedback_ids=data["feedback_ids"],
        ))

    # Sort by occurrences (most frequent first)
    patterns.sort(key=lambda p: p.occurrences, reverse=True)

    return patterns


def _extract_flags(feedback: FounderFeedback | FeedbackAnnotation) -> list[str]:
    """Extract pattern flags from feedback."""
    flags = []

    if isinstance(feedback, FounderFeedback):
        # Founder feedback has explicit flags
        if feedback.too_long:
            flags.append("too_long")
        if feedback.too_short:
            flags.append("too_short")
        if feedback.hook_weak:
            flags.append("hook_weak")
        if feedback.ending_unclear:
            flags.append("ending_unclear")
        if feedback.wrong_tone:
            flags.append("wrong_tone")
        if feedback.missing_key_message:
            flags.append("missing_key_message")

        # Level as a flag
        if feedback.level == FounderFeedbackLevel.MAJOR_CHANGES:
            flags.append("major_rework_needed")

    elif isinstance(feedback, FeedbackAnnotation):
        # Extract from issues
        for issue in feedback.issues:
            if issue.fix_category == FixCategory.PACING:
                if "long" in issue.description.lower():
                    flags.append("too_long")
                if "short" in issue.description.lower():
                    flags.append("too_short")
            if issue.fix_category == FixCategory.VISUAL_STYLE:
                if "hook" in issue.description.lower():
                    flags.append("hook_weak")
            if issue.fix_category == FixCategory.NARRATIVE:
                if "ending" in issue.description.lower():
                    flags.append("ending_unclear")
                if "message" in issue.description.lower():
                    flags.append("missing_key_message")

        # Check playbook adjustments
        adjustments = feedback.playbook_adjustments
        if adjustments.get("reduce_duration"):
            flags.append("too_long")
        if adjustments.get("stronger_hook"):
            flags.append("hook_weak")
        if adjustments.get("clearer_ending"):
            flags.append("ending_unclear")

    return flags


def _pattern_to_entry(pattern: FeedbackPattern) -> PlaybookEntry | None:
    """Convert a pattern to a playbook entry."""
    entry_id = f"entry_{hashlib.sha256(pattern.pattern_type.encode()).hexdigest()[:8]}"

    # Determine trigger (specific scenario/intent or general)
    trigger_scenario = None
    trigger_intent = None

    if len(pattern.scenarios) == 1:
        trigger_scenario = pattern.scenarios[0]
    if len(pattern.intents) == 1:
        trigger_intent = pattern.intents[0]

    # Determine adjustments based on pattern type
    pacing_adjustment = 0.0
    trimming_adjustment = 0.0
    hook_strength_adjustment = 0.0
    director_constraints = []
    description = ""
    rationale = ""

    if pattern.pattern_type == "too_long":
        trimming_adjustment = 0.05  # Increase trimming by 5%
        pacing_adjustment = 0.1    # Slightly more aggressive pacing
        director_constraints = ["reduce_shots", "shorter_shots"]
        description = "Content runs too long for platform"
        rationale = f"Detected in {pattern.occurrences} feedback instances"

    elif pattern.pattern_type == "too_short":
        trimming_adjustment = -0.05  # Reduce trimming
        pacing_adjustment = -0.1    # Slower pacing
        description = "Content is too brief"
        rationale = f"Detected in {pattern.occurrences} feedback instances"

    elif pattern.pattern_type == "hook_weak":
        hook_strength_adjustment = 0.2  # Stronger hook
        director_constraints = ["stronger_opening", "visual_hook"]
        description = "Opening hook needs more impact"
        rationale = f"Detected in {pattern.occurrences} feedback instances"

    elif pattern.pattern_type == "ending_unclear":
        director_constraints = ["clear_cta", "decisive_ending"]
        description = "Ending needs clearer call-to-action"
        rationale = f"Detected in {pattern.occurrences} feedback instances"

    elif pattern.pattern_type == "wrong_tone":
        description = "Tone doesn't match brand expectations"
        rationale = f"Detected in {pattern.occurrences} feedback instances"

    elif pattern.pattern_type == "missing_key_message":
        description = "Key message not coming through clearly"
        rationale = f"Detected in {pattern.occurrences} feedback instances"

    elif pattern.pattern_type == "major_rework_needed":
        trimming_adjustment = 0.1
        pacing_adjustment = 0.15
        description = "Significant rework frequently needed"
        rationale = f"Detected in {pattern.occurrences} feedback instances"

    else:
        # Unknown pattern, skip
        return None

    return PlaybookEntry(
        entry_id=entry_id,
        trigger_scenario=trigger_scenario,
        trigger_intent=trigger_intent,
        pacing_adjustment=pacing_adjustment,
        trimming_adjustment=trimming_adjustment,
        hook_strength_adjustment=hook_strength_adjustment,
        director_constraints=director_constraints,
        source_feedback_ids=pattern.feedback_ids,
        confidence=pattern.confidence,
        description=description,
        rationale=rationale,
    )


def _find_similar_entry(playbook: Playbook, new_entry: PlaybookEntry) -> PlaybookEntry | None:
    """Find an existing entry that's similar to the new one."""
    for entry in playbook.entries:
        # Match on trigger conditions and description
        if (
            entry.trigger_scenario == new_entry.trigger_scenario
            and entry.trigger_intent == new_entry.trigger_intent
            and entry.description == new_entry.description
        ):
            return entry
    return None


def _merge_entries(existing: PlaybookEntry, new: PlaybookEntry) -> None:
    """Merge a new entry into an existing one."""
    # Average the adjustments
    existing.pacing_adjustment = (existing.pacing_adjustment + new.pacing_adjustment) / 2
    existing.trimming_adjustment = (existing.trimming_adjustment + new.trimming_adjustment) / 2
    existing.hook_strength_adjustment = (
        existing.hook_strength_adjustment + new.hook_strength_adjustment
    ) / 2

    # Merge constraints
    for constraint in new.director_constraints:
        if constraint not in existing.director_constraints:
            existing.director_constraints.append(constraint)

    # Add feedback IDs
    existing.source_feedback_ids.extend(new.source_feedback_ids)

    # Update confidence (more occurrences = higher confidence)
    existing.confidence = min(1.0, existing.confidence + 0.1)

    # Update rationale
    existing.rationale = f"Updated from {len(existing.source_feedback_ids)} feedback instances"
