"""Iterative Refinement Controller with caps."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable

from pydantic import BaseModel, Field

from src.common.logging import get_logger
from src.common.models import (
    FeedbackAnnotation,
    FeedbackRecommendation,
    DimensionScores,
)
from src.common.models.base import generate_id
from src.knowledge_graph.scene_graph import SceneGraph
from src.agents import CriticAgent, CriticInput, CriticOutput

logger = get_logger(__name__)


class RefinementStatus(str, Enum):
    """Status of refinement process."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    CONVERGED = "converged"  # Quality threshold met
    MAX_ITERATIONS = "max_iterations"  # Hit iteration cap
    BUDGET_EXCEEDED = "budget_exceeded"  # Hit cost cap
    ABORTED = "aborted"
    FAILED = "failed"


class RefinementConfig(BaseModel):
    """Configuration for refinement loop."""

    # Iteration caps - TIGHT DEFAULTS for MVP discipline
    max_iterations: int = 2  # Tight cap: 2-3 max for MVP
    min_iterations: int = 1

    # Budget caps - Aligned to placeholder cost ($0 real gen)
    max_cost_dollars: float = 2.0  # Tight budget for MVP
    cost_per_critique: float = 0.05
    cost_per_fix: float = 0.20  # Lower fix cost for MVP

    # Quality thresholds
    target_overall_score: float = 7.0  # Achievable target
    min_acceptable_score: float = 5.0
    improvement_threshold: float = 0.2  # Tighter epsilon: stop if < 0.2 improvement

    # Dimension weights for prioritizing fixes
    dimension_weights: dict[str, float] = Field(default_factory=lambda: {
        "narrative_clarity": 1.2,
        "hook_strength": 1.5,  # Hook is critical
        "pacing": 1.0,
        "shot_composition": 1.0,
        "continuity": 0.8,
        "audio_mix": 0.7,
    })

    # Stopping conditions
    stop_on_approve: bool = True
    stop_on_minor_fixes: bool = True  # NEW: Stop if recommendation is minor_fixes
    stop_on_no_improvement: bool = True


class RefinementIteration(BaseModel):
    """Record of a single refinement iteration."""

    iteration: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Input state
    input_score: float = 0.0
    input_dimension_scores: DimensionScores | None = None

    # Actions taken
    issues_identified: int = 0
    fixes_applied: int = 0
    fix_descriptions: list[str] = Field(default_factory=list)

    # Output state
    output_score: float = 0.0
    output_dimension_scores: DimensionScores | None = None
    score_improvement: float = 0.0

    # Costs
    critique_cost: float = 0.0
    fix_cost: float = 0.0
    iteration_cost: float = 0.0

    # Critic feedback
    recommendation: FeedbackRecommendation | None = None
    feedback_id: str | None = None


class RefinementResult(BaseModel):
    """Result of the refinement process."""

    id: str = Field(default_factory=lambda: generate_id("refine"))
    status: RefinementStatus = RefinementStatus.NOT_STARTED
    stop_reason: str = ""  # Explicit reason for stopping
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Progress
    iterations_completed: int = 0
    total_runtime_seconds: float = 0.0

    # Quality trajectory
    initial_score: float = 0.0
    final_score: float = 0.0
    score_improvement: float = 0.0
    target_met: bool = False

    # Cost tracking
    total_cost: float = 0.0
    critique_costs: float = 0.0
    fix_costs: float = 0.0

    # Iteration history
    iterations: list[RefinementIteration] = Field(default_factory=list)

    # Final feedback
    final_feedback: FeedbackAnnotation | None = None

    # Errors
    errors: list[str] = Field(default_factory=list)


# Type alias for fix function
FixFunction = Callable[[SceneGraph, CriticOutput], SceneGraph]


