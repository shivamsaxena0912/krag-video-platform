"""Tests for pilot feedback data model and capture."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import json

from src.pilot.run import (
    PilotRun,
    PilotRunAttempt,
    PilotStatus,
    ApprovalOutcome,
    FeedbackMode,
    FeedbackDecision,
    FEEDBACK_FLAGS,
    create_pilot,
    PilotStore,
)


class TestFeedbackDataModel:
    """Test the feedback data model."""

    def test_feedback_decision_enum(self):
        """Test FeedbackDecision enum values."""
        assert FeedbackDecision.APPROVE.value == "approve"
        assert FeedbackDecision.MINOR_CHANGES.value == "minor_changes"
        assert FeedbackDecision.MAJOR_CHANGES.value == "major_changes"

    def test_feedback_mode_enum(self):
        """Test FeedbackMode enum values."""
        assert FeedbackMode.HUMAN.value == "human"
        assert FeedbackMode.SIMULATED.value == "simulated"

    def test_feedback_flags_list(self):
        """Test that all required flags are defined."""
        required_flags = [
            "hook_weak",
            "too_long",
            "too_short",
            "tone_mismatch",
            "cta_unclear",
            "pacing_flat",
            "pacing_rushed",
            "message_unclear",
            "ending_weak",
            "visuals_poor",
            "audio_issues",
            "off_brand",
            "wrong_audience",
        ]
        for flag in required_flags:
            assert flag in FEEDBACK_FLAGS

    def test_attempt_has_feedback_property(self):
        """Test has_feedback property on attempts."""
        attempt = PilotRunAttempt(
            attempt_id="test_1",
            attempt_number=1,
            created_at=datetime.now(timezone.utc),
        )
        assert attempt.has_feedback is False

        # With feedback_decision
        attempt.feedback_decision = FeedbackDecision.APPROVE
        assert attempt.has_feedback is True

    def test_attempt_to_dict_with_feedback(self):
        """Test serialization of attempt with feedback."""
        attempt = PilotRunAttempt(
            attempt_id="test_1",
            attempt_number=1,
            created_at=datetime.now(timezone.utc),
            feedback_mode=FeedbackMode.HUMAN,
            feedback_decision=FeedbackDecision.MINOR_CHANGES,
            feedback_flags=["hook_weak", "too_long"],
            feedback_notes="The hook needs work.",
            feedback_timestamp=datetime.now(timezone.utc),
        )

        data = attempt.to_dict()

        assert data["feedback_mode"] == "human"
        assert data["feedback_decision"] == "minor_changes"
        assert data["feedback_flags"] == ["hook_weak", "too_long"]
        assert data["feedback_notes"] == "The hook needs work."
        assert data["feedback_timestamp"] is not None

    def test_attempt_from_dict_with_feedback(self):
        """Test deserialization of attempt with feedback."""
        data = {
            "attempt_id": "test_1",
            "attempt_number": 1,
            "created_at": "2024-01-15T10:00:00+00:00",
            "feedback_mode": "simulated",
            "feedback_decision": "major_changes",
            "feedback_flags": ["cta_unclear"],
            "feedback_notes": "CTA is buried.",
            "feedback_timestamp": "2024-01-15T11:00:00+00:00",
            "feedback_persona": "growth_marketer",
        }

        attempt = PilotRunAttempt.from_dict(data)

        assert attempt.feedback_mode == FeedbackMode.SIMULATED
        assert attempt.feedback_decision == FeedbackDecision.MAJOR_CHANGES
        assert attempt.feedback_flags == ["cta_unclear"]
        assert attempt.feedback_notes == "CTA is buried."
        assert attempt.feedback_persona == "growth_marketer"

    def test_attempt_backward_compatibility(self):
        """Test backward compatibility with legacy fields."""
        data = {
            "attempt_id": "test_1",
            "attempt_number": 1,
            "created_at": "2024-01-15T10:00:00+00:00",
            # Legacy fields
            "feedback_level": "minor_changes",
            "founder_feedback": "Old style feedback",
            "feedback_received_at": "2024-01-15T11:00:00+00:00",
        }

        attempt = PilotRunAttempt.from_dict(data)

        # Should map legacy to new fields
        assert attempt.feedback_decision == FeedbackDecision.MINOR_CHANGES
        assert attempt.feedback_notes == "Old style feedback"
        assert attempt.has_feedback is True


class TestPilotRecordFeedback:
    """Test pilot.record_feedback method."""

    def test_record_feedback_basic(self):
        """Test recording basic feedback."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        pilot.add_attempt(video_path="test.mp4")

        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.APPROVE,
            flags=[],
            notes="Looks good!",
        )

        attempt = pilot.get_attempt(1)
        assert attempt.feedback_decision == FeedbackDecision.APPROVE
        assert attempt.feedback_notes == "Looks good!"
        assert attempt.feedback_mode == FeedbackMode.HUMAN

    def test_record_feedback_with_flags(self):
        """Test recording feedback with flags."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        pilot.add_attempt(video_path="test.mp4")

        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.MAJOR_CHANGES,
            flags=["hook_weak", "too_long", "pacing_flat"],
            notes="Start over.",
        )

        attempt = pilot.get_attempt(1)
        assert attempt.feedback_decision == FeedbackDecision.MAJOR_CHANGES
        assert attempt.feedback_flags == ["hook_weak", "too_long", "pacing_flat"]

    def test_record_simulated_feedback(self):
        """Test recording simulated feedback."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        pilot.add_attempt(video_path="test.mp4")

        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.MINOR_CHANGES,
            flags=["hook_weak"],
            notes="Hook needs work.",
            mode=FeedbackMode.SIMULATED,
            persona="speed_saas_founder",
        )

        attempt = pilot.get_attempt(1)
        assert attempt.feedback_mode == FeedbackMode.SIMULATED
        assert attempt.feedback_persona == "speed_saas_founder"

    def test_record_feedback_auto_approves_pilot(self):
        """Test that APPROVE decision auto-approves pilot."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        pilot.add_attempt(video_path="test.mp4")

        assert pilot.approval_outcome == ApprovalOutcome.PENDING

        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.APPROVE,
        )

        assert pilot.approval_outcome == ApprovalOutcome.APPROVED
        assert pilot.status == PilotStatus.COMPLETED

    def test_record_feedback_string_decision(self):
        """Test recording feedback with string decision."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        pilot.add_attempt(video_path="test.mp4")

        # String instead of enum
        pilot.record_feedback(
            attempt_number=1,
            decision="minor_changes",
            notes="Almost there.",
        )

        attempt = pilot.get_attempt(1)
        assert attempt.feedback_decision == FeedbackDecision.MINOR_CHANGES

    def test_record_feedback_invalid_attempt(self):
        """Test that recording feedback for invalid attempt raises error."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        with pytest.raises(ValueError, match="Attempt 1 not found"):
            pilot.record_feedback(
                attempt_number=1,
                decision=FeedbackDecision.APPROVE,
            )


class TestPilotFeedbackProperties:
    """Test pilot feedback-related properties."""

    def test_latest_has_feedback_no_attempts(self):
        """Test latest_has_feedback with no attempts."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        # No attempts yet - should return True (nothing to check)
        assert pilot.latest_has_feedback is True

    def test_latest_has_feedback_without_feedback(self):
        """Test latest_has_feedback when latest has no feedback."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        pilot.add_attempt(video_path="test.mp4")

        assert pilot.latest_has_feedback is False

    def test_latest_has_feedback_with_feedback(self):
        """Test latest_has_feedback when latest has feedback."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        pilot.add_attempt(video_path="test.mp4")
        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.MINOR_CHANGES,
        )

        assert pilot.latest_has_feedback is True

    def test_missing_feedback_attempts(self):
        """Test missing_feedback_attempts property."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )
        pilot.add_attempt(video_path="test1.mp4")
        pilot.add_attempt(video_path="test2.mp4")
        pilot.add_attempt(video_path="test3.mp4")

        # No feedback yet
        assert pilot.missing_feedback_attempts == [1, 2, 3]

        # Add feedback for attempt 2
        pilot.record_feedback(attempt_number=2, decision=FeedbackDecision.MINOR_CHANGES)

        assert pilot.missing_feedback_attempts == [1, 3]


class TestPilotStoreFeedback:
    """Test pilot store with feedback persistence."""

    def test_save_and_load_with_feedback(self):
        """Test saving and loading pilot with feedback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PilotStore(tmpdir)

            # Create pilot with feedback
            pilot = create_pilot(
                founder_name="Test",
                company_name="TestCo",
                scenario_type="feature_launch",
            )
            pilot.add_attempt(video_path="test.mp4", sla_passed=True)
            pilot.record_feedback(
                attempt_number=1,
                decision=FeedbackDecision.MINOR_CHANGES,
                flags=["hook_weak", "too_long"],
                notes="Hook needs work.",
                mode=FeedbackMode.SIMULATED,
                persona="speed_saas_founder",
            )

            store.save(pilot)

            # Load and verify
            loaded = store.load(pilot.pilot_id)

            assert loaded is not None
            attempt = loaded.get_attempt(1)
            assert attempt.feedback_decision == FeedbackDecision.MINOR_CHANGES
            assert attempt.feedback_flags == ["hook_weak", "too_long"]
            assert attempt.feedback_notes == "Hook needs work."
            assert attempt.feedback_mode == FeedbackMode.SIMULATED
            assert attempt.feedback_persona == "speed_saas_founder"
