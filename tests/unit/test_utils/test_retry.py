"""Tests for retry utilities."""

import io
from collections.abc import Generator

import pytest
from loguru import logger

from mrcis.errors import EmbeddingError, StorageError
from mrcis.utils.retry import (
    on_backoff,
    on_giveup,
    retry_embedding,
    retry_network,
    retry_storage,
)


@pytest.fixture
def log_capture() -> Generator[io.StringIO, None, None]:
    """Capture loguru output to a string buffer."""
    string_io = io.StringIO()
    handler_id = logger.add(string_io, format="{message}")
    yield string_io
    logger.remove(handler_id)


class TestRetryCallbacks:
    """Test retry callback functions."""

    def test_on_backoff_logs_warning(self, log_capture: io.StringIO) -> None:
        """on_backoff should log retry attempts."""

        def dummy_func() -> None:
            pass

        details = {
            "target": dummy_func,
            "tries": 2,
            "wait": 1.5,
            "exception": ValueError("test"),
        }
        on_backoff(details)

        log_output = log_capture.getvalue()
        assert "Retrying" in log_output
        assert "dummy_func" in log_output

    def test_on_giveup_logs_error(self, log_capture: io.StringIO) -> None:
        """on_giveup should log when retries exhausted."""

        def dummy_func() -> None:
            pass

        details = {
            "target": dummy_func,
            "tries": 3,
            "exception": ValueError("test"),
        }
        on_giveup(details)

        log_output = log_capture.getvalue()
        assert "Gave up" in log_output


class TestRetryDecorators:
    """Test retry decorator configurations."""

    def test_retry_embedding_decorator_exists(self) -> None:
        """retry_embedding decorator should be callable."""
        assert callable(retry_embedding)

    def test_retry_storage_decorator_exists(self) -> None:
        """retry_storage decorator should be callable."""
        assert callable(retry_storage)

    def test_retry_network_decorator_exists(self) -> None:
        """retry_network decorator should be callable."""
        assert callable(retry_network)

    @pytest.mark.asyncio
    async def test_retry_embedding_retries_on_error(self) -> None:
        """retry_embedding should retry on EmbeddingError."""
        call_count = 0

        @retry_embedding
        async def flaky_embed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise EmbeddingError("Temporary failure")
            return "success"

        result = await flaky_embed()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_storage_retries_on_error(self) -> None:
        """retry_storage should retry on StorageError."""
        call_count = 0

        @retry_storage
        async def flaky_storage() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise StorageError("Temporary failure")
            return "success"

        result = await flaky_storage()
        assert result == "success"
        assert call_count == 2
