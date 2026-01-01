"""Unit tests for agents."""

import pytest
from pathlib import Path

from src.agents import (
    StoryParserAgent,
    StoryParserInput,
    CriticAgent,
    CriticInput,
)
from src.common.models import SourceType


class TestStoryParserAgent:
    """Tests for StoryParserAgent."""

    @pytest.fixture
    def sample_text(self):
        """Sample narrative text for testing."""
        return """
# Test Story

## Scene 1: The Beginning

Marcus Aurelius sits in Rome, contemplating the future of the empire.
The city stretches before him, its marble temples gleaming in the afternoon sun.

## Scene 2: The Conflict

Commodus enters the arena, dressed as a gladiator.
The crowd watches in stunned silence as their emperor debases himself.

## Scene 3: The End

The Visigoths enter Rome. The eternal city falls.
"""

    @pytest.mark.asyncio
    async def test_parse_basic_text(self, sample_text):
        """Test parsing basic narrative text."""
        agent = StoryParserAgent()
        input_data = StoryParserInput(
            text=sample_text,
            title="Test Story",
        )

        result = await agent(input_data)

        assert result.scene_graph is not None
        assert result.scene_graph.story.title == "Test Story"
        assert len(result.scene_graph.scenes) == 3
        assert result.parsing_stats["scenes_created"] == 3

    @pytest.mark.asyncio
    async def test_character_extraction(self, sample_text):
        """Test character extraction from text."""
        agent = StoryParserAgent()
        input_data = StoryParserInput(
            text=sample_text,
            title="Character Test",
        )

        result = await agent(input_data)

        character_names = [c.name for c in result.scene_graph.characters]
        assert "Marcus Aurelius" in character_names
        assert "Commodus" in character_names

    @pytest.mark.asyncio
    async def test_location_extraction(self, sample_text):
        """Test location extraction from text."""
        agent = StoryParserAgent()
        input_data = StoryParserInput(
            text=sample_text,
            title="Location Test",
        )

        result = await agent(input_data)

        location_names = [l.name for l in result.scene_graph.locations]
        assert "Rome" in location_names

    @pytest.mark.asyncio
    async def test_shot_plan_generation(self, sample_text):
        """Test that shot plans are generated for scenes."""
        agent = StoryParserAgent()
        input_data = StoryParserInput(
            text=sample_text,
            title="Shot Plan Test",
        )

        result = await agent(input_data)

        assert len(result.scene_graph.shot_plans) == 3
        assert len(result.scene_graph.shots) >= 9  # At least 3 shots per scene

    @pytest.mark.asyncio
    async def test_scene_summaries(self, sample_text):
        """Test that scenes have summaries."""
        agent = StoryParserAgent()
        input_data = StoryParserInput(
            text=sample_text,
            title="Summary Test",
        )

        result = await agent(input_data)

        for scene in result.scene_graph.scenes:
            assert scene.summary
            assert len(scene.summary) > 10


class TestCriticAgent:
    """Tests for CriticAgent."""

    @pytest.fixture
    def sample_text(self):
        """Sample narrative text for testing."""
        return """
# Test Story

## Scene 1: Opening

Rome stands eternal. Marcus Aurelius contemplates duty and mortality.
The philosopher emperor writes by candlelight in his tent.

## Scene 2: Middle

Commodus enters the arena as a gladiator.
The crowd watches in horror.

## Scene 3: Ending

The empire falls. But ideas endure.
"""

    @pytest.mark.asyncio
    async def test_evaluate_scene_graph(self, sample_text):
        """Test evaluating a scene graph."""
        # First parse the story
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_text,
            title="Critic Test",
        ))

        # Then evaluate it
        critic = CriticAgent()
        critic_result = await critic(CriticInput(
            scene_graph=parse_result.scene_graph,
        ))

        assert critic_result.story_feedback is not None
        assert critic_result.story_feedback.overall_score >= 1.0
        assert critic_result.story_feedback.overall_score <= 10.0
        assert len(critic_result.scene_feedbacks) == 3

    @pytest.mark.asyncio
    async def test_feedback_has_scores(self, sample_text):
        """Test that feedback includes dimension scores."""
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_text,
            title="Scores Test",
        ))

        critic = CriticAgent()
        critic_result = await critic(CriticInput(
            scene_graph=parse_result.scene_graph,
        ))

        scores = critic_result.story_feedback.dimension_scores
        assert scores.narrative_clarity >= 1
        assert scores.pacing >= 1
        assert scores.shot_composition >= 1

    @pytest.mark.asyncio
    async def test_feedback_has_recommendation(self, sample_text):
        """Test that feedback includes recommendation."""
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_text,
            title="Recommendation Test",
        ))

        critic = CriticAgent()
        critic_result = await critic(CriticInput(
            scene_graph=parse_result.scene_graph,
        ))

        assert critic_result.story_feedback.recommendation is not None

    @pytest.mark.asyncio
    async def test_summary_statistics(self, sample_text):
        """Test that summary statistics are calculated."""
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=sample_text,
            title="Summary Stats Test",
        ))

        critic = CriticAgent()
        critic_result = await critic(CriticInput(
            scene_graph=parse_result.scene_graph,
        ))

        assert "story_score" in critic_result.summary
        assert "total_issues" in critic_result.summary
        assert "scene_scores" in critic_result.summary