class IterativeRefinementController:
    """
    Controls the Critic → Fix → Critic loop.

    Features:
    - Max iteration cap
    - Budget (cost) cap
    - Score convergence detection
    - Prioritized fix ordering
    - Full iteration history
    """

    def __init__(
        self,
        config: RefinementConfig | None = None,
        critic: CriticAgent | None = None,
    ):
        self.config = config or RefinementConfig()
        self.critic = critic or CriticAgent()
        self._fix_functions: list[FixFunction] = []

    def register_fix_function(self, fn: FixFunction) -> None:
        """Register a function that applies fixes to a SceneGraph."""
        self._fix_functions.append(fn)

    async def run(
        self,
        scene_graph: SceneGraph,
        fix_function: FixFunction | None = None,
    ) -> tuple[SceneGraph, RefinementResult]:
        """
        Run the iterative refinement loop.

        Args:
            scene_graph: Initial SceneGraph to refine
            fix_function: Function to apply fixes (optional, uses registered ones)

        Returns:
            Tuple of (refined_scene_graph, refinement_result)
        """
        result = RefinementResult(
            status=RefinementStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )

        current_graph = scene_graph
        total_cost = 0.0

        logger.info("refinement_started", story_id=scene_graph.story.id)

        try:
            for iteration_num in range(self.config.max_iterations):
                # Check budget before starting iteration
                if total_cost >= self.config.max_cost_dollars:
                    logger.info(
                        "budget_exceeded",
                        cost=total_cost,
                        cap=self.config.max_cost_dollars,
                    )
                    result = result.model_copy(update={
                        "status": RefinementStatus.BUDGET_EXCEEDED,
                    })
                    break

                # Run iteration
                iteration_result, current_graph, iteration_cost = await self._run_iteration(
                    iteration_num,
                    current_graph,
                    fix_function,
                )

                total_cost += iteration_cost
                result = result.model_copy(update={
                    "iterations": list(result.iterations) + [iteration_result],
                    "iterations_completed": iteration_num + 1,
                    "total_cost": total_cost,
                    "critique_costs": result.critique_costs + iteration_result.critique_cost,
                    "fix_costs": result.fix_costs + iteration_result.fix_cost,
                })

                # Record initial score on first iteration
                if iteration_num == 0:
                    result = result.model_copy(update={
                        "initial_score": iteration_result.input_score,
                    })

                # Check stopping conditions
                stop, status, reason = self._check_stopping_conditions(
                    iteration_result,
                    result,
                )

                if stop:
                    result = result.model_copy(update={
                        "status": status,
                        "stop_reason": reason,
                    })
                    break

            else:
                # Loop exhausted without stopping
                result = result.model_copy(update={
                    "status": RefinementStatus.MAX_ITERATIONS,
                    "stop_reason": f"max_iterations_reached: {self.config.max_iterations}",
                })

        except Exception as e:
            logger.error("refinement_failed", error=str(e))
            result = result.model_copy(update={
                "status": RefinementStatus.FAILED,
                "errors": list(result.errors) + [str(e)],
            })

        # Finalize result
        final_iteration = result.iterations[-1] if result.iterations else None
        final_score = final_iteration.output_score if final_iteration else 0.0

        result = result.model_copy(update={
            "completed_at": datetime.utcnow(),
            "final_score": final_score,
            "score_improvement": final_score - result.initial_score,
            "target_met": final_score >= self.config.target_overall_score,
            "total_runtime_seconds": (
                datetime.utcnow() - result.started_at
            ).total_seconds() if result.started_at else 0.0,
        })

        logger.info(
            "refinement_completed",
            status=result.status.value,
            iterations=result.iterations_completed,
            initial_score=result.initial_score,
            final_score=result.final_score,
            improvement=result.score_improvement,
            cost=result.total_cost,
        )

        return current_graph, result

    async def _run_iteration(
        self,
        iteration_num: int,
        scene_graph: SceneGraph,
        fix_function: FixFunction | None,
    ) -> tuple[RefinementIteration, SceneGraph, float]:
        """Run a single refinement iteration."""
        logger.info("iteration_started", iteration=iteration_num)

        iteration = RefinementIteration(iteration=iteration_num)
        total_cost = 0.0

        # Step 1: Run critic
        critic_result = await self.critic(CriticInput(scene_graph=scene_graph))
        critique_cost = self.config.cost_per_critique
        total_cost += critique_cost

        input_score = critic_result.story_feedback.overall_score
        input_dimensions = critic_result.story_feedback.dimension_scores

        iteration = iteration.model_copy(update={
            "input_score": input_score,
            "input_dimension_scores": input_dimensions,
            "issues_identified": len(critic_result.story_feedback.issues),
            "critique_cost": critique_cost,
            "recommendation": critic_result.story_feedback.recommendation,
            "feedback_id": critic_result.story_feedback.id,
        })

        logger.info(
            "critique_completed",
            iteration=iteration_num,
            score=input_score,
            issues=iteration.issues_identified,
            recommendation=critic_result.story_feedback.recommendation.value,
        )

        # Step 2: Apply fixes if needed and function available
        refined_graph = scene_graph
        fix_cost = 0.0
        fixes_applied = 0
        fix_descriptions = []

        if (
            fix_function
            and critic_result.story_feedback.recommendation != FeedbackRecommendation.APPROVE
            and iteration.issues_identified > 0
        ):
            # Prioritize fixes by dimension weight
            prioritized_issues = self._prioritize_issues(
                critic_result.story_feedback.issues
            )

            # Apply fix function
            try:
                refined_graph = fix_function(scene_graph, critic_result)
                fixes_applied = len(prioritized_issues)
                fix_descriptions = [
                    f"{issue.category.value}: {issue.description[:50]}"
                    for issue in prioritized_issues[:5]  # Log top 5
                ]
                fix_cost = self.config.cost_per_fix
                total_cost += fix_cost

                logger.info(
                    "fixes_applied",
                    iteration=iteration_num,
                    fixes=fixes_applied,
                )

            except Exception as e:
                logger.error("fix_failed", iteration=iteration_num, error=str(e))

        # Step 3: Re-evaluate after fixes
        if refined_graph is not scene_graph:
            post_fix_result = await self.critic(CriticInput(scene_graph=refined_graph))
            total_cost += self.config.cost_per_critique
            output_score = post_fix_result.story_feedback.overall_score
            output_dimensions = post_fix_result.story_feedback.dimension_scores
        else:
            output_score = input_score
            output_dimensions = input_dimensions

        iteration = iteration.model_copy(update={
            "output_score": output_score,
            "output_dimension_scores": output_dimensions,
            "score_improvement": output_score - input_score,
            "fixes_applied": fixes_applied,
            "fix_descriptions": fix_descriptions,
            "fix_cost": fix_cost,
            "iteration_cost": total_cost,
        })

        logger.info(
            "iteration_completed",
            iteration=iteration_num,
            input_score=input_score,
            output_score=output_score,
            improvement=iteration.score_improvement,
            cost=total_cost,
        )

        return iteration, refined_graph, total_cost

    def _prioritize_issues(self, issues: list) -> list:
        """Prioritize issues by dimension weight and severity."""
        # Map issues to their weights
        weighted_issues = []
        for issue in issues:
            # Extract dimension from category if possible
            category = issue.category.value if hasattr(issue, "category") else "other"
            weight = self.config.dimension_weights.get(category, 1.0)

            # Adjust by severity
            severity_multiplier = {
                "critical": 2.0,
                "major": 1.5,
                "minor": 1.0,
                "suggestion": 0.5,
            }.get(issue.severity.value if hasattr(issue, "severity") else "minor", 1.0)

            weighted_issues.append((issue, weight * severity_multiplier))

        # Sort by weight descending
        weighted_issues.sort(key=lambda x: x[1], reverse=True)
        return [issue for issue, _ in weighted_issues]

    def _check_stopping_conditions(
        self,
        iteration: RefinementIteration,
        result: RefinementResult,
    ) -> tuple[bool, RefinementStatus, str]:
        """Check if refinement should stop. Returns (should_stop, status, reason)."""

        # Condition 1: Target score reached
        if iteration.output_score >= self.config.target_overall_score:
            reason = f"target_score_reached: {iteration.output_score:.1f} >= {self.config.target_overall_score}"
            logger.info("target_reached", score=iteration.output_score, target=self.config.target_overall_score)
            return True, RefinementStatus.CONVERGED, reason

        # Condition 2: Critic approved
        if (
            self.config.stop_on_approve
            and iteration.recommendation == FeedbackRecommendation.APPROVE
        ):
            reason = "critic_recommendation: approve"
            logger.info("critic_approved")
            return True, RefinementStatus.CONVERGED, reason

        # Condition 3: Critic says minor fixes only (acceptable quality)
        if (
            self.config.stop_on_minor_fixes
            and iteration.recommendation == FeedbackRecommendation.REVISE_MINOR
        ):
            reason = "critic_recommendation: revise_minor (acceptable)"
            logger.info("minor_fixes_acceptable")
            return True, RefinementStatus.CONVERGED, reason

        # Condition 4: No improvement (epsilon check)
        if (
            self.config.stop_on_no_improvement
            and result.iterations_completed >= self.config.min_iterations
            and iteration.score_improvement < self.config.improvement_threshold
        ):
            reason = f"no_improvement: {iteration.score_improvement:.2f} < epsilon {self.config.improvement_threshold}"
            logger.info("no_improvement", improvement=iteration.score_improvement, threshold=self.config.improvement_threshold)
            return True, RefinementStatus.CONVERGED, reason

        # Condition 5: Budget cap
        if result.total_cost >= self.config.max_cost_dollars:
            reason = f"budget_exceeded: ${result.total_cost:.2f} >= ${self.config.max_cost_dollars:.2f}"
            return True, RefinementStatus.BUDGET_EXCEEDED, reason

        return False, RefinementStatus.IN_PROGRESS, ""


def default_fix_function(
    scene_graph: SceneGraph,
    critic_output: CriticOutput,
) -> SceneGraph:
    """
    Default fix function that applies heuristic improvements.

    This is a placeholder - real implementations would use
    LLM-based fixes or domain-specific rules.
    """
    # For now, just return the original (no-op fix)
    # In production, this would:
    # 1. Parse critic feedback
    # 2. Apply targeted fixes based on issue categories
    # 3. Return modified SceneGraph

    logger.debug(
        "default_fix_applied",
        issues=len(critic_output.story_feedback.issues),
    )

    return scene_graph


async def run_refinement_loop(
    scene_graph: SceneGraph,
    max_iterations: int = 2,  # Tight default
    max_cost: float = 2.0,  # Tight default
    target_score: float = 7.0,
    fix_function: FixFunction | None = None,
) -> tuple[SceneGraph, RefinementResult]:
    """Convenience function to run refinement with tight MVP defaults."""
    config = RefinementConfig(
        max_iterations=max_iterations,
        max_cost_dollars=max_cost,
        target_overall_score=target_score,
    )

    controller = IterativeRefinementController(config=config)

    return await controller.run(
        scene_graph,
        fix_function=fix_function or default_fix_function,
    )
