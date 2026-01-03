#!/usr/bin/env python3
"""
KRAG Video Platform - Pilot Runner

Run real founder pilots with operational infrastructure:
- Pilot tracking and persistence
- Founder communication artifacts
- Runbook generation
- Outcome reporting
- Human and simulated feedback capture

Usage:
    # Start a new pilot
    python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch

    # Start with brand biasing
    python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch --brand acme

    # Start with founder_preview quality (default) - real DALL-E images for key shots
    python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch --render-quality founder_preview

    # Start with draft quality (fast, all placeholders)
    python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch --render-quality draft

    # Start with demo_only quality (all high-fidelity, capped at $1)
    python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch --render-quality demo_only

    # Continue an existing pilot (requires feedback on last attempt)
    python scripts/run_pilot.py --continue-pilot pilot_20240115_abc12345

    # Continue with --force to skip feedback check
    python scripts/run_pilot.py --continue-pilot pilot_20240115_abc12345 --force

    # Submit human feedback interactively
    python scripts/run_pilot.py --feedback pilot_20240115_abc12345 --attempt 1

    # Generate feedback template file
    python scripts/run_pilot.py --feedback-template pilot_20240115_abc12345 --attempt 1

    # Submit feedback from file
    python scripts/run_pilot.py --submit-feedback pilot_20240115_abc12345 --attempt 1 --file feedback.json

    # Submit simulated feedback
    python scripts/run_pilot.py --simulate-feedback pilot_20240115_abc12345 --attempt 1 --persona growth_marketer

    # List active pilots
    python scripts/run_pilot.py --list

    # List available personas
    python scripts/run_pilot.py --list-personas

    # Generate outcome report for completed pilot
    python scripts/run_pilot.py --report pilot_20240115_abc12345

Pilot Scenarios:
    feature_launch       New feature or product update
    funding_announcement Raise announcement
    problem_solution     Cold outreach positioning

Brand Presets:
    acme       Bold tech startup (bold tone, aggressive pacing)
    wellness   Health/wellness brand (empathetic tone, gentle pacing)
    enterprise B2B enterprise (professional tone, moderate pacing)

Simulated Founder Personas:
    speed_saas_founder          Fast-moving, wants videos yesterday
    cautious_first_time_founder Worried about brand, needs reassurance
    growth_marketer             Obsessed with CTAs and conversions
    technical_founder           Hates fluff, wants accuracy
    brand_sensitive_founder     Former agency, obsessed with brand consistency
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pilot import (
    PilotRun,
    PilotStatus,
    ApprovalOutcome,
    FeedbackMode,
    FeedbackDecision,
    FEEDBACK_FLAGS,
    PilotStore,
    create_pilot,
    PilotRunbookBuilder,
    generate_founder_artifacts,
    generate_pilot_outcome_report,
)
from src.founder import (
    get_scenario,
    SCENARIOS,
    TimeToValueMetrics,
)
from src.brand import (
    BrandContext,
    ToneProfile,
    ClaimConservativeness,
    create_brand_context,
    apply_brand_bias,
)
from src.marketing import (
    get_preset,
    get_configs_for_intent,
)
from src.playbook import (
    load_playbook,
    apply_playbook,
)
from src.founder_simulation import (
    generate_feedback as generate_simulated_feedback,
    list_personas,
    get_persona,
    PERSONAS,
)
from src.generation import (
    RenderQuality,
    get_quality_preset,
)
from src.common.logging import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)

# Default storage directory for pilots
PILOT_STORAGE_DIR = Path(__file__).parent.parent / "data" / "pilots"


def get_brand_presets() -> dict[str, BrandContext]:
    """Get available brand presets."""
    return {
        "acme": create_brand_context(
            brand_name="Acme Corp",
            tone=ToneProfile.BOLD,
            pacing_aggressiveness=0.8,
            claim_conservativeness=ClaimConservativeness.AGGRESSIVE,
        ),
        "wellness": create_brand_context(
            brand_name="Serenity Wellness",
            tone=ToneProfile.EMPATHETIC,
            pacing_aggressiveness=0.3,
            claim_conservativeness=ClaimConservativeness.CONSERVATIVE,
        ),
        "enterprise": create_brand_context(
            brand_name="Enterprise Solutions Inc",
            tone=ToneProfile.PROFESSIONAL,
            pacing_aggressiveness=0.5,
            claim_conservativeness=ClaimConservativeness.MODERATE,
        ),
    }


def list_pilots(store: PilotStore) -> None:
    """List all pilots."""
    pilots = store.list_pilots()

    if not pilots:
        print("\nNo pilots found.")
        return

    print("\n" + "=" * 90)
    print("PILOT LIST")
    print("=" * 90)
    print()
    print(f"{'Pilot ID':<30} {'Founder':<12} {'Company':<12} {'Status':<10} {'Outcome':<10} {'Feedback':<8}")
    print("-" * 90)

    for pilot in pilots:
        # Check feedback status
        missing = pilot.missing_feedback_attempts
        if missing:
            feedback_status = f"need #{missing[0]}"
        else:
            feedback_status = "ok"

        print(
            f"{pilot.pilot_id:<30} "
            f"{pilot.founder_name[:11]:<12} "
            f"{pilot.company_name[:11]:<12} "
            f"{pilot.status.value:<10} "
            f"{pilot.approval_outcome.value:<10} "
            f"{feedback_status:<8}"
        )

    print()
    print(f"Total: {len(pilots)} pilots")

    # Summary by status
    active = sum(1 for p in pilots if p.status == PilotStatus.ACTIVE)
    completed = sum(1 for p in pilots if p.status == PilotStatus.COMPLETED)
    paused = sum(1 for p in pilots if p.status == PilotStatus.PAUSED)

    print(f"Active: {active} | Completed: {completed} | Paused: {paused}")
    print()


def show_personas() -> None:
    """List all available simulated founder personas."""
    print("\n" + "=" * 70)
    print("SIMULATED FOUNDER PERSONAS")
    print("=" * 70)
    print()

    for persona_id, persona in PERSONAS.items():
        print(f"  {persona_id}")
        print(f"    {persona.name}")
        print(f"    {persona.description}")
        print(f"    Patience: {persona.patience_level:.0%} | Quality bar: {persona.quality_bar:.0%}")
        print(f"    Platform: {persona.platform_bias.value} | Style: {persona.feedback_style.value}")
        print()


def show_pilot_report(store: PilotStore, pilot_id: str) -> None:
    """Generate and display outcome report for a pilot."""
    pilot = store.load(pilot_id)

    if not pilot:
        print(f"\nPilot not found: {pilot_id}")
        return

    output_path = PILOT_STORAGE_DIR / f"{pilot_id}_outcome_report.md"
    report = generate_pilot_outcome_report(pilot, output_path)

    print(report)
    print(f"\nReport saved to: {output_path}")


# =============================================================================
# FEEDBACK CAPTURE
# =============================================================================

def capture_interactive_feedback(
    store: PilotStore,
    pilot_id: str,
    attempt_number: int,
) -> bool:
    """Capture feedback interactively from the user.

    Args:
        store: Pilot storage.
        pilot_id: The pilot ID.
        attempt_number: Which attempt to add feedback to.

    Returns:
        True if feedback was captured successfully.
    """
    pilot = store.load(pilot_id)
    if not pilot:
        print(f"\nPilot not found: {pilot_id}")
        return False

    attempt = pilot.get_attempt(attempt_number)
    if not attempt:
        print(f"\nAttempt {attempt_number} not found in pilot {pilot_id}")
        return False

    if attempt.has_feedback:
        print(f"\nAttempt {attempt_number} already has feedback recorded.")
        print(f"Decision: {attempt.feedback_decision.value if attempt.feedback_decision else attempt.feedback_level}")
        return False

    # Show attempt info
    print("\n" + "=" * 60)
    print(f"FEEDBACK FOR ATTEMPT #{attempt_number}")
    print("=" * 60)
    print(f"   Pilot ID: {pilot.pilot_id}")
    print(f"   Founder: {pilot.founder_name}")
    print(f"   Company: {pilot.company_name}")
    print(f"   Scenario: {pilot.scenario_type}")
    print()
    print(f"   Video: {attempt.video_path}")
    print(f"   Review Pack: {attempt.review_pack_path}")
    print(f"   Duration: ~{attempt.time_to_first_cut_seconds:.1f}s")
    print(f"   Iterations: {attempt.iteration_count}")
    print(f"   SLA: {'PASSED' if attempt.sla_passed else 'FAILED'}")
    print()

    # Get decision
    print("DECISION (enter number):")
    print("  1. APPROVE - Ready to publish")
    print("  2. MINOR_CHANGES - Small tweaks needed")
    print("  3. MAJOR_CHANGES - Significant rework needed")
    print()

    while True:
        choice = input("Decision [1/2/3]: ").strip()
        if choice == "1":
            decision = FeedbackDecision.APPROVE
            break
        elif choice == "2":
            decision = FeedbackDecision.MINOR_CHANGES
            break
        elif choice == "3":
            decision = FeedbackDecision.MAJOR_CHANGES
            break
        else:
            print("Please enter 1, 2, or 3")

    # Get flags (only for non-approve)
    flags = []
    if decision != FeedbackDecision.APPROVE:
        print()
        print("FLAGS (enter numbers separated by commas, or press Enter to skip):")
        for i, flag in enumerate(FEEDBACK_FLAGS, 1):
            print(f"  {i:2}. {flag}")
        print()

        flag_input = input("Flags: ").strip()
        if flag_input:
            try:
                indices = [int(x.strip()) for x in flag_input.split(",")]
                flags = [FEEDBACK_FLAGS[i - 1] for i in indices if 1 <= i <= len(FEEDBACK_FLAGS)]
            except (ValueError, IndexError):
                print("Invalid flag selection, skipping flags")

    # Get notes
    print()
    print("NOTES (1-3 lines, blunt feedback. Press Enter twice to finish):")
    notes_lines = []
    while True:
        line = input()
        if not line:
            break
        notes_lines.append(line)
        if len(notes_lines) >= 3:
            break

    notes = "\n".join(notes_lines)

    # Record feedback
    pilot.record_feedback(
        attempt_number=attempt_number,
        decision=decision,
        flags=flags,
        notes=notes,
        mode=FeedbackMode.HUMAN,
    )

    # Save
    store.save(pilot)

    print()
    print("=" * 60)
    print("FEEDBACK RECORDED")
    print("=" * 60)
    print(f"   Decision: {decision.value}")
    if flags:
        print(f"   Flags: {', '.join(flags)}")
    if notes:
        print(f"   Notes: {notes[:50]}...")
    print()

    if decision == FeedbackDecision.APPROVE:
        print("   Pilot marked as APPROVED!")
    else:
        print(f"   Run: python scripts/run_pilot.py --continue-pilot {pilot_id}")

    return True


def generate_feedback_template(
    store: PilotStore,
    pilot_id: str,
    attempt_number: int,
) -> bool:
    """Generate a feedback template JSON file.

    Args:
        store: Pilot storage.
        pilot_id: The pilot ID.
        attempt_number: Which attempt to generate template for.

    Returns:
        True if template was generated.
    """
    pilot = store.load(pilot_id)
    if not pilot:
        print(f"\nPilot not found: {pilot_id}")
        return False

    attempt = pilot.get_attempt(attempt_number)
    if not attempt:
        print(f"\nAttempt {attempt_number} not found in pilot {pilot_id}")
        return False

    # Create template
    template = {
        "_instructions": "Fill in this template and submit with --submit-feedback",
        "_pilot_id": pilot_id,
        "_attempt_number": attempt_number,
        "_attempt_info": {
            "video_path": attempt.video_path,
            "review_pack_path": attempt.review_pack_path,
            "duration_seconds": attempt.time_to_first_cut_seconds,
            "iterations": attempt.iteration_count,
            "sla_passed": attempt.sla_passed,
        },
        "decision": "APPROVE | MINOR_CHANGES | MAJOR_CHANGES",
        "flags": {
            "_available": FEEDBACK_FLAGS,
            "_selected": [],
        },
        "notes": "Your blunt feedback here (1-3 sentences)",
    }

    # Write to review pack directory or pilot directory
    if attempt.review_pack_path:
        output_dir = Path(attempt.review_pack_path)
    else:
        output_dir = PILOT_STORAGE_DIR / pilot_id

    output_dir.mkdir(parents=True, exist_ok=True)
    template_path = output_dir / f"feedback_template_attempt_{attempt_number}.json"

    with open(template_path, "w") as f:
        json.dump(template, f, indent=2)

    print(f"\nFeedback template generated: {template_path}")
    print()
    print("Edit the template and submit with:")
    print(f"  python scripts/run_pilot.py --submit-feedback {pilot_id} --attempt {attempt_number} --file {template_path}")

    return True


def submit_feedback_from_file(
    store: PilotStore,
    pilot_id: str,
    attempt_number: int,
    file_path: Path,
) -> bool:
    """Submit feedback from a JSON file.

    Args:
        store: Pilot storage.
        pilot_id: The pilot ID.
        attempt_number: Which attempt to add feedback to.
        file_path: Path to the feedback JSON file.

    Returns:
        True if feedback was submitted successfully.
    """
    pilot = store.load(pilot_id)
    if not pilot:
        print(f"\nPilot not found: {pilot_id}")
        return False

    attempt = pilot.get_attempt(attempt_number)
    if not attempt:
        print(f"\nAttempt {attempt_number} not found in pilot {pilot_id}")
        return False

    if not file_path.exists():
        print(f"\nFeedback file not found: {file_path}")
        return False

    # Load and validate
    with open(file_path) as f:
        data = json.load(f)

    # Validate decision
    decision_str = data.get("decision", "").upper()
    if decision_str not in ("APPROVE", "MINOR_CHANGES", "MAJOR_CHANGES"):
        print(f"\nInvalid decision: {decision_str}")
        print("Must be one of: APPROVE, MINOR_CHANGES, MAJOR_CHANGES")
        return False

    decision = FeedbackDecision(decision_str.lower())

    # Get flags
    flags_data = data.get("flags", {})
    if isinstance(flags_data, dict):
        flags = flags_data.get("_selected", [])
    elif isinstance(flags_data, list):
        flags = flags_data
    else:
        flags = []

    # Validate flags
    invalid_flags = [f for f in flags if f not in FEEDBACK_FLAGS]
    if invalid_flags:
        print(f"\nWarning: Unknown flags will be ignored: {invalid_flags}")
        flags = [f for f in flags if f in FEEDBACK_FLAGS]

    # Get notes
    notes = data.get("notes", "")

    # Record feedback
    pilot.record_feedback(
        attempt_number=attempt_number,
        decision=decision,
        flags=flags,
        notes=notes,
        mode=FeedbackMode.HUMAN,
    )

    store.save(pilot)

    print()
    print("=" * 60)
    print("FEEDBACK SUBMITTED FROM FILE")
    print("=" * 60)
    print(f"   Pilot: {pilot_id}")
    print(f"   Attempt: {attempt_number}")
    print(f"   Decision: {decision.value}")
    if flags:
        print(f"   Flags: {', '.join(flags)}")
    print()

    if decision == FeedbackDecision.APPROVE:
        print("   Pilot marked as APPROVED!")

    return True


def simulate_feedback(
    store: PilotStore,
    pilot_id: str,
    attempt_number: int,
    persona_id: str,
) -> bool:
    """Generate simulated feedback from a persona.

    Args:
        store: Pilot storage.
        pilot_id: The pilot ID.
        attempt_number: Which attempt to add feedback to.
        persona_id: Which persona to use.

    Returns:
        True if feedback was generated successfully.
    """
    pilot = store.load(pilot_id)
    if not pilot:
        print(f"\nPilot not found: {pilot_id}")
        return False

    attempt = pilot.get_attempt(attempt_number)
    if not attempt:
        print(f"\nAttempt {attempt_number} not found in pilot {pilot_id}")
        return False

    if attempt.has_feedback:
        print(f"\nAttempt {attempt_number} already has feedback recorded.")
        return False

    # Get persona
    try:
        persona = get_persona(persona_id)
    except ValueError as e:
        print(f"\n{e}")
        print("\nUse --list-personas to see available personas")
        return False

    # Get scenario info
    scenario = get_scenario(pilot.scenario_type)
    brand_name = pilot.brand_context.get("brand_name") if pilot.brand_context else None

    # Generate feedback
    simulated = generate_simulated_feedback(
        persona=persona,
        attempt_number=attempt_number,
        duration_seconds=attempt.time_to_first_cut_seconds or 30.0,
        sla_passed=attempt.sla_passed,
        scenario_type=pilot.scenario_type,
        intent=scenario.marketing_intent.value,
        brand_name=brand_name,
        iteration_count=attempt.iteration_count,
    )

    # Record feedback
    pilot.record_feedback(
        attempt_number=attempt_number,
        decision=simulated.decision,
        flags=simulated.flags,
        notes=simulated.notes,
        mode=FeedbackMode.SIMULATED,
        persona=persona_id,
    )

    store.save(pilot)

    print()
    print("=" * 60)
    print("SIMULATED FEEDBACK GENERATED")
    print("=" * 60)
    print(f"   Persona: {persona.name}")
    print(f"   Decision: {simulated.decision.value}")
    if simulated.flags:
        print(f"   Flags: {', '.join(simulated.flags)}")
    print()
    print("   Notes:")
    for line in simulated.notes.split("\n"):
        print(f"     {line}")
    print()

    if simulated.decision == FeedbackDecision.APPROVE:
        print("   Pilot marked as APPROVED!")
    else:
        print(f"   Continue with: python scripts/run_pilot.py --continue-pilot {pilot_id}")

    return True


# =============================================================================
# PILOT OPERATIONS
# =============================================================================

async def run_pilot_attempt(
    pilot: PilotRun,
    store: PilotStore,
    brand: BrandContext | None = None,
    playbook_path: Path | None = None,
    render_quality: RenderQuality = RenderQuality.FOUNDER_PREVIEW,
) -> bool:
    """Run a single attempt within a pilot.

    Args:
        pilot: The pilot to run an attempt for.
        store: Pilot storage.
        brand: Optional brand context.
        playbook_path: Optional playbook path.
        render_quality: Render quality preset (draft, founder_preview, demo_only).

    Returns:
        True if attempt was successful.
    """
    # Check if we can add more attempts
    if not pilot.can_add_attempt:
        print(f"\nCannot add more attempts. Max attempts ({pilot.max_attempts}) reached.")
        return False

    attempt_number = pilot.attempt_count + 1
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Get render quality preset
    quality_preset = get_quality_preset(render_quality)
    reference_backend = quality_preset.get("reference_backend", "stub")
    cost_cap = quality_preset.get("reference_cost_cap", 0.5)

    print("\n" + "=" * 60)
    print(f"PILOT ATTEMPT #{attempt_number}")
    print("=" * 60)
    print(f"   Pilot ID: {pilot.pilot_id}")
    print(f"   Founder: {pilot.founder_name}")
    print(f"   Company: {pilot.company_name}")
    print(f"   Scenario: {pilot.scenario_type}")
    if brand:
        print(f"   Brand: {brand.brand_name} ({brand.tone.value})")
    print(f"   Render Quality: {render_quality.value} (backend: {reference_backend}, cost cap: ${cost_cap:.2f})")
    print()

    # Get scenario and intent
    scenario = get_scenario(pilot.scenario_type)
    intent = scenario.marketing_intent
    preset = get_preset(intent)

    # Get configs
    director_config, editorial_config, rhythm_config = get_configs_for_intent(intent)

    # Apply brand biasing if provided
    if brand:
        biased = apply_brand_bias(
            brand=brand,
            intent=intent,
            base_director_config=director_config,
            base_editorial_config=editorial_config,
            base_rhythm_config=rhythm_config,
        )
        director_config = biased.director_config
        editorial_config = biased.editorial_config
        rhythm_config = biased.rhythm_config
        print(f"   Applied {len(biased.biases_applied)} brand biases")

    # Apply playbook if provided
    if playbook_path and playbook_path.exists():
        playbook = load_playbook(playbook_path)
        director_config, editorial_config, rhythm_config, app = apply_playbook(
            playbook=playbook,
            director_config=director_config,
            editorial_config=editorial_config,
            rhythm_config=rhythm_config,
            scenario_id=scenario.scenario_id,
            intent=intent.value,
        )
        print(f"   Applied {len(app.entries_applied)} playbook entries")

    # Create output directory
    output_dir = PILOT_STORAGE_DIR / pilot.pilot_id / f"attempt_{attempt_number}_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Start metrics
    metrics = TimeToValueMetrics()

    # In a real implementation, this would run the full pipeline.
    # For now, we simulate a successful run.
    print("\n   Running pipeline...")
    print("   (In production, this runs the full video generation pipeline)")

    # Simulate time to first cut
    import time
    start_time = time.time()

    # Simulate some work
    await asyncio.sleep(0.5)

    # Record metrics
    metrics.record_first_cut()
    ttfc = metrics.time_to_first_cut_seconds or 0.0

    # Simulate SLA check
    sla_passed = True
    sla_violations: list[str] = []

    # Add the attempt
    attempt = pilot.add_attempt(
        video_path=str(output_dir / "draft_v1.mp4"),
        review_pack_path=str(output_dir / "review_pack"),
        time_to_first_cut_seconds=ttfc,
        iteration_count=1,
        total_cost_dollars=0.05,  # Simulated cost
        sla_passed=sla_passed,
        sla_violations=sla_violations,
    )

    # Save pilot state
    store.save(pilot)

    # Generate founder artifacts in output directory
    artifacts = generate_founder_artifacts(pilot, output_dir)

    print(f"\n   Attempt #{attempt_number} complete!")
    print(f"   Time to first cut: {ttfc:.1f}s")
    print(f"   SLA: {'PASSED' if sla_passed else 'FAILED'}")
    print(f"\n   Artifacts generated:")
    print(f"     - {artifacts.instructions_path}")
    print(f"     - {artifacts.expectations_path}")
    print(f"     - {artifacts.criteria_path}")

    print(f"\n   Output directory: {output_dir}")
    print()
    print("   NEXT STEP: Submit feedback for this attempt:")
    print(f"     Human:     python scripts/run_pilot.py --feedback {pilot.pilot_id} --attempt {attempt_number}")
    print(f"     Simulated: python scripts/run_pilot.py --simulate-feedback {pilot.pilot_id} --attempt {attempt_number} --persona growth_marketer")

    return True


async def start_new_pilot(
    founder_name: str,
    company_name: str,
    scenario_type: str,
    brand: BrandContext | None = None,
    playbook_path: Path | None = None,
    store: PilotStore | None = None,
    render_quality: RenderQuality = RenderQuality.FOUNDER_PREVIEW,
) -> PilotRun:
    """Start a new pilot engagement."""
    store = store or PilotStore(PILOT_STORAGE_DIR)

    # Create pilot
    pilot = create_pilot(
        founder_name=founder_name,
        company_name=company_name,
        scenario_type=scenario_type,
        brand_context=brand.to_dict() if brand else {},
        playbook_version=str(playbook_path) if playbook_path else None,
    )

    # Create pilot directory
    pilot_dir = PILOT_STORAGE_DIR / pilot.pilot_id
    pilot_dir.mkdir(parents=True, exist_ok=True)

    # Generate runbook
    runbook_path = pilot_dir / "pilot_runbook.txt"
    PilotRunbookBuilder(pilot).build(runbook_path)

    # Generate initial founder artifacts
    generate_founder_artifacts(pilot, pilot_dir)

    # Save pilot
    store.save(pilot)

    print("\n" + "=" * 60)
    print("NEW PILOT CREATED")
    print("=" * 60)
    print(f"   Pilot ID: {pilot.pilot_id}")
    print(f"   Founder: {founder_name}")
    print(f"   Company: {company_name}")
    print(f"   Scenario: {scenario_type}")
    print()
    print(f"   Pilot directory: {pilot_dir}")
    print()
    print("   Generated files:")
    print("     - pilot_runbook.txt")
    print("     - founder_instructions.txt")
    print("     - what_to_expect.txt")
    print("     - approval_criteria.txt")
    print()

    # Run first attempt
    print("Starting first attempt...")
    await run_pilot_attempt(pilot, store, brand, playbook_path, render_quality)

    return pilot


async def continue_pilot(
    pilot_id: str,
    store: PilotStore | None = None,
    force: bool = False,
    render_quality: RenderQuality = RenderQuality.FOUNDER_PREVIEW,
) -> bool:
    """Continue an existing pilot with a new attempt.

    Args:
        pilot_id: The pilot ID to continue.
        store: Optional pilot store.
        force: Skip feedback check if True.
        render_quality: Render quality preset.

    Returns:
        True if successful.
    """
    store = store or PilotStore(PILOT_STORAGE_DIR)

    pilot = store.load(pilot_id)
    if not pilot:
        print(f"\nPilot not found: {pilot_id}")
        return False

    if pilot.status != PilotStatus.ACTIVE:
        print(f"\nPilot is not active. Status: {pilot.status.value}")
        return False

    # ENFORCE: Check for feedback on latest attempt
    if not force and not pilot.latest_has_feedback:
        latest = pilot.latest_attempt
        print()
        print("=" * 60)
        print("FEEDBACK REQUIRED")
        print("=" * 60)
        print()
        print(f"   Attempt #{latest.attempt_number} has no feedback recorded.")
        print()
        print("   The pilot workflow requires feedback before continuing:")
        print("     attempt -> feedback -> next attempt -> feedback -> ...")
        print()
        print("   Submit feedback first:")
        print(f"     Human:     python scripts/run_pilot.py --feedback {pilot_id} --attempt {latest.attempt_number}")
        print(f"     Simulated: python scripts/run_pilot.py --simulate-feedback {pilot_id} --attempt {latest.attempt_number} --persona growth_marketer")
        print()
        print("   Or use --force to skip this check (not recommended):")
        print(f"     python scripts/run_pilot.py --continue-pilot {pilot_id} --force")
        print()
        return False

    # Reconstruct brand context if saved
    brand = None
    if pilot.brand_context:
        brand = BrandContext.from_dict(pilot.brand_context)

    # Reconstruct playbook path if saved
    playbook_path = None
    if pilot.playbook_version:
        playbook_path = Path(pilot.playbook_version)
        if not playbook_path.exists():
            playbook_path = None

    return await run_pilot_attempt(pilot, store, brand, playbook_path, render_quality)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="KRAG Video Platform - Pilot Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a new pilot
  python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch

  # Continue an existing pilot
  python scripts/run_pilot.py --continue-pilot pilot_20240115_abc12345

  # Submit human feedback interactively
  python scripts/run_pilot.py --feedback pilot_20240115_abc12345 --attempt 1

  # Submit simulated feedback
  python scripts/run_pilot.py --simulate-feedback pilot_20240115_abc12345 --attempt 1 --persona growth_marketer

  # Generate outcome report
  python scripts/run_pilot.py --report pilot_20240115_abc12345
""",
    )

    # New pilot arguments
    parser.add_argument("--founder", type=str, help="Founder name (required for new pilot)")
    parser.add_argument("--company", type=str, help="Company name (required for new pilot)")
    parser.add_argument("--scenario", type=str, choices=list(SCENARIOS.keys()), help="Scenario type")
    parser.add_argument("--brand", type=str, choices=["acme", "wellness", "enterprise"], help="Brand preset")
    parser.add_argument("--playbook", type=str, help="Path to playbook JSON file")
    parser.add_argument(
        "--render-quality",
        type=str,
        choices=["draft", "founder_preview", "demo_only"],
        default="founder_preview",
        help="Render quality preset (default: founder_preview)",
    )

    # Continue pilot
    parser.add_argument("--continue-pilot", type=str, metavar="PILOT_ID", help="Continue an existing pilot")
    parser.add_argument("--force", action="store_true", help="Force continue without feedback check")

    # Feedback capture
    parser.add_argument("--feedback", type=str, metavar="PILOT_ID", help="Submit feedback interactively")
    parser.add_argument("--feedback-template", type=str, metavar="PILOT_ID", help="Generate feedback template file")
    parser.add_argument("--submit-feedback", type=str, metavar="PILOT_ID", help="Submit feedback from file")
    parser.add_argument("--simulate-feedback", type=str, metavar="PILOT_ID", help="Generate simulated feedback")
    parser.add_argument("--attempt", type=int, help="Attempt number for feedback commands")
    parser.add_argument("--file", type=str, help="Path to feedback JSON file")
    parser.add_argument("--persona", type=str, choices=list_personas(), help="Persona for simulated feedback")

    # Listing and reports
    parser.add_argument("--list", action="store_true", help="List all pilots")
    parser.add_argument("--list-personas", action="store_true", help="List available simulated personas")
    parser.add_argument("--report", type=str, metavar="PILOT_ID", help="Generate outcome report")

    args = parser.parse_args()

    # Initialize store
    store = PilotStore(PILOT_STORAGE_DIR)

    # Handle commands
    if args.list:
        list_pilots(store)
        return

    if args.list_personas:
        show_personas()
        return

    if args.report:
        show_pilot_report(store, args.report)
        return

    # Feedback commands
    if args.feedback:
        if not args.attempt:
            print("\n--attempt is required with --feedback")
            sys.exit(1)
        success = capture_interactive_feedback(store, args.feedback, args.attempt)
        sys.exit(0 if success else 1)

    if args.feedback_template:
        if not args.attempt:
            print("\n--attempt is required with --feedback-template")
            sys.exit(1)
        success = generate_feedback_template(store, args.feedback_template, args.attempt)
        sys.exit(0 if success else 1)

    if args.submit_feedback:
        if not args.attempt:
            print("\n--attempt is required with --submit-feedback")
            sys.exit(1)
        if not args.file:
            print("\n--file is required with --submit-feedback")
            sys.exit(1)
        success = submit_feedback_from_file(store, args.submit_feedback, args.attempt, Path(args.file))
        sys.exit(0 if success else 1)

    if args.simulate_feedback:
        if not args.attempt:
            print("\n--attempt is required with --simulate-feedback")
            sys.exit(1)
        if not args.persona:
            print("\n--persona is required with --simulate-feedback")
            print("\nAvailable personas:")
            for p in list_personas():
                print(f"  {p}")
            sys.exit(1)
        success = simulate_feedback(store, args.simulate_feedback, args.attempt, args.persona)
        sys.exit(0 if success else 1)

    # Parse render quality
    render_quality = RenderQuality(args.render_quality)

    # Continue pilot
    if args.continue_pilot:
        success = asyncio.run(continue_pilot(
            args.continue_pilot, store, force=args.force, render_quality=render_quality
        ))
        sys.exit(0 if success else 1)

    # New pilot - validate required args
    if not args.founder or not args.company or not args.scenario:
        print("\nTo start a new pilot, you must provide --founder, --company, and --scenario")
        print("\nExample:")
        print('  python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch')
        print("\nOr use --list to see existing pilots, or --continue-pilot to continue one.")
        sys.exit(1)

    # Get brand if specified
    brand = None
    if args.brand:
        brand_presets = get_brand_presets()
        brand = brand_presets[args.brand]

    # Get playbook path if specified
    playbook_path = None
    if args.playbook:
        playbook_path = Path(args.playbook)
        if not playbook_path.exists():
            print(f"Warning: Playbook not found at {playbook_path}, ignoring")
            playbook_path = None

    # Start new pilot
    asyncio.run(start_new_pilot(
        founder_name=args.founder,
        company_name=args.company,
        scenario_type=args.scenario,
        brand=brand,
        playbook_path=playbook_path,
        store=store,
        render_quality=render_quality,
    ))


if __name__ == "__main__":
    main()
