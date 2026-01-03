"""Marketing summary generator for review packs.

This module generates marketing_summary.txt in non-filmmaker language,
explaining the marketing rationale behind editorial decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

from src.common.logging import get_logger
from src.common.models import Shot, ShotPurpose, BeatIntensity
from src.marketing.intent import MarketingIntent, MarketingPreset, get_preset
from src.editing.editorial import EditorialReport
from src.editing.rhythm import RhythmReport

logger = get_logger(__name__)


@dataclass
class MarketingSummary:
    """Marketing summary for the review pack."""

    intent: MarketingIntent
    preset: MarketingPreset

    # Content metrics
    total_duration: float
    shot_count: int

    # Purpose breakdown
    emotion_percent: float
    information_percent: float
    atmosphere_percent: float
    transition_percent: float

    # Intensity breakdown
    high_percent: float
    medium_percent: float
    low_percent: float

    # Editorial decisions
    trimmed_from: float  # Original duration
    trimmed_to: float  # Final duration
    reduction_percent: float

    # Notes in plain language
    target_audience_note: str
    platform_note: str
    cta_note: str
    hook_note: str
    pacing_note: str
    ending_note: str

    # Recommendations
    recommendations: list[str] = field(default_factory=list)


def generate_marketing_summary(
    shots: list[Shot],
    intent: MarketingIntent,
    editorial_report: EditorialReport | None = None,
    rhythm_report: RhythmReport | None = None,
    output_path: str | Path | None = None,
) -> MarketingSummary:
    """Generate a marketing summary for the review pack.

    Returns the summary and optionally writes to file.
    """
    preset = get_preset(intent)

    # Calculate metrics
    total_duration = sum(s.duration_seconds for s in shots)
    shot_count = len(shots)

    # Purpose breakdown
    purpose_counts = {}
    for shot in shots:
        if shot.purpose:
            purpose_counts[shot.purpose] = purpose_counts.get(shot.purpose, 0) + 1

    total = len(shots) or 1
    emotion_pct = purpose_counts.get(ShotPurpose.EMOTION, 0) / total
    info_pct = purpose_counts.get(ShotPurpose.INFORMATION, 0) / total
    atmo_pct = purpose_counts.get(ShotPurpose.ATMOSPHERE, 0) / total
    trans_pct = purpose_counts.get(ShotPurpose.TRANSITION, 0) / total

    # Intensity breakdown
    intensity_counts = {}
    for shot in shots:
        intensity_counts[shot.intensity] = intensity_counts.get(shot.intensity, 0) + 1

    high_pct = intensity_counts.get(BeatIntensity.HIGH, 0) / total
    med_pct = intensity_counts.get(BeatIntensity.MEDIUM, 0) / total
    low_pct = intensity_counts.get(BeatIntensity.LOW, 0) / total

    # Editorial metrics
    trimmed_from = editorial_report.original_duration if editorial_report else total_duration
    trimmed_to = total_duration
    reduction = editorial_report.reduction_percent if editorial_report else 0.0

    # Generate plain-language notes
    summary = MarketingSummary(
        intent=intent,
        preset=preset,
        total_duration=total_duration,
        shot_count=shot_count,
        emotion_percent=emotion_pct,
        information_percent=info_pct,
        atmosphere_percent=atmo_pct,
        transition_percent=trans_pct,
        high_percent=high_pct,
        medium_percent=med_pct,
        low_percent=low_pct,
        trimmed_from=trimmed_from,
        trimmed_to=trimmed_to,
        reduction_percent=reduction,
        target_audience_note=_generate_audience_note(intent, preset),
        platform_note=_generate_platform_note(intent, preset),
        cta_note=_generate_cta_note(intent, preset, shots),
        hook_note=_generate_hook_note(intent, preset, shots),
        pacing_note=_generate_pacing_note(shots, rhythm_report),
        ending_note=_generate_ending_note(intent, preset, shots),
        recommendations=_generate_recommendations(intent, preset, shots, emotion_pct, high_pct),
    )

    if output_path:
        _write_summary_file(summary, output_path)

    return summary


def _generate_audience_note(intent: MarketingIntent, preset: MarketingPreset) -> str:
    """Generate audience explanation."""
    if intent == MarketingIntent.PAID_AD:
        return (
            "This video targets cold audiences who have never heard of you. "
            "Every second must justify the viewer's attention. "
            "Assume they will scroll away unless immediately captivated."
        )
    elif intent == MarketingIntent.SOCIAL_REEL:
        return (
            "This video targets a mix of followers and discovery traffic. "
            "The opening hook is critical for algorithm performance. "
            "Engagement (likes, shares) drives distribution."
        )
    else:  # YOUTUBE_EXPLAINER
        return (
            "This video targets viewers actively seeking educational content. "
            "Retention over the first 30 seconds determines recommendation. "
            "Value delivery must be clear and structured."
        )


def _generate_platform_note(intent: MarketingIntent, preset: MarketingPreset) -> str:
    """Generate platform explanation."""
    return (
        f"Optimized for {preset.platform}. "
        f"Aspect ratio: {preset.aspect_ratio}. "
        f"Target duration: {preset.target_duration_seconds:.0f} seconds "
        f"(range: {preset.min_duration_seconds:.0f}-{preset.max_duration_seconds:.0f}s)."
    )


def _generate_cta_note(
    intent: MarketingIntent,
    preset: MarketingPreset,
    shots: list[Shot],
) -> str:
    """Generate CTA explanation."""
    cta = preset.intended_cta

    if intent == MarketingIntent.PAID_AD:
        return (
            f"Primary CTA: {cta}. "
            "The ending is designed to create urgency and prompt immediate action. "
            "No soft landing — the viewer should feel compelled to click."
        )
    elif intent == MarketingIntent.SOCIAL_REEL:
        return (
            f"Primary CTA: {cta}. "
            "The ending encourages engagement without hard selling. "
            "Emotional resonance drives sharing behavior."
        )
    else:  # YOUTUBE_EXPLAINER
        return (
            f"Primary CTA: {cta}. "
            "The ending provides closure while suggesting continued relationship. "
            "Subscribe prompt should feel earned, not forced."
        )


def _generate_hook_note(
    intent: MarketingIntent,
    preset: MarketingPreset,
    shots: list[Shot],
) -> str:
    """Generate hook explanation."""
    hook_duration = preset.hook_duration_seconds
    aggressiveness = preset.hook_aggressiveness

    # Analyze first few shots
    hook_shots = []
    cumulative = 0.0
    for shot in shots:
        if cumulative >= hook_duration:
            break
        hook_shots.append(shot)
        cumulative += shot.duration_seconds

    high_count = sum(1 for s in hook_shots if s.intensity == BeatIntensity.HIGH)
    emotion_count = sum(1 for s in hook_shots if s.purpose == ShotPurpose.EMOTION)

    if aggressiveness >= 0.9:
        intensity_desc = "maximum aggressiveness"
    elif aggressiveness >= 0.7:
        intensity_desc = "high aggressiveness"
    else:
        intensity_desc = "moderate approach"

    return (
        f"Hook window: First {hook_duration:.0f} seconds ({len(hook_shots)} shots). "
        f"Strategy: {intensity_desc}. "
        f"{high_count} high-intensity shots, {emotion_count} emotion-driven shots. "
        "Designed to stop the scroll and establish immediate interest."
    )


def _generate_pacing_note(
    shots: list[Shot],
    rhythm_report: RhythmReport | None,
) -> str:
    """Generate pacing explanation."""
    if not shots:
        return "No shots to analyze."

    avg_duration = sum(s.duration_seconds for s in shots) / len(shots)

    if avg_duration < 2.5:
        pace_desc = "Fast-paced, high-energy"
    elif avg_duration < 4.0:
        pace_desc = "Moderate, engaging"
    elif avg_duration < 6.0:
        pace_desc = "Deliberate, contemplative"
    else:
        pace_desc = "Slow, immersive"

    rhythm_note = ""
    if rhythm_report:
        if rhythm_report.monotony_score < 0.3:
            rhythm_note = " Strong rhythmic variation keeps viewer engaged."
        elif rhythm_report.monotony_score > 0.6:
            rhythm_note = " Consider adding more tempo changes to prevent fatigue."

    return (
        f"Average shot duration: {avg_duration:.1f}s. "
        f"Pacing style: {pace_desc}. "
        f"{len(shots)} total shots.{rhythm_note}"
    )


def _generate_ending_note(
    intent: MarketingIntent,
    preset: MarketingPreset,
    shots: list[Shot],
) -> str:
    """Generate ending explanation."""
    if not shots:
        return "No shots to analyze."

    final_shot = shots[-1]
    ending_intent = final_shot.ending_intent

    if intent == MarketingIntent.PAID_AD:
        if ending_intent == preset.ending_required_intent:
            return (
                "Ending is CTA-optimized with urgency. "
                "Cuts off before the viewer is comfortable — prompts action."
            )
        else:
            return (
                f"Warning: Ending intent is {ending_intent.value if ending_intent else 'unset'}, "
                f"but paid ads perform better with {preset.ending_required_intent.value}."
            )
    elif intent == MarketingIntent.SOCIAL_REEL:
        return (
            "Ending encourages continued engagement without hard CTA. "
            "Emotional landing designed to prompt likes and shares."
        )
    else:  # YOUTUBE_EXPLAINER
        return (
            "Ending provides satisfying closure with soft subscribe prompt. "
            "Resolution-focused to maximize viewer satisfaction."
        )


def _generate_recommendations(
    intent: MarketingIntent,
    preset: MarketingPreset,
    shots: list[Shot],
    emotion_pct: float,
    high_pct: float,
) -> list[str]:
    """Generate actionable recommendations."""
    recommendations = []

    total_duration = sum(s.duration_seconds for s in shots)

    # Duration check
    if total_duration > preset.max_duration_seconds:
        recommendations.append(
            f"TRIM REQUIRED: Video is {total_duration:.0f}s, max allowed is {preset.max_duration_seconds:.0f}s. "
            "Remove information-heavy shots first."
        )
    elif total_duration < preset.min_duration_seconds:
        recommendations.append(
            f"EXTEND: Video is {total_duration:.0f}s, minimum is {preset.min_duration_seconds:.0f}s. "
            "Add atmosphere or emotional beats."
        )

    # Emotion check
    target_emotion = preset.purpose_ratio_emotion
    if emotion_pct < target_emotion * 0.7:
        recommendations.append(
            f"LOW EMOTION: Only {emotion_pct:.0%} emotional content vs {target_emotion:.0%} target. "
            "Add more human-focused or emotionally resonant shots."
        )

    # Intensity check for paid ads
    if intent == MarketingIntent.PAID_AD:
        if high_pct < preset.intensity_ratio_high * 0.7:
            recommendations.append(
                f"LOW ENERGY: Only {high_pct:.0%} high-intensity vs {preset.intensity_ratio_high:.0%} target. "
                "Shorten shots and increase tempo for paid media performance."
            )

    # Shot count check
    if len(shots) > preset.max_shots:
        recommendations.append(
            f"TOO MANY SHOTS: {len(shots)} shots exceeds max {preset.max_shots}. "
            "Consolidate or remove redundant shots."
        )

    if not recommendations:
        recommendations.append(
            f"Video meets all {intent.value} requirements. Ready for review."
        )

    return recommendations


def _write_summary_file(summary: MarketingSummary, output_path: str | Path) -> None:
    """Write marketing summary to file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "=" * 70,
        "MARKETING SUMMARY - Review Pack",
        "=" * 70,
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Marketing Intent: {summary.intent.value.upper().replace('_', ' ')}",
        "",
        "--- WHO IS THIS FOR? ---",
        summary.target_audience_note,
        "",
        "--- WHERE WILL IT RUN? ---",
        summary.platform_note,
        "",
        "--- WHAT DO WE WANT THEM TO DO? ---",
        summary.cta_note,
        "",
        "--- HOW DOES IT OPEN? ---",
        summary.hook_note,
        "",
        "--- HOW DOES IT FLOW? ---",
        summary.pacing_note,
        "",
        "--- HOW DOES IT END? ---",
        summary.ending_note,
        "",
        "--- BY THE NUMBERS ---",
        f"Duration: {summary.total_duration:.1f} seconds",
        f"Shots: {summary.shot_count}",
        "",
        f"Content breakdown:",
        f"  Emotional content: {summary.emotion_percent:.0%}",
        f"  Informational content: {summary.information_percent:.0%}",
        f"  Atmosphere/mood: {summary.atmosphere_percent:.0%}",
        f"  Transitions: {summary.transition_percent:.0%}",
        "",
        f"Energy breakdown:",
        f"  High intensity: {summary.high_percent:.0%}",
        f"  Medium intensity: {summary.medium_percent:.0%}",
        f"  Low intensity: {summary.low_percent:.0%}",
        "",
        "--- WHY WE CUT IT THIS WAY ---",
        f"Started with: {summary.trimmed_from:.1f}s",
        f"Trimmed to: {summary.trimmed_to:.1f}s",
        f"Reduction: {summary.reduction_percent:.0%}",
        "",
        "We prioritized:",
    ]

    if summary.intent == MarketingIntent.PAID_AD:
        lines.extend([
            "1. Immediate visual impact (grab attention in under 2 seconds)",
            "2. High energy throughout (no boring moments)",
            "3. Clear CTA urgency (make them click NOW)",
            "4. Minimal explanation (show, don't tell)",
        ])
    elif summary.intent == MarketingIntent.SOCIAL_REEL:
        lines.extend([
            "1. Scroll-stopping opener (algorithm depends on retention)",
            "2. Emotional resonance (shareable moments)",
            "3. Rhythmic variety (keeps viewers watching)",
            "4. Soft engagement prompt (like/share feels natural)",
        ])
    else:  # YOUTUBE_EXPLAINER
        lines.extend([
            "1. Clear value proposition (why should they watch?)",
            "2. Structured information flow (easy to follow)",
            "3. Emotional anchors (keeps it human)",
            "4. Satisfying conclusion (earned subscribe prompt)",
        ])

    lines.extend([
        "",
        "--- RECOMMENDATIONS ---",
    ])
    for i, rec in enumerate(summary.recommendations, 1):
        lines.append(f"{i}. {rec}")

    lines.extend([
        "",
        "=" * 70,
        f"This video was optimized for: {summary.preset.platform}",
        f"Intended CTA: {summary.preset.intended_cta}",
        "=" * 70,
    ])

    with open(path, "w") as f:
        f.write("\n".join(lines))

    logger.info(
        "marketing_summary_generated",
        path=str(path),
        intent=summary.intent.value,
    )
