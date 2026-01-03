"""Brand bias application to pipeline configs.

This module applies BrandContext to DirectorConfig, EditorialConfig,
and RhythmConfig WITHOUT violating MarketingIntent SLAs.

The key principle: Brand biases WITHIN constraints, never AGAINST them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.common.logging import get_logger
from src.agents.director import DirectorConfig, PacingStyle, HookStrategy
from src.editing.editorial import EditorialConfig
from src.editing.rhythm import RhythmConfig
from src.marketing import MarketingIntent, MarketingPreset, get_preset
from src.brand.context import BrandContext, ToneProfile, ClaimConservativeness

logger = get_logger(__name__)


@dataclass
class BrandBiasedConfig:
    """Configuration biased by brand context."""

    director_config: DirectorConfig
    editorial_config: EditorialConfig
    rhythm_config: RhythmConfig

    # Tracking
    brand_context: BrandContext
    marketing_preset: MarketingPreset
    biases_applied: list[str]


def apply_brand_bias(
    brand: BrandContext,
    intent: MarketingIntent,
    base_director_config: DirectorConfig | None = None,
    base_editorial_config: EditorialConfig | None = None,
    base_rhythm_config: RhythmConfig | None = None,
) -> BrandBiasedConfig:
    """Apply brand context biases to pipeline configs.

    Brand biases are applied WITHIN the constraints of the MarketingIntent.
    If a brand bias would violate an SLA, the SLA wins.

    Args:
        brand: The brand context to apply.
        intent: The marketing intent (defines hard constraints).
        base_*_config: Optional base configs to bias from.

    Returns:
        BrandBiasedConfig with all biased configs and tracking.
    """
    preset = get_preset(intent)
    biases_applied = []

    # Start with base configs or defaults
    director = base_director_config or DirectorConfig()
    editorial = base_editorial_config or EditorialConfig()
    rhythm = base_rhythm_config or RhythmConfig()

    # === TONE BIASING ===
    director, tone_biases = _apply_tone_bias(director, brand.tone, preset)
    biases_applied.extend(tone_biases)

    # === PACING BIASING ===
    director, editorial, rhythm, pacing_biases = _apply_pacing_bias(
        director, editorial, rhythm, brand.pacing_aggressiveness, preset
    )
    biases_applied.extend(pacing_biases)

    # === CLAIM CONSERVATIVENESS ===
    director, claim_biases = _apply_claim_bias(
        director, brand.claim_conservativeness, preset
    )
    biases_applied.extend(claim_biases)

    # === VISUAL PREFERENCES ===
    director, visual_biases = _apply_visual_preferences(director, brand)
    biases_applied.extend(visual_biases)

    # === FINAL SLA ENFORCEMENT ===
    # Ensure we never violate hard limits
    director = _enforce_sla_limits(director, preset)
    editorial = _enforce_editorial_sla(editorial, preset)
    rhythm = _enforce_rhythm_sla(rhythm, preset)

    logger.info(
        "brand_bias_applied",
        brand=brand.brand_name,
        intent=intent.value,
        biases_count=len(biases_applied),
    )

    return BrandBiasedConfig(
        director_config=director,
        editorial_config=editorial,
        rhythm_config=rhythm,
        brand_context=brand,
        marketing_preset=preset,
        biases_applied=biases_applied,
    )


def _apply_tone_bias(
    config: DirectorConfig,
    tone: ToneProfile,
    preset: MarketingPreset,
) -> tuple[DirectorConfig, list[str]]:
    """Apply tone biases to director config."""
    biases = []

    # Tone -> Pacing style mapping
    tone_pacing = {
        ToneProfile.PROFESSIONAL: PacingStyle.MODERATE,
        ToneProfile.CASUAL: PacingStyle.MODERATE,
        ToneProfile.BOLD: PacingStyle.DYNAMIC,
        ToneProfile.EMPATHETIC: PacingStyle.CONTEMPLATIVE,
        ToneProfile.PLAYFUL: PacingStyle.DYNAMIC,
    }

    # Tone -> Hook strategy mapping
    tone_hook = {
        ToneProfile.PROFESSIONAL: HookStrategy.VISUAL_IMPACT,
        ToneProfile.CASUAL: HookStrategy.EMOTIONAL,
        ToneProfile.BOLD: HookStrategy.ACTION,
        ToneProfile.EMPATHETIC: HookStrategy.EMOTIONAL,
        ToneProfile.PLAYFUL: HookStrategy.MYSTERY,
    }

    new_pacing = tone_pacing.get(tone, config.default_pacing)
    new_hook = tone_hook.get(tone, config.default_hook_strategy)

    if new_pacing != config.default_pacing:
        config = DirectorConfig(
            **{**config.__dict__, "default_pacing": new_pacing}
        )
        biases.append(f"pacing_style: {new_pacing.value} (from tone: {tone.value})")

    if new_hook != config.default_hook_strategy:
        config = DirectorConfig(
            **{**config.__dict__, "default_hook_strategy": new_hook}
        )
        biases.append(f"hook_strategy: {new_hook.value} (from tone: {tone.value})")

    return config, biases


def _apply_pacing_bias(
    director: DirectorConfig,
    editorial: EditorialConfig,
    rhythm: RhythmConfig,
    aggressiveness: float,
    preset: MarketingPreset,
) -> tuple[DirectorConfig, EditorialConfig, RhythmConfig, list[str]]:
    """Apply pacing aggressiveness biases.

    Aggressiveness 0.0 = gentle, slow, contemplative
    Aggressiveness 1.0 = aggressive, fast, intense
    """
    biases = []

    # Bias shot duration within allowed range
    duration_range = preset.max_shot_duration - preset.min_shot_duration
    target_avg = preset.min_shot_duration + (duration_range * (1.0 - aggressiveness))

    new_min = max(preset.min_shot_duration, target_avg - 1.5)
    new_max = min(preset.max_shot_duration, target_avg + 2.0)

    if new_min != director.min_shot_duration or new_max != director.max_shot_duration:
        director = DirectorConfig(
            **{**director.__dict__, "min_shot_duration": new_min, "max_shot_duration": new_max}
        )
        biases.append(f"shot_duration: {new_min:.1f}-{new_max:.1f}s (aggressiveness: {aggressiveness:.0%})")

    # Bias trimming aggressiveness
    base_trim = preset.target_reduction_percent
    trim_adjustment = (aggressiveness - 0.5) * 0.1  # ±5% from base
    new_trim = max(0.10, min(0.35, base_trim + trim_adjustment))

    if abs(new_trim - editorial.target_reduction_percent) > 0.01:
        editorial = EditorialConfig(
            **{**editorial.__dict__, "target_reduction_percent": new_trim}
        )
        biases.append(f"trimming: {new_trim:.0%} (aggressiveness: {aggressiveness:.0%})")

    # Bias rhythm emotion tightening
    base_entry = 0.15
    base_exit = 0.20
    entry_adjustment = aggressiveness * 0.10  # Up to 10% more aggressive
    exit_adjustment = aggressiveness * 0.10

    new_entry = min(0.25, base_entry + entry_adjustment)
    new_exit = min(0.30, base_exit + exit_adjustment)

    rhythm = RhythmConfig(
        **{**rhythm.__dict__, "emotion_entry_trim": new_entry, "emotion_exit_trim": new_exit}
    )
    biases.append(f"emotion_trim: {new_entry:.0%}/{new_exit:.0%}")

    return director, editorial, rhythm, biases


def _apply_claim_bias(
    config: DirectorConfig,
    conservativeness: ClaimConservativeness,
    preset: MarketingPreset,
) -> tuple[DirectorConfig, list[str]]:
    """Apply claim conservativeness biases.

    This primarily affects hook strategy and shot variety.
    """
    biases = []

    if conservativeness == ClaimConservativeness.CONSERVATIVE:
        # Conservative: less aggressive hooks, more variety
        if config.default_hook_strategy == HookStrategy.ACTION:
            config = DirectorConfig(
                **{**config.__dict__, "default_hook_strategy": HookStrategy.VISUAL_IMPACT}
            )
            biases.append("hook: visual_impact (conservative claims)")
        config = DirectorConfig(**{**config.__dict__, "prefer_variety": True})
        biases.append("prefer_variety: true (conservative)")

    elif conservativeness == ClaimConservativeness.AGGRESSIVE:
        # Aggressive: bold hooks, less variety (more focus)
        if config.default_hook_strategy == HookStrategy.MYSTERY:
            config = DirectorConfig(
                **{**config.__dict__, "default_hook_strategy": HookStrategy.ACTION}
            )
            biases.append("hook: action (aggressive claims)")
        config = DirectorConfig(**{**config.__dict__, "prefer_variety": False})
        biases.append("prefer_variety: false (aggressive)")

    return config, biases


def _apply_visual_preferences(
    config: DirectorConfig,
    brand: BrandContext,
) -> tuple[DirectorConfig, list[str]]:
    """Apply visual preference biases."""
    biases = []

    # Note: These would affect shot type selection in DirectorAgent
    # For now, we just track the preferences
    if brand.prefer_close_ups:
        biases.append("visual_preference: close_ups")
    elif brand.prefer_wide_shots:
        biases.append("visual_preference: wide_shots")

    if not brand.prefer_motion:
        # Bias toward static shots
        biases.append("motion_preference: static")

    return config, biases


def _enforce_sla_limits(
    config: DirectorConfig,
    preset: MarketingPreset,
) -> DirectorConfig:
    """Ensure director config respects SLA limits."""
    return DirectorConfig(
        target_duration_seconds=min(
            config.target_duration_seconds,
            preset.target_duration_seconds,
        ),
        min_shot_duration=max(
            config.min_shot_duration,
            preset.min_shot_duration,
        ),
        max_shot_duration=min(
            config.max_shot_duration,
            preset.max_shot_duration,
        ),
        hook_duration=min(
            config.hook_duration,
            preset.hook_duration_seconds,
        ),
        min_shots_per_scene=config.min_shots_per_scene,
        max_shots_per_scene=min(
            config.max_shots_per_scene,
            preset.max_shots,
        ),
        default_pacing=config.default_pacing,
        default_hook_strategy=config.default_hook_strategy,
        prefer_variety=config.prefer_variety,
        include_transitions=config.include_transitions,
        include_audio_cues=config.include_audio_cues,
    )


def _enforce_editorial_sla(
    config: EditorialConfig,
    preset: MarketingPreset,
) -> EditorialConfig:
    """Ensure editorial config respects SLA limits."""
    return EditorialConfig(
        target_reduction_percent=config.target_reduction_percent,
        min_reduction_percent=config.min_reduction_percent,
        max_reduction_percent=config.max_reduction_percent,
        min_shot_duration=max(
            config.min_shot_duration,
            preset.min_shot_duration,
        ),
        max_shot_duration=min(
            config.max_shot_duration,
            preset.max_shot_duration,
        ),
        opening_duration=min(
            config.opening_duration,
            preset.opening_duration_seconds,
        ),
        ending_duration=min(
            config.ending_duration,
            preset.ending_duration_seconds,
        ),
        opening_allowed_purposes=config.opening_allowed_purposes,
        ending_allowed_purposes=config.ending_allowed_purposes,
    )


def _enforce_rhythm_sla(
    config: RhythmConfig,
    preset: MarketingPreset,
) -> RhythmConfig:
    """Ensure rhythm config respects SLA limits."""
    # Rhythm config doesn't have direct SLA constraints
    # but we ensure emotion trimming doesn't go too aggressive
    return RhythmConfig(
        min_duration_variation=config.min_duration_variation,
        max_same_intensity_run=config.max_same_intensity_run,
        emotion_entry_trim=min(config.emotion_entry_trim, 0.30),  # Max 30%
        emotion_exit_trim=min(config.emotion_exit_trim, 0.35),   # Max 35%
        emotion_peak_preserve=max(config.emotion_peak_preserve, 0.50),  # Min 50%
        high_shot_min_duration=max(
            config.high_shot_min_duration,
            preset.min_shot_duration,
        ),
        low_shot_max_duration=min(
            config.low_shot_max_duration,
            preset.max_shot_duration,
        ),
        force_interstitial_after_high=config.force_interstitial_after_high,
    )
