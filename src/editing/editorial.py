"""Editorial authority module for enforcing edit discipline.

This module implements the "trimming-first" editorial philosophy:
- Every shot must declare a purpose
- Shots without purpose are removed
- Duration is reduced 15-20% before rendering
- Opening must hook (EMOTION/ATMOSPHERE only)
- Ending must resolve or provoke (EMOTION/TRANSITION only)

The goal: Make the edit feel shorter than it actually is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from src.common.logging import get_logger
from src.common.models import Shot, ShotRole, ShotPurpose

logger = get_logger(__name__)


# Purpose inference from shot role
ROLE_TO_PURPOSE_MAP = {
    ShotRole.ESTABLISHING: ShotPurpose.ATMOSPHERE,
    ShotRole.ACTION: ShotPurpose.EMOTION,
    ShotRole.REACTION: ShotPurpose.EMOTION,
    ShotRole.DETAIL: ShotPurpose.INFORMATION,
    ShotRole.TRANSITION: ShotPurpose.TRANSITION,
    ShotRole.MONTAGE: ShotPurpose.ATMOSPHERE,
    ShotRole.CLIMAX: ShotPurpose.EMOTION,
    ShotRole.RESOLUTION: ShotPurpose.EMOTION,
}

# Trimming priority (lower = cut first)
PURPOSE_TRIM_PRIORITY = {
    ShotPurpose.INFORMATION: 1,  # Cut first - facts can be inferred
    ShotPurpose.ATMOSPHERE: 2,   # Cut second - mood can be compressed
    ShotPurpose.TRANSITION: 3,   # Preserve for flow
    ShotPurpose.EMOTION: 4,      # Preserve most - this is the point
}


@dataclass
class EditorialConfig:
    """Configuration for editorial authority."""

    # Trimming targets
    target_reduction_percent: float = 0.175  # 17.5% (middle of 15-20%)
    min_reduction_percent: float = 0.15
    max_reduction_percent: float = 0.20

    # Duration constraints
    min_shot_duration: float = 1.5  # Minimum shot length after trimming
    max_shot_duration: float = 8.0  # Maximum before considering split

    # Opening rules (first N seconds)
    opening_duration: float = 5.0
    opening_allowed_purposes: tuple = (ShotPurpose.EMOTION, ShotPurpose.ATMOSPHERE)

    # Ending rules (last N seconds)
    ending_duration: float = 5.0
    ending_allowed_purposes: tuple = (ShotPurpose.EMOTION, ShotPurpose.TRANSITION)


@dataclass
class EditorialReport:
    """Report of editorial decisions made."""

    # Original state
    original_shot_count: int = 0
    original_duration: float = 0.0

    # After trimming
    trimmed_shot_count: int = 0
    trimmed_duration: float = 0.0
    reduction_percent: float = 0.0

    # Removed shots
    removed_no_purpose: list[str] = field(default_factory=list)
    removed_information: list[str] = field(default_factory=list)
    removed_atmosphere: list[str] = field(default_factory=list)
    shortened_shots: list[dict] = field(default_factory=list)

    # Violations fixed
    opening_violations_fixed: int = 0
    ending_violations_fixed: int = 0

    # Quality
    emotional_density: float = 0.0  # emotion_shots / total_duration
    information_density: float = 0.0

    # Notes
    director_notes: list[str] = field(default_factory=list)
    biggest_flaw: str = ""


def infer_purpose(shot: Shot) -> ShotPurpose:
    """Infer shot purpose from its role and content.

    Uses the role-to-purpose mapping as primary signal,
    with content analysis as fallback.
    """
    # If already assigned, return it
    if shot.purpose is not None:
        return shot.purpose

    # Infer from role
    role = shot.visual_spec.role if shot.visual_spec else ShotRole.ACTION
    if role in ROLE_TO_PURPOSE_MAP:
        return ROLE_TO_PURPOSE_MAP[role]

    # Content-based inference fallback
    desc_lower = shot.visual_description.lower() if shot.visual_description else ""

    # Check for emotional content
    emotion_signals = ["tears", "smile", "anger", "fear", "joy", "sorrow", "triumph",
                       "devastation", "hope", "despair", "embrace", "weep", "scream"]
    if any(signal in desc_lower for signal in emotion_signals):
        return ShotPurpose.EMOTION

    # Check for information content
    info_signals = ["map", "document", "text", "inscription", "chart", "diagram",
                    "explaining", "showing", "reveals", "indicates"]
    if any(signal in desc_lower for signal in info_signals):
        return ShotPurpose.INFORMATION

    # Check for atmosphere content
    atmo_signals = ["landscape", "sky", "establishing", "environment", "panorama",
                    "wide shot", "aerial", "sunset", "sunrise", "weather"]
    if any(signal in desc_lower for signal in atmo_signals):
        return ShotPurpose.ATMOSPHERE

    # Default based on shot type
    if shot.shot_type.value in ["extreme_wide", "wide"]:
        return ShotPurpose.ATMOSPHERE
    elif shot.shot_type.value in ["close_up", "extreme_close"]:
        return ShotPurpose.EMOTION

    return ShotPurpose.INFORMATION  # Conservative default


def assign_purposes(shots: list[Shot]) -> list[Shot]:
    """Assign purpose to all shots that lack one.

    Returns new list with purposes assigned.
    """
    result = []
    for shot in shots:
        if shot.purpose is None:
            purpose = infer_purpose(shot)
            shot = shot.model_copy(update={"purpose": purpose})
        result.append(shot)
    return result


class EditorialAuthority:
    """Enforces editorial discipline on shot sequences.

    The editorial authority makes the hard decisions:
    - What to cut
    - What to shorten
    - What to keep

    The goal is not completeness, but impact.
    """

    def __init__(self, config: EditorialConfig | None = None):
        self.config = config or EditorialConfig()

    def apply(self, shots: list[Shot]) -> tuple[list[Shot], EditorialReport]:
        """Apply editorial authority to shot sequence.

        Returns (trimmed_shots, report).
        """
        report = EditorialReport(
            original_shot_count=len(shots),
            original_duration=sum(s.duration_seconds for s in shots),
        )

        # Step 1: Assign purposes
        shots = assign_purposes(shots)

        # Step 2: Remove shots without valid purpose (shouldn't happen after assign)
        shots, removed = self._remove_purposeless(shots)
        report.removed_no_purpose = removed

        # Step 3: Enforce opening aggression
        shots, opening_fixes = self._enforce_opening(shots)
        report.opening_violations_fixed = opening_fixes

        # Step 4: Enforce ending decisiveness
        shots, ending_fixes = self._enforce_ending(shots)
        report.ending_violations_fixed = ending_fixes

        # Step 5: Trimming pass for 15-20% reduction
        shots, trim_details = self._trim_for_impact(shots, report.original_duration)
        report.removed_information = trim_details["removed_info"]
        report.removed_atmosphere = trim_details["removed_atmo"]
        report.shortened_shots = trim_details["shortened"]

        # Step 6: Resequence
        shots = self._resequence(shots)

        # Calculate final metrics
        report.trimmed_shot_count = len(shots)
        report.trimmed_duration = sum(s.duration_seconds for s in shots)
        report.reduction_percent = 1.0 - (report.trimmed_duration / report.original_duration) if report.original_duration > 0 else 0

        # Calculate densities
        emotion_duration = sum(s.duration_seconds for s in shots if s.purpose == ShotPurpose.EMOTION)
        info_duration = sum(s.duration_seconds for s in shots if s.purpose == ShotPurpose.INFORMATION)
        report.emotional_density = emotion_duration / report.trimmed_duration if report.trimmed_duration > 0 else 0
        report.information_density = info_duration / report.trimmed_duration if report.trimmed_duration > 0 else 0

        # Generate director notes
        report.director_notes = self._generate_notes(shots, report)
        report.biggest_flaw = self._identify_biggest_flaw(shots, report)

        logger.info(
            "editorial_authority_applied",
            original_shots=report.original_shot_count,
            trimmed_shots=report.trimmed_shot_count,
            original_duration=f"{report.original_duration:.1f}s",
            trimmed_duration=f"{report.trimmed_duration:.1f}s",
            reduction=f"{report.reduction_percent:.1%}",
        )

        return shots, report

    def _remove_purposeless(self, shots: list[Shot]) -> tuple[list[Shot], list[str]]:
        """Remove any shots that still lack purpose."""
        kept = []
        removed = []
        for shot in shots:
            if shot.purpose is None:
                removed.append(shot.id)
                logger.debug("removed_purposeless_shot", shot_id=shot.id)
            else:
                kept.append(shot)
        return kept, removed

    def _enforce_opening(self, shots: list[Shot]) -> tuple[list[Shot], int]:
        """Enforce opening aggression rules.

        First 5 seconds must be EMOTION or ATMOSPHERE only.
        INFORMATION shots in opening are converted or removed.
        """
        if not shots:
            return shots, 0

        opening_end = self.config.opening_duration
        cumulative = 0.0
        fixes = 0
        result = []

        for shot in shots:
            in_opening = cumulative < opening_end

            if in_opening and shot.purpose == ShotPurpose.INFORMATION:
                # Convert to ATMOSPHERE (we keep visuals, drop info expectation)
                shot = shot.model_copy(update={"purpose": ShotPurpose.ATMOSPHERE})
                fixes += 1
                logger.debug(
                    "opening_violation_fixed",
                    shot_id=shot.id,
                    action="converted_to_atmosphere",
                )

            result.append(shot)
            cumulative += shot.duration_seconds

        return result, fixes

    def _enforce_ending(self, shots: list[Shot]) -> tuple[list[Shot], int]:
        """Enforce ending decisiveness rules.

        Last 5 seconds must be EMOTION or TRANSITION only.
        INFORMATION shots in ending are converted or removed.
        """
        if not shots:
            return shots, 0

        total_duration = sum(s.duration_seconds for s in shots)
        ending_start = total_duration - self.config.ending_duration
        cumulative = 0.0
        fixes = 0
        result = []

        for shot in shots:
            in_ending = cumulative + shot.duration_seconds > ending_start

            if in_ending and shot.purpose == ShotPurpose.INFORMATION:
                # Convert to EMOTION (resolve rather than inform)
                shot = shot.model_copy(update={"purpose": ShotPurpose.EMOTION})
                fixes += 1
                logger.debug(
                    "ending_violation_fixed",
                    shot_id=shot.id,
                    action="converted_to_emotion",
                )
            elif in_ending and shot.purpose == ShotPurpose.ATMOSPHERE:
                # Atmosphere in ending is weak - convert to EMOTION
                shot = shot.model_copy(update={"purpose": ShotPurpose.EMOTION})
                fixes += 1

            result.append(shot)
            cumulative += shot.duration_seconds

        return result, fixes

    def _trim_for_impact(
        self,
        shots: list[Shot],
        original_duration: float,
    ) -> tuple[list[Shot], dict]:
        """Apply trimming pass for 15-20% reduction.

        Priority order:
        1. Remove INFORMATION shots (cut first)
        2. Remove ATMOSPHERE shots (cut second)
        3. Shorten remaining shots
        """
        target_duration = original_duration * (1 - self.config.target_reduction_percent)
        current_duration = sum(s.duration_seconds for s in shots)

        removed_info = []
        removed_atmo = []
        shortened = []

        result = list(shots)

        # Sort by trim priority (INFORMATION first)
        def trim_priority(shot: Shot) -> int:
            return PURPOSE_TRIM_PRIORITY.get(shot.purpose, 99)

        # Phase 1: Remove low-priority shots
        while current_duration > target_duration and len(result) > 3:
            # Find lowest priority shot
            sorted_by_priority = sorted(
                enumerate(result),
                key=lambda x: (trim_priority(x[1]), -x[1].duration_seconds)
            )

            # Try to remove lowest priority
            for idx, shot in sorted_by_priority:
                if shot.purpose == ShotPurpose.EMOTION:
                    continue  # Never remove emotion shots

                # Check if removal breaks opening/ending rules
                temp_result = result[:idx] + result[idx+1:]
                if self._check_structural_integrity(temp_result):
                    removed_duration = shot.duration_seconds
                    if shot.purpose == ShotPurpose.INFORMATION:
                        removed_info.append(shot.id)
                    elif shot.purpose == ShotPurpose.ATMOSPHERE:
                        removed_atmo.append(shot.id)

                    result = temp_result
                    current_duration -= removed_duration
                    logger.debug(
                        "shot_removed_for_trim",
                        shot_id=shot.id,
                        purpose=shot.purpose.value,
                        duration=removed_duration,
                    )
                    break
            else:
                # No more shots to remove
                break

        # Phase 2: Shorten remaining shots if needed
        while current_duration > target_duration:
            # Find longest non-EMOTION shot
            longest_idx = -1
            longest_dur = 0
            for idx, shot in enumerate(result):
                if shot.duration_seconds > longest_dur and shot.duration_seconds > self.config.min_shot_duration:
                    if shot.purpose != ShotPurpose.EMOTION or shot.duration_seconds > self.config.max_shot_duration:
                        longest_idx = idx
                        longest_dur = shot.duration_seconds

            if longest_idx < 0:
                break  # Nothing more to shorten

            shot = result[longest_idx]
            # Shorten by 20% or to min, whichever is larger
            new_duration = max(
                shot.duration_seconds * 0.8,
                self.config.min_shot_duration
            )
            reduction = shot.duration_seconds - new_duration

            if reduction > 0.1:  # Only if meaningful reduction
                shortened.append({
                    "shot_id": shot.id,
                    "original": shot.duration_seconds,
                    "new": new_duration,
                    "reduction": reduction,
                })
                result[longest_idx] = shot.model_copy(update={"duration_seconds": new_duration})
                current_duration -= reduction
            else:
                break

        return result, {
            "removed_info": removed_info,
            "removed_atmo": removed_atmo,
            "shortened": shortened,
        }

    def _check_structural_integrity(self, shots: list[Shot]) -> bool:
        """Check if shot sequence maintains structural integrity."""
        if len(shots) < 2:
            return False

        # Must have at least one EMOTION shot
        has_emotion = any(s.purpose == ShotPurpose.EMOTION for s in shots)
        return has_emotion

    def _resequence(self, shots: list[Shot]) -> list[Shot]:
        """Resequence shots after trimming."""
        result = []
        for i, shot in enumerate(shots):
            result.append(shot.model_copy(update={"sequence": i}))
        return result

    def _generate_notes(self, shots: list[Shot], report: EditorialReport) -> list[str]:
        """Generate director notes critiquing the cut."""
        notes = []

        # Pacing analysis
        avg_duration = report.trimmed_duration / len(shots) if shots else 0
        if avg_duration > 5.0:
            notes.append(f"Pacing feels slow. Average shot is {avg_duration:.1f}s - consider tightening to under 4s.")
        elif avg_duration < 2.0:
            notes.append(f"Pacing is aggressive at {avg_duration:.1f}s average. Some breathing room might help.")

        # Information density
        if report.information_density > 0.4:
            notes.append(f"Too much information ({report.information_density:.0%} of duration). The audience will tune out. Show, don't tell.")
        elif report.information_density < 0.1 and report.original_shot_count > 10:
            notes.append("Very low information content. Make sure the story is still being told.")

        # Emotional density
        if report.emotional_density < 0.3:
            notes.append(f"Emotional content is only {report.emotional_density:.0%}. Where's the heart? Add reaction shots.")
        elif report.emotional_density > 0.7:
            notes.append("Strong emotional density. This could land hard if the visuals deliver.")

        # Shot count analysis
        if report.trimmed_shot_count > 20 and avg_duration < 3:
            notes.append("Many quick cuts. Make sure there's rhythm, not just speed.")

        # Trimming effectiveness
        if report.reduction_percent < 0.10:
            notes.append(f"Only {report.reduction_percent:.0%} trimmed. Be more ruthless - if it doesn't serve, cut it.")
        elif report.reduction_percent > 0.25:
            notes.append(f"Aggressive trim at {report.reduction_percent:.0%}. Make sure narrative clarity survived.")

        # Structural notes
        if shots:
            first_purpose = shots[0].purpose
            last_purpose = shots[-1].purpose

            if first_purpose == ShotPurpose.INFORMATION:
                notes.append("Opening with information is a mistake. Hook emotionally first.")

            if last_purpose == ShotPurpose.INFORMATION:
                notes.append("Ending on information is weak. Close with emotion or provocative transition.")

        return notes

    def _identify_biggest_flaw(self, shots: list[Shot], report: EditorialReport) -> str:
        """Identify the single biggest editorial flaw."""
        flaws = []

        # Check for opening weakness
        if shots and shots[0].purpose != ShotPurpose.EMOTION:
            flaws.append(("opening_not_emotional", 3, "The opening doesn't grab. Lead with emotion."))

        # Check for ending weakness
        if shots and shots[-1].purpose not in (ShotPurpose.EMOTION, ShotPurpose.TRANSITION):
            flaws.append(("ending_weak", 3, "The ending doesn't land. It needs to resolve or provoke."))

        # Check pacing
        avg_dur = report.trimmed_duration / len(shots) if shots else 0
        if avg_dur > 6.0:
            flaws.append(("too_slow", 4, f"Pacing is glacial at {avg_dur:.1f}s average. Cut deeper."))
        elif avg_dur > 4.5:
            flaws.append(("slow", 2, f"Pacing drags at {avg_dur:.1f}s average. Tighten individual shots."))

        # Check info density
        if report.information_density > 0.5:
            flaws.append(("too_informational", 4, f"This is a lecture, not a story. {report.information_density:.0%} is information."))

        # Check emotion density
        if report.emotional_density < 0.2:
            flaws.append(("no_heart", 5, "There's no emotional center. Add human moments."))

        # Check trim effectiveness
        if report.reduction_percent < 0.08:
            flaws.append(("not_trimmed", 3, "The edit is flabby. Nothing was really cut."))

        if not flaws:
            return "The edit is solid. Minor polish only."

        # Return highest priority flaw
        flaws.sort(key=lambda x: -x[1])
        return flaws[0][2]


def generate_director_notes_file(
    shots: list[Shot],
    report: EditorialReport,
    output_path: str | Path,
    rhythm_report: "RhythmReport | None" = None,
) -> None:
    """Generate director_notes.txt file with editorial and rhythm critique."""
    from src.editing.rhythm import RhythmReport

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "=" * 60,
        "DIRECTOR'S NOTES - Edit Room Critique",
        "=" * 60,
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "--- VITAL STATS ---",
        f"Original: {report.original_shot_count} shots, {report.original_duration:.1f}s",
        f"After trim: {report.trimmed_shot_count} shots, {report.trimmed_duration:.1f}s",
        f"Reduction: {report.reduction_percent:.1%}",
        "",
        f"Emotional density: {report.emotional_density:.0%}",
        f"Information density: {report.information_density:.0%}",
        "",
        "--- WHAT WAS CUT ---",
    ]

    if report.removed_information:
        lines.append(f"INFORMATION shots removed: {len(report.removed_information)}")
    if report.removed_atmosphere:
        lines.append(f"ATMOSPHERE shots removed: {len(report.removed_atmosphere)}")
    if report.shortened_shots:
        total_saved = sum(s["reduction"] for s in report.shortened_shots)
        lines.append(f"Shots shortened: {len(report.shortened_shots)} (saved {total_saved:.1f}s)")

    lines.extend([
        "",
        "--- NOTES ON THE CUT ---",
    ])

    for note in report.director_notes:
        lines.append(f"• {note}")

    # Add rhythm section if available
    if rhythm_report:
        lines.extend([
            "",
            "--- RHYTHM ANALYSIS ---",
            f"Intensity distribution: LOW={rhythm_report.low_count}, "
            f"MEDIUM={rhythm_report.medium_count}, HIGH={rhythm_report.high_count}",
            f"Intensity changes: {rhythm_report.intensity_changes}",
            f"Monotony score: {rhythm_report.monotony_score:.0%} (0%=dynamic, 100%=flat)",
            f"Duration variance: {rhythm_report.duration_variance:.1f}",
            "",
        ])

        for note in rhythm_report.rhythm_notes:
            lines.append(f"• {note}")

        if rhythm_report.ending_intent:
            lines.extend([
                "",
                f"Ending intent: {rhythm_report.ending_intent.upper()}",
            ])

        lines.extend([
            "",
            "--- WHERE DID ATTENTION DIP? ---",
            rhythm_report.attention_dip_location,
        ])

        # Rhythm corrections
        if rhythm_report.intensity_runs_broken or rhythm_report.duration_variations_added or rhythm_report.emotion_shots_tightened:
            lines.extend([
                "",
                "--- RHYTHM CORRECTIONS MADE ---",
            ])
            if rhythm_report.intensity_runs_broken:
                lines.append(f"Intensity runs broken: {rhythm_report.intensity_runs_broken}")
            if rhythm_report.duration_variations_added:
                lines.append(f"Duration variations added: {rhythm_report.duration_variations_added}")
            if rhythm_report.emotion_shots_tightened:
                lines.append(f"EMOTION shots tightened: {rhythm_report.emotion_shots_tightened}")

    lines.extend([
        "",
        "--- THE BIGGEST PROBLEM ---",
        report.biggest_flaw,
        "",
        "--- SHOT BREAKDOWN BY PURPOSE ---",
    ])

    purpose_counts = {}
    for shot in shots:
        p = shot.purpose.value if shot.purpose else "none"
        purpose_counts[p] = purpose_counts.get(p, 0) + 1

    for purpose, count in sorted(purpose_counts.items()):
        lines.append(f"{purpose.upper()}: {count} shots")

    # Intensity breakdown
    if rhythm_report:
        lines.extend([
            "",
            "--- SHOT BREAKDOWN BY INTENSITY ---",
            f"LOW: {rhythm_report.low_count} shots",
            f"MEDIUM: {rhythm_report.medium_count} shots",
            f"HIGH: {rhythm_report.high_count} shots",
        ])

    lines.extend([
        "",
        "=" * 60,
        "Remember: Rhythm is contrast. Shorter is almost always better.",
        "=" * 60,
    ])

    path.write_text("\n".join(lines))
    logger.info("director_notes_generated", path=str(path))


@dataclass
class VersionComparison:
    """Comparison between two versions for improvement validation."""

    v1_shots: int
    v1_duration: float
    v1_emotion_score: float

    v2_shots: int
    v2_duration: float
    v2_emotion_score: float

    improvement_valid: bool
    failure_reason: str | None = None


def validate_version_improvement(
    v1_shots: list[Shot],
    v2_shots: list[Shot],
    v1_emotion_score: float,
    v2_emotion_score: float,
) -> VersionComparison:
    """Validate that v2 is an improvement over v1.

    v2 must have:
    - Fewer shots OR shorter total duration
    - Equal or higher emotional impact score

    If not, the refinement is marked as failed.
    """
    v1_dur = sum(s.duration_seconds for s in v1_shots)
    v2_dur = sum(s.duration_seconds for s in v2_shots)

    # Check structural improvement
    structural_improvement = (
        len(v2_shots) < len(v1_shots) or
        v2_dur < v1_dur
    )

    # Check emotional preservation
    emotional_preserved = v2_emotion_score >= v1_emotion_score - 0.1  # Allow small margin

    improvement_valid = structural_improvement and emotional_preserved

    failure_reason = None
    if not structural_improvement:
        failure_reason = f"v2 is not tighter: {len(v2_shots)} shots/{v2_dur:.1f}s vs v1's {len(v1_shots)} shots/{v1_dur:.1f}s"
    elif not emotional_preserved:
        failure_reason = f"v2 lost emotional impact: {v2_emotion_score:.1f} vs v1's {v1_emotion_score:.1f}"

    return VersionComparison(
        v1_shots=len(v1_shots),
        v1_duration=v1_dur,
        v1_emotion_score=v1_emotion_score,
        v2_shots=len(v2_shots),
        v2_duration=v2_dur,
        v2_emotion_score=v2_emotion_score,
        improvement_valid=improvement_valid,
        failure_reason=failure_reason,
    )
