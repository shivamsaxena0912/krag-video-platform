"""Feedback consumption via playbook constraints and retrieval re-ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from src.common.logging import get_logger
from src.common.models import (
    FeedbackAnnotation,
    FeedbackTargetType,
    FeedbackRecommendation,
    FixCategory,
    IssueSeverity,
)
from src.knowledge_graph import Neo4jClient
from src.rag import QdrantVectorClient

logger = get_logger(__name__)


class PlaybookConstraintType(str, Enum):
    """Types of playbook constraints derived from feedback."""

    # Shot constraints
    AVOID_SHOT_TYPE = "avoid_shot_type"
    PREFER_SHOT_TYPE = "prefer_shot_type"
    MIN_SHOT_DURATION = "min_shot_duration"
    MAX_SHOT_DURATION = "max_shot_duration"

    # Pacing constraints
    PREFER_STATIC = "prefer_static"
    PREFER_DYNAMIC = "prefer_dynamic"
    REDUCE_CUTS = "reduce_cuts"
    INCREASE_CUTS = "increase_cuts"

    # Composition constraints
    PREFER_WIDE = "prefer_wide"
    PREFER_CLOSE = "prefer_close"
    AVOID_EXTREME_ANGLES = "avoid_extreme_angles"

    # Audio constraints
    REDUCE_MUSIC_VOLUME = "reduce_music_volume"
    ADD_AMBIENT_AUDIO = "add_ambient_audio"

    # Other
    CUSTOM = "custom"


@dataclass
class PlaybookConstraint:
    """A constraint derived from feedback."""

    constraint_type: PlaybookConstraintType
    value: str
    weight: float = 1.0  # How strongly to apply
    source_feedback_id: str | None = None
    expires_at: datetime | None = None

    def to_string(self) -> str:
        """Convert to string format for DirectorAgent."""
        return f"{self.constraint_type.value}:{self.value}"


class ReRankingConfig(BaseModel):
    """Configuration for retrieval re-ranking."""

    # Boost factors for positive feedback
    positive_boost: float = 1.5
    approve_boost: float = 2.0

    # Penalty factors for negative feedback
    negative_penalty: float = 0.5
    reject_penalty: float = 0.1

    # Recency weighting
    recency_half_life_days: int = 30
    min_recency_weight: float = 0.3

    # Score thresholds
    min_score_for_boost: float = 7.0
    max_score_for_penalty: float = 4.0


class FeedbackAggregation(BaseModel):
    """Aggregated feedback statistics."""

    total_feedbacks: int = 0
    avg_overall_score: float = 0.0
    avg_dimension_scores: dict[str, float] = Field(default_factory=dict)

    # Issue frequencies
    issue_category_counts: dict[str, int] = Field(default_factory=dict)
    most_common_issues: list[str] = Field(default_factory=list)

    # Derived constraints
    constraints: list[str] = Field(default_factory=list)


class FeedbackConsumer:
    """
    Consumes feedback to derive playbook constraints and re-rank retrievals.

    Features:
    - Extracts playbook constraints from feedback patterns
    - Re-ranks similar content retrieval based on feedback scores
    - Aggregates feedback for trend analysis
    - Expires old feedback based on recency
    """

    def __init__(
        self,
        neo4j: Neo4jClient | None = None,
        qdrant: QdrantVectorClient | None = None,
        rerank_config: ReRankingConfig | None = None,
    ):
        self.neo4j = neo4j
        self.qdrant = qdrant
        self.rerank_config = rerank_config or ReRankingConfig()

    async def get_playbook_constraints(
        self,
        story_id: str | None = None,
        scene_id: str | None = None,
        limit: int = 20,
    ) -> list[PlaybookConstraint]:
        """
        Get playbook constraints derived from recent feedback.

        Constraints are derived from:
        1. Explicit playbook_constraints in feedback
        2. Patterns in issue categories
        3. Fix requests with high priority
        """
        constraints = []

        if not self.neo4j:
            logger.warning("no_neo4j_client")
            return constraints

        # Fetch relevant feedback
        feedbacks = await self._fetch_recent_feedback(
            story_id=story_id,
            scene_id=scene_id,
            limit=limit,
        )

        logger.info("feedbacks_fetched", count=len(feedbacks))

        for feedback in feedbacks:
            # Extract explicit constraints
            for constraint_str in feedback.playbook_constraints:
                constraint = self._parse_constraint_string(
                    constraint_str,
                    feedback.id,
                )
                if constraint:
                    constraints.append(constraint)

            # Derive constraints from issues
            issue_constraints = self._derive_constraints_from_issues(feedback)
            constraints.extend(issue_constraints)

            # Extract from fix requests
            fix_constraints = self._derive_constraints_from_fixes(feedback)
            constraints.extend(fix_constraints)

        # Deduplicate and weight
        constraints = self._deduplicate_constraints(constraints)

        logger.info("constraints_derived", count=len(constraints))
        return constraints

    async def _fetch_recent_feedback(
        self,
        story_id: str | None = None,
        scene_id: str | None = None,
        limit: int = 20,
        days: int = 90,
    ) -> list[FeedbackAnnotation]:
        """Fetch recent feedback from Neo4j."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Build query based on target
        if story_id:
            query = """
            MATCH (f:Feedback {target_id: $target_id})
            WHERE f.created_at >= $cutoff
            RETURN f
            ORDER BY f.created_at DESC
            LIMIT $limit
            """
            params = {
                "target_id": story_id,
                "cutoff": cutoff.isoformat(),
                "limit": limit,
            }
        elif scene_id:
            query = """
            MATCH (f:Feedback {target_id: $target_id})
            WHERE f.created_at >= $cutoff
            RETURN f
            ORDER BY f.created_at DESC
            LIMIT $limit
            """
            params = {
                "target_id": scene_id,
                "cutoff": cutoff.isoformat(),
                "limit": limit,
            }
        else:
            # Get all recent feedback
            query = """
            MATCH (f:Feedback)
            WHERE f.created_at >= $cutoff
            RETURN f
            ORDER BY f.created_at DESC
            LIMIT $limit
            """
            params = {
                "cutoff": cutoff.isoformat(),
                "limit": limit,
            }

        records = await self.neo4j.execute(query, params)

        feedbacks = []
        for record in records:
            try:
                feedback_data = dict(record["f"])
                # Parse JSON fields if needed
                feedback = FeedbackAnnotation(**feedback_data)
                feedbacks.append(feedback)
            except Exception as e:
                logger.warning("feedback_parse_error", error=str(e))

        return feedbacks

    def _parse_constraint_string(
        self,
        constraint_str: str,
        feedback_id: str,
    ) -> PlaybookConstraint | None:
        """Parse a constraint string into a PlaybookConstraint."""
        try:
            # Format: "constraint_type:value" or "constraint_type"
            if ":" in constraint_str:
                type_str, value = constraint_str.split(":", 1)
            else:
                type_str = constraint_str
                value = "true"

            # Map to enum
            type_mapping = {
                "prefer_static": PlaybookConstraintType.PREFER_STATIC,
                "prefer_dynamic": PlaybookConstraintType.PREFER_DYNAMIC,
                "min_duration": PlaybookConstraintType.MIN_SHOT_DURATION,
                "max_duration": PlaybookConstraintType.MAX_SHOT_DURATION,
                "avoid_extreme_close": PlaybookConstraintType.AVOID_SHOT_TYPE,
                "prefer_wide": PlaybookConstraintType.PREFER_WIDE,
                "prefer_close": PlaybookConstraintType.PREFER_CLOSE,
                "reduce_cuts": PlaybookConstraintType.REDUCE_CUTS,
            }

            constraint_type = type_mapping.get(
                type_str.lower(),
                PlaybookConstraintType.CUSTOM,
            )

            return PlaybookConstraint(
                constraint_type=constraint_type,
                value=value,
                source_feedback_id=feedback_id,
            )

        except Exception as e:
            logger.warning("constraint_parse_error", error=str(e))
            return None

    def _derive_constraints_from_issues(
        self,
        feedback: FeedbackAnnotation,
    ) -> list[PlaybookConstraint]:
        """Derive constraints from issue patterns."""
        constraints = []

        # Count issues by category
        category_counts: dict[FixCategory, int] = {}
        for issue in feedback.issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

        # Derive constraints from frequent issues
        for category, count in category_counts.items():
            if count >= 2:  # Multiple issues in same category
                constraint = self._category_to_constraint(category, feedback)
                if constraint:
                    constraints.append(constraint)

        return constraints

    def _category_to_constraint(
        self,
        category: FixCategory,
        feedback: FeedbackAnnotation,
    ) -> PlaybookConstraint | None:
        """Map issue category to a constraint."""
        mapping = {
            FixCategory.PACING: PlaybookConstraint(
                constraint_type=PlaybookConstraintType.REDUCE_CUTS,
                value="true",
                source_feedback_id=feedback.id,
            ),
            FixCategory.SHOT_COMPOSITION: PlaybookConstraint(
                constraint_type=PlaybookConstraintType.PREFER_WIDE,
                value="true",
                source_feedback_id=feedback.id,
            ),
            FixCategory.CONTINUITY: PlaybookConstraint(
                constraint_type=PlaybookConstraintType.PREFER_STATIC,
                value="true",
                source_feedback_id=feedback.id,
            ),
        }

        return mapping.get(category)

    def _derive_constraints_from_fixes(
        self,
        feedback: FeedbackAnnotation,
    ) -> list[PlaybookConstraint]:
        """Derive constraints from fix requests."""
        constraints = []

        for fix in feedback.fix_requests:
            if fix.action == "adjust_pacing":
                params = fix.parameters or {}
                if params.get("reduce_duration_by_percent", 0) > 0:
                    constraints.append(PlaybookConstraint(
                        constraint_type=PlaybookConstraintType.REDUCE_CUTS,
                        value=str(params["reduce_duration_by_percent"]),
                        weight=fix.priority / 3.0,  # Normalize priority
                        source_feedback_id=feedback.id,
                    ))

            elif fix.action == "prefer_static":
                constraints.append(PlaybookConstraint(
                    constraint_type=PlaybookConstraintType.PREFER_STATIC,
                    value="true",
                    source_feedback_id=feedback.id,
                ))

        return constraints

    def _deduplicate_constraints(
        self,
        constraints: list[PlaybookConstraint],
    ) -> list[PlaybookConstraint]:
        """Deduplicate constraints, keeping highest weight."""
        seen: dict[str, PlaybookConstraint] = {}

        for constraint in constraints:
            key = f"{constraint.constraint_type.value}:{constraint.value}"
            if key not in seen or constraint.weight > seen[key].weight:
                seen[key] = constraint

        return list(seen.values())

    def compute_rerank_score(
        self,
        base_score: float,
        feedback: FeedbackAnnotation | None,
    ) -> float:
        """
        Compute re-ranked score based on feedback.

        Args:
            base_score: Original similarity score (0-1)
            feedback: Associated feedback, if any

        Returns:
            Adjusted score
        """
        if feedback is None:
            return base_score

        config = self.rerank_config

        # Apply boost or penalty based on recommendation
        if feedback.recommendation == FeedbackRecommendation.APPROVE:
            multiplier = config.approve_boost
        elif feedback.recommendation == FeedbackRecommendation.REJECT:
            multiplier = config.reject_penalty
        elif feedback.overall_score >= config.min_score_for_boost:
            multiplier = config.positive_boost
        elif feedback.overall_score <= config.max_score_for_penalty:
            multiplier = config.negative_penalty
        else:
            # Linear interpolation for middle scores
            range_size = config.min_score_for_boost - config.max_score_for_penalty
            position = (feedback.overall_score - config.max_score_for_penalty) / range_size
            multiplier = config.negative_penalty + position * (config.positive_boost - config.negative_penalty)

        # Apply recency weighting
        if feedback.created_at:
            age_days = (datetime.utcnow() - feedback.created_at).days
            recency_factor = 0.5 ** (age_days / config.recency_half_life_days)
            recency_weight = max(config.min_recency_weight, recency_factor)
            # Blend original multiplier with recency
            multiplier = 1.0 + (multiplier - 1.0) * recency_weight

        return min(1.0, base_score * multiplier)

    async def aggregate_feedback(
        self,
        target_id: str | None = None,
        days: int = 90,
    ) -> FeedbackAggregation:
        """Aggregate feedback for analysis."""
        feedbacks = await self._fetch_recent_feedback(
            story_id=target_id,
            limit=100,
            days=days,
        )

        if not feedbacks:
            return FeedbackAggregation()

        # Calculate averages
        total = len(feedbacks)
        sum_overall = sum(f.overall_score for f in feedbacks)

        # Dimension averages
        dim_sums: dict[str, float] = {}
        dim_counts: dict[str, int] = {}
        for f in feedbacks:
            if f.dimension_scores:
                for dim in ["narrative_clarity", "hook_strength", "pacing",
                           "shot_composition", "continuity", "audio_mix"]:
                    score = getattr(f.dimension_scores, dim, 0)
                    dim_sums[dim] = dim_sums.get(dim, 0) + score
                    dim_counts[dim] = dim_counts.get(dim, 0) + 1

        dim_avgs = {
            dim: dim_sums[dim] / dim_counts[dim]
            for dim in dim_sums
            if dim_counts[dim] > 0
        }

        # Issue frequencies
        category_counts: dict[str, int] = {}
        for f in feedbacks:
            for issue in f.issues:
                cat = issue.category.value
                category_counts[cat] = category_counts.get(cat, 0) + 1

        # Sort by frequency
        sorted_categories = sorted(
            category_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        most_common = [cat for cat, _ in sorted_categories[:5]]

        # Derive constraints from patterns
        constraints = []
        for f in feedbacks:
            constraints.extend(f.playbook_constraints)

        return FeedbackAggregation(
            total_feedbacks=total,
            avg_overall_score=sum_overall / total,
            avg_dimension_scores=dim_avgs,
            issue_category_counts=category_counts,
            most_common_issues=most_common,
            constraints=list(set(constraints)),
        )


async def get_constraints_for_story(
    neo4j: Neo4jClient,
    story_id: str,
) -> list[str]:
    """Convenience function to get constraint strings for a story."""
    consumer = FeedbackConsumer(neo4j=neo4j)
    constraints = await consumer.get_playbook_constraints(story_id=story_id)
    return [c.to_string() for c in constraints]
