"""Indexing functions for scenes and shots in Qdrant."""

from uuid import uuid4

from qdrant_client.http import models as qdrant_models

from src.common.logging import get_logger
from src.common.models import Scene, Shot, ShotPlan
from src.rag.client import QdrantVectorClient
from src.rag.embeddings import BaseEmbeddingProvider

logger = get_logger(__name__)

# Collection names
SCENE_COLLECTION = "scenes"
SHOT_COLLECTION = "shots"

# Default embedding dimension (for stub)
DEFAULT_DIMENSION = 384


async def ensure_collections(
    client: QdrantVectorClient,
    dimension: int = DEFAULT_DIMENSION,
) -> dict:
    """Ensure required collections exist."""
    results = {
        SCENE_COLLECTION: False,
        SHOT_COLLECTION: False,
    }

    # Create scenes collection
    created = await client.create_collection(
        collection_name=SCENE_COLLECTION,
        vector_size=dimension,
        distance="Cosine",
    )
    results[SCENE_COLLECTION] = created

    # Create shots collection
    created = await client.create_collection(
        collection_name=SHOT_COLLECTION,
        vector_size=dimension,
        distance="Cosine",
    )
    results[SHOT_COLLECTION] = created

    return results


async def index_scene(
    client: QdrantVectorClient,
    embedder: BaseEmbeddingProvider,
    scene: Scene,
    story_id: str,
) -> dict:
    """
    Index a scene in Qdrant.

    Creates an embedding from the scene summary and stores with metadata.
    """
    # Create text to embed
    text_to_embed = f"{scene.summary}\n\n{scene.raw_text[:1000]}"

    # Generate embedding
    embedding = await embedder.embed_text(text_to_embed)

    # Create point
    point = qdrant_models.PointStruct(
        id=str(uuid4()),  # Qdrant needs UUID
        vector=embedding,
        payload={
            "scene_id": scene.id,
            "story_id": story_id,
            "sequence": scene.sequence,
            "summary": scene.summary,
            "setting_location": scene.setting.location_name,
            "setting_era": scene.setting.era,
            "emotional_beat": scene.emotional_beat.primary_emotion,
            "word_count": scene.word_count,
            "type": "scene",
        },
    )

    # Upsert to collection
    result = await client.upsert_points(
        collection_name=SCENE_COLLECTION,
        points=[point],
    )

    logger.info("scene_indexed", scene_id=scene.id, story_id=story_id)
    return {
        "scene_id": scene.id,
        "point_id": str(point.id),
        "status": result["status"],
    }


async def index_scenes(
    client: QdrantVectorClient,
    embedder: BaseEmbeddingProvider,
    scenes: list[Scene],
    story_id: str,
) -> dict:
    """Index multiple scenes."""
    results = {
        "indexed": 0,
        "errors": [],
    }

    for scene in scenes:
        try:
            await index_scene(client, embedder, scene, story_id)
            results["indexed"] += 1
        except Exception as e:
            results["errors"].append({
                "scene_id": scene.id,
                "error": str(e),
            })
            logger.error("scene_indexing_error", scene_id=scene.id, error=str(e))

    return results


async def index_shot(
    client: QdrantVectorClient,
    embedder: BaseEmbeddingProvider,
    shot: Shot,
    scene_id: str,
    story_id: str,
) -> dict:
    """
    Index a shot in Qdrant.

    Creates an embedding from the shot description and stores with metadata.
    """
    # Create text to embed
    text_parts = [
        f"Shot type: {shot.shot_type.value}",
        f"Subject: {shot.subject}",
        f"Mood: {shot.mood}",
        f"Description: {shot.visual_description}",
    ]
    if shot.narration_text:
        text_parts.append(f"Narration: {shot.narration_text}")

    text_to_embed = "\n".join(text_parts)

    # Generate embedding
    embedding = await embedder.embed_text(text_to_embed)

    # Create point
    point = qdrant_models.PointStruct(
        id=str(uuid4()),
        vector=embedding,
        payload={
            "shot_id": shot.id,
            "shot_plan_id": shot.shot_plan_id,
            "scene_id": scene_id,
            "story_id": story_id,
            "sequence": shot.sequence,
            "shot_type": shot.shot_type.value,
            "subject": shot.subject,
            "mood": shot.mood,
            "duration_seconds": shot.duration_seconds,
            "has_narration": bool(shot.narration_text),
            "type": "shot",
        },
    )

    # Upsert to collection
    result = await client.upsert_points(
        collection_name=SHOT_COLLECTION,
        points=[point],
    )

    logger.info("shot_indexed", shot_id=shot.id, scene_id=scene_id)
    return {
        "shot_id": shot.id,
        "point_id": str(point.id),
        "status": result["status"],
    }


