"""Preset adapter for applying marketing intent to pipeline components.

This module translates MarketingPreset into configuration for:
- DirectorAgent (DirectorConfig)
- EditorialAuthority (EditorialConfig)
- RhythmicAuthority (RhythmConfig)

The adapter ensures that marketing intent overrides generic director behavior.
"""

from __future__ import annotations

from src.common.logging import get_logger
from src.agents.director import DirectorConfig, PacingStyle, HookStrategy
from src.editing.editorial import EditorialConfig
from src.editing.rhythm import RhythmConfig
from src.marketing.intent import MarketingIntent, MarketingPreset, get_preset

logger = get_logger(__name__)


def create_director_config(preset: MarketingPreset) -> DirectorConfig:
    """Create DirectorConfig from MarketingPreset.

    The preset overrides default director behavior to ensure
    marketing-outcome-driven shot planning.
    """
    # Map hook aggressiveness to hook strategy
    if preset.hook_aggressiveness >= 0.9:
        hook_strategy = HookStrategy.ACTION
    elif preset.hook_aggressiveness >= 0.7:
        hook_strategy = HookStrategy.VISUAL_IMPACT
    elif preset.hook_aggressiveness >= 0.5:
        hook_strategy = HookStrategy.EMOTIONAL
    else:
        hook_strategy = HookStrategy.MYSTERY

    # Map intensity distribution to pacing style
    if preset.intensity_ratio_high >= 0.5:
        pacing = PacingStyle.INTENSE
    elif preset.intensity_ratio_high >= 0.35:
        pacing = PacingStyle.DYNAMIC
    elif preset.intensity_ratio_low >= 0.3:
        pacing = PacingStyle.CONTEMPLATIVE
    else:
        pacing = PacingStyle.MODERATE

    config = DirectorConfig(
        target_duration_seconds=preset.target_duration_seconds,
        min_shot_duration=preset.min_shot_duration,
        max_shot_duration=preset.max_shot_duration,
        hook_duration=preset.hook_duration_seconds,
        min_shots_per_scene=3,
        max_shots_per_scene=min(preset.max_shots, 15),  # Per-scene limit
        default_pacing=pacing,
        default_hook_strategy=hook_strategy,
        prefer_variety=preset.intent != MarketingIntent.PAID_AD,  # Less variety for ads
        include_transitions=True,
        include_audio_cues=True,
    )

    logger.debug(
        "director_config_from_preset",
        intent=preset.intent.value,
        pacing=pacing.value,
        hook_strategy=hook_strategy.value,
    )

    return config


def create_editorial_config(preset: MarketingPreset) -> EditorialConfig:
    """Create EditorialConfig from MarketingPreset.

    The preset controls trimming aggressiveness and opening/ending rules.
    """
    config = EditorialConfig(
        target_reduction_percent=preset.target_reduction_percent,
        opening_duration=preset.opening_duration_seconds,
        ending_duration=preset.ending_duration_seconds,
        min_shot_duration=preset.min_shot_duration,
        max_shot_duration=preset.max_shot_duration,
        opening_allowed_purposes=preset.opening_required_purposes,
        ending_allowed_purposes=preset.ending_required_purposes,
    )

    logger.debug(
        "editorial_config_from_preset",
        intent=preset.intent.value,
        reduction=f"{preset.target_reduction_percent:.0%}",
    )

    return config


def create_rhythm_config(preset: MarketingPreset) -> RhythmConfig:
    """Create RhythmConfig from MarketingPreset.

    The preset controls intensity distribution and EMOTION shot handling.
    """
    # More aggressive EMOTION tightening for ads
    if preset.intent == MarketingIntent.PAID_AD:
        emotion_entry_trim = 0.20  # Cut 20% from start
        emotion_exit_trim = 0.25   # Cut 25% from end
    elif preset.intent == MarketingIntent.SOCIAL_REEL:
        emotion_entry_trim = 0.15
        emotion_exit_trim = 0.20
    else:  # YOUTUBE_EXPLAINER
        emotion_entry_trim = 0.10  # More breathing room
        emotion_exit_trim = 0.15

    # Stricter variation for high-energy intents
    if preset.intensity_ratio_high >= 0.5:
        min_duration_variation = 0.50  # Force 50% variation
        max_same_intensity_run = 2
    else:
        min_duration_variation = 0.40
        max_same_intensity_run = 3

    config = RhythmConfig(
        min_duration_variation=min_duration_variation,
        max_same_intensity_run=max_same_intensity_run,
        emotion_entry_trim=emotion_entry_trim,
        emotion_exit_trim=emotion_exit_trim,
        emotion_peak_preserve=0.65,
        high_shot_min_duration=preset.min_shot_duration,
        low_shot_max_duration=preset.max_shot_duration,
        force_interstitial_after_high=preset.intent == MarketingIntent.PAID_AD,
    )

    logger.debug(
        "rhythm_config_from_preset",
        intent=preset.intent.value,
        emotion_trim=f"{emotion_entry_trim:.0%}/{emotion_exit_trim:.0%}",
    )

    return config


def get_configs_for_intent(
    intent: MarketingIntent,
) -> tuple[DirectorConfig, EditorialConfig, RhythmConfig]:
    """Get all configs for a marketing intent.

    Returns (DirectorConfig, EditorialConfig, RhythmConfig).
    """
    preset = get_preset(intent)

    return (
        create_director_config(preset),
        create_editorial_config(preset),
        create_rhythm_config(preset),
    )
