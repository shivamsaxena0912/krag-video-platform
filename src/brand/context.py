"""Brand context for biasing video output.

This module provides lightweight brand biasing that:
- Adjusts tone (professional, casual, bold, etc.)
- Controls pacing aggressiveness
- Sets claim conservativeness

BrandContext NEVER violates MarketingIntent SLAs — it only biases
within the allowed constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToneProfile(str, Enum):
    """Brand tone profiles."""

    PROFESSIONAL = "professional"
    """Formal, authoritative, trustworthy. For B2B, enterprise."""

    CASUAL = "casual"
    """Friendly, approachable, conversational. For consumer brands."""

    BOLD = "bold"
    """Confident, assertive, provocative. For disruptors."""

    EMPATHETIC = "empathetic"
    """Understanding, supportive, warm. For health, wellness."""

    PLAYFUL = "playful"
    """Fun, lighthearted, energetic. For lifestyle, gaming."""


class ClaimConservativeness(str, Enum):
    """How conservative claims should be."""

    AGGRESSIVE = "aggressive"
    """Strong claims, superlatives allowed. For bold positioning."""

    MODERATE = "moderate"
    """Balanced claims, some superlatives. Default."""

    CONSERVATIVE = "conservative"
    """Careful claims, avoid superlatives. For regulated industries."""


@dataclass
class BrandContext:
    """Brand context for biasing video output.

    This is a lightweight abstraction that influences defaults
    without violating SLA constraints.
    """

    # Identity
    brand_name: str
    brand_id: str | None = None

    # Tone
    tone: ToneProfile = ToneProfile.PROFESSIONAL

    # Pacing aggressiveness (0.0 = very gentle, 1.0 = very aggressive)
    # This biases within the MarketingIntent's allowed range
    pacing_aggressiveness: float = 0.5

    # Claim conservativeness
    claim_conservativeness: ClaimConservativeness = ClaimConservativeness.MODERATE

    # Visual preferences
    prefer_close_ups: bool = False  # Bias toward close-up shots
    prefer_wide_shots: bool = False  # Bias toward wide shots
    prefer_motion: bool = True  # Bias toward motion vs static

    # Audio preferences
    prefer_music: bool = True
    prefer_voiceover: bool = True

    # Keywords to include/avoid
    include_keywords: list[str] = field(default_factory=list)
    avoid_keywords: list[str] = field(default_factory=list)

    # Tagline or key message
    tagline: str | None = None

    def validate(self) -> list[str]:
        """Validate brand context configuration."""
        errors = []

        if not self.brand_name:
            errors.append("brand_name is required")

        if not 0.0 <= self.pacing_aggressiveness <= 1.0:
            errors.append("pacing_aggressiveness must be between 0.0 and 1.0")

        if self.prefer_close_ups and self.prefer_wide_shots:
            errors.append("Cannot prefer both close-ups and wide shots")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "brand_name": self.brand_name,
            "brand_id": self.brand_id,
            "tone": self.tone.value,
            "pacing_aggressiveness": self.pacing_aggressiveness,
            "claim_conservativeness": self.claim_conservativeness.value,
            "prefer_close_ups": self.prefer_close_ups,
            "prefer_wide_shots": self.prefer_wide_shots,
            "prefer_motion": self.prefer_motion,
            "prefer_music": self.prefer_music,
            "prefer_voiceover": self.prefer_voiceover,
            "include_keywords": self.include_keywords,
            "avoid_keywords": self.avoid_keywords,
            "tagline": self.tagline,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrandContext":
        """Create from dictionary."""
        return cls(
            brand_name=data.get("brand_name", "Unknown"),
            brand_id=data.get("brand_id"),
            tone=ToneProfile(data.get("tone", "professional")),
            pacing_aggressiveness=data.get("pacing_aggressiveness", 0.5),
            claim_conservativeness=ClaimConservativeness(
                data.get("claim_conservativeness", "moderate")
            ),
            prefer_close_ups=data.get("prefer_close_ups", False),
            prefer_wide_shots=data.get("prefer_wide_shots", False),
            prefer_motion=data.get("prefer_motion", True),
            prefer_music=data.get("prefer_music", True),
            prefer_voiceover=data.get("prefer_voiceover", True),
            include_keywords=data.get("include_keywords", []),
            avoid_keywords=data.get("avoid_keywords", []),
            tagline=data.get("tagline"),
        )


def create_brand_context(
    brand_name: str,
    tone: str | ToneProfile = ToneProfile.PROFESSIONAL,
    pacing_aggressiveness: float = 0.5,
    claim_conservativeness: str | ClaimConservativeness = ClaimConservativeness.MODERATE,
    **kwargs: Any,
) -> BrandContext:
    """Create a brand context with sensible defaults.

    Args:
        brand_name: Name of the brand.
        tone: Tone profile (string or enum).
        pacing_aggressiveness: 0.0 (gentle) to 1.0 (aggressive).
        claim_conservativeness: How careful with claims.
        **kwargs: Additional BrandContext fields.

    Returns:
        Configured BrandContext.
    """
    if isinstance(tone, str):
        tone = ToneProfile(tone)
    if isinstance(claim_conservativeness, str):
        claim_conservativeness = ClaimConservativeness(claim_conservativeness)

    return BrandContext(
        brand_name=brand_name,
        tone=tone,
        pacing_aggressiveness=pacing_aggressiveness,
        claim_conservativeness=claim_conservativeness,
        **kwargs,
    )
