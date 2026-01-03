"""SLA validation for marketing intent constraints.

This module enforces hard constraints and provides fail-fast validation
to ensure predictable marketing outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.common.logging import get_logger
from src.common.models import Shot, ShotPurpose, BeatIntensity, EndingIntent
from src.marketing.intent import MarketingIntent, MarketingPreset, get_preset

logger = get_logger(__name__)


class ViolationType(str, Enum):
    """Type of SLA violation."""
    DURATION_EXCEEDED = "duration_exceeded"
    DURATION_UNDER = "duration_under"
    ITERATION_EXCEEDED = "iteration_exceeded"
    COST_EXCEEDED = "cost_exceeded"
    SHOT_COUNT_EXCEEDED = "shot_count_exceeded"
    OPENING_VIOLATION = "opening_violation"
    ENDING_VIOLATION = "ending_violation"
    PURPOSE_RATIO_VIOLATION = "purpose_ratio_violation"
    INTENSITY_RATIO_VIOLATION = "intensity_ratio_violation"


@dataclass
class SLAViolation:
    """A single SLA violation."""
    violation_type: ViolationType
    message: str
    expected: Any
    actual: Any
    severity: str = "error"  # "error" = fail-fast, "warning" = log only


@dataclass
class SLAReport:
    """Report of SLA validation results."""
    intent: MarketingIntent
    passed: bool
    violations: list[SLAViolation] = field(default_factory=list)
    warnings: list[SLAViolation] = field(default_factory=list)

    # Metrics
    total_duration: float = 0.0
    shot_count: int = 0
    iteration_count: int = 0
    total_cost: float = 0.0

    # Purpose distribution
    purpose_distribution: dict[ShotPurpose, float] = field(default_factory=dict)
    intensity_distribution: dict[BeatIntensity, float] = field(default_factory=dict)

    def add_violation(self, violation: SLAViolation) -> None:
        """Add a violation to the report."""
        if violation.severity == "error":
            self.violations.append(violation)
            self.passed = False
        else:
            self.warnings.append(violation)


class SLAValidator:
    """Validates pipeline outputs against marketing intent constraints.

    This validator enforces hard constraints and fails fast when violated.
    """

    def __init__(self, preset: MarketingPreset):
        self.preset = preset

    def validate_shots(self, shots: list[Shot]) -> SLAReport:
        """Validate shots against the preset constraints."""
        report = SLAReport(
            intent=self.preset.intent,
            passed=True,
            shot_count=len(shots),
        )

        if not shots:
            report.add_violation(SLAViolation(
                violation_type=ViolationType.SHOT_COUNT_EXCEEDED,
                message="No shots provided",
                expected="at least 1",
                actual=0,
            ))
            return report

        # Calculate total duration
        report.total_duration = sum(s.duration_seconds for s in shots)

        # Check duration bounds
        self._check_duration(report)

        # Check shot count
        self._check_shot_count(report, shots)

        # Check opening
        self._check_opening(report, shots)

        # Check ending
        self._check_ending(report, shots)

        # Check purpose distribution
        self._check_purpose_distribution(report, shots)

        # Check intensity distribution
        self._check_intensity_distribution(report, shots)

        return report

    def validate_iteration_count(self, count: int) -> SLAViolation | None:
        """Validate iteration count against preset limit."""
        if count > self.preset.max_iterations:
            return SLAViolation(
                violation_type=ViolationType.ITERATION_EXCEEDED,
                message=f"Exceeded max iterations for {self.preset.intent.value}",
                expected=self.preset.max_iterations,
                actual=count,
            )
        return None

    def validate_cost(self, cost: float) -> SLAViolation | None:
        """Validate cost against preset limit."""
        if cost > self.preset.max_cost_dollars:
            return SLAViolation(
                violation_type=ViolationType.COST_EXCEEDED,
                message=f"Exceeded max cost for {self.preset.intent.value}",
                expected=self.preset.max_cost_dollars,
                actual=cost,
            )
        return None

    def _check_duration(self, report: SLAReport) -> None:
        """Check duration bounds."""
        if report.total_duration > self.preset.max_duration_seconds:
            report.add_violation(SLAViolation(
                violation_type=ViolationType.DURATION_EXCEEDED,
                message=f"Duration {report.total_duration:.1f}s exceeds max {self.preset.max_duration_seconds:.1f}s",
                expected=self.preset.max_duration_seconds,
                actual=report.total_duration,
            ))

        if report.total_duration < self.preset.min_duration_seconds:
            report.add_violation(SLAViolation(
                violation_type=ViolationType.DURATION_UNDER,
                message=f"Duration {report.total_duration:.1f}s under min {self.preset.min_duration_seconds:.1f}s",
                expected=self.preset.min_duration_seconds,
                actual=report.total_duration,
                severity="warning",  # Under is less critical than over
            ))

    def _check_shot_count(self, report: SLAReport, shots: list[Shot]) -> None:
        """Check shot count limit."""
        if len(shots) > self.preset.max_shots:
            report.add_violation(SLAViolation(
                violation_type=ViolationType.SHOT_COUNT_EXCEEDED,
                message=f"Shot count {len(shots)} exceeds max {self.preset.max_shots}",
                expected=self.preset.max_shots,
                actual=len(shots),
            ))

    def _check_opening(self, report: SLAReport, shots: list[Shot]) -> None:
        """Check opening rules."""
        opening_duration = self.preset.opening_duration_seconds
        required_purposes = self.preset.opening_required_purposes
        required_intensity = self.preset.opening_required_intensity

        # Get shots in opening window
        opening_shots = []
        cumulative = 0.0
        for shot in shots:
            if cumulative >= opening_duration:
                break
            opening_shots.append(shot)
            cumulative += shot.duration_seconds

        if not opening_shots:
            return

        # Check purposes
        opening_purposes = {s.purpose for s in opening_shots if s.purpose}
        if not opening_purposes.intersection(set(required_purposes)):
            report.add_violation(SLAViolation(
                violation_type=ViolationType.OPENING_VIOLATION,
                message=f"Opening lacks required purposes: {[p.value for p in required_purposes]}",
                expected=[p.value for p in required_purposes],
                actual=[p.value for p in opening_purposes] if opening_purposes else [],
            ))

        # Check intensity (at least one shot should match)
        opening_intensities = {s.intensity for s in opening_shots}
        if required_intensity not in opening_intensities:
            # For HIGH requirement, check if we have HIGH; otherwise warning
            if required_intensity == BeatIntensity.HIGH and BeatIntensity.HIGH not in opening_intensities:
                report.add_violation(SLAViolation(
                    violation_type=ViolationType.OPENING_VIOLATION,
                    message=f"Opening lacks HIGH intensity for hook",
                    expected=required_intensity.value,
                    actual=[i.value for i in opening_intensities],
                    severity="warning",
                ))

    def _check_ending(self, report: SLAReport, shots: list[Shot]) -> None:
        """Check ending rules."""
        ending_duration = self.preset.ending_duration_seconds
        required_intent = self.preset.ending_required_intent
        required_purposes = self.preset.ending_required_purposes

        # Get shots in ending window
        ending_shots = []
        cumulative = 0.0
        for shot in reversed(shots):
            if cumulative >= ending_duration:
                break
            ending_shots.append(shot)
            cumulative += shot.duration_seconds

        if not ending_shots:
            return

        # Check final shot ending intent
        final_shot = shots[-1]
        if final_shot.ending_intent and final_shot.ending_intent != required_intent:
            report.add_violation(SLAViolation(
                violation_type=ViolationType.ENDING_VIOLATION,
                message=f"Ending intent mismatch: expected {required_intent.value}",
                expected=required_intent.value,
                actual=final_shot.ending_intent.value if final_shot.ending_intent else None,
                severity="warning",  # Intent can be overridden
            ))

        # Check purposes in ending
        ending_purposes = {s.purpose for s in ending_shots if s.purpose}
        if not ending_purposes.intersection(set(required_purposes)):
            report.add_violation(SLAViolation(
                violation_type=ViolationType.ENDING_VIOLATION,
                message=f"Ending lacks required purposes: {[p.value for p in required_purposes]}",
                expected=[p.value for p in required_purposes],
                actual=[p.value for p in ending_purposes] if ending_purposes else [],
                severity="warning",
            ))

    def _check_purpose_distribution(self, report: SLAReport, shots: list[Shot]) -> None:
        """Check purpose distribution against targets."""
        purpose_counts: dict[ShotPurpose, int] = {}
        for shot in shots:
            if shot.purpose:
                purpose_counts[shot.purpose] = purpose_counts.get(shot.purpose, 0) + 1

        total = len(shots)
        if total == 0:
            return

        # Calculate actual ratios
        report.purpose_distribution = {
            purpose: count / total
            for purpose, count in purpose_counts.items()
        }

        # Check INFORMATION ratio (should not exceed target by too much)
        info_ratio = purpose_counts.get(ShotPurpose.INFORMATION, 0) / total
        target_info = self.preset.purpose_ratio_information
        if info_ratio > target_info * 2:  # Allow 2x tolerance
            report.add_violation(SLAViolation(
                violation_type=ViolationType.PURPOSE_RATIO_VIOLATION,
                message=f"Too much INFORMATION content: {info_ratio:.0%} vs target {target_info:.0%}",
                expected=target_info,
                actual=info_ratio,
                severity="warning",
            ))

        # Check EMOTION ratio (should meet minimum)
        emotion_ratio = purpose_counts.get(ShotPurpose.EMOTION, 0) / total
        target_emotion = self.preset.purpose_ratio_emotion
        if emotion_ratio < target_emotion * 0.5:  # Allow 0.5x tolerance
            report.add_violation(SLAViolation(
                violation_type=ViolationType.PURPOSE_RATIO_VIOLATION,
                message=f"Not enough EMOTION content: {emotion_ratio:.0%} vs target {target_emotion:.0%}",
                expected=target_emotion,
                actual=emotion_ratio,
                severity="warning",
            ))

    def _check_intensity_distribution(self, report: SLAReport, shots: list[Shot]) -> None:
        """Check intensity distribution against targets."""
        intensity_counts: dict[BeatIntensity, int] = {}
        for shot in shots:
            intensity_counts[shot.intensity] = intensity_counts.get(shot.intensity, 0) + 1

        total = len(shots)
        if total == 0:
            return

        # Calculate actual ratios
        report.intensity_distribution = {
            intensity: count / total
            for intensity, count in intensity_counts.items()
        }

        # For paid ads, check HIGH intensity is sufficient
        if self.preset.intent == MarketingIntent.PAID_AD:
            high_ratio = intensity_counts.get(BeatIntensity.HIGH, 0) / total
            target_high = self.preset.intensity_ratio_high
            if high_ratio < target_high * 0.5:
                report.add_violation(SLAViolation(
                    violation_type=ViolationType.INTENSITY_RATIO_VIOLATION,
                    message=f"Not enough HIGH intensity: {high_ratio:.0%} vs target {target_high:.0%}",
                    expected=target_high,
                    actual=high_ratio,
                    severity="warning",
                ))


def validate_pipeline_sla(
    shots: list[Shot],
    intent: MarketingIntent,
    iteration_count: int = 0,
    total_cost: float = 0.0,
) -> SLAReport:
    """Validate pipeline outputs against marketing intent SLA.

    This is the main entry point for SLA validation.
    Raises ValueError if critical constraints are violated (fail-fast).
    """
    preset = get_preset(intent)
    validator = SLAValidator(preset)

    report = validator.validate_shots(shots)
    report.iteration_count = iteration_count
    report.total_cost = total_cost

    # Check iteration count
    iter_violation = validator.validate_iteration_count(iteration_count)
    if iter_violation:
        report.add_violation(iter_violation)

    # Check cost
    cost_violation = validator.validate_cost(total_cost)
    if cost_violation:
        report.add_violation(cost_violation)

    # Log results
    if report.passed:
        logger.info(
            "sla_validation_passed",
            intent=intent.value,
            duration=f"{report.total_duration:.1f}s",
            shots=report.shot_count,
            warnings=len(report.warnings),
        )
    else:
        logger.error(
            "sla_validation_failed",
            intent=intent.value,
            violations=len(report.violations),
            first_violation=report.violations[0].message if report.violations else None,
        )

    return report


def enforce_sla(
    shots: list[Shot],
    intent: MarketingIntent,
    iteration_count: int = 0,
    total_cost: float = 0.0,
) -> SLAReport:
    """Enforce SLA with fail-fast behavior.

    Raises ValueError if any critical constraint is violated.
    """
    report = validate_pipeline_sla(shots, intent, iteration_count, total_cost)

    if not report.passed:
        violation_messages = [v.message for v in report.violations]
        raise ValueError(
            f"SLA violation for {intent.value}: {'; '.join(violation_messages)}"
        )

    return report
