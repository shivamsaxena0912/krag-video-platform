"""Unit tests for IterativeRefinementController."""

import pytest
from datetime import datetime

from src.orchestration.refinement import (
    IterativeRefinementController,
    RefinementConfig,
    RefinementResult,
    RefinementIteration,
    RefinementStatus,
    default_fix_function,
    run_refinement_loop,
)
from src.orchestration.feedback_consumer import (
    FeedbackConsumer,
    FeedbackAggregation,
    PlaybookConstraint,
    PlaybookConstraintType,
    ReRankingConfig,
)
from src.common.models import (
    FeedbackAnnotation,
    FeedbackRecommendation,
    DimensionScores,
    FeedbackTargetType,
    FeedbackSource,
)
from src.knowledge_graph.scene_graph import SceneGraph
from src.common.models import Story, Scene, SceneSetting, EmotionalBeat


@pytest.fixture
def sample_scene_graph():
    """Create a sample SceneGraph for testing."""
    story = Story(
        title="Test Story",
        description="A test narrative",
    )

    scenes = [
        Scene(
            story_id=story.id,
            sequence=i,
            raw_text=f"Scene {i} content",
            summary=f"Scene {i} summary",
            setting=SceneSetting(location_name=f"Location {i}"),
            emotional_beat=EmotionalBeat(primary_emotion="neutral"),
        )
        for i in range(3)
    ]

    return SceneGraph(
        story=story,
        scenes=scenes,
        characters=[],
        locations=[],
        shot_plans=[],
        shots=[],
    )


