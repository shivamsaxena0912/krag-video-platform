"""Fidelity selection policies for visual reference generation.

This module provides policies for selecting which shots should receive
REFERENCE fidelity (AI-generated images) vs PLACEHOLDER fidelity.

Key design principle: These policies only affect visual content,
never shot timing, count, or sequencing.

Default policy: Only generate REFERENCE visuals for a small subset
of key shots (hook, climax, establishing) with a cost cap.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.common.logging import get_logger
from src.common.models import Shot, ShotRole, ShotVisualSpec, VisualFidelityLevel

logger = get_logger(__name__)


@dataclass
class FidelityPolicyConfig:
    """Configuration for fidelity selection policy.

    Attributes:
        max_reference_shots: Maximum number of shots to mark REFERENCE
        cost_cap_usd: Maximum cost budget for REFERENCE generation
        include_hook: Include first shot of first scene (hook shot)
        include_climax: Include shots with CLIMAX role
        include_establishing: Include shots with ESTABLISHING role
        include_resolution: Include final resolution shot
        establishing_limit: Max number of ESTABLISHING shots (not all scenes)
    """

    max_reference_shots: int = 5
    cost_cap_usd: float = 0.50
    include_hook: bool = True
    include_climax: bool = True
    include_establishing: bool = True
    include_resolution: bool = True
    establishing_limit: int = 2  # Only first N establishing shots


class DefaultFidelityPolicy:
    """Default policy for selecting REFERENCE shots.

    Selects a minimal set of key shots for look-dev:
    - Hook shot (first shot of video)
    - Climax shots (peak dramatic moments)
    - First N establishing shots (scene context)
    - Final resolution shot (if present)

    All other shots remain PLACEHOLDER.
    """

    def __init__(self, config: FidelityPolicyConfig | None = None):
        self.config = config or FidelityPolicyConfig()

    def apply(self, shots: list[Shot]) -> list[Shot]:
        """Apply fidelity policy to shots.

        Modifies visual_spec.fidelity_level for selected shots.
        Returns NEW list of shots (immutable update).

        Args:
            shots: List of shots to process

        Returns:
            New list of shots with fidelity levels assigned
        """
        if not shots:
            return shots

        # Track which shots to mark as REFERENCE
        reference_indices: set[int] = set()
        establishing_count = 0

        for i, shot in enumerate(shots):
            if len(reference_indices) >= self.config.max_reference_shots:
                break

            role = shot.visual_spec.role if shot.visual_spec else ShotRole.ACTION

            # Hook shot (first shot of video)
            if self.config.include_hook and i == 0:
                reference_indices.add(i)
                logger.debug("fidelity_hook_shot", shot_id=shot.id, index=i)

            # Climax shots
            elif self.config.include_climax and role == ShotRole.CLIMAX:
                reference_indices.add(i)
                logger.debug("fidelity_climax_shot", shot_id=shot.id, index=i)

            # Establishing shots (limited)
            elif (
                self.config.include_establishing
                and role == ShotRole.ESTABLISHING
                and establishing_count < self.config.establishing_limit
            ):
                reference_indices.add(i)
                establishing_count += 1
                logger.debug("fidelity_establishing_shot", shot_id=shot.id, index=i)

        # Resolution shot (last shot if role is RESOLUTION)
        if (
            self.config.include_resolution
            and len(reference_indices) < self.config.max_reference_shots
            and shots
        ):
            last_shot = shots[-1]
            last_role = last_shot.visual_spec.role if last_shot.visual_spec else None
            if last_role == ShotRole.RESOLUTION:
                reference_indices.add(len(shots) - 1)
                logger.debug("fidelity_resolution_shot", shot_id=last_shot.id)

        # Build new shots list with updated fidelity
        updated_shots = []
        for i, shot in enumerate(shots):
            if i in reference_indices:
                # Mark as REFERENCE
                updated_shot = _update_shot_fidelity(shot, VisualFidelityLevel.REFERENCE)
            else:
                # Ensure PLACEHOLDER (explicit)
                updated_shot = _update_shot_fidelity(shot, VisualFidelityLevel.PLACEHOLDER)
            updated_shots.append(updated_shot)

        logger.info(
            "fidelity_policy_applied",
            total_shots=len(shots),
            reference_shots=len(reference_indices),
            reference_indices=sorted(reference_indices),
        )

        return updated_shots

    def preview(self, shots: list[Shot]) -> dict:
        """Preview policy without applying it.

        Useful for cost estimation before commitment.

        Returns:
            Summary of what would be marked REFERENCE
        """
        test_shots = self.apply(shots)

        reference_shots = []
        for i, shot in enumerate(test_shots):
            if shot.visual_spec and shot.visual_spec.fidelity_level == VisualFidelityLevel.REFERENCE:
                reference_shots.append({
                    "index": i,
                    "shot_id": shot.id,
                    "role": shot.visual_spec.role.value if shot.visual_spec else "unknown",
                })

        return {
            "total_shots": len(shots),
            "reference_count": len(reference_shots),
            "reference_shots": reference_shots,
            "estimated_cost_usd": len(reference_shots) * 0.04,  # Rough estimate
            "policy_config": {
                "max_reference_shots": self.config.max_reference_shots,
                "cost_cap_usd": self.config.cost_cap_usd,
            },
        }


def _update_shot_fidelity(shot: Shot, fidelity: VisualFidelityLevel) -> Shot:
    """Update a shot's fidelity level (immutable).

    Creates a new Shot with updated visual_spec.fidelity_level.
    """
    if shot.visual_spec is None:
        # Create minimal visual spec with fidelity
        new_spec = ShotVisualSpec(fidelity_level=fidelity)
    else:
        # Update existing spec's fidelity
        new_spec = shot.visual_spec.model_copy(update={"fidelity_level": fidelity})

    return shot.model_copy(update={"visual_spec": new_spec})


def apply_fidelity_by_role(
    shots: list[Shot],
    roles: list[ShotRole],
    max_per_role: int = 2,
) -> list[Shot]:
    """Apply REFERENCE fidelity to shots with specific roles.

    Simpler alternative to full policy - just mark by role.

    Args:
        shots: List of shots
        roles: List of roles to mark as REFERENCE
        max_per_role: Maximum shots per role to mark

    Returns:
        Updated shots list
    """
    role_counts: dict[ShotRole, int] = {role: 0 for role in roles}
    updated_shots = []

    for shot in shots:
        role = shot.visual_spec.role if shot.visual_spec else ShotRole.ACTION

        if role in roles and role_counts[role] < max_per_role:
            updated_shot = _update_shot_fidelity(shot, VisualFidelityLevel.REFERENCE)
            role_counts[role] += 1
        else:
            updated_shot = _update_shot_fidelity(shot, VisualFidelityLevel.PLACEHOLDER)

        updated_shots.append(updated_shot)

    return updated_shots


def mark_shots_reference(
    shots: list[Shot],
    shot_ids: list[str],
) -> list[Shot]:
    """Mark specific shots as REFERENCE by ID.

    Explicit selection - useful for expert requests.

    Args:
        shots: List of shots
        shot_ids: IDs of shots to mark REFERENCE

    Returns:
        Updated shots list
    """
    id_set = set(shot_ids)
    updated_shots = []

    for shot in shots:
        if shot.id in id_set:
            updated_shot = _update_shot_fidelity(shot, VisualFidelityLevel.REFERENCE)
        else:
            updated_shot = _update_shot_fidelity(shot, VisualFidelityLevel.PLACEHOLDER)
        updated_shots.append(updated_shot)

    return updated_shots
