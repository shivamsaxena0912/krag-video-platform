"""Embedding interface and implementations."""

from abc import ABC, abstractmethod
import hashlib
from typing import Protocol

from src.common.config import get_settings
from src.common.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text."""
        ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        ...

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...


class BaseEmbeddingProvider(ABC):
    """Base class for embedding providers."""

    def __init__(self, model: str, dimension: int):
        self.model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text."""
        pass

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts (default: sequential)."""
        return [await self.embed_text(text) for text in texts]


class StubEmbeddingProvider(BaseEmbeddingProvider):
    """
    Stub embedding provider for testing.

    Generates deterministic pseudo-embeddings based on text hash.
    NOT suitable for production - use OpenAI or another real provider.
    """

    def __init__(self, dimension: int = 384):
        super().__init__(model="stub", dimension=dimension)
        logger.warning("using_stub_embeddings")

    async def embed_text(self, text: str) -> list[float]:
        """Generate a deterministic pseudo-embedding from text hash."""
        # Create a hash of the text
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Convert hash to floats in range [-1, 1]
        embedding = []
        for i in range(0, min(len(text_hash), self._dimension * 2), 2):
            byte_val = int(text_hash[i:i+2], 16)
            normalized = (byte_val / 255.0) * 2 - 1
            embedding.append(normalized)

        # Pad or truncate to exact dimension
        while len(embedding) < self._dimension:
            embedding.append(0.0)

        return embedding[:self._dimension]


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider."""

    DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model: str = "text-embedding-3-small"):
        dimension = self.DIMENSIONS.get(model, 1536)
        super().__init__(model=model, dimension=dimension)

        settings = get_settings()
        self.api_key = settings.openai_api_key

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package required: pip install openai")

    async def embed_text(self, text: str) -> list[float]:
        """Embed text using OpenAI API."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]


def get_embedding_provider(
    provider: str = "stub",
    model: str | None = None,
    dimension: int = 384,
) -> BaseEmbeddingProvider:
    """
    Factory function to get an embedding provider.

    Args:
        provider: "stub" or "openai"
        model: Model name (for OpenAI)
        dimension: Embedding dimension (for stub)

    Returns:
        An embedding provider instance
    """
    if provider == "stub":
        return StubEmbeddingProvider(dimension=dimension)
    elif provider == "openai":
        model = model or get_settings().default_embedding_model
        return OpenAIEmbeddingProvider(model=model)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
