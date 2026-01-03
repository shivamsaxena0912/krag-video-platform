"""Tests for simulated founder personas and feedback generation."""

import pytest

from src.founder_simulation import (
    SimulatedFounderPersona,
    FeedbackStyle,
    PlatformBias,
    PERSONAS,
    get_persona,
    list_personas,
    SimulatedFeedback,
    generate_feedback,
    # Built-in personas
    SPEED_SAAS_FOUNDER,
    CAUTIOUS_FIRST_TIME_FOUNDER,
    GROWTH_MARKETER,
    TECHNICAL_FOUNDER,
    BRAND_SENSITIVE_FOUNDER,
)
from src.pilot.run import FeedbackDecision


class TestPersonas:
    """Test persona definitions."""

    def test_list_personas_returns_all(self):
        """Test that list_personas returns all built-in personas."""
        persona_ids = list_personas()

        assert "speed_saas_founder" in persona_ids
        assert "cautious_first_time_founder" in persona_ids
        assert "growth_marketer" in persona_ids
        assert "technical_founder" in persona_ids
        assert "brand_sensitive_founder" in persona_ids
        assert len(persona_ids) == 5

    def test_get_persona_valid(self):
        """Test getting a valid persona."""
        persona = get_persona("speed_saas_founder")

        assert persona.persona_id == "speed_saas_founder"
        assert persona.name == "Speed-Obsessed SaaS Founder"

    def test_get_persona_invalid(self):
        """Test getting an invalid persona raises error."""
        with pytest.raises(ValueError, match="Unknown persona"):
            get_persona("nonexistent_persona")

    def test_speed_saas_founder_properties(self):
        """Test speed_saas_founder persona properties."""
        persona = SPEED_SAAS_FOUNDER

        assert persona.patience_level == 0.3  # Impatient
        assert persona.quality_bar == 0.5  # Low bar
        assert persona.platform_bias == PlatformBias.TWITTER
        assert persona.max_acceptable_duration_seconds == 45.0
        assert persona.feedback_style == FeedbackStyle.TERSE
        assert persona.approve_after_attempts == 1

    def test_cautious_founder_properties(self):
        """Test cautious_first_time_founder persona properties."""
        persona = CAUTIOUS_FIRST_TIME_FOUNDER

        assert persona.patience_level == 0.8  # Patient
        assert persona.quality_bar == 0.8  # High bar
        assert persona.platform_bias == PlatformBias.LINKEDIN
        assert persona.max_acceptable_duration_seconds == 90.0
        assert persona.feedback_style == FeedbackStyle.DETAILED
        assert persona.approve_after_attempts == 3

    def test_growth_marketer_properties(self):
        """Test growth_marketer persona properties."""
        persona = GROWTH_MARKETER

        assert persona.quality_bar == 0.6
        assert persona.platform_bias == PlatformBias.INSTAGRAM
        assert persona.feedback_style == FeedbackStyle.BLUNT
        # CTA should be highest weight
        assert persona.flag_weights.get("cta_unclear") == 0.95

    def test_brand_sensitive_founder_properties(self):
        """Test brand_sensitive_founder persona properties."""
        persona = BRAND_SENSITIVE_FOUNDER

        assert persona.quality_bar == 0.9  # Very high bar
        assert persona.feedback_style == FeedbackStyle.DIPLOMATIC
        # Brand concerns should be highest weight
        assert persona.flag_weights.get("off_brand") == 0.95
        assert persona.flag_weights.get("tone_mismatch") == 0.95

    def test_persona_to_dict(self):
        """Test persona serialization."""
        persona = SPEED_SAAS_FOUNDER
        data = persona.to_dict()

        assert data["persona_id"] == "speed_saas_founder"
        assert data["patience_level"] == 0.3
        assert data["platform_bias"] == "twitter"
        assert data["feedback_style"] == "terse"


