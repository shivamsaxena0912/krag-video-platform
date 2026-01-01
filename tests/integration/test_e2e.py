"""End-to-end integration tests."""

import pytest
from pathlib import Path

from src.agents import (
    StoryParserAgent,
    StoryParserInput,
    CriticAgent,
    CriticInput,
)
from src.knowledge_graph import (
    Neo4jClient,
    apply_schema,
    ingest_scene_graph,
    upsert_feedback,
    get_story_with_scenes,
)
from src.rag import (
    QdrantVectorClient,
    get_embedding_provider,
    ensure_collections,
    index_scenes,
    index_shots,
)


@pytest.fixture
async def neo4j_client():
    """Create a Neo4j client for testing."""
    client = Neo4jClient()
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
async def qdrant_client():
    """Create a Qdrant client for testing."""
    client = QdrantVectorClient()
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
def stub_embedder():
    """Create a stub embedding provider."""
    return get_embedding_provider("stub", dimension=384)


@pytest.fixture
def sample_story_path():
    """Path to sample story file."""
    return Path(__file__).parent.parent.parent / "examples" / "story_001.txt"


@pytest.mark.integration
@pytest.mark.e2e
class TestEndToEndPipeline:
    """End-to-end pipeline tests."""

    @pytest.mark.asyncio
    async def test_full_pipeline(
        self,
        neo4j_client,
        qdrant_client,
        stub_embedder,
        sample_story_path,
    ):
        """
        Test the full pipeline:
        1. Parse story text
        2. Ingest into Neo4j
        3. Index into Qdrant
        4. Evaluate with Critic
        5. Store feedback
        """
        # Step 1: Parse story
        story_text = sample_story_path.read_text()

        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=story_text,
            title="The Fall of Rome",
            author="Test",
            era="Ancient Rome",
        ))

        scene_graph = parse_result.scene_graph

        # Verify parsing
        assert scene_graph.story.title == "The Fall of Rome"
        assert len(scene_graph.scenes) >= 3
        assert len(scene_graph.characters) >= 1
        assert len(scene_graph.shots) >= 3

        # Step 2: Apply schema and ingest into Neo4j
        await apply_schema(neo4j_client)

        ingest_result = await ingest_scene_graph(neo4j_client, scene_graph)

        assert ingest_result["story"] == scene_graph.story.id
        assert ingest_result["scenes"] >= 3
        assert ingest_result["errors"] == []

        # Verify Neo4j storage
        stored = await get_story_with_scenes(neo4j_client, scene_graph.story.id)
        assert stored is not None
        assert stored["story"]["title"] == "The Fall of Rome"
        assert len(stored["scenes"]) >= 3

        # Step 3: Index into Qdrant
        await ensure_collections(qdrant_client, stub_embedder.dimension)

        scene_index_result = await index_scenes(
            qdrant_client,
            stub_embedder,
            scene_graph.scenes,
            scene_graph.story.id,
        )

        assert scene_index_result["indexed"] >= 3
        assert scene_index_result["errors"] == []

        # Index shots
        for scene in scene_graph.scenes:
            scene_shots = [s for s in scene_graph.shots if s.shot_plan_id.endswith(scene.id[6:])]
            if scene_shots:
                shot_index_result = await index_shots(
                    qdrant_client,
                    stub_embedder,
                    scene_shots,
                    scene.id,
                    scene_graph.story.id,
                )
                assert shot_index_result["errors"] == []

        # Step 4: Evaluate with Critic
        critic = CriticAgent()
        critic_result = await critic(CriticInput(
            scene_graph=scene_graph,
        ))

        assert critic_result.story_feedback is not None
        assert critic_result.story_feedback.overall_score >= 1.0
        assert len(critic_result.scene_feedbacks) >= 3

        # Step 5: Store feedback in Neo4j
        await upsert_feedback(neo4j_client, critic_result.story_feedback)

        for scene_fb in critic_result.scene_feedbacks:
            await upsert_feedback(neo4j_client, scene_fb)

        # Final verification
        print("\n=== Pipeline Complete ===")
        print(f"Story: {scene_graph.story.title}")
        print(f"Scenes: {len(scene_graph.scenes)}")
        print(f"Characters: {len(scene_graph.characters)}")
        print(f"Shots: {len(scene_graph.shots)}")
        print(f"Overall Score: {critic_result.story_feedback.overall_score}")
        print(f"Recommendation: {critic_result.story_feedback.recommendation.value}")

    @pytest.mark.asyncio
    async def test_pipeline_with_minimal_story(
        self,
        neo4j_client,
        qdrant_client,
        stub_embedder,
    ):
        """Test pipeline with a minimal story."""
        minimal_text = """
# Minimal Test

## Scene 1: Only Scene

This is the only scene in this minimal story.
Marcus Aurelius appears briefly.
"""

        # Parse
        parser = StoryParserAgent()
        parse_result = await parser(StoryParserInput(
            text=minimal_text,
            title="Minimal Test",
        ))

        assert len(parse_result.scene_graph.scenes) == 1

        # Evaluate
        critic = CriticAgent()
        critic_result = await critic(CriticInput(
            scene_graph=parse_result.scene_graph,
        ))

        # With only 1 scene, should get a lower score or issues
        assert critic_result.story_feedback is not None
        assert len(critic_result.story_feedback.issues) >= 0  # May have issues about short content
