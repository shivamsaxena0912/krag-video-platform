"""Critic Agent v0 - Evaluates generated output and produces structured feedback."""

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent, AgentConfig
from src.common.logging import get_logger
from src.common.models import (
    FeedbackAnnotation,
    FeedbackSource,
    FeedbackTargetType,
    FeedbackRecommendation,
    DimensionScores,
    FeedbackIssue,
    FixCategory,
    IssueSeverity,
    TimeRange,
    TimestampedNote,
    FixRequest,
)
from src.knowledge_graph.scene_graph import SceneGraph

logger = get_logger(__name__)


# =============================================================================
# Input/Output Models
# =============================================================================


class CriticInput(BaseModel):
    """Input for the Critic Agent."""

    scene_graph: SceneGraph
    evaluation_mode: str = "comprehensive"  # "comprehensive" or "quick"


class CriticOutput(BaseModel):
    """Output from the Critic Agent."""

    story_feedback: FeedbackAnnotation
    scene_feedbacks: list[FeedbackAnnotation] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


# =============================================================================
# Critic Agent
# =============================================================================


class CriticAgent(BaseAgent[CriticInput, CriticOutput]):
    """
    Evaluates scene graphs and produces structured feedback.

    This is a v0 rule-based implementation. Future versions will use LLM
    for more nuanced evaluation.
    """

    def __init__(self):
        super().__init__(AgentConfig(name="CriticAgent"))

    async def execute(self, input: CriticInput) -> CriticOutput:
        """Evaluate scene graph and produce feedback."""
        logger.info(
            "evaluating_scene_graph",
            story_id=input.scene_graph.story.id,
            scenes=len(input.scene_graph.scenes),
        )

        # Evaluate the overall story
        story_feedback = self._evaluate_story(input.scene_graph)

        # Evaluate individual scenes
        scene_feedbacks = []
        for scene in input.scene_graph.scenes:
            scene_fb = self._evaluate_scene(scene, input.scene_graph)
            scene_feedbacks.append(scene_fb)

        # Calculate summary
        summary = self._calculate_summary(story_feedback, scene_feedbacks)

        logger.info(
            "evaluation_complete",
            story_id=input.scene_graph.story.id,
            overall_score=story_feedback.overall_score,
            recommendation=story_feedback.recommendation.value,
        )

        return CriticOutput(
            story_feedback=story_feedback,
            scene_feedbacks=scene_feedbacks,
            summary=summary,
        )

    def _evaluate_story(self, scene_graph: SceneGraph) -> FeedbackAnnotation:
        """Evaluate the overall story."""
        issues = []
        strengths = []

        # Check scene coverage
        if len(scene_graph.scenes) < 3:
            issues.append(FeedbackIssue(
                dimension="narrative_clarity",
                severity=IssueSeverity.MAJOR,
                description="Story has fewer than 3 scenes, may lack depth",
                fix_category=FixCategory.ADD_SHOT,
                suggested_fix="Consider adding more scenes to develop the narrative",
            ))
        else:
            strengths.append(f"Good scene coverage with {len(scene_graph.scenes)} scenes")

        # Check character presence
        if len(scene_graph.characters) < 2:
            issues.append(FeedbackIssue(
                dimension="narrative_clarity",
                severity=IssueSeverity.MINOR,
                description="Few characters identified",
                fix_category=FixCategory.OTHER,
                suggested_fix="Review text for additional character mentions",
            ))
        else:
            strengths.append(f"Rich cast of {len(scene_graph.characters)} characters")

        # Check shot plans
        if not scene_graph.shot_plans:
            issues.append(FeedbackIssue(
                dimension="shot_composition",
                severity=IssueSeverity.CRITICAL,
                description="No shot plans generated",
                fix_category=FixCategory.ADD_SHOT,
                suggested_fix="Generate shot plans for all scenes",
            ))

        # Check for shot variety
        shot_types = set()
        for shot in scene_graph.shots:
            shot_types.add(shot.shot_type.value)

        if len(shot_types) < 3:
            issues.append(FeedbackIssue(
                dimension="shot_composition",
                severity=IssueSeverity.MINOR,
                description="Limited shot type variety",
                fix_category=FixCategory.CHANGE_SHOT_TYPE,
                taxonomy_labels=["shot_variety", "visual_interest"],
                suggested_fix="Add more varied shot types (close-ups, cutaways)",
            ))
        else:
            strengths.append(f"Good shot variety with {len(shot_types)} different types")

        # Calculate scores
        scores = self._calculate_story_scores(scene_graph, issues)

        # Determine recommendation
        recommendation = self._determine_recommendation(scores.average())

        return FeedbackAnnotation(
            source=FeedbackSource.AI_CRITIC,
            target_type=FeedbackTargetType.STORY,
            target_id=scene_graph.story.id,
            dimension_scores=scores,
            overall_score=round(scores.to_overall_score(), 1),
            taxonomy_labels=["story_level", "automated_critique"],
            issues=issues,
            strengths=strengths,
            recommendation=recommendation,
        )

    def _evaluate_scene(
        self,
        scene,
        scene_graph: SceneGraph,
    ) -> FeedbackAnnotation:
        """Evaluate a single scene."""
        issues = []
        strengths = []
        timestamped_notes = []

        # Check scene summary
        if not scene.summary or len(scene.summary) < 20:
            issues.append(FeedbackIssue(
                dimension="narrative_clarity",
                severity=IssueSeverity.MINOR,
                description="Scene summary is too short or missing",
                fix_category=FixCategory.REWRITE_NARRATION,
                suggested_fix="Add a more detailed scene summary",
            ))
        else:
            strengths.append("Clear scene summary")

        # Check word count / pacing
        if scene.word_count < 50:
            issues.append(FeedbackIssue(
                dimension="pacing",
                severity=IssueSeverity.MINOR,
                description="Scene content is very short",
                fix_category=FixCategory.ADJUST_DURATION,
                suggested_fix="Consider expanding scene content",
            ))
        elif scene.word_count > 500:
            issues.append(FeedbackIssue(
                dimension="pacing",
                severity=IssueSeverity.SUGGESTION,
                description="Scene content is lengthy, may need multiple shots",
                fix_category=FixCategory.ADD_SHOT,
                suggested_fix="Consider breaking into multiple visual segments",
            ))

        # Check emotional beat
        if scene.emotional_beat.intensity < 0.3:
            timestamped_notes.append(TimestampedNote(
                timestamp_seconds=0,
                note="Low emotional intensity may result in flat video",
                severity=IssueSeverity.SUGGESTION,
            ))

        # Check setting clarity
        if scene.setting.location_name == "Unknown Location":
            issues.append(FeedbackIssue(
                dimension="continuity",
                severity=IssueSeverity.MINOR,
                description="Location not clearly identified",
                fix_category=FixCategory.FIX_CONSISTENCY,
                suggested_fix="Specify a clear location for visual consistency",
            ))
        else:
            strengths.append(f"Clear setting: {scene.setting.location_name}")

        # Calculate scene-specific scores
        scores = self._calculate_scene_scores(scene, issues)

        return FeedbackAnnotation(
            source=FeedbackSource.AI_CRITIC,
            target_type=FeedbackTargetType.SCENE,
            target_id=scene.id,
            dimension_scores=scores,
            overall_score=round(scores.to_overall_score(), 1),
            taxonomy_labels=["scene_level", "automated_critique"],
            issues=issues,
            strengths=strengths,
            timestamped_notes=timestamped_notes,
            recommendation=self._determine_recommendation(scores.average()),
        )

    def _calculate_story_scores(
        self,
        scene_graph: SceneGraph,
        issues: list[FeedbackIssue],
    ) -> DimensionScores:
        """Calculate dimension scores for a story."""
        # Start with baseline scores
        narrative_clarity = 4
        hook_strength = 3
        pacing = 4
        shot_composition = 4
        continuity = 4
        audio_mix = 3  # Default, no audio yet

        # Adjust based on content
        if len(scene_graph.scenes) >= 5:
            narrative_clarity = 5
            pacing = 4

        if len(scene_graph.characters) >= 3:
            narrative_clarity = min(5, narrative_clarity + 1)

        if len(scene_graph.shots) >= len(scene_graph.scenes) * 3:
            shot_composition = 5

        # Penalize for critical/major issues
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                if issue.dimension == "narrative_clarity":
                    narrative_clarity = max(1, narrative_clarity - 2)
                elif issue.dimension == "shot_composition":
                    shot_composition = max(1, shot_composition - 2)
            elif issue.severity == IssueSeverity.MAJOR:
                if issue.dimension == "narrative_clarity":
                    narrative_clarity = max(1, narrative_clarity - 1)

        return DimensionScores(
            narrative_clarity=narrative_clarity,
            hook_strength=hook_strength,
            pacing=pacing,
            shot_composition=shot_composition,
            continuity=continuity,
            audio_mix=audio_mix,
        )

    def _calculate_scene_scores(
        self,
        scene,
        issues: list[FeedbackIssue],
    ) -> DimensionScores:
        """Calculate dimension scores for a scene."""
        narrative_clarity = 4
        hook_strength = 3
        pacing = 4
        shot_composition = 4
        continuity = 4
        audio_mix = 3

        # Boost for good summary
        if scene.summary and len(scene.summary) >= 50:
            narrative_clarity = 5

        # Boost for clear emotional beat
        if scene.emotional_beat.intensity >= 0.5:
            hook_strength = 4

        # Adjust for issues
        for issue in issues:
            if issue.dimension in ["narrative_clarity", "pacing", "continuity"]:
                if issue.severity == IssueSeverity.MAJOR:
                    if issue.dimension == "narrative_clarity":
                        narrative_clarity = max(1, narrative_clarity - 1)
                    elif issue.dimension == "pacing":
                        pacing = max(1, pacing - 1)

        return DimensionScores(
            narrative_clarity=narrative_clarity,
            hook_strength=hook_strength,
            pacing=pacing,
            shot_composition=shot_composition,
            continuity=continuity,
            audio_mix=audio_mix,
        )

    def _determine_recommendation(
        self,
        average_score: float,
    ) -> FeedbackRecommendation:
        """Determine recommendation based on average score."""
        if average_score >= 4.5:
            return FeedbackRecommendation.APPROVE
        elif average_score >= 4.0:
            return FeedbackRecommendation.APPROVE_WITH_NOTES
        elif average_score >= 3.0:
            return FeedbackRecommendation.MINOR_FIXES
        elif average_score >= 2.0:
            return FeedbackRecommendation.MAJOR_REVISION
        else:
            return FeedbackRecommendation.REJECT

    def _calculate_summary(
        self,
        story_feedback: FeedbackAnnotation,
        scene_feedbacks: list[FeedbackAnnotation],
    ) -> dict:
        """Calculate summary statistics."""
        scene_scores = [sf.overall_score for sf in scene_feedbacks]

        return {
            "story_score": story_feedback.overall_score,
            "story_recommendation": story_feedback.recommendation.value,
            "total_issues": len(story_feedback.issues) + sum(
                len(sf.issues) for sf in scene_feedbacks
            ),
            "critical_issues": sum(
                1 for i in story_feedback.issues
                if i.severity == IssueSeverity.CRITICAL
            ) + sum(
                sum(1 for i in sf.issues if i.severity == IssueSeverity.CRITICAL)
                for sf in scene_feedbacks
            ),
            "scene_scores": {
                "min": min(scene_scores) if scene_scores else 0,
                "max": max(scene_scores) if scene_scores else 0,
                "avg": sum(scene_scores) / len(scene_scores) if scene_scores else 0,
            },
            "strengths_count": len(story_feedback.strengths) + sum(
                len(sf.strengths) for sf in scene_feedbacks
            ),
        }


# =============================================================================
# Convenience Functions
# =============================================================================


async def evaluate_scene_graph(
    scene_graph: SceneGraph,
    mode: str = "comprehensive",
) -> CriticOutput:
    """Evaluate a scene graph using the Critic Agent."""
    agent = CriticAgent()
    return await agent(CriticInput(
        scene_graph=scene_graph,
        evaluation_mode=mode,
    ))
