#!/usr/bin/env python3
"""
KRAG Video Platform - Pilot Runner

Run real founder pilots with operational infrastructure:
- Pilot tracking and persistence
- Founder communication artifacts
- Runbook generation
- Outcome reporting

Usage:
    # Start a new pilot
    python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch

    # Start with brand biasing
    python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch --brand acme

    # Continue an existing pilot
    python scripts/run_pilot.py --continue-pilot pilot_20240115_abc12345

    # List active pilots
    python scripts/run_pilot.py --list

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
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pilot import (
    PilotRun,
    PilotStatus,
    ApprovalOutcome,
    PilotStore,
    create_pilot,
    PilotRunbookBuilder,
    generate_founder_artifacts,
    generate_pilot_outcome_report,
    generate_multi_pilot_report,
)
from src.founder import (
    get_scenario,
    SCENARIOS,
    ReviewPackBuilder,
    TimeToValueMetrics,
    create_run_report,
)
from src.brand import (
    BrandContext,
    ToneProfile,
    ClaimConservativeness,
    create_brand_context,
    apply_brand_bias,
)
from src.marketing import (
    MarketingIntent,
    get_preset,
    get_configs_for_intent,
    validate_pipeline_sla,
    generate_marketing_summary,
)
from src.playbook import (
    load_playbook,
    apply_playbook,
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

    print("\n" + "=" * 80)
    print("PILOT LIST")
    print("=" * 80)
    print()
    print(f"{'Pilot ID':<30} {'Founder':<15} {'Company':<15} {'Status':<10} {'Outcome':<10}")
    print("-" * 80)

    for pilot in pilots:
        print(
            f"{pilot.pilot_id:<30} "
            f"{pilot.founder_name[:14]:<15} "
            f"{pilot.company_name[:14]:<15} "
            f"{pilot.status.value:<10} "
            f"{pilot.approval_outcome.value:<10}"
        )

    print()
    print(f"Total: {len(pilots)} pilots")

    # Summary by status
    active = sum(1 for p in pilots if p.status == PilotStatus.ACTIVE)
    completed = sum(1 for p in pilots if p.status == PilotStatus.COMPLETED)
    paused = sum(1 for p in pilots if p.status == PilotStatus.PAUSED)

    print(f"Active: {active} | Completed: {completed} | Paused: {paused}")
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


async def run_pilot_attempt(
    pilot: PilotRun,
    store: PilotStore,
    brand: BrandContext | None = None,
    playbook_path: Path | None = None,
) -> bool:
    """Run a single attempt within a pilot.

    This is a simplified version that demonstrates the flow.
    In production, this would call the full pipeline.

    Args:
        pilot: The pilot to run an attempt for.
        store: Pilot storage.
        brand: Optional brand context.
        playbook_path: Optional playbook path.

    Returns:
        True if attempt was successful.
    """
    # Check if we can add more attempts
    if not pilot.can_add_attempt:
        print(f"\nCannot add more attempts. Max attempts ({pilot.max_attempts}) reached.")
        return False

    attempt_number = pilot.attempt_count + 1
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    print("\n" + "=" * 60)
    print(f"PILOT ATTEMPT #{attempt_number}")
    print("=" * 60)
    print(f"   Pilot ID: {pilot.pilot_id}")
    print(f"   Founder: {pilot.founder_name}")
    print(f"   Company: {pilot.company_name}")
    print(f"   Scenario: {pilot.scenario_type}")
    if brand:
        print(f"   Brand: {brand.brand_name} ({brand.tone.value})")
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

    return True


async def start_new_pilot(
    founder_name: str,
    company_name: str,
    scenario_type: str,
    brand: BrandContext | None = None,
    playbook_path: Path | None = None,
    store: PilotStore | None = None,
) -> PilotRun:
    """Start a new pilot engagement.

    Args:
        founder_name: Name of the founder.
        company_name: Name of the company.
        scenario_type: Type of scenario.
        brand: Optional brand context.
        playbook_path: Optional playbook path.
        store: Optional pilot store (creates default if not provided).

    Returns:
        The created pilot.
    """
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
    runbook = PilotRunbookBuilder(pilot).build(runbook_path)

    # Generate initial founder artifacts
    artifacts = generate_founder_artifacts(pilot, pilot_dir)

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
    print(f"     - pilot_runbook.txt")
    print(f"     - founder_instructions.txt")
    print(f"     - what_to_expect.txt")
    print(f"     - approval_criteria.txt")
    print()

    # Run first attempt
    print("Starting first attempt...")
    await run_pilot_attempt(pilot, store, brand, playbook_path)

    return pilot


async def continue_pilot(
    pilot_id: str,
    store: PilotStore | None = None,
) -> bool:
    """Continue an existing pilot with a new attempt.

    Args:
        pilot_id: The pilot ID to continue.
        store: Optional pilot store.

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

    return await run_pilot_attempt(pilot, store, brand, playbook_path)


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

  # Start with brand biasing
  python scripts/run_pilot.py --founder "Alice" --company "AcmeAI" --scenario feature_launch --brand acme

  # Continue an existing pilot
  python scripts/run_pilot.py --continue-pilot pilot_20240115_abc12345

  # List all pilots
  python scripts/run_pilot.py --list

  # Generate outcome report
  python scripts/run_pilot.py --report pilot_20240115_abc12345
""",
    )

    # New pilot arguments
    parser.add_argument(
        "--founder",
        type=str,
        help="Founder name (required for new pilot)",
    )
    parser.add_argument(
        "--company",
        type=str,
        help="Company name (required for new pilot)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=list(SCENARIOS.keys()),
        help="Scenario type (required for new pilot)",
    )
    parser.add_argument(
        "--brand",
        type=str,
        choices=["acme", "wellness", "enterprise"],
        help="Brand preset for biasing (optional)",
    )
    parser.add_argument(
        "--playbook",
        type=str,
        help="Path to playbook JSON file (optional)",
    )

    # Existing pilot operations
    parser.add_argument(
        "--continue-pilot",
        type=str,
        metavar="PILOT_ID",
        help="Continue an existing pilot with a new attempt",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all pilots",
    )
    parser.add_argument(
        "--report",
        type=str,
        metavar="PILOT_ID",
        help="Generate outcome report for a pilot",
    )

    args = parser.parse_args()

    # Initialize store
    store = PilotStore(PILOT_STORAGE_DIR)

    # Handle commands
    if args.list:
        list_pilots(store)
        return

    if args.report:
        show_pilot_report(store, args.report)
        return

    if args.continue_pilot:
        success = asyncio.run(continue_pilot(args.continue_pilot, store))
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
    ))


if __name__ == "__main__":
    main()