class TestRefinementConfig:
    """Tests for RefinementConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RefinementConfig()

        assert config.max_iterations == 5
        assert config.min_iterations == 1
        assert config.max_cost_dollars == 10.0
        assert config.target_overall_score == 7.5
        assert config.improvement_threshold == 0.5

    def test_dimension_weights(self):
        """Test dimension weights are set correctly."""
        config = RefinementConfig()

        assert config.dimension_weights["hook_strength"] == 1.5
        assert config.dimension_weights["narrative_clarity"] == 1.2
        assert config.dimension_weights["pacing"] == 1.0

    def test_custom_values(self):
        """Test custom configuration."""
        config = RefinementConfig(
            max_iterations=3,
            max_cost_dollars=5.0,
            target_overall_score=8.0,
        )

        assert config.max_iterations == 3
        assert config.max_cost_dollars == 5.0
        assert config.target_overall_score == 8.0


class TestRefinementResult:
    """Tests for RefinementResult."""

    def test_initial_state(self):
        """Test initial result state."""
        result = RefinementResult()

        assert result.status == RefinementStatus.NOT_STARTED
        assert result.iterations_completed == 0
        assert result.total_cost == 0.0
        assert len(result.iterations) == 0

    def test_model_copy_updates(self):
        """Test immutable updates via model_copy."""
        result = RefinementResult()

        updated = result.model_copy(update={
            "status": RefinementStatus.IN_PROGRESS,
            "iterations_completed": 1,
        })

        assert updated.status == RefinementStatus.IN_PROGRESS
        assert updated.iterations_completed == 1
        # Original unchanged
        assert result.status == RefinementStatus.NOT_STARTED


class TestRefinementIteration:
    """Tests for RefinementIteration."""

    def test_iteration_creation(self):
        """Test creating an iteration record."""
        iteration = RefinementIteration(
            iteration=0,
            input_score=5.0,
            output_score=6.0,
            score_improvement=1.0,
            issues_identified=3,
            fixes_applied=2,
        )

        assert iteration.iteration == 0
        assert iteration.score_improvement == 1.0
        assert iteration.issues_identified == 3


class TestIterativeRefinementController:
    """Tests for IterativeRefinementController."""

    def test_initialization(self):
        """Test controller initialization."""
        controller = IterativeRefinementController()

        assert controller.config.max_iterations == 5
        assert controller.critic is not None

    def test_custom_config(self):
        """Test controller with custom config."""
        config = RefinementConfig(max_iterations=3)
        controller = IterativeRefinementController(config=config)

        assert controller.config.max_iterations == 3

    @pytest.mark.asyncio
    async def test_run_returns_result(self, sample_scene_graph):
        """Test run returns SceneGraph and RefinementResult."""
        controller = IterativeRefinementController(
            config=RefinementConfig(max_iterations=1),
        )

        refined_graph, result = await controller.run(sample_scene_graph)

        assert isinstance(refined_graph, SceneGraph)
        assert isinstance(result, RefinementResult)
        assert result.iterations_completed >= 1

    @pytest.mark.asyncio
    async def test_run_records_iterations(self, sample_scene_graph):
        """Test run records iteration history."""
        controller = IterativeRefinementController(
            config=RefinementConfig(max_iterations=2),
        )

        _, result = await controller.run(sample_scene_graph)

        assert len(result.iterations) >= 1
        for iteration in result.iterations:
            assert iteration.input_score >= 0
            assert iteration.iteration_cost >= 0

    @pytest.mark.asyncio
    async def test_budget_enforcement(self, sample_scene_graph):
        """Test budget cap is enforced."""
        controller = IterativeRefinementController(
            config=RefinementConfig(
                max_iterations=10,
                max_cost_dollars=0.10,  # Very low budget
                cost_per_critique=0.05,
            ),
        )

        _, result = await controller.run(sample_scene_graph)

        assert result.total_cost <= 0.20  # Allow small overage
        assert result.status in [
            RefinementStatus.BUDGET_EXCEEDED,
            RefinementStatus.CONVERGED,
            RefinementStatus.MAX_ITERATIONS,
        ]

    @pytest.mark.asyncio
    async def test_max_iterations_respected(self, sample_scene_graph):
        """Test max iterations cap is respected."""
        controller = IterativeRefinementController(
            config=RefinementConfig(max_iterations=2),
        )

        _, result = await controller.run(sample_scene_graph)

        assert result.iterations_completed <= 2

    @pytest.mark.asyncio
    async def test_fix_function_called(self, sample_scene_graph):
        """Test fix function is called when provided."""
        fix_called = {"count": 0}

        def custom_fix(scene_graph, critic_output):
            fix_called["count"] += 1
            return scene_graph

        controller = IterativeRefinementController(
            config=RefinementConfig(max_iterations=2),
        )

        await controller.run(sample_scene_graph, fix_function=custom_fix)

        # Fix function should be called at least once
        assert fix_called["count"] >= 1

    def test_prioritize_issues_by_weight(self):
        """Test issue prioritization."""
        from src.common.models import FeedbackIssue, FixCategory, IssueSeverity

        controller = IterativeRefinementController()

        issues = [
            FeedbackIssue(
                category=FixCategory.PACING,
                severity=IssueSeverity.MINOR,
                description="Pacing issue",
            ),
            FeedbackIssue(
                category=FixCategory.HOOK,
                severity=IssueSeverity.MAJOR,
                description="Hook issue",
            ),
        ]

        prioritized = controller._prioritize_issues(issues)

        # Hook should be first (higher weight + major severity)
        assert prioritized[0].category == FixCategory.HOOK


class TestDefaultFixFunction:
    """Tests for default_fix_function."""

    @pytest.mark.asyncio
    async def test_returns_scene_graph(self, sample_scene_graph):
        """Test default fix function returns SceneGraph."""
        from src.agents import CriticAgent, CriticInput

        critic = CriticAgent()
        critic_output = await critic(CriticInput(scene_graph=sample_scene_graph))

        result = default_fix_function(sample_scene_graph, critic_output)

        assert isinstance(result, SceneGraph)
        assert result.story.id == sample_scene_graph.story.id


class TestRunRefinementLoop:
    """Tests for run_refinement_loop convenience function."""

    @pytest.mark.asyncio
    async def test_convenience_function(self, sample_scene_graph):
        """Test the convenience function works."""
        refined, result = await run_refinement_loop(
            sample_scene_graph,
            max_iterations=1,
            max_cost=1.0,
        )

        assert isinstance(refined, SceneGraph)
        assert isinstance(result, RefinementResult)


class TestFeedbackConsumer:
    """Tests for FeedbackConsumer."""

    def test_initialization(self):
        """Test consumer initialization."""
        consumer = FeedbackConsumer()

        assert consumer.rerank_config is not None

    def test_parse_constraint_string(self):
        """Test constraint string parsing."""
        consumer = FeedbackConsumer()

        constraint = consumer._parse_constraint_string(
            "min_duration:3.0",
            "feedback_001",
        )

        assert constraint is not None
        assert constraint.constraint_type == PlaybookConstraintType.MIN_SHOT_DURATION
        assert constraint.value == "3.0"
        assert constraint.source_feedback_id == "feedback_001"

    def test_rerank_score_with_positive_feedback(self):
        """Test score boosting for positive feedback."""
        consumer = FeedbackConsumer()

        feedback = FeedbackAnnotation(
            target_type=FeedbackTargetType.STORY,
            target_id="story_001",
            source=FeedbackSource.HUMAN_EXPERT,
            dimension_scores=DimensionScores(),
            overall_score=8.0,  # High score
            recommendation=FeedbackRecommendation.APPROVE,
        )

        base_score = 0.5
        reranked = consumer.compute_rerank_score(base_score, feedback)

        # Should be boosted
        assert reranked > base_score

    def test_rerank_score_with_negative_feedback(self):
        """Test score penalty for negative feedback."""
        consumer = FeedbackConsumer()

        feedback = FeedbackAnnotation(
            target_type=FeedbackTargetType.STORY,
            target_id="story_001",
            source=FeedbackSource.HUMAN_EXPERT,
            dimension_scores=DimensionScores(),
            overall_score=3.0,  # Low score
            recommendation=FeedbackRecommendation.REJECT,
        )

        base_score = 0.5
        reranked = consumer.compute_rerank_score(base_score, feedback)

        # Should be penalized
        assert reranked < base_score

    def test_rerank_score_no_feedback(self):
        """Test score unchanged with no feedback."""
        consumer = FeedbackConsumer()

        base_score = 0.5
        reranked = consumer.compute_rerank_score(base_score, None)

        assert reranked == base_score


class TestReRankingConfig:
    """Tests for ReRankingConfig."""

    def test_default_values(self):
        """Test default re-ranking configuration."""
        config = ReRankingConfig()

        assert config.positive_boost == 1.5
        assert config.approve_boost == 2.0
        assert config.negative_penalty == 0.5
        assert config.recency_half_life_days == 30


class TestPlaybookConstraint:
    """Tests for PlaybookConstraint."""

    def test_to_string(self):
        """Test constraint string conversion."""
        constraint = PlaybookConstraint(
            constraint_type=PlaybookConstraintType.MIN_SHOT_DURATION,
            value="3.0",
        )

        assert constraint.to_string() == "min_shot_duration:3.0"

    def test_weight_default(self):
        """Test default weight is 1.0."""
        constraint = PlaybookConstraint(
            constraint_type=PlaybookConstraintType.PREFER_STATIC,
            value="true",
        )

        assert constraint.weight == 1.0
