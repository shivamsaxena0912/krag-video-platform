"""Review pack builder for founder-ready output.

This module creates a clean, review-ready folder that non-technical
founders can easily understand and share with stakeholders.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.logging import get_logger
from src.founder.scenario import FounderScenario
from src.marketing import MarketingIntent

logger = get_logger(__name__)


@dataclass
class ReviewPack:
    """A review-ready package for founders."""

    pack_path: Path
    scenario: FounderScenario
    version: int

    # Files included
    video_path: Path | None = None
    marketing_summary_path: Path | None = None
    director_notes_path: Path | None = None
    what_changed_path: Path | None = None
    checklist_path: Path | None = None

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = 0.0
    shot_count: int = 0

    def is_complete(self) -> bool:
        """Check if all required files are present."""
        return all([
            self.video_path and self.video_path.exists(),
            self.marketing_summary_path and self.marketing_summary_path.exists(),
            self.checklist_path and self.checklist_path.exists(),
        ])


class ReviewPackBuilder:
    """Builds review-ready packages for founders.

    Creates a single folder per run containing everything needed
    for non-technical review and approval.
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        scenario: FounderScenario,
        version: int,
        video_path: Path | None,
        marketing_summary_path: Path | None,
        director_notes_path: Path | None,
        previous_pack: ReviewPack | None = None,
        duration_seconds: float = 0.0,
        shot_count: int = 0,
        changes_made: list[str] | None = None,
    ) -> ReviewPack:
        """Build a review pack.

        Args:
            scenario: The founder scenario
            version: Version number (1, 2, 3...)
            video_path: Path to the rendered video
            marketing_summary_path: Path to marketing summary
            director_notes_path: Path to director notes
            previous_pack: Previous version for diff generation
            duration_seconds: Video duration
            shot_count: Number of shots
            changes_made: List of changes from previous version

        Returns:
            A ReviewPack with all files copied to the pack folder.
        """
        # Create pack folder
        pack_name = f"review_v{version}_{scenario.scenario_id}"
        pack_path = self.output_dir / pack_name
        pack_path.mkdir(parents=True, exist_ok=True)

        pack = ReviewPack(
            pack_path=pack_path,
            scenario=scenario,
            version=version,
            duration_seconds=duration_seconds,
            shot_count=shot_count,
        )

        # Copy video
        if video_path and video_path.exists():
            dest = pack_path / "final_video.mp4"
            shutil.copy2(video_path, dest)
            pack.video_path = dest

        # Copy marketing summary
        if marketing_summary_path and marketing_summary_path.exists():
            dest = pack_path / "marketing_summary.txt"
            shutil.copy2(marketing_summary_path, dest)
            pack.marketing_summary_path = dest

        # Copy director notes
        if director_notes_path and director_notes_path.exists():
            dest = pack_path / "director_notes.txt"
            shutil.copy2(director_notes_path, dest)
            pack.director_notes_path = dest

        # Generate what_changed
        what_changed_path = pack_path / "what_changed_since_last_version.txt"
        self._write_what_changed(
            what_changed_path,
            version,
            previous_pack,
            changes_made or [],
        )
        pack.what_changed_path = what_changed_path

        # Generate checklist
        checklist_path = pack_path / "recommended_publish_checklist.txt"
        self._write_checklist(checklist_path, scenario, duration_seconds)
        pack.checklist_path = checklist_path

        logger.info(
            "review_pack_built",
            path=str(pack_path),
            version=version,
            scenario=scenario.scenario_id,
        )

        return pack

    def _write_what_changed(
        self,
        path: Path,
        version: int,
        previous_pack: ReviewPack | None,
        changes_made: list[str],
    ) -> None:
        """Write the what_changed file."""
        lines = [
            "=" * 60,
            "WHAT CHANGED SINCE LAST VERSION",
            "=" * 60,
            "",
            f"Current Version: v{version}",
        ]

        if version == 1:
            lines.extend([
                "",
                "This is the FIRST VERSION.",
                "",
                "No previous version to compare against.",
                "",
                "Review this cut and provide feedback:",
                "  - APPROVE: Ready to publish",
                "  - MINOR_CHANGES: Small tweaks needed",
                "  - MAJOR_CHANGES: Significant rework required",
            ])
        else:
            lines.extend([
                f"Previous Version: v{version - 1}",
                "",
                "--- CHANGES MADE ---",
            ])

            if changes_made:
                for i, change in enumerate(changes_made, 1):
                    lines.append(f"{i}. {change}")
            else:
                lines.append("No specific changes recorded.")

            if previous_pack:
                lines.extend([
                    "",
                    "--- COMPARISON ---",
                    f"Previous duration: {previous_pack.duration_seconds:.1f}s",
                    f"Current duration: N/A (see marketing summary)",
                    f"Previous shots: {previous_pack.shot_count}",
                ])

        lines.extend([
            "",
            "=" * 60,
        ])

        with open(path, "w") as f:
            f.write("\n".join(lines))

    def _write_checklist(
        self,
        path: Path,
        scenario: FounderScenario,
        duration_seconds: float,
    ) -> None:
        """Write the publish checklist."""
        lines = [
            "=" * 60,
            "RECOMMENDED PUBLISH CHECKLIST",
            "=" * 60,
            "",
            f"Scenario: {scenario.scenario_name}",
            f"Platform: {scenario.platform}",
            f"Goal: {scenario.goal.value.upper()}",
            "",
            "--- BEFORE YOU PUBLISH ---",
            "",
            "[ ] Watch the video with sound OFF",
            "    Does it make sense visually?",
            "",
            "[ ] Watch the video with sound ON",
            "    Is the audio clear and well-timed?",
            "",
            "[ ] Check the first 3 seconds",
            "    Would YOU stop scrolling?",
            "",
            "[ ] Check the ending",
            "    Is the CTA clear?",
            "",
            f"[ ] Verify duration: {duration_seconds:.1f}s",
            f"    Target: {scenario.recommended_length}",
            "",
            "--- MUST INCLUDE (per scenario) ---",
        ]

        for item in scenario.must_include:
            lines.append(f"[ ] {item}")

        lines.extend([
            "",
            "--- AVOID (per scenario) ---",
        ])

        for item in scenario.avoid:
            lines.append(f"[X] NOT: {item}")

        lines.extend([
            "",
            "--- PLATFORM-SPECIFIC ---",
            "",
        ])

        if "LinkedIn" in scenario.platform:
            lines.extend([
                "[ ] LinkedIn: Add captions (85% watch without sound)",
                "[ ] LinkedIn: First comment ready with context",
                "[ ] LinkedIn: Tag relevant people/companies",
            ])

        if "Twitter" in scenario.platform:
            lines.extend([
                "[ ] Twitter: Prepare tweet copy (<280 chars)",
                "[ ] Twitter: Add alt text for accessibility",
            ])

        if "TikTok" in scenario.platform or "Meta" in scenario.platform:
            lines.extend([
                "[ ] Ads: Creative approved in Ads Manager",
                "[ ] Ads: Targeting configured",
                "[ ] Ads: Budget set",
            ])

        if "YouTube" in scenario.platform:
            lines.extend([
                "[ ] YouTube: Title optimized for search",
                "[ ] YouTube: Thumbnail ready",
                "[ ] YouTube: Description with links",
            ])

        lines.extend([
            "",
            "--- AFTER PUBLISH ---",
            "",
            "[ ] Monitor first 24h engagement",
            "[ ] Respond to comments promptly",
            "[ ] Track against success criteria:",
            f"    {scenario.success_criteria}",
            "",
            "=" * 60,
            "Good luck! 🚀",
            "=" * 60,
        ])

        with open(path, "w") as f:
            f.write("\n".join(lines))
