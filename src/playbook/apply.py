"""Apply playbook entries to pipeline configs.

This module takes a Playbook and applies matching entries to
DirectorConfig, EditorialConfig, and RhythmConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.common.logging import get_logger
from src.agents.director import DirectorConfig
from src.editing.editorial import EditorialConfig
from src.editing.rhythm import RhythmConfig
from src.playbook.playbook import Playbook, PlaybookEntry

logger = get_logger(__name__)


@dataclass
class PlaybookApplication:
    """Result of applying a playbook."""

    # Input context
    scenario_id: str | None
    intent: str | None

    # Entries applied
    entries_matched: int = 0
    entries_applied: list[PlaybookEntry] = field(default_factory=list)

    # Adjustments made
    total_pacing_adjustment: float = 0.0
    total_trimming_adjustment: float = 0.0
    total_hook_adjustment: float = 0.0
    director_constraints: list[str] = field(default_factory=list)

    # Overrides applied
    duration_override: float | None = None
    shots_override: int | None = None


def apply_playbook(
    playbook: Playbook,
    director_config: DirectorConfig,
    editorial_config: EditorialConfig,
    rhythm_config: RhythmConfig,
    scenario_id: str | None = None,
    intent: str | None = None,
    confidence_threshold: float = 0.3,
) -> tuple[DirectorConfig, EditorialConfig, RhythmConfig, PlaybookApplication]:
    """Apply playbook entries to pipeline configs.

    Entries are applied if they match the scenario/intent context
    and have sufficient confidence.

    Args:
        playbook: The playbook to apply.
        director_config: Director config to modify.
        editorial_config: Editorial config to modify.
        rhythm_config: Rhythm config to modify.
        scenario_id: Current scenario ID for matching.
        intent: Current intent for matching.
        confidence_threshold: Minimum confidence to apply an entry.

    Returns:
        Tuple of (director, editorial, rhythm, application_result).
    """
    result = PlaybookApplication(
        scenario_id=scenario_id,
        intent=intent,
    )

    # Find matching entries
    matching = playbook.get_matching_entries(scenario_id, intent)
    result.entries_matched = len(matching)

    # Filter by confidence
    applicable = [e for e in matching if e.confidence >= confidence_threshold]

    if not applicable:
        logger.debug(
            "no_playbook_entries_applied",
            matched=len(matching),
            above_threshold=0,
        )
        return director_config, editorial_config, rhythm_config, result

    # Apply each entry
    for entry in applicable:
        director_config, editorial_config, rhythm_config = _apply_entry(
            entry, director_config, editorial_config, rhythm_config, result
        )
        result.entries_applied.append(entry)

    logger.info(
        "playbook_applied",
        playbook_id=playbook.playbook_id,
        entries_applied=len(result.entries_applied),
        pacing_adj=result.total_pacing_adjustment,
        trimming_adj=result.total_trimming_adjustment,
        hook_adj=result.total_hook_adjustment,
    )

    return director_config, editorial_config, rhythm_config, result


def _apply_entry(
    entry: PlaybookEntry,
    director: DirectorConfig,
    editorial: EditorialConfig,
    rhythm: RhythmConfig,
    result: PlaybookApplication,
) -> tuple[DirectorConfig, EditorialConfig, RhythmConfig]:
    """Apply a single playbook entry."""

    # === PACING ADJUSTMENT ===
    if entry.pacing_adjustment != 0.0:
        result.total_pacing_adjustment += entry.pacing_adjustment

        # Apply to rhythm config's emotion trimming
        new_entry_trim = rhythm.emotion_entry_trim + (entry.pacing_adjustment * 0.1)
        new_exit_trim = rhythm.emotion_exit_trim + (entry.pacing_adjustment * 0.1)

        # Clamp to valid range
        new_entry_trim = max(0.05, min(0.35, new_entry_trim))
        new_exit_trim = max(0.10, min(0.40, new_exit_trim))

        rhythm = RhythmConfig(
            **{
                **rhythm.__dict__,
                "emotion_entry_trim": new_entry_trim,
                "emotion_exit_trim": new_exit_trim,
            }
        )

    # === TRIMMING ADJUSTMENT ===
    if entry.trimming_adjustment != 0.0:
        result.total_trimming_adjustment += entry.trimming_adjustment

        # Apply to editorial config
        new_target = editorial.target_reduction_percent + entry.trimming_adjustment
        new_target = max(0.10, min(0.40, new_target))

        editorial = EditorialConfig(
            **{
                **editorial.__dict__,
                "target_reduction_percent": new_target,
            }
        )

    # === HOOK STRENGTH ADJUSTMENT ===
    if entry.hook_strength_adjustment != 0.0:
        result.total_hook_adjustment += entry.hook_strength_adjustment

        # Apply to director config's hook duration
        # Stronger hook = longer hook duration
        hook_delta = entry.hook_strength_adjustment * 2.0  # seconds
        new_hook = director.hook_duration + hook_delta
        new_hook = max(1.0, min(5.0, new_hook))

        director = DirectorConfig(
            **{
                **director.__dict__,
                "hook_duration": new_hook,
            }
        )

    # === DIRECTOR CONSTRAINTS ===
    if entry.director_constraints:
        for constraint in entry.director_constraints:
            if constraint not in result.director_constraints:
                result.director_constraints.append(constraint)

    # === DURATION OVERRIDES ===
    if entry.max_duration_override is not None:
        if result.duration_override is None or entry.max_duration_override < result.duration_override:
            result.duration_override = entry.max_duration_override
            director = DirectorConfig(
                **{
                    **director.__dict__,
                    "target_duration_seconds": entry.max_duration_override,
                }
            )

    # === SHOTS OVERRIDES ===
    if entry.max_shots_override is not None:
        if result.shots_override is None or entry.max_shots_override < result.shots_override:
            result.shots_override = entry.max_shots_override
            director = DirectorConfig(
                **{
                    **director.__dict__,
                    "max_shots_per_scene": entry.max_shots_override,
                }
            )

    return director, editorial, rhythm


def describe_application(application: PlaybookApplication) -> str:
    """Generate a human-readable description of what was applied."""
    if not application.entries_applied:
        return "No playbook entries were applied."

    lines = [
        f"Applied {len(application.entries_applied)} playbook entries:",
        "",
    ]

    for entry in application.entries_applied:
        lines.append(f"  - {entry.description} (confidence: {entry.confidence:.0%})")

    lines.append("")
    lines.append("Adjustments:")

    if application.total_pacing_adjustment != 0:
        direction = "faster" if application.total_pacing_adjustment > 0 else "slower"
        lines.append(f"  - Pacing: {direction} ({application.total_pacing_adjustment:+.2f})")

    if application.total_trimming_adjustment != 0:
        direction = "more" if application.total_trimming_adjustment > 0 else "less"
        lines.append(f"  - Trimming: {direction} aggressive ({application.total_trimming_adjustment:+.2%})")

    if application.total_hook_adjustment != 0:
        direction = "stronger" if application.total_hook_adjustment > 0 else "weaker"
        lines.append(f"  - Hook: {direction} ({application.total_hook_adjustment:+.2f})")

    if application.director_constraints:
        lines.append(f"  - Constraints: {', '.join(application.director_constraints)}")

    if application.duration_override:
        lines.append(f"  - Max duration: {application.duration_override:.1f}s")

    if application.shots_override:
        lines.append(f"  - Max shots: {application.shots_override}")

    return "\n".join(lines)
