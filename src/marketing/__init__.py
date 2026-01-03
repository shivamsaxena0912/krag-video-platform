"""Marketing intent and preset configuration."""

from src.marketing.intent import (
    MarketingIntent,
    MarketingPreset,
    get_preset,
    PRESETS,
)
from src.marketing.adapter import (
    create_director_config,
    create_editorial_config,
    create_rhythm_config,
    get_configs_for_intent,
)
from src.marketing.summary import (
    generate_marketing_summary,
    MarketingSummary,
)
from src.marketing.validation import (
    SLAValidator,
    SLAViolation,
    SLAReport,
    validate_pipeline_sla,
    enforce_sla,
)

__all__ = [
    # Intent
    "MarketingIntent",
    "MarketingPreset",
    "get_preset",
    "PRESETS",
    # Adapter
    "create_director_config",
    "create_editorial_config",
    "create_rhythm_config",
    "get_configs_for_intent",
    # Summary
    "generate_marketing_summary",
    "MarketingSummary",
    # Validation
    "SLAValidator",
    "SLAViolation",
    "SLAReport",
    "validate_pipeline_sla",
    "enforce_sla",
]
