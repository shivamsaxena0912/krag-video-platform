"""Simulated founder personas for pilot testing.

Each persona encodes realistic founder behavior patterns
for pressure-testing the video generation system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FeedbackStyle(str, Enum):
    """How the persona communicates feedback."""

    BLUNT = "blunt"
    """Direct, no-nonsense feedback."""

    DIPLOMATIC = "diplomatic"
    """Softer, more constructive feedback."""

    TERSE = "terse"
    """Minimal words, gets to the point."""

    DETAILED = "detailed"
    """Thorough explanations of issues."""


class PlatformBias(str, Enum):
    """Which platform the persona prioritizes."""

    INSTAGRAM = "instagram"
    """Short, punchy, visual-first."""

    LINKEDIN = "linkedin"
    """Professional, longer-form acceptable."""

    TWITTER = "twitter"
    """Ultra-short, hook-driven."""

    YOUTUBE = "youtube"
    """Longer acceptable, story matters."""

    TIKTOK = "tiktok"
    """Trend-aware, fast-paced."""


@dataclass
class SimulatedFounderPersona:
    """A simulated founder with consistent behavior patterns.

    Used to generate realistic feedback without real founders,
    enabling pressure-testing of the pilot system.
    """

    # Identity
    persona_id: str
    name: str
    description: str

    # Patience and quality expectations
    patience_level: float  # 0.0 (impatient) to 1.0 (very patient)
    quality_bar: float  # 0.0 (accepts anything) to 1.0 (perfectionist)

    # Platform and content preferences
    platform_bias: PlatformBias
    max_acceptable_duration_seconds: float
    min_acceptable_duration_seconds: float

    # Flag weights - higher = more likely to flag this issue
    flag_weights: dict[str, float] = field(default_factory=dict)

    # Communication style
    feedback_style: FeedbackStyle = FeedbackStyle.BLUNT

    # Approval thresholds
    approve_after_attempts: int = 2  # How many attempts before likely to approve
    major_changes_threshold: float = 0.7  # Quality below this = MAJOR_CHANGES

    # Typical phrases for feedback generation
    approval_phrases: list[str] = field(default_factory=list)
    minor_changes_phrases: list[str] = field(default_factory=list)
    major_changes_phrases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "description": self.description,
            "patience_level": self.patience_level,
            "quality_bar": self.quality_bar,
            "platform_bias": self.platform_bias.value,
            "max_acceptable_duration_seconds": self.max_acceptable_duration_seconds,
            "min_acceptable_duration_seconds": self.min_acceptable_duration_seconds,
            "flag_weights": self.flag_weights,
            "feedback_style": self.feedback_style.value,
            "approve_after_attempts": self.approve_after_attempts,
            "major_changes_threshold": self.major_changes_threshold,
        }


# =============================================================================
# BUILT-IN PERSONAS
# =============================================================================

SPEED_SAAS_FOUNDER = SimulatedFounderPersona(
    persona_id="speed_saas_founder",
    name="Speed-Obsessed SaaS Founder",
    description="Moves fast, ships fast, wants videos yesterday. Prioritizes speed over polish.",
    patience_level=0.3,
    quality_bar=0.5,
    platform_bias=PlatformBias.TWITTER,
    max_acceptable_duration_seconds=45.0,
    min_acceptable_duration_seconds=15.0,
    flag_weights={
        "too_long": 0.9,
        "pacing_flat": 0.7,
        "hook_weak": 0.8,
        "cta_unclear": 0.6,
        "tone_mismatch": 0.3,
        "visuals_poor": 0.2,
    },
    feedback_style=FeedbackStyle.TERSE,
    approve_after_attempts=1,
    major_changes_threshold=0.6,
    approval_phrases=[
        "Ship it.",
        "Good enough, let's go.",
        "This works, send it.",
    ],
    minor_changes_phrases=[
        "Too long. Cut 10 seconds.",
        "Hook needs work. Faster.",
        "Almost there, tighten it up.",
    ],
    major_changes_phrases=[
        "Way too slow. Start over.",
        "This won't work. Too long.",
        "No one will watch this. Redo.",
    ],
)

CAUTIOUS_FIRST_TIME_FOUNDER = SimulatedFounderPersona(
    persona_id="cautious_first_time_founder",
    name="Cautious First-Time Founder",
    description="First startup, worried about brand perception. Needs reassurance, overthinks details.",
    patience_level=0.8,
    quality_bar=0.8,
    platform_bias=PlatformBias.LINKEDIN,
    max_acceptable_duration_seconds=90.0,
    min_acceptable_duration_seconds=30.0,
    flag_weights={
        "off_brand": 0.9,
        "tone_mismatch": 0.9,
        "message_unclear": 0.8,
        "visuals_poor": 0.7,
        "hook_weak": 0.5,
        "too_long": 0.3,
    },
    feedback_style=FeedbackStyle.DETAILED,
    approve_after_attempts=3,
    major_changes_threshold=0.75,
    approval_phrases=[
        "I think this is ready. Let me check with my co-founder first... okay yes, approved.",
        "This feels right for our brand. Let's use it.",
        "I'm happy with this. Good work.",
    ],
    minor_changes_phrases=[
        "The tone feels slightly off. We're more approachable than this. Can you warm it up?",
        "I like the structure but the visuals don't quite match our brand guidelines.",
        "Almost there! The message is good but the ending could be stronger.",
    ],
    major_changes_phrases=[
        "This doesn't feel like us at all. I think we need to go back to basics.",
        "I'm worried our customers won't relate to this. Can we try a different approach?",
        "The core message isn't coming through. Let's rethink this.",
    ],
)

GROWTH_MARKETER = SimulatedFounderPersona(
    persona_id="growth_marketer",
    name="Growth Marketer Founder",
    description="All about conversion. Obsessed with CTAs, hooks, and metrics. Wants results.",
    patience_level=0.5,
    quality_bar=0.6,
    platform_bias=PlatformBias.INSTAGRAM,
    max_acceptable_duration_seconds=60.0,
    min_acceptable_duration_seconds=15.0,
    flag_weights={
        "cta_unclear": 0.95,
        "hook_weak": 0.9,
        "ending_weak": 0.85,
        "too_long": 0.7,
        "pacing_flat": 0.6,
        "message_unclear": 0.5,
        "tone_mismatch": 0.3,
    },
    feedback_style=FeedbackStyle.BLUNT,
    approve_after_attempts=2,
    major_changes_threshold=0.65,
    approval_phrases=[
        "CTA is clear, hook is strong. This will convert. Approved.",
        "I can see this getting clicks. Let's run it.",
        "Good. The ask is obvious. Ship it.",
    ],
    minor_changes_phrases=[
        "The CTA gets lost at the end. Make it impossible to miss.",
        "Hook is weak. First 2 seconds need to stop the scroll.",
        "Ending is soft. Hit them with the CTA harder.",
    ],
    major_changes_phrases=[
        "Where's the CTA? I can't find it. This won't convert.",
        "No one is going to stop scrolling for this hook. Start over.",
        "This is brand video, not performance video. I need conversions.",
    ],
)

TECHNICAL_FOUNDER = SimulatedFounderPersona(
    persona_id="technical_founder",
    name="Technical Founder",
    description="Engineer-turned-CEO. Wants accuracy, hates fluff. Skeptical of marketing speak.",
    patience_level=0.6,
    quality_bar=0.7,
    platform_bias=PlatformBias.YOUTUBE,
    max_acceptable_duration_seconds=120.0,
    min_acceptable_duration_seconds=30.0,
    flag_weights={
        "message_unclear": 0.9,
        "wrong_audience": 0.8,
        "too_short": 0.7,
        "hook_weak": 0.5,
        "cta_unclear": 0.5,
        "tone_mismatch": 0.6,
        "pacing_rushed": 0.7,
    },
    feedback_style=FeedbackStyle.DETAILED,
    approve_after_attempts=2,
    major_changes_threshold=0.7,
    approval_phrases=[
        "The technical accuracy is good and the message is clear. Approved.",
        "This explains what we do correctly. I'm satisfied.",
        "Good. It's not overselling. Use it.",
    ],
    minor_changes_phrases=[
        "The explanation at 0:23 is technically incorrect. Fix that claim.",
        "Too much marketing fluff. Trim the buzzwords, add substance.",
        "The pacing is rushed. Our product is complex, give it room.",
    ],
    major_changes_phrases=[
        "This oversimplifies what we do. It's misleading. Redo.",
        "Wrong audience. This is for enterprise, not consumers.",
        "Too much hype, not enough substance. Start over.",
    ],
)

BRAND_SENSITIVE_FOUNDER = SimulatedFounderPersona(
    persona_id="brand_sensitive_founder",
    name="Brand-Sensitive Founder",
    description="Former brand/agency background. Obsessed with visual quality, tone, and brand consistency.",
    patience_level=0.7,
    quality_bar=0.9,
    platform_bias=PlatformBias.INSTAGRAM,
    max_acceptable_duration_seconds=60.0,
    min_acceptable_duration_seconds=20.0,
    flag_weights={
        "off_brand": 0.95,
        "tone_mismatch": 0.95,
        "visuals_poor": 0.9,
        "pacing_flat": 0.7,
        "ending_weak": 0.6,
        "hook_weak": 0.6,
        "cta_unclear": 0.4,
    },
    feedback_style=FeedbackStyle.DIPLOMATIC,
    approve_after_attempts=3,
    major_changes_threshold=0.8,
    approval_phrases=[
        "This feels like us. The visual language is on point. Love it.",
        "The tone is perfect. This is exactly our voice. Approved.",
        "Beautiful work. This represents our brand well.",
    ],
    minor_changes_phrases=[
        "The color grading feels slightly off from our brand palette. Can we warm it up?",
        "Love the direction, but the pacing in the middle section feels rushed.",
        "Almost perfect! The font in the end card isn't our brand font though.",
    ],
    major_changes_phrases=[
        "This doesn't feel like our brand at all. The tone is completely wrong.",
        "I wouldn't put our logo on this. The visual quality isn't there.",
        "We have brand guidelines for a reason. This ignores all of them.",
    ],
)


# Registry of all built-in personas
PERSONAS: dict[str, SimulatedFounderPersona] = {
    "speed_saas_founder": SPEED_SAAS_FOUNDER,
    "cautious_first_time_founder": CAUTIOUS_FIRST_TIME_FOUNDER,
    "growth_marketer": GROWTH_MARKETER,
    "technical_founder": TECHNICAL_FOUNDER,
    "brand_sensitive_founder": BRAND_SENSITIVE_FOUNDER,
}


def get_persona(persona_id: str) -> SimulatedFounderPersona:
    """Get a persona by ID.

    Args:
        persona_id: The persona identifier.

    Returns:
        The persona.

    Raises:
        ValueError: If persona not found.
    """
    if persona_id not in PERSONAS:
        available = ", ".join(PERSONAS.keys())
        raise ValueError(f"Unknown persona: {persona_id}. Available: {available}")
    return PERSONAS[persona_id]


def list_personas() -> list[str]:
    """List all available persona IDs."""
    return list(PERSONAS.keys())
