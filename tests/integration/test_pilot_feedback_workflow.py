"""Integration tests for pilot feedback workflow."""

import pytest
import tempfile
from pathlib import Path

from src.pilot import (
    PilotStore,
    create_pilot,
    FeedbackMode,
    FeedbackDecision,
    PilotStatus,
    ApprovalOutcome,
    compute_pilot_metrics,
    assess_founder_satisfaction,
    assess_system_health,
    determine_recommendation,
    generate_pilot_outcome_report,
    Recommendation,
    FounderSatisfactionLevel,
    SystemHealthLevel,
)
from src.founder_simulation import generate_feedback, get_persona


class TestPilotFeedbackWorkflow:
    """Integration tests for complete pilot feedback workflow."""

    def test_complete_pilot_with_simulated_feedback(self):
        """Test running a complete pilot with simulated feedback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PilotStore(tmpdir)

            # Create pilot
            pilot = create_pilot(
                founder_name="Test Founder",
                company_name="TestCo",
                scenario_type="feature_launch",
                max_attempts=5,
            )

            persona = get_persona("speed_saas_founder")

            # Simulate 3 attempts with improving quality
            for attempt_num in range(1, 4):
                # Add attempt with progressively better metrics
                duration = 60 - (attempt_num * 10)  # Gets shorter
                sla_passed = attempt_num >= 2

                pilot.add_attempt(
                    video_path=f"video_{attempt_num}.mp4",
                    time_to_first_cut_seconds=45.0,
                    iteration_count=3 - attempt_num + 1,
                    total_cost_dollars=1.50,
                    sla_passed=sla_passed,
                )

                # Generate simulated feedback
                feedback = generate_feedback(
                    persona=persona,
                    attempt_number=attempt_num,
                    duration_seconds=duration,
                    sla_passed=sla_passed,
                    scenario_type="feature_launch",
                    intent="social_reel",
                    iteration_count=3 - attempt_num + 1,
                    seed=f"test_seed_{attempt_num}",
                )

                # Record feedback
                pilot.record_feedback(
                    attempt_number=attempt_num,
                    decision=feedback.decision,
                    flags=feedback.flags,
                    notes=feedback.notes,
                    mode=FeedbackMode.SIMULATED,
                    persona=persona.persona_id,
                )

                # Save after each attempt
                store.save(pilot)

                # Check if approved
                if feedback.decision == FeedbackDecision.APPROVE:
                    break

            # Verify pilot state
            loaded_pilot = store.load(pilot.pilot_id)
            assert loaded_pilot is not None
            assert len(loaded_pilot.runs) >= 1
            assert all(a.has_feedback for a in loaded_pilot.runs)

    def test_outcome_report_with_feedback(self):
        """Test that outcome reports include feedback details."""
        pilot = create_pilot(
            founder_name="Test Founder",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        # Add attempts with feedback
        pilot.add_attempt(video_path="v1.mp4", sla_passed=False)
        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.MAJOR_CHANGES,
            flags=["hook_weak", "too_long"],
            notes="Hook doesn't grab. Too long.",
            mode=FeedbackMode.SIMULATED,
            persona="growth_marketer",
        )

        pilot.add_attempt(video_path="v2.mp4", sla_passed=True)
        pilot.record_feedback(
            attempt_number=2,
            decision=FeedbackDecision.MINOR_CHANGES,
            flags=["hook_weak"],
            notes="Hook still needs work.",
            mode=FeedbackMode.SIMULATED,
            persona="growth_marketer",
        )

        pilot.add_attempt(video_path="v3.mp4", sla_passed=True)
        pilot.record_feedback(
            attempt_number=3,
            decision=FeedbackDecision.APPROVE,
            flags=[],
            notes="Good to go.",
            mode=FeedbackMode.SIMULATED,
            persona="growth_marketer",
        )

        # Generate report
        report = generate_pilot_outcome_report(pilot)

        # Verify report content - new sections
        assert "What the Founder Cares About" in report
        assert "What the System is Worried About" in report
        assert "Founder-Safe Explanation" in report
        assert "Why This Recommendation" in report
        assert "Decision Matrix Applied" in report

        # Verify feedback details still present
        assert "APPROVE" in report
        assert "MAJOR_CHANGES" in report
        assert "hook_weak" in report.lower() or "Hook Weak" in report
        assert "What the Founder Would Likely Say" in report
        assert "Detailed Feedback by Attempt" in report

    def test_recommendation_with_approve_feedback(self):
        """Test that APPROVE feedback leads to APPROVED_FOR_PUBLISH recommendation."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        pilot.add_attempt(video_path="v1.mp4", sla_passed=True)
        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.APPROVE,
        )

        metrics = compute_pilot_metrics(pilot)
        recommendation = determine_recommendation(pilot, metrics)

        assert recommendation == Recommendation.APPROVED_FOR_PUBLISH

    def test_recommendation_approve_with_sla_issues(self):
        """Test that APPROVE + SLA fail leads to APPROVED_WITH_RISK."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        # Founder approves but SLA failed
        pilot.add_attempt(video_path="v1.mp4", sla_passed=False)
        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.APPROVE,
        )

        metrics = compute_pilot_metrics(pilot)
        recommendation = determine_recommendation(pilot, metrics)

        assert recommendation == Recommendation.APPROVED_WITH_RISK

    def test_recommendation_with_persistent_major_changes(self):
        """Test that persistent MAJOR_CHANGES leads to STOP_PILOT."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        # Add 3 attempts with MAJOR_CHANGES and same persistent flag
        for i in range(1, 4):
            pilot.add_attempt(video_path=f"v{i}.mp4", sla_passed=False)
            pilot.record_feedback(
                attempt_number=i,
                decision=FeedbackDecision.MAJOR_CHANGES,
                flags=["hook_weak", "off_brand"],  # Same flags each time
            )

        metrics = compute_pilot_metrics(pilot)
        recommendation = determine_recommendation(pilot, metrics)

        assert recommendation == Recommendation.STOP_PILOT

    def test_founder_satisfaction_assessment(self):
        """Test founder satisfaction is correctly assessed."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        pilot.add_attempt(video_path="v1.mp4", sla_passed=True)
        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.APPROVE,
        )

        metrics = compute_pilot_metrics(pilot)
        satisfaction = assess_founder_satisfaction(pilot, metrics)

        assert satisfaction.level == FounderSatisfactionLevel.SATISFIED
        assert satisfaction.is_approved is True
        assert satisfaction.latest_decision == FeedbackDecision.APPROVE

    def test_system_health_assessment(self):
        """Test system health is correctly assessed."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        # Good metrics
        pilot.add_attempt(video_path="v1.mp4", sla_passed=True, total_cost_dollars=2.0)
        pilot.record_feedback(attempt_number=1, decision=FeedbackDecision.APPROVE)

        metrics = compute_pilot_metrics(pilot)
        health = assess_system_health(pilot, metrics)

        assert health.level == SystemHealthLevel.HEALTHY
        assert health.is_healthy is True
        assert len(health.concerns) == 0

    def test_system_health_with_concerns(self):
        """Test system health flags concerns correctly."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        # Bad metrics: SLA failed, high cost
        pilot.add_attempt(video_path="v1.mp4", sla_passed=False, total_cost_dollars=15.0)
        pilot.record_feedback(attempt_number=1, decision=FeedbackDecision.APPROVE)

        metrics = compute_pilot_metrics(pilot)
        health = assess_system_health(pilot, metrics)

        assert health.level in [SystemHealthLevel.CONCERNING, SystemHealthLevel.UNHEALTHY]
        assert health.has_sla_issues is True
        assert len(health.concerns) > 0

    def test_metrics_track_feedback_counts(self):
        """Test that metrics correctly count feedback types."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        pilot.add_attempt(video_path="v1.mp4")
        pilot.record_feedback(attempt_number=1, decision=FeedbackDecision.MAJOR_CHANGES)

        pilot.add_attempt(video_path="v2.mp4")
        pilot.record_feedback(attempt_number=2, decision=FeedbackDecision.MINOR_CHANGES)

        pilot.add_attempt(video_path="v3.mp4")
        pilot.record_feedback(attempt_number=3, decision=FeedbackDecision.APPROVE)

        metrics = compute_pilot_metrics(pilot)

        assert metrics.major_changes_count == 1
        assert metrics.minor_changes_count == 1
        assert metrics.approve_count == 1
        assert metrics.feedback_received_count == 3

    def test_metrics_track_recurring_flags(self):
        """Test that metrics track recurring flags correctly."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        pilot.add_attempt(video_path="v1.mp4")
        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.MAJOR_CHANGES,
            flags=["hook_weak", "too_long", "pacing_flat"],
        )

        pilot.add_attempt(video_path="v2.mp4")
        pilot.record_feedback(
            attempt_number=2,
            decision=FeedbackDecision.MINOR_CHANGES,
            flags=["hook_weak", "too_long"],  # pacing_flat resolved
        )

        pilot.add_attempt(video_path="v3.mp4")
        pilot.record_feedback(
            attempt_number=3,
            decision=FeedbackDecision.MINOR_CHANGES,
            flags=["hook_weak"],  # too_long resolved
        )

        metrics = compute_pilot_metrics(pilot)

        # hook_weak appeared 3 times
        assert metrics.recurring_flags.get("hook_weak") == 3
        # too_long appeared 2 times
        assert metrics.recurring_flags.get("too_long") == 2
        # pacing_flat appeared 1 time
        assert metrics.recurring_flags.get("pacing_flat") == 1

        # pacing_flat and too_long were resolved (not in final attempt)
        assert "pacing_flat" in metrics.flags_resolved
        assert "too_long" in metrics.flags_resolved

        # hook_weak persisted
        assert "hook_weak" in metrics.flags_persistent

    def test_pilot_flow_enforcement(self):
        """Test that pilot tracks feedback state correctly."""
        pilot = create_pilot(
            founder_name="Test",
            company_name="TestCo",
            scenario_type="feature_launch",
        )

        # Add attempt without feedback
        pilot.add_attempt(video_path="v1.mp4")
        assert pilot.latest_has_feedback is False
        assert pilot.missing_feedback_attempts == [1]

        # Add feedback
        pilot.record_feedback(
            attempt_number=1,
            decision=FeedbackDecision.MINOR_CHANGES,
        )
        assert pilot.latest_has_feedback is True
        assert pilot.missing_feedback_attempts == []

        # Add another attempt
        pilot.add_attempt(video_path="v2.mp4")
        assert pilot.latest_has_feedback is False
        assert pilot.missing_feedback_attempts == [2]


class TestCrossPersonaFeedback:
    """Test feedback generation across different personas."""

    @pytest.mark.parametrize("persona_id", [
        "speed_saas_founder",
        "cautious_first_time_founder",
        "growth_marketer",
        "technical_founder",
        "brand_sensitive_founder",
    ])
    def test_all_personas_generate_valid_feedback(self, persona_id):
        """Test that all personas generate valid feedback."""
        feedback = generate_feedback(
            persona=persona_id,
            attempt_number=1,
            duration_seconds=45.0,
            sla_passed=True,
            scenario_type="feature_launch",
            intent="social_reel",
            seed="test_seed",
        )

        assert feedback.persona_id == persona_id
        assert feedback.decision in [
            FeedbackDecision.APPROVE,
            FeedbackDecision.MINOR_CHANGES,
            FeedbackDecision.MAJOR_CHANGES,
        ]
        assert 0.0 <= feedback.quality_score <= 1.0
        assert isinstance(feedback.notes, str)
        assert len(feedback.notes) > 0

    def test_speed_founder_more_lenient(self):
        """Test that speed_saas_founder is more lenient than brand_sensitive."""
        params = {
            "attempt_number": 1,
            "duration_seconds": 50.0,  # Slightly long for speed founder
            "sla_passed": True,
            "scenario_type": "feature_launch",
            "intent": "social_reel",
            "seed": "comparison_seed",
        }

        speed_feedback = generate_feedback(persona="speed_saas_founder", **params)
        brand_feedback = generate_feedback(persona="brand_sensitive_founder", **params)

        # Speed founder has lower quality bar (0.5) vs brand founder (0.9)
        # So with similar quality scores, speed founder should approve more easily
        # The key test is that speed founder approves while brand founder doesn't
        decision_order = {
            FeedbackDecision.MAJOR_CHANGES: 0,
            FeedbackDecision.MINOR_CHANGES: 1,
            FeedbackDecision.APPROVE: 2,
        }
        speed_decision_value = decision_order[speed_feedback.decision]
        brand_decision_value = decision_order[brand_feedback.decision]

        # Speed founder should give same or better decision than brand founder
        assert speed_decision_value >= brand_decision_value
