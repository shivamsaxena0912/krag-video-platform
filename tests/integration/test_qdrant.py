"""Integration tests for Qdrant operations."""

import pytest

from src.rag import (
    QdrantVectorClient,
    get_embedding_provider,
    ensure_collections,
    index_scene,
    index_shot,
    search_similar_scenes,
    search_similar_shots,
    SCENE_COLLECTION,
    SHOT_COLLECTION,
)
from src.common.models import (
    Scene,
    SceneSetting,
    EmotionalBeat,
    Shot,
    ShotType,
    Composition,
    MotionSpec,
)


@pytest.fixture
async def qdrant_client():
    """Create a Qdrant client for testing."""
    client = QdrantVectorClient()
    try:
        await client.connect()
        yield client
    finally:
        await client.close()


@pytest.fixture
def stub_embedder():
    """Create a stub embedding provider."""
    return get_embedding_provider("stub", dimension=384)


@pytest.mark.integration
class TestQdrantConnection:
    """Tests for Qdrant connection."""

    @pytest.mark.asyncio
    async def test_health_check(self, qdrant_client):
        """Test Qdrant health check."""
        is_healthy = await qdrant_client.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_ensure_collections(self, qdrant_client, stub_embedder):
        """Test creating collections."""
        result = await ensure_collections(
            qdrant_client,
            dimension=stub_embedder.dimension,
        )

        assert SCENE_COLLECTION in result
        assert SHOT_COLLECTION in result


@pytest.mark.integration
class TestQdrantIndexing:
    """Tests for Qdrant indexing operations."""

    @pytest.mark.asyncio
    async def test_index_scene(self, qdrant_client, stub_embedder):
        """Test indexing a scene."""
        # Ensure collections exist
        await ensure_collections(qdrant_client, stub_embedder.dimension)

        scene = Scene(
            story_id="story_test_123",
            sequence=1,
            raw_text="The Colosseum at dawn, gladiators prepare for battle.",
            summary="Opening scene at the Colosseum",
            setting=SceneSetting(
                location_name="Colosseum",
                location_description="The great amphitheater",
                era="Ancient Rome",
            ),
            emotional_beat=EmotionalBeat(
                primary_emotion="tension",
                intensity=0.7,
            ),
            word_count=10,
        )

        result = await index_scene(
            qdrant_client,
            stub_embedder,
            scene,
            story_id="story_test_123",
        )

        assert result["scene_id"] == scene.id
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_index_shot(self, qdrant_client, stub_embedder):
        """Test indexing a shot."""
        await ensure_collections(qdrant_client, stub_embedder.dimension)

        shot = Shot(
            shot_plan_id="plan_test_123",
            sequence=1,
            shot_type=ShotType.WIDE,
            duration_seconds=4.0,
            subject="Colosseum exterior",
            mood="epic",
            visual_description="Establishing shot of the Colosseum at dawn",
            composition=Composition(),
            motion=MotionSpec(),
        )

        result = await index_shot(
            qdrant_client,
            stub_embedder,
            shot,
            scene_id="scene_test_123",
            story_id="story_test_123",
        )

        assert result["shot_id"] == shot.id
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_search_similar_scenes(self, qdrant_client, stub_embedder):
        """Test searching for similar scenes."""
        await ensure_collections(qdrant_client, stub_embedder.dimension)

        # Index a scene first
        scene = Scene(
            story_id="story_search_test",
            sequence=1,
            raw_text="Battle at the gates of Rome",
            summary="Military scene with soldiers",
            setting=SceneSetting(
                location_name="Gates of Rome",
                location_description="City gates",
            ),
            emotional_beat=EmotionalBeat(primary_emotion="action"),
        )
        await index_scene(qdrant_client, stub_embedder, scene, "story_search_test")

        # Search for similar
        results = await search_similar_scenes(
            qdrant_client,
            stub_embedder,
            query_text="Roman soldiers fighting",
            limit=5,
        )

        assert isinstance(results, list)
        # Results may or may not include our scene depending on embedding similarity

    @pytest.mark.asyncio
    async def test_search_similar_shots(self, qdrant_client, stub_embedder):
        """Test searching for similar shots."""
        await ensure_collections(qdrant_client, stub_embedder.dimension)

        # Index a shot first
        shot = Shot(
            shot_plan_id="plan_search_test",
            sequence=1,
            shot_type=ShotType.CLOSE_UP,
            duration_seconds=2.0,
            subject="Emperor's face",
            mood="dramatic",
            visual_description="Close-up of the emperor's stern expression",
            composition=Composition(),
            motion=MotionSpec(),
        )
        await index_shot(
            qdrant_client,
            stub_embedder,
            shot,
            scene_id="scene_search_test",
            story_id="story_search_test",
        )

        # Search for similar
        results = await search_similar_shots(
            qdrant_client,
            stub_embedder,
            query_text="dramatic face shot",
            limit=5,
        )

        assert isinstance(results, list)


@pytest.mark.integration
class TestEmbeddingProvider:
    """Tests for embedding providers."""

    @pytest.mark.asyncio
    async def test_stub_embedder(self, stub_embedder):
        """Test stub embedding provider."""
        text = "Test text for embedding"
        embedding = await stub_embedder.embed_text(text)

        assert len(embedding) == stub_embedder.dimension
        assert all(isinstance(v, float) for v in embedding)

    @pytest.mark.asyncio
    async def test_stub_embedder_deterministic(self, stub_embedder):
        """Test that stub embedder is deterministic."""
        text = "Same text produces same embedding"

        embedding1 = await stub_embedder.embed_text(text)
        embedding2 = await stub_embedder.embed_text(text)

        assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_batch_embedding(self, stub_embedder):
        """Test batch embedding."""
        texts = ["First text", "Second text", "Third text"]
        embeddings = await stub_embedder.embed_texts(texts)

        assert len(embeddings) == 3
        assert all(len(e) == stub_embedder.dimension for e in embeddings)
