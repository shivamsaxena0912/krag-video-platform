"""Rhythmic authority module for enforcing tempo and contrast.

This module implements rhythmic discipline:
- Every shot has an intensity (LOW/MEDIUM/HIGH)
- No long runs of identical intensity
- Adjacent shots must vary by ±40% in duration
- EMOTION shots are tightened differently (late entry, early exit)
- Final shot must declare an ending intent

The goal: Make parts feel too fast, parts unexpectedly still.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.common.logging import get_logger
from src.common.models import Shot, ShotRole, ShotPurpose, BeatIntensity, EndingIntent

logger = get_logger(__name__)


# Intensity inference from shot characteristics
ROLE_TO_INTENSITY = {
    ShotRole.ESTABLISHING: BeatIntensity.LOW,
    ShotRole.ACTION: BeatIntensity.HIGH,
    ShotRole.REACTION: BeatIntensity.MEDIUM,
    ShotRole.DETAIL: BeatIntensity.LOW,
    ShotRole.TRANSITION: BeatIntensity.LOW,
    ShotRole.MONTAGE: BeatIntensity.HIGH,
    ShotRole.CLIMAX: BeatIntensity.HIGH,
    ShotRole.RESOLUTION: BeatIntensity.LOW,
}

PURPOSE_TO_INTENSITY = {
    ShotPurpose.INFORMATION: BeatIntensity.LOW,
    ShotPurpose.EMOTION: BeatIntensity.HIGH,
    ShotPurpose.ATMOSPHERE: BeatIntensity.LOW,
    ShotPurpose.TRANSITION: BeatIntensity.MEDIUM,
}

# Duration targets by intensity
INTENSITY_DURATION_TARGETS = {
    BeatIntensity.LOW: (4.0, 8.0),    # Breathing room: longer shots
    BeatIntensity.MEDIUM: (2.5, 5.0),  # Normal flow
    BeatIntensity.HIGH: (1.5, 3.5),    # Urgency: shorter shots
}

# Ending intent duration biases
ENDING_INTENT_DURATION = {
    EndingIntent.RESOLUTION: 1.3,    # Longer, let it breathe
    EndingIntent.PROVOCATION: 0.7,   # Shorter, cut before comfortable
    EndingIntent.TRANSITION: 1.0,    # Normal
}


@dataclass
class RhythmConfig:
    """Configuration for rhythmic authority."""

    # Variation requirements
    min_duration_variation: float = 0.40  # ±40% between adjacent shots
    max_same_intensity_run: int = 2       # Max consecutive shots of same intensity

    # EMOTION shot tightening
    emotion_entry_trim: float = 0.15      # Trim 15% from start (late entry)
    emotion_exit_trim: float = 0.20       # Trim 20% from end (early exit)
    emotion_peak_preserve: float = 0.65   # Preserve 65% of duration as peak

    # Intensity thresholds
    high_shot_min_duration: float = 1.5
    low_shot_max_duration: float = 8.0

    # Contrast enforcement
    force_interstitial_after_high: bool = True


@dataclass
class RhythmReport:
    """Report of rhythmic decisions made."""

    # Intensity distribution
    low_count: int = 0
    medium_count: int = 0
    high_count: int = 0
    intensity_distribution: dict[BeatIntensity, int] = field(default_factory=dict)

    # Rhythm metrics
    average_duration: float = 0.0
    duration_variance: float = 0.0
    duration_variation_achieved: float = 0.0  # Average variation between adjacent shots
    intensity_changes: int = 0
    monotony_score: float = 0.0  # 0 = varied, 1 = flat
    max_intensity_run: int = 0  # Longest run of same intensity
    attention_dip_count: int = 0  # Number of detected attention dips

    # Corrections made
    intensity_runs_broken: int = 0
    duration_variations_added: int = 0
    emotion_shots_tightened: int = 0

    # Ending
    ending_intent: EndingIntent = EndingIntent.RESOLUTION
    ending_duration_bias: float = 1.0

    # Rhythm notes
    rhythm_notes: list[str] = field(default_factory=list)
    attention_dip_location: str = ""


def infer_intensity(shot: Shot) -> BeatIntensity:
    """Infer shot intensity from role, purpose, and content."""
    # If already assigned non-default, keep it
    if shot.intensity != BeatIntensity.MEDIUM:
        return shot.intensity

    # Check role first
    role = shot.visual_spec.role if shot.visual_spec else None
    if role and role in ROLE_TO_INTENSITY:
        return ROLE_TO_INTENSITY[role]

    # Check purpose
    if shot.purpose and shot.purpose in PURPOSE_TO_INTENSITY:
        return PURPOSE_TO_INTENSITY[shot.purpose]

    # Content-based inference
    desc_lower = (shot.visual_description or "").lower()

    # High intensity signals
    high_signals = ["battle", "fight", "explosion", "chase", "scream", "attack",
                    "clash", "charge", "urgent", "desperate", "climax", "peak"]
    if any(signal in desc_lower for signal in high_signals):
        return BeatIntensity.HIGH

    # Low intensity signals
    low_signals = ["peaceful", "quiet", "still", "contemplat", "reflection",
                   "sunset", "sunrise", "landscape", "silence", "slow"]
    if any(signal in desc_lower for signal in low_signals):
        return BeatIntensity.LOW

    # Default based on duration
    if shot.duration_seconds < 2.5:
        return BeatIntensity.HIGH
    elif shot.duration_seconds > 5.0:
        return BeatIntensity.LOW

    return BeatIntensity.MEDIUM


def infer_ending_intent(shot: Shot, all_shots: list[Shot]) -> EndingIntent:
    """Infer ending intent for final shot based on content and context."""
    desc_lower = (shot.visual_description or "").lower()
    purpose = shot.purpose

    # Resolution signals
    resolution_signals = ["peace", "rest", "home", "embrace", "smile", "safe",
                         "complete", "finish", "end", "close", "settle"]
    if any(signal in desc_lower for signal in resolution_signals):
        return EndingIntent.RESOLUTION

    # Provocation signals
    provocation_signals = ["question", "uncertain", "dark", "threat", "shadow",
                          "unknown", "mystery", "ominous", "cliff", "edge"]
    if any(signal in desc_lower for signal in provocation_signals):
        return EndingIntent.PROVOCATION

    # Check emotional arc
    if len(all_shots) > 5:
        late_emotions = sum(1 for s in all_shots[-5:] if s.purpose == ShotPurpose.EMOTION)
        if late_emotions >= 3:
            return EndingIntent.RESOLUTION  # Emotional ending suggests resolution

    # Default based on purpose
    if purpose == ShotPurpose.EMOTION:
        return EndingIntent.RESOLUTION
    elif purpose == ShotPurpose.TRANSITION:
        return EndingIntent.TRANSITION

    return EndingIntent.PROVOCATION  # Default to provocative (more interesting)


class RhythmicAuthority:
    """Enforces rhythmic discipline on shot sequences.

    The rhythmic authority controls tempo:
    - When to speed up
    - When to slow down
    - Where to create contrast

    The goal is not uniformity, but dynamics.
    """

    def __init__(self, config: RhythmConfig | None = None):
        self.config = config or RhythmConfig()

    def apply(self, shots: list[Shot]) -> tuple[list[Shot], RhythmReport]:
        """Apply rhythmic authority to shot sequence.

        Returns (processed_shots, report).
        """
        if not shots:
            return shots, RhythmReport()

        report = RhythmReport()

        # Step 1: Assign intensities
        shots = self._assign_intensities(shots)

        # Step 2: Enforce ending intent
        shots, report.ending_intent, report.ending_duration_bias = self._enforce_ending(shots)

        # Step 3: Break monotonous intensity runs
        shots, report.intensity_runs_broken = self._break_intensity_runs(shots)

        # Step 4: Enforce duration variation
        shots, report.duration_variations_added = self._enforce_duration_variation(shots)

        # Step 5: Tighten EMOTION shots differently
        shots, report.emotion_shots_tightened = self._tighten_emotion_shots(shots)

        # Step 6: Calculate metrics
        self._calculate_metrics(shots, report)

        # Step 7: Generate rhythm notes
        report.rhythm_notes = self._generate_rhythm_notes(shots, report)
        report.attention_dip_location = self._find_attention_dip(shots)

        logger.info(
            "rhythmic_authority_applied",
            low=report.low_count,
            medium=report.medium_count,
            high=report.high_count,
            intensity_changes=report.intensity_changes,
            monotony_score=f"{report.monotony_score:.2f}",
        )

        return shots, report

    def _assign_intensities(self, shots: list[Shot]) -> list[Shot]:
        """Assign intensity to all shots."""
        result = []
        for shot in shots:
            intensity = infer_intensity(shot)
            result.append(shot.model_copy(update={"intensity": intensity}))
        return result

    def _enforce_ending(self, shots: list[Shot]) -> tuple[list[Shot], EndingIntent, float]:
        """Enforce ending intent on final shot."""
        if not shots:
            return shots, EndingIntent.RESOLUTION, 1.0

        final_shot = shots[-1]

        # Infer or keep existing intent
        if final_shot.ending_intent is None:
            intent = infer_ending_intent(final_shot, shots)
        else:
            intent = final_shot.ending_intent

        # Apply duration bias
        duration_bias = ENDING_INTENT_DURATION.get(intent, 1.0)
        new_duration = final_shot.duration_seconds * duration_bias

        # Clamp to reasonable range
        new_duration = max(2.0, min(10.0, new_duration))

        # Update final shot
        updated_final = final_shot.model_copy(update={
            "ending_intent": intent,
            "duration_seconds": new_duration,
            "intensity": BeatIntensity.HIGH if intent == EndingIntent.PROVOCATION else BeatIntensity.LOW,
        })

        return shots[:-1] + [updated_final], intent, duration_bias

    def _break_intensity_runs(self, shots: list[Shot]) -> tuple[list[Shot], int]:
        """Break runs of identical intensity."""
        if len(shots) < 3:
            return shots, 0

        result = list(shots)
        fixes = 0
        max_run = self.config.max_same_intensity_run

        i = 0
        while i < len(result) - max_run:
            # Check for run
            run_start = i
            run_intensity = result[i].intensity
            run_length = 1

            while i + run_length < len(result) and result[i + run_length].intensity == run_intensity:
                run_length += 1

            if run_length > max_run:
                # Break the run by alternating intensity
                for j in range(run_start + max_run, run_start + run_length):
                    shot = result[j]
                    if run_intensity == BeatIntensity.HIGH:
                        new_intensity = BeatIntensity.MEDIUM
                    elif run_intensity == BeatIntensity.LOW:
                        new_intensity = BeatIntensity.MEDIUM
                    else:
                        new_intensity = BeatIntensity.LOW if j % 2 == 0 else BeatIntensity.HIGH

                    result[j] = shot.model_copy(update={"intensity": new_intensity})
                    fixes += 1

            i += run_length

        return result, fixes

    def _enforce_duration_variation(self, shots: list[Shot]) -> tuple[list[Shot], int]:
        """Enforce ±40% duration variation between adjacent shots."""
        if len(shots) < 2:
            return shots, 0

        result = list(shots)
        fixes = 0
        min_var = self.config.min_duration_variation

        for i in range(1, len(result)):
            prev_dur = result[i - 1].duration_seconds
            curr_dur = result[i].duration_seconds

            # Calculate variation
            if prev_dur > 0:
                variation = abs(curr_dur - prev_dur) / prev_dur
            else:
                variation = 1.0

            if variation < min_var:
                # Need more contrast
                shot = result[i]

                # Decide whether to shorten or lengthen based on intensity
                if shot.intensity == BeatIntensity.HIGH:
                    # HIGH shots should be shorter
                    target = prev_dur * (1 - min_var - 0.1)
                    target = max(self.config.high_shot_min_duration, target)
                elif shot.intensity == BeatIntensity.LOW:
                    # LOW shots should be longer
                    target = prev_dur * (1 + min_var + 0.1)
                    target = min(self.config.low_shot_max_duration, target)
                else:
                    # MEDIUM - alternate
                    if prev_dur > 3.5:
                        target = prev_dur * (1 - min_var)
                    else:
                        target = prev_dur * (1 + min_var)

                if abs(target - curr_dur) > 0.3:  # Only if meaningful change
                    result[i] = shot.model_copy(update={"duration_seconds": target})
                    fixes += 1
                    logger.debug(
                        "duration_variation_added",
                        shot_id=shot.id,
                        original=curr_dur,
                        new=target,
                        variation=variation,
                    )

        return result, fixes

    def _tighten_emotion_shots(self, shots: list[Shot]) -> tuple[list[Shot], int]:
        """Tighten EMOTION shots: late entry, preserve peak, early exit."""
        result = []
        tightened = 0

        for shot in shots:
            if shot.purpose == ShotPurpose.EMOTION and shot.duration_seconds > 2.0:
                # Calculate new duration
                # Original: [----entry----][----peak----][----exit----]
                # New:      [--entry--][----peak----][--exit--]
                original = shot.duration_seconds

                # Trim entry and exit, preserve peak
                entry_trim = original * self.config.emotion_entry_trim
                exit_trim = original * self.config.emotion_exit_trim
                new_duration = original - entry_trim - exit_trim

                # Ensure minimum duration
                new_duration = max(1.5, new_duration)

                if new_duration < original * 0.9:  # At least 10% reduction
                    result.append(shot.model_copy(update={"duration_seconds": new_duration}))
                    tightened += 1
                    logger.debug(
                        "emotion_shot_tightened",
                        shot_id=shot.id,
                        original=original,
                        new=new_duration,
                        entry_trimmed=entry_trim,
                        exit_trimmed=exit_trim,
                    )
                else:
                    result.append(shot)
            else:
                result.append(shot)

        return result, tightened

    def _calculate_metrics(self, shots: list[Shot], report: RhythmReport) -> None:
        """Calculate rhythm metrics."""
        if not shots:
            return

        # Count intensities
        report.low_count = sum(1 for s in shots if s.intensity == BeatIntensity.LOW)
        report.medium_count = sum(1 for s in shots if s.intensity == BeatIntensity.MEDIUM)
        report.high_count = sum(1 for s in shots if s.intensity == BeatIntensity.HIGH)
        report.intensity_distribution = {
            BeatIntensity.LOW: report.low_count,
            BeatIntensity.MEDIUM: report.medium_count,
            BeatIntensity.HIGH: report.high_count,
        }

        # Duration stats
        durations = [s.duration_seconds for s in shots]
        report.average_duration = sum(durations) / len(durations)

        if len(durations) > 1:
            mean = report.average_duration
            report.duration_variance = sum((d - mean) ** 2 for d in durations) / len(durations)

            # Calculate average variation between adjacent shots
            variations = []
            for i in range(1, len(durations)):
                if durations[i - 1] > 0:
                    var = abs(durations[i] - durations[i - 1]) / durations[i - 1]
                    variations.append(var)
            report.duration_variation_achieved = sum(variations) / len(variations) if variations else 0.0
        else:
            report.duration_variance = 0.0
            report.duration_variation_achieved = 0.0

        # Count intensity changes and find max run
        changes = 0
        max_run = 1
        current_run = 1
        for i in range(1, len(shots)):
            if shots[i].intensity != shots[i - 1].intensity:
                changes += 1
                current_run = 1
            else:
                current_run += 1
                max_run = max(max_run, current_run)
        report.intensity_changes = changes
        report.max_intensity_run = max_run

        # Count attention dips (sequences of LOW intensity with uniform duration)
        dip_count = 0
        window_size = 3
        for i in range(len(shots) - window_size + 1):
            window = shots[i:i + window_size]
            low_count = sum(1 for s in window if s.intensity == BeatIntensity.LOW)
            if low_count >= window_size - 1:
                dip_count += 1
        report.attention_dip_count = dip_count

        # Monotony score (0 = varied, 1 = flat)
        max_changes = len(shots) - 1
        if max_changes > 0:
            report.monotony_score = 1.0 - (changes / max_changes)
        else:
            report.monotony_score = 0.0

    def _generate_rhythm_notes(self, shots: list[Shot], report: RhythmReport) -> list[str]:
        """Generate rhythm critique notes."""
        notes = []

        # Monotony assessment
        if report.monotony_score > 0.7:
            notes.append(f"Rhythm feels FLAT. Monotony score: {report.monotony_score:.0%}. "
                        "Add more intensity changes.")
        elif report.monotony_score > 0.5:
            notes.append(f"Rhythm is somewhat uniform ({report.monotony_score:.0%} monotony). "
                        "Consider more dramatic contrasts.")
        elif report.monotony_score < 0.3:
            notes.append(f"Rhythm is DYNAMIC. Good intensity variation ({report.intensity_changes} changes).")

        # Duration variance
        if report.duration_variance < 1.0:
            notes.append("Shot durations are too uniform. Vary more dramatically.")
        elif report.duration_variance > 10.0:
            notes.append("Strong duration variation. This creates visual rhythm.")

        # Intensity balance
        total = report.low_count + report.medium_count + report.high_count
        if total > 0:
            high_pct = report.high_count / total
            low_pct = report.low_count / total

            if high_pct > 0.5:
                notes.append(f"Too many HIGH intensity shots ({high_pct:.0%}). "
                            "The audience needs breathing room.")
            elif high_pct < 0.15:
                notes.append(f"Not enough HIGH intensity ({high_pct:.0%}). "
                            "Where are the peaks?")

            if low_pct < 0.1:
                notes.append("Almost no LOW intensity moments. Add stillness for contrast.")

        # Tempo assessment
        if report.average_duration > 5.0:
            notes.append(f"Tempo is SLOW (avg {report.average_duration:.1f}s). "
                        "Consider more aggressive cuts.")
        elif report.average_duration < 2.5:
            notes.append(f"Tempo is FAST (avg {report.average_duration:.1f}s). "
                        "Make sure it's intentional, not frantic.")

        # Ending assessment
        if report.ending_intent:
            notes.append(f"Ending intent: {report.ending_intent.value.upper()} "
                        f"(duration bias: {report.ending_duration_bias:.1f}x)")

        return notes

    def _find_attention_dip(self, shots: list[Shot]) -> str:
        """Find where attention likely dips in the sequence."""
        if len(shots) < 5:
            return "Sequence too short to analyze."

        # Look for runs of LOW/MEDIUM intensity with uniform duration
        worst_section = None
        worst_score = 0

        window_size = 4
        for i in range(len(shots) - window_size):
            window = shots[i:i + window_size]

            # Score: lower = more attention-losing
            intensity_score = sum(
                0 if s.intensity == BeatIntensity.HIGH else
                0.5 if s.intensity == BeatIntensity.MEDIUM else 1
                for s in window
            )

            # Check duration uniformity
            durations = [s.duration_seconds for s in window]
            mean_dur = sum(durations) / len(durations)
            uniformity = sum(abs(d - mean_dur) for d in durations) / len(durations)

            # Low uniformity (similar durations) = bad
            uniformity_penalty = 2 if uniformity < 0.5 else 0

            score = intensity_score + uniformity_penalty

            if score > worst_score:
                worst_score = score
                worst_section = (i, i + window_size)

        if worst_section:
            start, end = worst_section
            return (f"Attention likely dips around shots {start + 1}-{end} "
                   f"(low intensity, uniform pacing).")

        return "No obvious attention dip detected."


def assign_intensities_and_ending(shots: list[Shot]) -> list[Shot]:
    """Convenience function to assign intensities and ending intent."""
    if not shots:
        return shots

    result = []
    for i, shot in enumerate(shots):
        intensity = infer_intensity(shot)
        shot = shot.model_copy(update={"intensity": intensity})

        # Assign ending intent to final shot
        if i == len(shots) - 1:
            intent = infer_ending_intent(shot, shots)
            shot = shot.model_copy(update={"ending_intent": intent})

        result.append(shot)

    return result
