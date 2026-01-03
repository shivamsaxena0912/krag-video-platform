"""Marketing intent abstraction and presets.

This module defines the MarketingIntent enum and hard constraint presets
that override generic director behavior. Each intent maps to a specific
marketing outcome with predictable, platform-appropriate outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from src.common.models import ShotPurpose, EndingIntent, BeatIntensity


class MarketingIntent(str, Enum):
    """Marketing intent for the video output.

    Each intent maps to a specific platform and marketing outcome:
    - PAID_AD: Short, aggressive, CTA-driven (Meta, TikTok, YouTube pre-roll)
    - SOCIAL_REEL: Vertical, hook-heavy, engagement-optimized (Instagram, TikTok)
    - YOUTUBE_EXPLAINER: Longer, educational, retention-focused (YouTube main content)
    """

    PAID_AD = "paid_ad"
    SOCIAL_REEL = "social_reel"
    YOUTUBE_EXPLAINER = "youtube_explainer"


@dataclass(frozen=True)
class MarketingPreset:
    """Hard constraint preset for a marketing intent.

    These presets override generic director behavior to ensure
    marketing-outcome-driven predictability.
    """

    intent: MarketingIntent

    # Duration constraints (hard limits)
    max_duration_seconds: float
    min_duration_seconds: float
    target_duration_seconds: float

    # Iteration limits (SLA)
    max_iterations: int
    max_cost_dollars: float

    # Hook aggressiveness (0.0 = gentle, 1.0 = maximum)
    hook_aggressiveness: float
    hook_duration_seconds: float

    # Trimming configuration
    target_reduction_percent: float  # How aggressively to trim

    # Opening rules (first N seconds)
    opening_duration_seconds: float
    opening_required_purposes: tuple[ShotPurpose, ...]
    opening_required_intensity: BeatIntensity

    # Ending rules (last N seconds)
    ending_duration_seconds: float
    ending_required_intent: EndingIntent
    ending_required_purposes: tuple[ShotPurpose, ...]

    # Purpose distribution targets (sum to 1.0)
    purpose_ratio_emotion: float
    purpose_ratio_information: float
    purpose_ratio_atmosphere: float
    purpose_ratio_transition: float

    # Intensity distribution targets (sum to 1.0)
    intensity_ratio_high: float
    intensity_ratio_medium: float
    intensity_ratio_low: float

    # Shot constraints
    min_shot_duration: float
    max_shot_duration: float
    max_shots: int

    # Platform metadata
    platform: str
    target_audience: str
    intended_cta: str
    aspect_ratio: str

    def validate(self) -> list[str]:
        """Validate preset configuration."""
        errors = []

        if self.min_duration_seconds > self.max_duration_seconds:
            errors.append("min_duration > max_duration")

        if self.target_duration_seconds < self.min_duration_seconds:
            errors.append("target_duration < min_duration")

        if self.target_duration_seconds > self.max_duration_seconds:
            errors.append("target_duration > max_duration")

        purpose_sum = (
            self.purpose_ratio_emotion +
            self.purpose_ratio_information +
            self.purpose_ratio_atmosphere +
            self.purpose_ratio_transition
        )
        if abs(purpose_sum - 1.0) > 0.01:
            errors.append(f"purpose ratios sum to {purpose_sum}, not 1.0")

        intensity_sum = (
            self.intensity_ratio_high +
            self.intensity_ratio_medium +
            self.intensity_ratio_low
        )
        if abs(intensity_sum - 1.0) > 0.01:
            errors.append(f"intensity ratios sum to {intensity_sum}, not 1.0")

        return errors


# =============================================================================
# HARD CONSTRAINT PRESETS
# =============================================================================

PRESET_PAID_AD = MarketingPreset(
    intent=MarketingIntent.PAID_AD,

    # Duration: 15-30 seconds (paid media standard)
    max_duration_seconds=30.0,
    min_duration_seconds=15.0,
    target_duration_seconds=25.0,

    # SLA: Fast, cheap
    max_iterations=2,
    max_cost_dollars=1.0,

    # Hook: Maximum aggressiveness (first 3s must grab)
    hook_aggressiveness=1.0,
    hook_duration_seconds=3.0,

    # Trimming: Aggressive (cut 25%+)
    target_reduction_percent=0.25,

    # Opening: First 3s must be EMOTION/ATMOSPHERE at HIGH intensity
    opening_duration_seconds=3.0,
    opening_required_purposes=(ShotPurpose.EMOTION, ShotPurpose.ATMOSPHERE),
    opening_required_intensity=BeatIntensity.HIGH,

    # Ending: Last 3s must be TRANSITION with CTA (PROVOCATION)
    ending_duration_seconds=3.0,
    ending_required_intent=EndingIntent.PROVOCATION,
    ending_required_purposes=(ShotPurpose.TRANSITION,),

    # Purpose: Heavy EMOTION, minimal INFORMATION
    purpose_ratio_emotion=0.60,
    purpose_ratio_information=0.05,
    purpose_ratio_atmosphere=0.20,
    purpose_ratio_transition=0.15,

    # Intensity: Mostly HIGH (urgency)
    intensity_ratio_high=0.60,
    intensity_ratio_medium=0.30,
    intensity_ratio_low=0.10,

    # Shots: Short, punchy
    min_shot_duration=1.5,
    max_shot_duration=4.0,
    max_shots=12,

    # Platform
    platform="Meta/TikTok/YouTube Pre-roll",
    target_audience="Cold audience, scroll-stopping required",
    intended_cta="Click/Swipe/Learn More",
    aspect_ratio="9:16 or 1:1",
)

PRESET_SOCIAL_REEL = MarketingPreset(
    intent=MarketingIntent.SOCIAL_REEL,

    # Duration: 30-60 seconds (engagement sweet spot)
    max_duration_seconds=60.0,
    min_duration_seconds=30.0,
    target_duration_seconds=45.0,

    # SLA: Moderate
    max_iterations=3,
    max_cost_dollars=1.5,

    # Hook: High aggressiveness (3s hook is critical)
    hook_aggressiveness=0.85,
    hook_duration_seconds=3.0,

    # Trimming: Moderate-aggressive (cut 20%)
    target_reduction_percent=0.20,

    # Opening: First 3s must be EMOTION at HIGH intensity
    opening_duration_seconds=3.0,
    opening_required_purposes=(ShotPurpose.EMOTION,),
    opening_required_intensity=BeatIntensity.HIGH,

    # Ending: Last 5s should be EMOTION with soft CTA (TRANSITION)
    ending_duration_seconds=5.0,
    ending_required_intent=EndingIntent.TRANSITION,
    ending_required_purposes=(ShotPurpose.EMOTION, ShotPurpose.TRANSITION),

    # Purpose: Balanced emotion and atmosphere
    purpose_ratio_emotion=0.50,
    purpose_ratio_information=0.10,
    purpose_ratio_atmosphere=0.25,
    purpose_ratio_transition=0.15,

    # Intensity: Dynamic with contrast
    intensity_ratio_high=0.45,
    intensity_ratio_medium=0.35,
    intensity_ratio_low=0.20,

    # Shots: Varied for engagement
    min_shot_duration=2.0,
    max_shot_duration=5.0,
    max_shots=18,

    # Platform
    platform="Instagram Reels/TikTok",
    target_audience="Followers and explore page",
    intended_cta="Like/Share/Follow",
    aspect_ratio="9:16",
)

PRESET_YOUTUBE_EXPLAINER = MarketingPreset(
    intent=MarketingIntent.YOUTUBE_EXPLAINER,

    # Duration: 2-5 minutes (educational content)
    max_duration_seconds=300.0,
    min_duration_seconds=120.0,
    target_duration_seconds=180.0,

    # SLA: More iterations allowed for quality
    max_iterations=5,
    max_cost_dollars=3.0,

    # Hook: Moderate (8s hook for retention)
    hook_aggressiveness=0.65,
    hook_duration_seconds=8.0,

    # Trimming: Conservative (cut 15%)
    target_reduction_percent=0.15,

    # Opening: First 8s can include INFORMATION to establish credibility
    opening_duration_seconds=8.0,
    opening_required_purposes=(ShotPurpose.EMOTION, ShotPurpose.ATMOSPHERE, ShotPurpose.INFORMATION),
    opening_required_intensity=BeatIntensity.MEDIUM,

    # Ending: Last 10s should be RESOLUTION with subscribe CTA
    ending_duration_seconds=10.0,
    ending_required_intent=EndingIntent.RESOLUTION,
    ending_required_purposes=(ShotPurpose.EMOTION, ShotPurpose.TRANSITION),

    # Purpose: Balanced information and emotion
    purpose_ratio_emotion=0.35,
    purpose_ratio_information=0.30,
    purpose_ratio_atmosphere=0.20,
    purpose_ratio_transition=0.15,

    # Intensity: More LOW for comprehension
    intensity_ratio_high=0.25,
    intensity_ratio_medium=0.45,
    intensity_ratio_low=0.30,

    # Shots: Longer, more contemplative
    min_shot_duration=3.0,
    max_shot_duration=8.0,
    max_shots=45,

    # Platform
    platform="YouTube",
    target_audience="Subscribers and search traffic",
    intended_cta="Subscribe/Watch Next",
    aspect_ratio="16:9",
)


PRESETS: dict[MarketingIntent, MarketingPreset] = {
    MarketingIntent.PAID_AD: PRESET_PAID_AD,
    MarketingIntent.SOCIAL_REEL: PRESET_SOCIAL_REEL,
    MarketingIntent.YOUTUBE_EXPLAINER: PRESET_YOUTUBE_EXPLAINER,
}


def get_preset(intent: MarketingIntent) -> MarketingPreset:
    """Get the preset for a marketing intent."""
    if intent not in PRESETS:
        raise ValueError(f"No preset defined for intent: {intent}")
    return PRESETS[intent]
