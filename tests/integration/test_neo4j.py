"""Integration tests for Neo4j operations."""

import pytest

from src.knowledge_graph import (
    Neo4jClient,
    apply_schema,
    upsert_story,
    upsert_scene,
    upsert_feedback,
    get_story_with_scenes,
    SceneGraph,
    ingest_scene_graph,
)
from src.common.models import (
    Story,
    SourceType,
    SourceMetadata,
    Scene,
    SceneSetting,
    EmotionalBeat,
    FeedbackAnnotation,
    FeedbackSource,
    FeedbackTargetType,
    DimensionScores,
)


@pytest.fixture
async def neo4j_client():
    """Create a Neo4j client for testing."""
    client = Neo4jClient()
    try:
        await client.connect()
        yield client
    finally:
        await client.close()


@pytest.mark.integration
class TestNeo4jConnection:
    """Tests for Neo4j connection."""

    @pytest.mark.asyncio
    async def test_health_check(self, neo4j_client):
        """Test Neo4j health check."""
        is_healthy = await neo4j_client.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_apply_schema(self, neo4j_client):
        """Test applying schema constraints and indexes."""
        result = await apply_schema(neo4j_client)

        assert "constraints_applied" in result
        assert "indexes_applied" in result
        assert result["constraints_applied"] >= 0
        assert result["indexes_applied"] >= 0


@pytest.mark.integration
class TestNeo4jOperations:
    """Tests for Neo4j CRUD operations."""

    @pytest.mark.asyncio
    async def test_upsert_story(self, neo4j_client):
        """Test upserting a story."""
        story = Story(
            title="Test Story for Neo4j",
            source_type=SourceType.NARRATIVE,
            source_metadata=SourceMetadata(title="Test Story"),
        )

        result = await upsert_story(neo4j_client, story)

        assert result["id"] == story.id
        assert result["action"] == "upsert"

    @pytest.mark.asyncio
    async def test_upsert_scene(self, neo4j_client):
        """Test upserting a scene linked to a story."""
        # Create story first
        story = Story(
            title="Story with Scene",
            source_type=SourceType.NARRATIVE,
            source_metadata=SourceMetadata(title="Story with Scene"),
        )
        await upsert_story(neo4j_client, story)

        # Create scene
        scene = Scene(
            story_id=story.id,
            sequence=1,
            raw_text="Test scene content",
            setting=SceneSetting(
                location_name="Test Location",
                location_description="A test location",
            ),
            emotional_beat=EmotionalBeat(primary_emotion="neutral"),
        )

        result = await upsert_scene(neo4j_client, scene)

        assert result["id"] == scene.id
        assert result["action"] == "upsert"

    @pytest.mark.asyncio
    async def test_get_story_with_scenes(self, neo4j_client):
        """Test retrieving a story with its scenes."""
        # Create story
        story = Story(
            title="Story for Retrieval",
            source_type=SourceType.NARRATIVE,
            source_metadata=SourceMetadata(title="Story for Retrieval"),
        )
        await upsert_story(neo4j_client, story)

        # Create scenes
        for i in range(3):
            scene = Scene(
                story_id=story.id,
                sequence=i + 1,
                raw_text=f"Scene {i+1} content",
                setting=SceneSetting(
                    location_name=f"Location {i+1}",
                    location_description=f"Description {i+1}",
                ),
                emotional_beat=EmotionalBeat(primary_emotion="neutral"),
            )
            await upsert_scene(neo4j_client, scene)

        # Retrieve
        result = await get_story_with_scenes(neo4j_client, story.id)

        assert result is not None
        assert result["story"] is not None
        assert len(result["scenes"]) == 3

    @pytest.mark.asyncio
    async def test_upsert_feedback(self, neo4j_client):
        """Test upserting feedback."""
        # Create story first
        story = Story(
            title="Story with Feedback",
            source_type=SourceType.NARRATIVE,
            source_metadata=SourceMetadata(title="Story with Feedback"),
        )
        await upsert_story(neo4j_client, story)

        # Create feedback
        feedback = FeedbackAnnotation(
            source=FeedbackSource.AI_CRITIC,
            target_type=FeedbackTargetType.STORY,
            target_id=story.id,
            dimension_scores=DimensionScores(
                narrative_clarity=4,
                hook_strength=3,
                pacing=4,
                shot_composition=4,
                continuity=4,
                audio_mix=3,
            ),
            overall_score=7.3,
        )

        result = await upsert_feedback(neo4j_client, feedback)

        assert result["id"] == feedback.id
        assert result["action"] == "upsert"


@pytest.mark.integration
class TestSceneGraphIngestion:
    """Tests for SceneGraph ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_scene_graph(self, neo4j_client):
        """Test ingesting a complete scene graph."""
        from src.agents import StoryParserAgent, StoryParserInput

        # Parse a simple story
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text="""
# Test Story for Ingestion

## Scene 1: Opening

Rome at dawn. Marcus Aurelius contemplates.

## Scene 2: Middle

The empire faces challenges. Commodus plots.
""",
            title="Ingestion Test Story",
        ))

        # Ingest into Neo4j
        result = await ingest_scene_graph(
            neo4j_client,
            parse_result.scene_graph,
        )

        assert result["story"] is not None
        assert result["scenes"] >= 2
        assert result["errors"] == []
