"""Tests for EmbeddingService."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mrcis.config.models import EmbeddingConfig
from mrcis.services.embedder import EmbeddingService


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    """Create test embedding config."""
    return EmbeddingConfig(
        provider="openai_compatible",
        api_url="http://localhost:11434/v1",
        api_key="test-key",
        model="test-model",
        dimensions=1024,
        batch_size=10,
        timeout_seconds=30.0,
    )


@pytest.fixture
def mock_openai_response() -> MagicMock:
    """Create mock OpenAI embedding response."""
    response = MagicMock()
    response.data = [
        MagicMock(index=0, embedding=[0.1] * 1024),
        MagicMock(index=1, embedding=[0.2] * 1024),
    ]
    return response


class TestEmbeddingServiceInit:
    """Test EmbeddingService initialization."""

    def test_creates_with_config(self, embedding_config: EmbeddingConfig) -> None:
        """Should create service with config."""
        service = EmbeddingService(embedding_config)
        assert service.config == embedding_config
        assert service._client is None

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self, embedding_config: EmbeddingConfig) -> None:
        """Should create AsyncOpenAI client on initialize."""
        service = EmbeddingService(embedding_config)

        with patch("mrcis.services.embedder.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(index=0, embedding=[0.1] * 1024)])
            )
            mock_client_class.return_value = mock_client

            await service.initialize()

            mock_client_class.assert_called_once_with(
                base_url=embedding_config.api_url,
                api_key=embedding_config.api_key,
                timeout=embedding_config.timeout_seconds,
            )


class TestEmbedTexts:
    """Test embed_texts method."""

    @pytest.mark.asyncio
    async def test_embed_empty_list_returns_empty(self, embedding_config: EmbeddingConfig) -> None:
        """Empty input should return empty output."""
        service = EmbeddingService(embedding_config)
        result = await service.embed_texts([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_single_text(self, embedding_config: EmbeddingConfig) -> None:
        """Should embed single text."""
        service = EmbeddingService(embedding_config)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(index=0, embedding=[0.1] * 1024)]

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.embed_texts(["hello world"])

        assert len(result) == 1
        assert len(result[0]) == 1024

    @pytest.mark.asyncio
    async def test_embed_batches_large_input(self, embedding_config: EmbeddingConfig) -> None:
        """Should batch texts larger than batch_size."""
        embedding_config.batch_size = 2
        service = EmbeddingService(embedding_config)

        call_count = 0

        async def mock_create(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            texts = kwargs["input"]
            response = MagicMock()
            response.data = [
                MagicMock(index=i, embedding=[0.1 * (i + 1)] * 1024) for i in range(len(texts))
            ]
            return response

        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        service._client = mock_client

        result = await service.embed_texts(["a", "b", "c", "d", "e"])

        assert len(result) == 5
        assert call_count == 3  # 2 + 2 + 1


class TestEmbedQuery:
    """Test embed_query method."""

    @pytest.mark.asyncio
    async def test_embed_query_returns_single_vector(
        self, embedding_config: EmbeddingConfig
    ) -> None:
        """embed_query should return single vector."""
        service = EmbeddingService(embedding_config)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(index=0, embedding=[0.5] * 1024)]

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.embed_query("search query")

        assert isinstance(result, list)
        assert len(result) == 1024


class TestEosToken:
    """Test EOS token appending behavior."""

    @pytest.mark.asyncio
    async def test_eos_token_appended_when_enabled(self, embedding_config: EmbeddingConfig) -> None:
        """Should append EOS token to each text when append_eos_token is True."""
        embedding_config.append_eos_token = True
        embedding_config.eos_token = "</s>"
        service = EmbeddingService(embedding_config)

        captured_input: list[str] = []

        async def mock_create(**kwargs: Any) -> MagicMock:
            captured_input.extend(kwargs["input"])
            response = MagicMock()
            response.data = [MagicMock(index=0, embedding=[0.1] * 1024)]
            return response

        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        service._client = mock_client

        await service.embed_texts(["hello world"])

        assert captured_input == ["hello world</s>"]

    @pytest.mark.asyncio
    async def test_eos_token_not_appended_by_default(
        self, embedding_config: EmbeddingConfig
    ) -> None:
        """Should not append EOS token when append_eos_token is False (default)."""
        service = EmbeddingService(embedding_config)

        captured_input: list[str] = []

        async def mock_create(**kwargs: Any) -> MagicMock:
            captured_input.extend(kwargs["input"])
            response = MagicMock()
            response.data = [MagicMock(index=0, embedding=[0.1] * 1024)]
            return response

        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        service._client = mock_client

        await service.embed_texts(["hello world"])

        assert captured_input == ["hello world"]

    @pytest.mark.asyncio
    async def test_custom_eos_token(self, embedding_config: EmbeddingConfig) -> None:
        """Should use custom EOS token string."""
        embedding_config.append_eos_token = True
        embedding_config.eos_token = "[SEP]"
        service = EmbeddingService(embedding_config)

        captured_input: list[str] = []

        async def mock_create(**kwargs: Any) -> MagicMock:
            captured_input.extend(kwargs["input"])
            response = MagicMock()
            response.data = [MagicMock(index=i, embedding=[0.1] * 1024) for i in range(2)]
            return response

        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        service._client = mock_client

        await service.embed_texts(["foo", "bar"])

        assert captured_input == ["foo[SEP]", "bar[SEP]"]


class TestClose:
    """Test close method."""

    @pytest.mark.asyncio
    async def test_close_closes_client(self, embedding_config: EmbeddingConfig) -> None:
        """close should close the client."""
        service = EmbeddingService(embedding_config)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        service._client = mock_client

        await service.close()

        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_no_client(self, embedding_config: EmbeddingConfig) -> None:
        """close should handle case when client is None."""
        service = EmbeddingService(embedding_config)
        await service.close()  # Should not raise
