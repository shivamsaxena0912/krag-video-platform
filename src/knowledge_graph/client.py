"""Neo4j client for the Knowledge Graph."""

from contextlib import asynccontextmanager
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import ServiceUnavailable

from src.common.config import get_settings
from src.common.logging import get_logger

logger = get_logger(__name__)


class Neo4jClient:
    """Async Neo4j client wrapper."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ):
        """Initialize Neo4j client."""
        settings = get_settings()
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.database = database or settings.neo4j_database
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            # Verify connectivity
            try:
                await self._driver.verify_connectivity()
                logger.info("neo4j_connected", uri=self.uri)
            except ServiceUnavailable as e:
                logger.error("neo4j_connection_failed", error=str(e))
                raise

    async def close(self) -> None:
        """Close the connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("neo4j_disconnected")

    @asynccontextmanager
    async def session(self):
        """Get an async session context manager."""
        if not self._driver:
            await self.connect()
        session = self._driver.session(database=self.database)
        try:
            yield session
        finally:
            await session.close()

    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a write query and return summary."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            summary = await result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_created": summary.counters.relationships_created,
                "relationships_deleted": summary.counters.relationships_deleted,
                "properties_set": summary.counters.properties_set,
            }

    async def health_check(self) -> bool:
        """Check if Neo4j is reachable."""
        try:
            if not self._driver:
                await self.connect()
            await self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.warning("neo4j_health_check_failed", error=str(e))
            return False


# Global client instance
_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """Get or create the global Neo4j client."""
    global _client
    if _client is None:
        _client = Neo4jClient()
    return _client


async def init_neo4j() -> Neo4jClient:
    """Initialize and return the Neo4j client."""
    client = get_neo4j_client()
    await client.connect()
    return client


async def close_neo4j() -> None:
    """Close the global Neo4j client."""
    global _client
    if _client:
        await _client.close()
        _client = None