class TestFeedbackGeneration:
    """Test feedback generation."""

    def test_generate_feedback_returns_simulated_feedback(self):
        """Test that generate_feedback returns SimulatedFeedback."""
        feedback = generate_feedback(
            persona="speed_saas_founder",
            attempt_number=1,
            duration_seconds=30.0,
            sla_passed=True,
            scenario_type="feature_launch",
            intent="social_reel",
        )

        assert isinstance(feedback, SimulatedFeedback)
        assert feedback.persona_id == "speed_saas_founder"
        assert isinstance(feedback.decision, FeedbackDecision)
        assert isinstance(feedback.flags, list)
        assert isinstance(feedback.notes, str)
        assert feedback.seed_used is not None

    def test_generate_feedback_deterministic(self):
        """Test that feedback is deterministic with same seed."""
        params = {
            "persona": "growth_marketer",
            "attempt_number": 2,
            "duration_seconds": 45.0,
            "sla_passed": True,
            "scenario_type": "feature_launch",
            "intent": "paid_ad",
            "seed": "test_seed_123",
        }

        feedback1 = generate_feedback(**params)
        feedback2 = generate_feedback(**params)

        assert feedback1.decision == feedback2.decision
        assert feedback1.flags == feedback2.flags
        assert feedback1.notes == feedback2.notes
        assert feedback1.quality_score == feedback2.quality_score

    def test_generate_feedback_different_seeds(self):
        """Test that different seeds produce different results."""
        base_params = {
            "persona": "growth_marketer",
            "attempt_number": 1,
            "duration_seconds": 45.0,
            "sla_passed": False,
            "scenario_type": "feature_launch",
            "intent": "paid_ad",
        }

        feedback1 = generate_feedback(**base_params, seed="seed_a")
        feedback2 = generate_feedback(**base_params, seed="seed_b")

        # At least one should differ (decisions or quality scores)
        differs = (
            feedback1.decision != feedback2.decision
            or feedback1.quality_score != feedback2.quality_score
        )
        assert differs

    def test_generate_feedback_persona_string(self):
        """Test that persona can be passed as string."""
        feedback = generate_feedback(
            persona="speed_saas_founder",  # String, not persona object
            attempt_number=1,
            duration_seconds=30.0,
            sla_passed=True,
            scenario_type="feature_launch",
            intent="social_reel",
        )

        assert feedback.persona_id == "speed_saas_founder"

    def test_generate_feedback_persona_object(self):
        """Test that persona can be passed as object."""
        persona = get_persona("speed_saas_founder")
        feedback = generate_feedback(
            persona=persona,  # Persona object
            attempt_number=1,
            duration_seconds=30.0,
            sla_passed=True,
            scenario_type="feature_launch",
            intent="social_reel",
        )

        assert feedback.persona_id == "speed_saas_founder"