async def index_shots(
    client: QdrantVectorClient,
    embedder: BaseEmbeddingProvider,
    shots: list[Shot],
    scene_id: str,
    story_id: str,
) -> dict:
    """Index multiple shots."""
    results = {
        "indexed": 0,
        "errors": [],
    }

    for shot in shots:
        try:
            await index_shot(client, embedder, shot, scene_id, story_id)
            results["indexed"] += 1
        except Exception as e:
            results["errors"].append({
                "shot_id": shot.id,
                "error": str(e),
            })
            logger.error("shot_indexing_error", shot_id=shot.id, error=str(e))

    return results


async def search_similar_scenes(
    client: QdrantVectorClient,
    embedder: BaseEmbeddingProvider,
    query_text: str,
    story_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Search for similar scenes."""
    # Generate query embedding
    query_embedding = await embedder.embed_text(query_text)

    # Build filter if story_id specified
    filter_conditions = None
    if story_id:
        filter_conditions = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="story_id",
                    match=qdrant_models.MatchValue(value=story_id),
                ),
            ],
        )

    # Search
    results = await client.search(
        collection_name=SCENE_COLLECTION,
        query_vector=query_embedding,
        limit=limit,
        filter_conditions=filter_conditions,
    )

    return [
        {
            "score": r.score,
            "scene_id": r.payload.get("scene_id"),
            "story_id": r.payload.get("story_id"),
            "summary": r.payload.get("summary"),
            "sequence": r.payload.get("sequence"),
        }
        for r in results
    ]


async def search_similar_shots(
    client: QdrantVectorClient,
    embedder: BaseEmbeddingProvider,
    query_text: str,
    story_id: str | None = None,
    shot_type: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Search for similar shots."""
    # Generate query embedding
    query_embedding = await embedder.embed_text(query_text)

    # Build filter
    must_conditions = []
    if story_id:
        must_conditions.append(
            qdrant_models.FieldCondition(
                key="story_id",
                match=qdrant_models.MatchValue(value=story_id),
            )
        )
    if shot_type:
        must_conditions.append(
            qdrant_models.FieldCondition(
                key="shot_type",
                match=qdrant_models.MatchValue(value=shot_type),
            )
        )

    filter_conditions = None
    if must_conditions:
        filter_conditions = qdrant_models.Filter(must=must_conditions)

    # Search
    results = await client.search(
        collection_name=SHOT_COLLECTION,
        query_vector=query_embedding,
        limit=limit,
        filter_conditions=filter_conditions,
    )

    return [
        {
            "score": r.score,
            "shot_id": r.payload.get("shot_id"),
            "scene_id": r.payload.get("scene_id"),
            "shot_type": r.payload.get("shot_type"),
            "subject": r.payload.get("subject"),
            "mood": r.payload.get("mood"),
        }
        for r in results
    ]


async def delete_story_vectors(
    client: QdrantVectorClient,
    story_id: str,
) -> dict:
    """Delete all vectors for a story."""
    filter_conditions = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="story_id",
                match=qdrant_models.MatchValue(value=story_id),
            ),
        ],
    )

    # Delete from scenes
    scene_result = await client.delete_by_filter(
        collection_name=SCENE_COLLECTION,
        filter_conditions=filter_conditions,
    )

    # Delete from shots
    shot_result = await client.delete_by_filter(
        collection_name=SHOT_COLLECTION,
        filter_conditions=filter_conditions,
    )

    logger.info("story_vectors_deleted", story_id=story_id)
    return {
        "scenes_deleted": scene_result["status"],
        "shots_deleted": shot_result["status"],
    }
