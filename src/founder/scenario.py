"""Founder scenario abstraction for real-world validation.

This module defines business scenarios that map to MarketingIntents,
making the system accessible to founders without requiring them to
understand video production terminology.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from src.marketing import MarketingIntent


class FounderGoal(str, Enum):
    """What the founder is trying to achieve."""
    LAUNCH = "launch"           # Announce something new
    ANNOUNCE = "announce"       # Share news/milestone
    CONVERT = "convert"         # Drive specific action


@dataclass(frozen=True)
class FounderScenario:
    """A business scenario that a founder would recognize.

    This abstraction hides video production complexity behind
    business goals and contexts that founders understand.
    """

    # Identity
    scenario_name: str
    scenario_id: str

    # Business context
    business_context: str
    target_customer: str
    platform: str

    # Goal and success
    goal: FounderGoal
    success_criteria: str

    # Mapping to system
    marketing_intent: MarketingIntent

    # Guidance for the founder
    recommended_length: str
    tone_guidance: str
    must_include: list[str]
    avoid: list[str]

    def describe(self) -> str:
        """Return a founder-friendly description."""
        return (
            f"{self.scenario_name}\n"
            f"Goal: {self.goal.value.upper()}\n"
            f"Platform: {self.platform}\n"
            f"Success: {self.success_criteria}"
        )


# =============================================================================
# BUILT-IN SCENARIOS
# =============================================================================

FEATURE_LAUNCH = FounderScenario(
    scenario_name="Feature Launch",
    scenario_id="feature_launch",

    business_context=(
        "You're launching a new feature or product update. "
        "Your audience already knows who you are — they need to understand "
        "what's new and why it matters to them."
    ),
    target_customer="Existing users and warm leads",
    platform="LinkedIn, Twitter, Product Hunt",

    goal=FounderGoal.LAUNCH,
    success_criteria=(
        "Viewer understands the feature in <30 seconds and feels "
        "compelled to try it. Measured by click-through to product."
    ),

    marketing_intent=MarketingIntent.SOCIAL_REEL,

    recommended_length="30-45 seconds",
    tone_guidance="Confident, clear, slightly excited but not hype-y",
    must_include=[
        "The problem this solves (first 5 seconds)",
        "The feature in action (visual demo moment)",
        "Clear next step (try it / learn more)",
    ],
    avoid=[
        "Technical jargon",
        "Long explanations",
        "Multiple CTAs",
        "Apologetic language",
    ],
)

FUNDING_ANNOUNCEMENT = FounderScenario(
    scenario_name="Funding Announcement",
    scenario_id="funding_announcement",

    business_context=(
        "You've raised funding and need to announce it. "
        "This isn't just about the money — it's about credibility, "
        "momentum, and attracting future customers and talent."
    ),
    target_customer="Investors, potential hires, potential customers",
    platform="LinkedIn, Twitter, TechCrunch embed",

    goal=FounderGoal.ANNOUNCE,
    success_criteria=(
        "Viewer feels the company has momentum and is worth watching. "
        "Measured by profile visits, follower growth, inbound inquiries."
    ),

    marketing_intent=MarketingIntent.SOCIAL_REEL,

    recommended_length="45-60 seconds",
    tone_guidance="Grateful but not sycophantic, forward-looking, ambitious",
    must_include=[
        "The 'why now' (market timing)",
        "What you're building (one sentence)",
        "What this funding enables (vision)",
        "Gratitude to team and investors (brief)",
    ],
    avoid=[
        "Exact valuation unless required",
        "Excessive investor name-dropping",
        "Promises you can't keep",
        "Humble-bragging",
    ],
)

PROBLEM_SOLUTION = FounderScenario(
    scenario_name="Problem/Solution Positioning",
    scenario_id="problem_solution",

    business_context=(
        "You need to explain what you do to people who've never heard of you. "
        "This is cold outreach content — the viewer owes you nothing "
        "and will scroll away if you don't hook them immediately."
    ),
    target_customer="Cold audience, problem-aware but not solution-aware",
    platform="Meta ads, TikTok ads, YouTube pre-roll",

    goal=FounderGoal.CONVERT,
    success_criteria=(
        "Viewer experiences 'that's me!' recognition in first 3 seconds "
        "and clicks to learn more. Measured by CTR and CPL."
    ),

    marketing_intent=MarketingIntent.PAID_AD,

    recommended_length="15-25 seconds",
    tone_guidance="Direct, empathetic, urgent but not pushy",
    must_include=[
        "The pain point (first 3 seconds, specific)",
        "The consequence of not solving it",
        "Your solution (one sentence)",
        "Clear CTA with urgency",
    ],
    avoid=[
        "Starting with your company name",
        "Feature lists",
        "Soft language ('maybe', 'might')",
        "Multiple value propositions",
    ],
)


SCENARIOS: dict[str, FounderScenario] = {
    "feature_launch": FEATURE_LAUNCH,
    "funding_announcement": FUNDING_ANNOUNCEMENT,
    "problem_solution": PROBLEM_SOLUTION,
}


def get_scenario(scenario_id: str) -> FounderScenario:
    """Get a scenario by ID."""
    if scenario_id not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(f"Unknown scenario: {scenario_id}. Available: {available}")
    return SCENARIOS[scenario_id]
