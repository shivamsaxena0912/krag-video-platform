"""RAG (Retrieval-Augmented Generation) module."""

from src.rag.client import (
    QdrantVectorClient,
    get_qdrant_client,
    init_qdrant,
    close_qdrant,
)
from src.rag.embeddings import (
    BaseEmbeddingProvider,
    StubEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from src.rag.indexing import (
    SCENE_COLLECTION,
    SHOT_COLLECTION,
    ensure_collections,
    index_scene,
    index_scenes,
    index_shot,
    index_shots,
    search_similar_scenes,
    search_similar_shots,
    delete_story_vectors,
)

__all__ = [
    # Client
    "QdrantVectorClient",
    "get_qdrant_client",
    "init_qdrant",
    "close_qdrant",
    # Embeddings
    "BaseEmbeddingProvider",
    "StubEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "get_embedding_provider",
    # Indexing
    "SCENE_COLLECTION",
    "SHOT_COLLECTION",
    "ensure_collections",
    "index_scene",
    "index_scenes",
    "index_shot",
    "index_shots",
    "search_similar_scenes",
    "search_similar_shots",
    "delete_story_vectors",
]
