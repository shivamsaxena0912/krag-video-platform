"""Simulated founder feedback generator.

Generates realistic feedback based on persona characteristics
and video attempt metadata. Deterministic given a seed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from src.pilot.run import FeedbackDecision, FEEDBACK_FLAGS
from src.founder_simulation.personas import (
    SimulatedFounderPersona,
    FeedbackStyle,
    get_persona,
)


@dataclass
class SimulatedFeedback:
    """Generated feedback from a simulated persona."""

    decision: FeedbackDecision
    flags: list[str]
    notes: str
    persona_id: str

    # Debug info
    quality_score: float
    seed_used: str


def generate_feedback(
    persona: SimulatedFounderPersona | str,
    attempt_number: int,
    duration_seconds: float,
    sla_passed: bool,
    scenario_type: str,
    intent: str,
    brand_name: str | None = None,
    iteration_count: int = 1,
    seed: str | None = None,
) -> SimulatedFeedback:
    """Generate simulated founder feedback.

    Deterministic: same inputs + seed = same output.

    Args:
        persona: Persona instance or ID string.
        attempt_number: Which attempt this is (1, 2, 3...).
        duration_seconds: Video duration.
        sla_passed: Whether SLA constraints were met.
        scenario_type: Type of scenario (feature_launch, etc.).
        intent: Marketing intent (paid_ad, social_reel, etc.).
        brand_name: Brand name if provided.
        iteration_count: Number of iterations in this attempt.
        seed: Optional seed for determinism. If None, generates from inputs.

    Returns:
        SimulatedFeedback with decision, flags, and notes.
    """
    # Resolve persona
    if isinstance(persona, str):
        persona = get_persona(persona)

    # Generate seed if not provided
    if seed is None:
        seed_input = f"{persona.persona_id}:{attempt_number}:{duration_seconds}:{scenario_type}:{intent}"
        seed = hashlib.sha256(seed_input.encode()).hexdigest()[:16]

    # Calculate quality score based on persona preferences
    quality_score = _calculate_quality_score(
        persona=persona,
        duration_seconds=duration_seconds,
        sla_passed=sla_passed,
        attempt_number=attempt_number,
        iteration_count=iteration_count,
        seed=seed,
    )

    # Determine decision based on quality score and persona
    decision = _determine_decision(
        persona=persona,
        quality_score=quality_score,
        attempt_number=attempt_number,
        seed=seed,
    )

    # Select flags based on persona weights
    flags = _select_flags(
        persona=persona,
        decision=decision,
        duration_seconds=duration_seconds,
        seed=seed,
    )

    # Generate feedback notes
    notes = _generate_notes(
        persona=persona,
        decision=decision,
        flags=flags,
        attempt_number=attempt_number,
        duration_seconds=duration_seconds,
        brand_name=brand_name,
        seed=seed,
    )

    return SimulatedFeedback(
        decision=decision,
        flags=flags,
        notes=notes,
        persona_id=persona.persona_id,
        quality_score=quality_score,
        seed_used=seed,
    )


def _calculate_quality_score(
    persona: SimulatedFounderPersona,
    duration_seconds: float,
    sla_passed: bool,
    attempt_number: int,
    iteration_count: int,
    seed: str,
) -> float:
    """Calculate perceived quality score (0.0 to 1.0).

    This is the persona's subjective assessment of the video.
    """
    score = 0.5  # Base score

    # SLA compliance bonus
    if sla_passed:
        score += 0.15

    # Duration check
    if duration_seconds > persona.max_acceptable_duration_seconds:
        # Too long - penalize based on how much over
        overage = (duration_seconds - persona.max_acceptable_duration_seconds) / persona.max_acceptable_duration_seconds
        score -= min(0.3, overage * 0.2)
    elif duration_seconds < persona.min_acceptable_duration_seconds:
        # Too short - mild penalty
        score -= 0.1

    # Attempt number bonus (later attempts assumed to be better)
    attempt_bonus = min(0.2, (attempt_number - 1) * 0.1)
    score += attempt_bonus

    # Iteration bonus (more iterations = better refined)
    iteration_bonus = min(0.1, (iteration_count - 1) * 0.05)
    score += iteration_bonus

    # Add some deterministic variation based on seed
    seed_variation = _seed_to_float(seed, "quality") * 0.2 - 0.1
    score += seed_variation

    # Clamp to valid range
    return max(0.0, min(1.0, score))


def _determine_decision(
    persona: SimulatedFounderPersona,
    quality_score: float,
    attempt_number: int,
    seed: str,
) -> FeedbackDecision:
    """Determine the feedback decision based on quality and persona."""

    # Patience factor - more patient personas are more likely to approve
    patience_boost = persona.patience_level * 0.1

    # Attempt factor - more likely to approve on later attempts
    if attempt_number >= persona.approve_after_attempts:
        attempt_boost = 0.15
    else:
        attempt_boost = 0.0

    adjusted_score = quality_score + patience_boost + attempt_boost

    # Add small deterministic variation
    variation = _seed_to_float(seed, "decision") * 0.1

    final_score = adjusted_score + variation

    # Decision thresholds
    if final_score >= persona.quality_bar:
        return FeedbackDecision.APPROVE
    elif final_score >= persona.major_changes_threshold:
        return FeedbackDecision.MINOR_CHANGES
    else:
        return FeedbackDecision.MAJOR_CHANGES


def _select_flags(
    persona: SimulatedFounderPersona,
    decision: FeedbackDecision,
    duration_seconds: float,
    seed: str,
) -> list[str]:
    """Select feedback flags based on persona weights."""
    flags = []

    # Number of flags based on decision severity
    if decision == FeedbackDecision.APPROVE:
        max_flags = 0
    elif decision == FeedbackDecision.MINOR_CHANGES:
        max_flags = 2
    else:  # MAJOR_CHANGES
        max_flags = 4

    if max_flags == 0:
        return flags

    # Sort flags by weight for this persona
    weighted_flags = [
        (flag, persona.flag_weights.get(flag, 0.3))
        for flag in FEEDBACK_FLAGS
    ]
    weighted_flags.sort(key=lambda x: x[1], reverse=True)

    # Select top flags based on seed
    seed_value = _seed_to_float(seed, "flags")
    threshold = 0.5 - (seed_value * 0.3)  # Varies threshold based on seed

    for flag, weight in weighted_flags:
        if len(flags) >= max_flags:
            break
        if weight >= threshold:
            # Special handling for duration flags
            if flag == "too_long" and duration_seconds <= persona.max_acceptable_duration_seconds:
                continue
            if flag == "too_short" and duration_seconds >= persona.min_acceptable_duration_seconds:
                continue
            flags.append(flag)

    return flags


def _generate_notes(
    persona: SimulatedFounderPersona,
    decision: FeedbackDecision,
    flags: list[str],
    attempt_number: int,
    duration_seconds: float,
    brand_name: str | None,
    seed: str,
) -> str:
    """Generate feedback notes based on persona style."""

    # Select base phrase
    if decision == FeedbackDecision.APPROVE:
        phrases = persona.approval_phrases or ["Approved."]
    elif decision == FeedbackDecision.MINOR_CHANGES:
        phrases = persona.minor_changes_phrases or ["Minor changes needed."]
    else:
        phrases = persona.major_changes_phrases or ["Major changes needed."]

    # Deterministically select phrase
    phrase_index = int(_seed_to_float(seed, "phrase") * len(phrases))
    base_phrase = phrases[phrase_index % len(phrases)]

    # Add flag-specific details based on style
    if persona.feedback_style == FeedbackStyle.TERSE:
        if flags:
            flag_text = ", ".join(f.replace("_", " ") for f in flags[:2])
            return f"{base_phrase} Issues: {flag_text}."
        return base_phrase

    elif persona.feedback_style == FeedbackStyle.BLUNT:
        if flags:
            flag_details = []
            for flag in flags:
                flag_details.append(_flag_to_blunt_feedback(flag, duration_seconds))
            return f"{base_phrase} {' '.join(flag_details)}"
        return base_phrase

    elif persona.feedback_style == FeedbackStyle.DIPLOMATIC:
        if flags:
            flag_details = []
            for flag in flags:
                flag_details.append(_flag_to_diplomatic_feedback(flag))
            return f"{base_phrase} {' '.join(flag_details)}"
        return base_phrase

    else:  # DETAILED
        lines = [base_phrase]
        if flags:
            lines.append("Specific issues:")
            for flag in flags:
                lines.append(f"- {_flag_to_detailed_feedback(flag, duration_seconds)}")
        if attempt_number > 1:
            lines.append(f"This is attempt {attempt_number} - let's get this right.")
        return "\n".join(lines)


def _flag_to_blunt_feedback(flag: str, duration: float) -> str:
    """Convert flag to blunt feedback text."""
    mapping = {
        "hook_weak": "Hook doesn't grab. Fix it.",
        "too_long": f"At {duration:.0f}s, way too long. Cut it.",
        "too_short": "Too short. Need more substance.",
        "tone_mismatch": "Wrong tone. Doesn't sound like us.",
        "cta_unclear": "CTA is buried. Make it obvious.",
        "pacing_flat": "Pacing is boring. Add energy.",
        "pacing_rushed": "Too rushed. Slow down.",
        "message_unclear": "Message is lost. Clarify the point.",
        "ending_weak": "Ending is soft. Stronger finish.",
        "visuals_poor": "Visuals aren't good enough.",
        "audio_issues": "Audio quality is bad.",
        "off_brand": "This isn't on-brand.",
        "wrong_audience": "Wrong audience for this.",
    }
    return mapping.get(flag, f"{flag.replace('_', ' ').title()}.")


def _flag_to_diplomatic_feedback(flag: str) -> str:
    """Convert flag to diplomatic feedback text."""
    mapping = {
        "hook_weak": "I feel the opening could be more attention-grabbing.",
        "too_long": "The length feels a bit long for our audience.",
        "too_short": "I wonder if we could add a bit more depth.",
        "tone_mismatch": "The tone doesn't quite match our brand voice.",
        "cta_unclear": "The call-to-action could be more prominent.",
        "pacing_flat": "The rhythm feels a bit monotonous in places.",
        "pacing_rushed": "It might benefit from a slightly slower pace.",
        "message_unclear": "I'm not sure the key message comes through clearly.",
        "ending_weak": "The ending could be stronger.",
        "visuals_poor": "The visual quality could be improved.",
        "audio_issues": "There are some audio elements to address.",
        "off_brand": "This doesn't quite feel like our brand.",
        "wrong_audience": "This might not resonate with our target audience.",
    }
    return mapping.get(flag, f"Consider addressing: {flag.replace('_', ' ')}.")


def _flag_to_detailed_feedback(flag: str, duration: float) -> str:
    """Convert flag to detailed feedback text."""
    mapping = {
        "hook_weak": "The opening 3 seconds don't create enough urgency to stop the scroll",
        "too_long": f"At {duration:.0f} seconds, this exceeds our optimal duration for the platform",
        "too_short": "The video doesn't give enough time to develop the message properly",
        "tone_mismatch": "The voice and style don't align with our established brand guidelines",
        "cta_unclear": "Viewers won't know what action to take - the CTA needs to be unmissable",
        "pacing_flat": "The energy level stays too consistent - we need dynamic pacing",
        "pacing_rushed": "Information is coming too fast for viewers to absorb",
        "message_unclear": "The core value proposition isn't communicated clearly enough",
        "ending_weak": "The conclusion doesn't leave a strong impression or drive action",
        "visuals_poor": "The visual quality doesn't meet our standards for published content",
        "audio_issues": "Audio quality issues (levels, clarity, or mixing) need addressing",
        "off_brand": "This doesn't represent our brand identity as established in our guidelines",
        "wrong_audience": "The messaging seems aimed at a different audience than our target",
    }
    return mapping.get(flag, f"{flag.replace('_', ' ').title()}: needs attention")


def _seed_to_float(seed: str, salt: str) -> float:
    """Convert seed + salt to a float between 0 and 1.

    Deterministic: same seed + salt always returns same float.
    """
    combined = f"{seed}:{salt}"
    hash_bytes = hashlib.sha256(combined.encode()).digest()
    # Use first 4 bytes as an integer
    value = int.from_bytes(hash_bytes[:4], "big")
    # Normalize to 0-1 range
    return value / (2**32 - 1)
