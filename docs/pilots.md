# Pilot Operations Guide

This guide covers how to run real founder pilots using the KRAG Video Platform's pilot operations layer.

## Overview

The pilot operations layer provides infrastructure for running real founder engagements:

- **PilotRun**: Track multi-run engagements per founder
- **Runbook**: Document what we're testing and our commitments
- **Artifacts**: Generate founder-facing communication documents
- **Outcome Reports**: Analyze what happened for internal learning

## Quick Start

### Start a New Pilot

```bash
python scripts/run_pilot.py \
  --founder "Alice Chen" \
  --company "AcmeAI" \
  --scenario feature_launch \
  --brand acme
```

This will:
1. Create a new pilot with a unique ID
2. Generate a runbook and founder artifacts
3. Run the first video generation attempt
4. Save all state to disk

### Continue an Existing Pilot

```bash
python scripts/run_pilot.py --continue-pilot pilot_20240115_abc12345
```

### List All Pilots

```bash
python scripts/run_pilot.py --list
```

### Generate Outcome Report

```bash
python scripts/run_pilot.py --report pilot_20240115_abc12345
```

## Pilot Lifecycle

```
NEW PILOT
    │
    ├── Generate runbook (pilot_runbook.txt)
    ├── Generate founder artifacts
    │     ├── founder_instructions.txt
    │     ├── what_to_expect.txt
    │     └── approval_criteria.txt
    │
    ▼
ATTEMPT #1
    │
    ├── Run pipeline
    ├── Generate review pack
    ├── Send to founder
    │
    ▼
FEEDBACK RECEIVED
    │
    ├── APPROVE → Mark pilot complete ───┐
    │                                    │
    ├── MINOR CHANGES → Continue ────────┤
    │                                    │
    └── MAJOR CHANGES → Iterate ─────────┤
                                         │
                                         ▼
                                  PILOT COMPLETE
                                         │
                                         ▼
                               OUTCOME REPORT
```

## Available Scenarios

| Scenario | Description | Default Intent |
|----------|-------------|----------------|
| `feature_launch` | New feature or product update | social_reel |
| `funding_announcement` | Raise announcement | social_reel |
| `problem_solution` | Cold outreach positioning | paid_ad |

## Brand Presets

| Brand | Tone | Pacing | Claims |
|-------|------|--------|--------|
| `acme` | Bold | Aggressive (0.8) | Aggressive |
| `wellness` | Empathetic | Gentle (0.3) | Conservative |
| `enterprise` | Professional | Moderate (0.5) | Moderate |

## File Structure

```
data/pilots/
├── pilot_20240115_abc12345.json     # Pilot state
└── pilot_20240115_abc12345/
    ├── pilot_runbook.txt            # What we're testing
    ├── founder_instructions.txt     # How to review
    ├── what_to_expect.txt           # Timeline & quality
    ├── approval_criteria.txt        # What "ready" means
    ├── attempt_1_20240115_100000/
    │   ├── draft_v1.mp4
    │   ├── review_pack/
    │   ├── founder_instructions.txt
    │   └── ...
    └── attempt_2_20240116_090000/
        └── ...
```

## Pilot State

Each pilot tracks:

```python
@dataclass
class PilotRun:
    pilot_id: str
    founder_name: str
    company_name: str
    scenario_type: str
    brand_context: dict
    playbook_version: str | None
    runs: list[PilotRunAttempt]
    status: PilotStatus  # ACTIVE, PAUSED, COMPLETED
    approval_outcome: ApprovalOutcome  # PENDING, APPROVED, DROPPED
```

Each attempt tracks:

```python
@dataclass
class PilotRunAttempt:
    attempt_number: int
    video_path: str
    review_pack_path: str
    time_to_first_cut_seconds: float
    iteration_count: int
    total_cost_dollars: float
    sla_passed: bool
    founder_feedback: str | None
    feedback_level: str | None  # "approve", "minor_changes", "major_changes"
```

## Founder Artifacts

### pilot_runbook.txt

Internal document (for us) that covers:
- What we are testing
- What success looks like
- Iteration limits
- Feedback we want
- What we promise (and don't promise)

### founder_instructions.txt

Instructions for the founder on how to review:
- Watch the video
- Read the marketing summary
- Give feedback (APPROVE / MINOR CHANGES / MAJOR CHANGES)
- What makes good feedback

### what_to_expect.txt

Set expectations:
- Timeline
- Number of iterations
- Output quality (draft vs production)
- What's included and not included

### approval_criteria.txt

Defines "ready to publish":
- Platform-specific criteria
- Brand alignment checklist
- Technical quality checklist
- Business readiness checklist

## Outcome Reports

After a pilot completes, generate an outcome report:

```bash
python scripts/run_pilot.py --report pilot_20240115_abc12345
```

The report includes:
- Total videos generated
- Average time-to-first-cut
- Average iterations
- Approval rate
- Common feedback themes
- What improved vs first run
- Recommendation: PROCEED / REVISE / STOP

### Recommendations

| Recommendation | Meaning |
|----------------|---------|
| **PROCEED** | Pilot successful, continue with similar engagements |
| **REVISE** | Issues detected, revise approach before more pilots |
| **STOP** | Significant failure, stop and reassess |

## Programmatic Usage

```python
from src.pilot import (
    PilotStore,
    create_pilot,
    PilotRunbookBuilder,
    generate_founder_artifacts,
    generate_pilot_outcome_report,
)

# Initialize store
store = PilotStore("data/pilots")

# Create pilot
pilot = create_pilot(
    founder_name="Alice Chen",
    company_name="AcmeAI",
    scenario_type="feature_launch",
)

# Generate runbook
runbook = PilotRunbookBuilder(pilot).build("pilot_runbook.txt")

# Generate artifacts
artifacts = generate_founder_artifacts(pilot, "output/")

# Add an attempt
attempt = pilot.add_attempt(
    video_path="output/draft_v1.mp4",
    time_to_first_cut_seconds=45.0,
    sla_passed=True,
)

# Record feedback
pilot.record_feedback(
    attempt_number=1,
    feedback="Good start but hook is weak",
    level="major_changes",
)

# Save state
store.save(pilot)

# Generate outcome report
report = generate_pilot_outcome_report(pilot)
```

## Guardrails

The pilot operations layer intentionally does NOT:

- Add UI components
- Handle billing or payments
- Automate founder approvals
- Generalize to agency workflows
- Modify creative pipeline logic

It focuses purely on operational clarity for running real pilots.

## Best Practices

1. **Always generate a runbook** - It documents our commitments
2. **Send all artifacts to founder** - Set clear expectations upfront
3. **Record feedback immediately** - Don't let state go stale
4. **Generate outcome reports** - Learn from every pilot
5. **Use brand presets** - Consistent biasing across attempts
6. **Respect iteration limits** - Don't exceed max_attempts

## Troubleshooting

### Pilot not found

```bash
python scripts/run_pilot.py --list
```

Check the pilot ID exists and is spelled correctly.

### Cannot add more attempts

The pilot has reached `max_attempts`. Either:
- Mark as dropped and start a new pilot
- Increase `max_attempts` if justified

### Founder not responding

Use `pilot.pause("Waiting for founder feedback")` to track the delay.
Resume with `pilot.resume()` when ready.
