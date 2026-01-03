"""Founder communication artifacts.

Generates plain-English documents for founders:
- founder_instructions.txt: How to review and give feedback
- what_to_expect.txt: Timeline, iterations, output quality
- approval_criteria.txt: What "ready to publish" means
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.pilot.run import PilotRun


def generate_founder_instructions(
    pilot: PilotRun,
    output_path: Path | str | None = None,
) -> str:
    """Generate instructions for the founder on how to review and give feedback.

    Written in plain English, non-technical language.

    Args:
        pilot: The pilot run.
        output_path: Optional path to write the file.

    Returns:
        The instructions content.
    """
    lines = [
        "HOW TO REVIEW YOUR VIDEO",
        "=" * 40,
        "",
        f"Hi {pilot.founder_name.split()[0]},",
        "",
        "Here's how to review the video we've created for you and give us feedback.",
        "",
        "",
        "STEP 1: WATCH THE VIDEO",
        "-" * 40,
        "",
        "Open the video file (final_video.mp4) in your review pack folder.",
        "Watch it all the way through at least once without stopping.",
        "",
        "Pro tip: Watch it on the device your audience will use.",
        "If it's for Instagram, watch on your phone.",
        "",
        "",
        "STEP 2: READ THE MARKETING SUMMARY",
        "-" * 40,
        "",
        "Open marketing_summary.txt to see:",
        "  - Who this video is for",
        "  - What action we want viewers to take",
        "  - Key points the video covers",
        "",
        "Does this match what you had in mind?",
        "",
        "",
        "STEP 3: CHECK THE DIRECTOR NOTES (OPTIONAL)",
        "-" * 40,
        "",
        "If you're curious why we made certain creative choices,",
        "director_notes.txt explains our thinking.",
        "",
        "This is optional - you don't need to read it to give feedback.",
        "",
        "",
        "STEP 4: GIVE US YOUR FEEDBACK",
        "-" * 40,
        "",
        "Reply with one of these three responses:",
        "",
        "  APPROVE",
        "  --------",
        "  \"This is ready to publish.\"",
        "  We're done! You can use this video.",
        "",
        "  MINOR CHANGES",
        "  -------------",
        "  \"I like it, but please adjust...\"",
        "  Tell us specific small changes. Examples:",
        "    - \"The opening is too slow\"",
        "    - \"Can you make it 5 seconds shorter?\"",
        "    - \"The ending needs a stronger call-to-action\"",
        "",
        "  MAJOR CHANGES",
        "  -------------",
        "  \"This doesn't work for me because...\"",
        "  Tell us what's fundamentally wrong. Examples:",
        "    - \"The tone is too serious, we're a playful brand\"",
        "    - \"This misses our key message entirely\"",
        "    - \"This doesn't feel like our company\"",
        "",
        "",
        "WHAT MAKES GOOD FEEDBACK",
        "-" * 40,
        "",
        "  Good: \"The video feels too slow in the middle section\"",
        "  Bad:  \"I don't like it\"",
        "",
        "  Good: \"Our key message about pricing isn't clear enough\"",
        "  Bad:  \"It needs to be better\"",
        "",
        "  Good: \"The ending should say 'Start your free trial' more prominently\"",
        "  Bad:  \"Fix the ending\"",
        "",
        "The more specific you are, the faster we can make it right.",
        "",
        "",
        "QUESTIONS?",
        "-" * 40,
        "",
        "Just reply to this email with any questions.",
        f"Please include your Pilot ID: {pilot.pilot_id}",
        "",
        "We're here to help!",
        "",
    ]

    content = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

    return content


def generate_what_to_expect(
    pilot: PilotRun,
    output_path: Path | str | None = None,
) -> str:
    """Generate a document explaining what the founder should expect.

    Covers timeline, iterations, and output quality.

    Args:
        pilot: The pilot run.
        output_path: Optional path to write the file.

    Returns:
        The content.
    """
    lines = [
        "WHAT TO EXPECT FROM THIS PILOT",
        "=" * 40,
        "",
        f"Hi {pilot.founder_name.split()[0]},",
        "",
        "Here's what you can expect from working with us on this video pilot.",
        "",
        "",
        "TIMELINE",
        "-" * 40,
        "",
        "  Today:     You receive your first video draft",
        "  24 hours:  We respond to your feedback with a revised version",
        "  3-5 days:  We aim to reach a final, approved video",
        "",
        "Note: This depends on how quickly you can review and give feedback.",
        "We work fast, but we need your input to improve.",
        "",
        "",
        "HOW MANY ITERATIONS?",
        "-" * 40,
        "",
        f"  Maximum video attempts:  {pilot.max_attempts}",
        f"  Iterations per attempt:  {pilot.max_iterations_per_attempt}",
        "",
        "Most founders approve within 2-3 iterations.",
        "If we can't get it right in these attempts, we'll discuss next steps.",
        "",
        "",
        "OUTPUT QUALITY",
        "-" * 40,
        "",
        "What you'll get:",
        "  [x] Professional video structure and pacing",
        "  [x] Platform-optimized length and format",
        "  [x] Clear narrative flow and call-to-action",
        "  [x] Ready-to-publish video file",
        "",
        "What this pilot does NOT include:",
        "  [ ] Custom music (we use placeholder music beds)",
        "  [ ] Professional voice-over (using synthesized audio)",
        "  [ ] Custom graphics or animations",
        "  [ ] 4K or cinema-quality footage",
        "",
        "This is about nailing the structure, pacing, and message.",
        "Production polish comes later.",
        "",
        "",
        "YOUR REVIEW PACK",
        "-" * 40,
        "",
        "Each time we send you a video, you'll get a folder containing:",
        "",
        "  final_video.mp4",
        "    The video file itself. Watch this first.",
        "",
        "  marketing_summary.txt",
        "    Plain-English summary of the video's purpose.",
        "    Who it's for, what action we want viewers to take.",
        "",
        "  director_notes.txt",
        "    Why we made the creative choices we did.",
        "    Useful if you want to understand our thinking.",
        "",
        "  what_changed_since_last_version.txt",
        "    After the first version, this explains what we changed.",
        "    Helps you see if we addressed your feedback.",
        "",
        "  recommended_publish_checklist.txt",
        "    Final checks before you publish the video.",
        "",
        "",
        "WHAT WE NEED FROM YOU",
        "-" * 40,
        "",
        "  1. Watch the video within 24-48 hours",
        "  2. Give us clear, specific feedback",
        "  3. Tell us APPROVE, MINOR CHANGES, or MAJOR CHANGES",
        "",
        "The faster you respond, the faster we iterate.",
        "",
        "",
        "QUESTIONS?",
        "-" * 40,
        "",
        "Reply to this email anytime.",
        f"Pilot ID: {pilot.pilot_id}",
        "",
    ]

    content = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

    return content


def generate_approval_criteria(
    pilot: PilotRun,
    output_path: Path | str | None = None,
) -> str:
    """Generate a document explaining what 'ready to publish' means.

    Args:
        pilot: The pilot run.
        output_path: Optional path to write the file.

    Returns:
        The content.
    """
    # Determine platform-specific criteria based on scenario
    platform_criteria = {
        "feature_launch": [
            "Video is 30-60 seconds (optimal for social feeds)",
            "Hook grabs attention in first 3 seconds",
            "Feature benefit is clearly demonstrated",
            "Call-to-action is specific (try it, sign up, learn more)",
        ],
        "funding_announcement": [
            "Video is 45-90 seconds (enough for the story)",
            "Company vision is clearly communicated",
            "Key metrics or milestones are mentioned",
            "Ends with forward-looking statement",
        ],
        "problem_solution": [
            "Video is 30-45 seconds (short for cold outreach)",
            "Problem is immediately relatable",
            "Solution is clearly positioned",
            "Call-to-action is low-friction (watch demo, learn more)",
        ],
    }

    criteria = platform_criteria.get(pilot.scenario_type, [
        "Video meets target duration for platform",
        "Key message is clearly communicated",
        "Call-to-action is present and clear",
        "Pacing feels appropriate for the audience",
    ])

    lines = [
        "WHAT 'READY TO PUBLISH' MEANS",
        "=" * 40,
        "",
        f"Hi {pilot.founder_name.split()[0]},",
        "",
        "Here's how to know when your video is ready to publish.",
        "",
        "",
        "THE APPROVAL CHECKLIST",
        "-" * 40,
        "",
        "Your video is ready to publish when you can say YES to all of these:",
        "",
    ]

    for i, criterion in enumerate(criteria, 1):
        lines.append(f"  {i}. [ ] {criterion}")

    lines.extend([
        "",
        "",
        "BRAND ALIGNMENT",
        "-" * 40,
        "",
        "  [ ] The tone matches how we talk to customers",
        "  [ ] The visual style feels like our brand",
        "  [ ] Nothing in the video would embarrass us",
        "  [ ] We'd be proud to share this with investors",
        "",
        "",
        "TECHNICAL QUALITY",
        "-" * 40,
        "",
        "  [ ] Audio is clear and audible",
        "  [ ] Transitions are smooth (no jarring cuts)",
        "  [ ] Text is readable on mobile",
        "  [ ] No obvious technical glitches",
        "",
        "",
        "BUSINESS READINESS",
        "-" * 40,
        "",
        "  [ ] The message is accurate (no false claims)",
        "  [ ] Legal has no concerns (if applicable)",
        "  [ ] Landing page or CTA destination exists",
        "  [ ] We're ready to handle the response",
        "",
        "",
        "WHEN TO SAY 'APPROVE'",
        "-" * 40,
        "",
        "Say APPROVE when:",
        "  - You'd publish this video TODAY without changes",
        "  - You're confident it represents your company well",
        "  - The message will resonate with your audience",
        "",
        "Don't say APPROVE if:",
        "  - You're settling because you're tired of iterations",
        "  - You're hoping to 'fix it later'",
        "  - You have lingering doubts about the message",
        "",
        "It's better to ask for one more iteration than to publish",
        "something you're not proud of.",
        "",
        "",
        "WHAT HAPPENS AFTER APPROVAL",
        "-" * 40,
        "",
        "  1. We mark the video as final",
        "  2. You receive the approved video file",
        "  3. You can publish it on your platform",
        "  4. We collect learnings to improve future videos",
        "",
        "That's it! The video is yours to use.",
        "",
        "",
        "QUESTIONS?",
        "-" * 40,
        "",
        f"Pilot ID: {pilot.pilot_id}",
        "Reply to this email anytime.",
        "",
    ])

    content = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

    return content


@dataclass
class FounderArtifacts:
    """Collection of all founder communication artifacts."""

    founder_instructions: str
    what_to_expect: str
    approval_criteria: str

    instructions_path: Path | None = None
    expectations_path: Path | None = None
    criteria_path: Path | None = None


def generate_founder_artifacts(
    pilot: PilotRun,
    output_dir: Path | str,
) -> FounderArtifacts:
    """Generate all founder communication artifacts.

    Args:
        pilot: The pilot run.
        output_dir: Directory to write the artifacts.

    Returns:
        FounderArtifacts with all content and paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    instructions_path = output_dir / "founder_instructions.txt"
    expectations_path = output_dir / "what_to_expect.txt"
    criteria_path = output_dir / "approval_criteria.txt"

    instructions = generate_founder_instructions(pilot, instructions_path)
    expectations = generate_what_to_expect(pilot, expectations_path)
    criteria = generate_approval_criteria(pilot, criteria_path)

    return FounderArtifacts(
        founder_instructions=instructions,
        what_to_expect=expectations,
        approval_criteria=criteria,
        instructions_path=instructions_path,
        expectations_path=expectations_path,
        criteria_path=criteria_path,
    )