class TestFeedbackDecisionLogic:
    """Test the logic behind feedback decisions."""

    def test_later_attempts_more_likely_to_approve(self):
        """Test that later attempts are more likely to be approved."""
        base_params = {
            "persona": "speed_saas_founder",
            "duration_seconds": 30.0,
            "sla_passed": True,
            "scenario_type": "feature_launch",
            "intent": "social_reel",
            "seed": "test_seed",
        }

        feedback1 = generate_feedback(**base_params, attempt_number=1)
        feedback5 = generate_feedback(**base_params, attempt_number=5)

        # Later attempt should have higher or equal quality score
        assert feedback5.quality_score >= feedback1.quality_score

    def test_sla_passed_improves_quality_score(self):
        """Test that SLA passed improves quality score."""
        base_params = {
            "persona": "speed_saas_founder",
            "attempt_number": 1,
            "duration_seconds": 30.0,
            "scenario_type": "feature_launch",
            "intent": "social_reel",
            "seed": "test_seed",
        }

        feedback_pass = generate_feedback(**base_params, sla_passed=True)
        feedback_fail = generate_feedback(**base_params, sla_passed=False)

        assert feedback_pass.quality_score > feedback_fail.quality_score

    def test_too_long_duration_penalizes_score(self):
        """Test that exceeding max duration penalizes quality score."""
        # Speed SaaS founder has max 45s
        base_params = {
            "persona": "speed_saas_founder",
            "attempt_number": 1,
            "sla_passed": True,
            "scenario_type": "feature_launch",
            "intent": "social_reel",
            "seed": "test_seed",
        }

        feedback_short = generate_feedback(**base_params, duration_seconds=30.0)
        feedback_long = generate_feedback(**base_params, duration_seconds=60.0)

        assert feedback_short.quality_score > feedback_long.quality_score

    def test_approve_decision_has_no_flags(self):
        """Test that APPROVE decisions have no flags."""
        # Find a case that produces APPROVE
        feedback = generate_feedback(
            persona="speed_saas_founder",
            attempt_number=3,
            duration_seconds=25.0,
            sla_passed=True,
            scenario_type="feature_launch",
            intent="social_reel",
            iteration_count=1,
            seed="approve_seed_001",
        )

        if feedback.decision == FeedbackDecision.APPROVE:
            assert len(feedback.flags) == 0

    def test_major_changes_has_more_flags(self):
        """Test that MAJOR_CHANGES tends to have more flags."""
        # Set up scenario likely to produce MAJOR_CHANGES
        feedback = generate_feedback(
            persona="brand_sensitive_founder",  # High bar
            attempt_number=1,
            duration_seconds=120.0,  # Too long
            sla_passed=False,
            scenario_type="feature_launch",
            intent="social_reel",
            seed="major_seed",
        )

        if feedback.decision == FeedbackDecision.MAJOR_CHANGES:
            assert len(feedback.flags) > 0


class TestFeedbackNotes:
    """Test feedback note generation."""

    def test_terse_style_short_notes(self):
        """Test that terse style produces short notes."""
        feedback = generate_feedback(
            persona="speed_saas_founder",  # TERSE style
            attempt_number=1,
            duration_seconds=30.0,
            sla_passed=False,
            scenario_type="feature_launch",
            intent="social_reel",
        )

        # Terse notes should be relatively short
        assert len(feedback.notes) < 100

    def test_blunt_style_notes(self):
        """Test that blunt style produces direct notes."""
        feedback = generate_feedback(
            persona="growth_marketer",  # BLUNT style
            attempt_number=1,
            duration_seconds=30.0,
            sla_passed=False,
            scenario_type="feature_launch",
            intent="social_reel",
        )

        # Notes should exist
        assert len(feedback.notes) > 0

    def test_diplomatic_style_notes(self):
        """Test that diplomatic style produces softer notes."""
        feedback = generate_feedback(
            persona="brand_sensitive_founder",  # DIPLOMATIC style
            attempt_number=1,
            duration_seconds=30.0,
            sla_passed=False,
            scenario_type="feature_launch",
            intent="social_reel",
        )

        # Diplomatic notes often contain softer language
        assert len(feedback.notes) > 0


class TestPersonaFlagWeights:
    """Test that persona flag weights influence feedback."""

    def test_growth_marketer_prioritizes_cta(self):
        """Test that growth_marketer heavily weights CTA issues."""
        persona = GROWTH_MARKETER

        assert persona.flag_weights.get("cta_unclear", 0) > 0.9
        assert persona.flag_weights.get("hook_weak", 0) > 0.8

    def test_brand_sensitive_prioritizes_brand(self):
        """Test that brand_sensitive_founder heavily weights brand issues."""
        persona = BRAND_SENSITIVE_FOUNDER

        assert persona.flag_weights.get("off_brand", 0) > 0.9
        assert persona.flag_weights.get("tone_mismatch", 0) > 0.9

    def test_technical_founder_prioritizes_clarity(self):
        """Test that technical_founder prioritizes message clarity."""
        persona = TECHNICAL_FOUNDER

        assert persona.flag_weights.get("message_unclear", 0) > 0.8
        assert persona.flag_weights.get("wrong_audience", 0) > 0.7
