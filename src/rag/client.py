"""Qdrant client for vector storage."""

from __future__ import annotations

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from src.common.config import get_settings
from src.common.logging import get_logger

logger = get_logger(__name__)


class QdrantVectorClient:
    """Async Qdrant client wrapper."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize Qdrant client."""
        settings = get_settings()
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self._client: AsyncQdrantClient | None = None

    async def connect(self) -> None:
        """Establish connection to Qdrant."""
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=self.url,
                api_key=self.api_key if self.api_key else None,
            )
            logger.info("qdrant_connected", url=self.url)

    async def close(self) -> None:
        """Close the connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("qdrant_disconnected")

    @property
    def client(self) -> AsyncQdrantClient:
        """Get the underlying client."""
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._client

    async def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            if not self._client:
                await self.connect()
            # Try to list collections as health check
            await self._client.get_collections()
            return True
        except Exception as e:
            logger.warning("qdrant_health_check_failed", error=str(e))
            return False

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "Cosine",
        on_disk: bool = False,
    ) -> bool:
        """Create a collection if it doesn't exist."""
        try:
            collections = await self.client.get_collections()
            existing = [c.name for c in collections.collections]

            if collection_name in existing:
                logger.info("collection_exists", name=collection_name)
                return False

            distance_enum = getattr(qdrant_models.Distance, distance.upper())

            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=vector_size,
                    distance=distance_enum,
                    on_disk=on_disk,
                ),
            )
            logger.info("collection_created", name=collection_name, size=vector_size)
            return True

        except Exception as e:
            logger.error("collection_create_error", error=str(e))
            raise

    async def upsert_points(
        self,
        collection_name: str,
        points: list[qdrant_models.PointStruct],
    ) -> dict:
        """Upsert points into a collection."""
        result = await self.client.upsert(
            collection_name=collection_name,
            points=points,
        )
        logger.info(
            "points_upserted",
            collection=collection_name,
            count=len(points),
        )
        return {"status": result.status.value, "count": len(points)}

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
        filter_conditions: qdrant_models.Filter | None = None,
        with_payload: bool = True,
    ) -> list[qdrant_models.ScoredPoint]:
        """Search for similar vectors."""
        results = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=filter_conditions,
            with_payload=with_payload,
        )
        return results

    async def delete_by_filter(
        self,
        collection_name: str,
        filter_conditions: qdrant_models.Filter,
    ) -> dict:
        """Delete points matching a filter."""
        result = await self.client.delete(
            collection_name=collection_name,
            points_selector=qdrant_models.FilterSelector(
                filter=filter_conditions,
            ),
        )
        return {"status": result.status.value}

    async def get_collection_info(
        self,
        collection_name: str,
    ) -> dict:
        """Get collection information."""
        info = await self.client.get_collection(collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.value,
        }


# Global client instance
_client: QdrantVectorClient | None = None


def get_qdrant_client() -> QdrantVectorClient:
    """Get or create the global Qdrant client."""
    global _client
    if _client is None:
        _client = QdrantVectorClient()
    return _client


async def init_qdrant() -> QdrantVectorClient:
    """Initialize and return the Qdrant client."""
    client = get_qdrant_client()
    await client.connect()
    return client


async def close_qdrant() -> None:
    """Close the global Qdrant client."""
    global _client
    if _client:
        await _client.close()
        _client = None
