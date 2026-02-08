"""Port interface for embedding services."""

from collections.abc import Sequence
from typing import Protocol


class EmbedderPort(Protocol):
    """Protocol for text embedding services.

    Implementations must provide methods to generate vector embeddings
    from text for semantic search.
    """

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: Sequence of text strings to embed

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query string.

        Args:
            query: Query text to embed

        Returns:
            Single embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...

    async def close(self) -> None:
        """Close embedding service resources."""
        ...
