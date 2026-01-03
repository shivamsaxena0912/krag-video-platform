"""Simulated founder feedback generation.

This module provides personas and feedback generation for
testing pilots without real founders.
"""

from src.founder_simulation.personas import (
    SimulatedFounderPersona,
    FeedbackStyle,
    PlatformBias,
    PERSONAS,
    get_persona,
    list_personas,
    # Built-in personas
    SPEED_SAAS_FOUNDER,
    CAUTIOUS_FIRST_TIME_FOUNDER,
    GROWTH_MARKETER,
    TECHNICAL_FOUNDER,
    BRAND_SENSITIVE_FOUNDER,
)
from src.founder_simulation.generator import (
    SimulatedFeedback,
    generate_feedback,
)

__all__ = [
    # Personas
    "SimulatedFounderPersona",
    "FeedbackStyle",
    "PlatformBias",
    "PERSONAS",
    "get_persona",
    "list_personas",
    # Built-in personas
    "SPEED_SAAS_FOUNDER",
    "CAUTIOUS_FIRST_TIME_FOUNDER",
    "GROWTH_MARKETER",
    "TECHNICAL_FOUNDER",
    "BRAND_SENSITIVE_FOUNDER",
    # Generator
    "SimulatedFeedback",
    "generate_feedback",
]
