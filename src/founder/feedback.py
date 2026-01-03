"""Founder feedback mode for simplified review.

This module translates simple founder feedback (APPROVE/MINOR/MAJOR)
into structured internal feedback without exposing complexity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.common.logging import get_logger
from src.common.models import (
    FeedbackAnnotation,
    FeedbackSource,
    FeedbackTargetType,
    FeedbackRecommendation,
    FeedbackIssue,
    IssueSeverity,
    FixCategory,
)
from src.founder.scenario import FounderScenario

logger = get_logger(__name__)


class FounderFeedbackLevel(str, Enum):
    """Simple feedback levels that founders understand."""

    APPROVE = "approve"
    """Ready to publish. No changes needed."""

    MINOR_CHANGES = "minor_changes"
    """Small tweaks needed. Same direction, better execution."""

    MAJOR_CHANGES = "major_changes"
    """Significant rework required. Reconsider approach."""


@dataclass
class FounderFeedback:
    """Simplified feedback from a founder.

    This is what founders actually provide — simple, high-level feedback
    without needing to understand video production.
    """

    level: FounderFeedbackLevel
    notes: str = ""  # Optional free-form notes

    # Optional specific callouts (still simple)
    too_long: bool = False
    too_short: bool = False
    hook_weak: bool = False
    ending_unclear: bool = False
    wrong_tone: bool = False
    missing_key_message: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "notes": self.notes,
            "too_long": self.too_long,
            "too_short": self.too_short,
            "hook_weak": self.hook_weak,
            "ending_unclear": self.ending_unclear,
            "wrong_tone": self.wrong_tone,
            "missing_key_message": self.missing_key_message,
        }


def translate_founder_feedback(
    feedback: FounderFeedback,
    scenario: FounderScenario,
    story_id: str,
) -> FeedbackAnnotation:
    """Translate founder feedback into structured system feedback.

    This is the bridge between founder simplicity and system complexity.
    The founder never needs to know about ShotPurpose, BeatIntensity, etc.
    """
    issues = []
    playbook_adjustments = {}

    # Determine overall recommendation
    if feedback.level == FounderFeedbackLevel.APPROVE:
        recommendation = FeedbackRecommendation.APPROVE
    elif feedback.level == FounderFeedbackLevel.MINOR_CHANGES:
        recommendation = FeedbackRecommendation.APPROVE_WITH_NOTES
    else:
        recommendation = FeedbackRecommendation.REVISE

    # Translate specific callouts into issues
    if feedback.too_long:
        issues.append(FeedbackIssue(
            description="Video is too long for the platform and goal",
            severity=IssueSeverity.MAJOR if feedback.level == FounderFeedbackLevel.MAJOR_CHANGES else IssueSeverity.MODERATE,
            fix_category=FixCategory.PACING,
            suggested_fix="Reduce duration by 20-30%. Cut information-heavy sections first.",
        ))
        playbook_adjustments["reduce_duration"] = True
        playbook_adjustments["aggressive_trim"] = True

    if feedback.too_short:
        issues.append(FeedbackIssue(
            description="Video is too short to convey the message",
            severity=IssueSeverity.MODERATE,
            fix_category=FixCategory.PACING,
            suggested_fix="Add more context or emotional beats. Don't rush.",
        ))
        playbook_adjustments["extend_duration"] = True

    if feedback.hook_weak:
        issues.append(FeedbackIssue(
            description="Opening hook doesn't grab attention",
            severity=IssueSeverity.MAJOR,
            fix_category=FixCategory.VISUAL_STYLE,
            suggested_fix="Strengthen first 3 seconds. Start with the problem, not the solution.",
        ))
        playbook_adjustments["stronger_hook"] = True
        playbook_adjustments["hook_aggressiveness"] = 1.0

    if feedback.ending_unclear:
        issues.append(FeedbackIssue(
            description="Ending doesn't have a clear CTA",
            severity=IssueSeverity.MAJOR,
            fix_category=FixCategory.NARRATIVE,
            suggested_fix="Make the next step obvious. What should the viewer DO?",
        ))
        playbook_adjustments["clearer_ending"] = True
        playbook_adjustments["ending_intent"] = "provocation"

    if feedback.wrong_tone:
        issues.append(FeedbackIssue(
            description="Tone doesn't match the brand or scenario",
            severity=IssueSeverity.MODERATE,
            fix_category=FixCategory.VISUAL_STYLE,
            suggested_fix=f"Adjust tone to: {scenario.tone_guidance}",
        ))
        playbook_adjustments["adjust_tone"] = True

    if feedback.missing_key_message:
        issues.append(FeedbackIssue(
            description="Missing key message or value proposition",
            severity=IssueSeverity.MAJOR,
            fix_category=FixCategory.NARRATIVE,
            suggested_fix=f"Ensure these are included: {', '.join(scenario.must_include)}",
        ))
        playbook_adjustments["reinforce_message"] = True

    # Add notes as a general issue if provided
    if feedback.notes and feedback.level != FounderFeedbackLevel.APPROVE:
        issues.append(FeedbackIssue(
            description=f"Founder notes: {feedback.notes}",
            severity=IssueSeverity.MODERATE,
            fix_category=FixCategory.NARRATIVE,
            suggested_fix="Address founder's specific concerns.",
        ))

    # Calculate an approximate score
    if feedback.level == FounderFeedbackLevel.APPROVE:
        overall_score = 9.0
    elif feedback.level == FounderFeedbackLevel.MINOR_CHANGES:
        overall_score = 7.0 - (len(issues) * 0.5)
        overall_score = max(5.0, overall_score)
    else:
        overall_score = 4.0 - (len(issues) * 0.3)
        overall_score = max(2.0, overall_score)

    # Create the structured feedback
    annotation = FeedbackAnnotation(
        target_type=FeedbackTargetType.STORY,
        target_id=story_id,
        source=FeedbackSource.HUMAN,
        author_id="founder",
        overall_score=overall_score,
        recommendation=recommendation,
        issues=issues,
        playbook_adjustments=playbook_adjustments,
        raw_feedback={
            "founder_feedback": feedback.to_dict(),
            "scenario": scenario.scenario_id,
        },
    )

    logger.info(
        "founder_feedback_translated",
        level=feedback.level.value,
        issues=len(issues),
        recommendation=recommendation.value,
        score=overall_score,
    )

    return annotation


def create_feedback_prompt(scenario: FounderScenario) -> str:
    """Generate a prompt for collecting founder feedback.

    This can be displayed in CLI or UI to guide the founder.
    """
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 REVIEW: {scenario.scenario_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Watch the video and answer:

1. Overall verdict:
   [A] APPROVE - Ready to publish
   [M] MINOR_CHANGES - Small tweaks needed
   [X] MAJOR_CHANGES - Significant rework required

2. Quick checks (Y/N):
   - Is it too long? ___
   - Is it too short? ___
   - Is the hook weak? ___
   - Is the ending unclear? ___
   - Is the tone wrong? ___
   - Is a key message missing? ___

3. Notes (optional):
   _________________________________________________

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Remember the goal: {scenario.goal.value.upper()}
Success criteria: {scenario.success_criteria}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
