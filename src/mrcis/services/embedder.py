"""Embedding service using OpenAI-compatible API.

Supports Ollama, LM Studio, and any OpenAI-compatible API
using the official OpenAI Python SDK.
"""

from collections.abc import Sequence

from loguru import logger
from openai import AsyncOpenAI

from mrcis.config.models import EmbeddingConfig


class EmbeddingService:
    """
    OpenAI-compatible embedding client.

    Supports Ollama, LM Studio, and any OpenAI-compatible API
    using the official OpenAI Python SDK.
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self._client: AsyncOpenAI | None = None

    async def initialize(self) -> None:
        """Initialize AsyncOpenAI client and validate connection."""
        self._client = AsyncOpenAI(
            base_url=self.config.api_url,
            api_key=self.config.api_key,
            timeout=self.config.timeout_seconds,
        )

        # Validate connection with a test embedding
        try:
            test = await self.embed_texts(["test"])
            if len(test[0]) != self.config.dimensions:
                raise ValueError(
                    f"Model returned {len(test[0])} dimensions, expected {self.config.dimensions}"
                )
            logger.info("Embedding service ready: model={}", self.config.model)
        except Exception as e:
            logger.error("Embedding service initialization failed: {}", e)
            raise

    async def close(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.close()

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Handles batching automatically.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i : i + self.config.batch_size]
            embeddings = await self._embed_batch(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query."""
        results = await self.embed_texts([query])
        return results[0]

    async def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a single batch using the OpenAI SDK."""
        if self._client is None:
            raise RuntimeError("EmbeddingService not initialized. Call initialize() first.")

        response = await self._client.embeddings.create(
            model=self.config.model,
            input=list(texts),
        )

        # Sort by index to maintain order (API may return out of order)
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]
