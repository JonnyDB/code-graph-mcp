"""Tests for ServerRuntime lifecycle management."""

import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mrcis.server_runtime import ServerRuntime


def _make_mock_context():
    """Create a mock ServerContext with all required attributes."""
    mock_context = MagicMock()
    mock_context.background_tasks = []
    mock_context.indexer = MagicMock()
    mock_context.indexer.process_backlog = AsyncMock()
    mock_context.indexer.retry_failed_files = AsyncMock()
    mock_context.resolver = MagicMock()
    mock_context.resolver.run_forever = AsyncMock()
    mock_context.watcher = MagicMock()
    mock_context.watcher.start = AsyncMock()
    mock_context.watcher.on_change = MagicMock()
    mock_context.file_event_router = MagicMock()
    mock_context.file_event_router.handle = MagicMock()
    mock_context.is_writer = True
    return mock_context


def _make_mock_config(tmp_path: Path | None = None):
    """Create a mock configuration."""
    config = MagicMock()
    data_dir = tmp_path or Path("/tmp/test")
    config.storage.data_directory = data_dir
    config.storage.state_db_name = "test.db"
    config.storage.vector_table_name = "vectors"
    config.embedding.dimensions = 1024
    config.repositories = []
    config.indexing.resolution_interval_seconds = 60
    config.indexing.max_retries = 3
    config.indexing.watch_debounce_ms = 100
    config.files = MagicMock()
    config.logging.level = "INFO"
    return config


class TestServerRuntimeLifecycle:
    """Tests for ServerRuntime lifecycle management."""

    @pytest.mark.asyncio
    async def test_runtime_starts_uninitialized(self):
        """ServerRuntime should start in uninitialized state."""
        runtime = ServerRuntime()

        assert runtime.is_initialized() is False
        assert runtime.is_writer is False

        with pytest.raises(RuntimeError, match="Server not initialized"):
            runtime.get_context()

    @pytest.mark.asyncio
    async def test_runtime_prevents_double_initialization(self, tmp_path: Path):
        """ServerRuntime should raise error if started twice."""
        config = _make_mock_config(tmp_path)
        runtime = ServerRuntime()

        with (
            patch("mrcis.server_runtime.initialize_services") as mock_init,
            patch("mrcis.server_runtime.configure_logging"),
            patch("mrcis.server_runtime.startup_indexing"),
        ):
            mock_init.return_value = _make_mock_context()

            await runtime.start(config, Path("/tmp/config.yaml"))

            with pytest.raises(RuntimeError, match="already initialized"):
                await runtime.start(config, Path("/tmp/config.yaml"))

    @pytest.mark.asyncio
    async def test_runtime_stop_when_not_started(self):
        """ServerRuntime should handle stop when not started."""
        runtime = ServerRuntime()
        await runtime.stop()  # Should not raise


class TestServerRuntimeWriterMode:
    """Tests for writer mode startup and behavior."""

    @pytest.mark.asyncio
    async def test_writer_startup_acquires_lock(self, tmp_path: Path):
        """Writer startup should acquire the lock and start all background tasks."""
        config = _make_mock_config(tmp_path)
        runtime = ServerRuntime()

        with (
            patch("mrcis.server_runtime.initialize_services") as mock_init,
            patch("mrcis.server_runtime.configure_logging"),
            patch("mrcis.server_runtime.startup_indexing"),
        ):
            mock_context = _make_mock_context()
            mock_init.return_value = mock_context

            await runtime.start(config, Path("/tmp/config.yaml"))

            assert runtime.is_initialized() is True
            assert runtime.is_writer is True
            assert mock_context.is_writer is True
            # 5 writer tasks: process_backlog, retry_failed, resolver, watcher, heartbeat
            assert len(mock_context.background_tasks) == 5
            mock_init.assert_called_once_with(config)

    @pytest.mark.asyncio
    async def test_writer_startup_calls_startup_indexing(self, tmp_path: Path):
        """Writer startup should scan repositories."""
        config = _make_mock_config(tmp_path)
        runtime = ServerRuntime()

        with (
            patch("mrcis.server_runtime.initialize_services") as mock_init,
            patch("mrcis.server_runtime.configure_logging"),
            patch("mrcis.server_runtime.startup_indexing") as mock_startup,
        ):
            mock_context = _make_mock_context()
            mock_init.return_value = mock_context

            await runtime.start(config, Path("/tmp/config.yaml"))

            mock_startup.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_writer_stop_releases_lock(self, tmp_path: Path):
        """Stopping a writer runtime should release the lock."""
        config = _make_mock_config(tmp_path)
        runtime = ServerRuntime()

        with (
            patch("mrcis.server_runtime.initialize_services") as mock_init,
            patch("mrcis.server_runtime.shutdown_services") as mock_shutdown,
            patch("mrcis.server_runtime.configure_logging"),
            patch("mrcis.server_runtime.startup_indexing"),
        ):
            mock_context = _make_mock_context()
            mock_init.return_value = mock_context
            mock_shutdown.return_value = None

            await runtime.start(config, Path("/tmp/config.yaml"))

            # Lock file should exist
            lock_path = tmp_path / "mrcis.lock"
            assert lock_path.exists()

            await runtime.stop()

            assert runtime.is_initialized() is False
            assert runtime.is_writer is False
            assert not lock_path.exists()
            mock_shutdown.assert_called_once_with(mock_context)


class TestServerRuntimeReadOnlyMode:
    """Tests for read-only mode startup and behavior."""

    @pytest.mark.asyncio
    async def test_readonly_startup_when_lock_held(self, tmp_path: Path):
        """Runtime should start read-only when another instance holds the lock."""
        config = _make_mock_config(tmp_path)

        # Create a lock file held by the current process (simulating another instance)
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text(f"{os.getpid()}\n{datetime.now(UTC).isoformat()}\n")

        runtime = ServerRuntime()

        with (
            patch("mrcis.server_runtime.initialize_services") as mock_init,
            patch("mrcis.server_runtime.configure_logging"),
            patch("mrcis.server_runtime.startup_indexing") as mock_startup,
        ):
            mock_context = _make_mock_context()
            mock_init.return_value = mock_context

            await runtime.start(config, Path("/tmp/config.yaml"))

            assert runtime.is_initialized() is True
            assert runtime.is_writer is False
            assert mock_context.is_writer is False
            # Only 1 task: lock check loop
            assert len(mock_context.background_tasks) == 1
            # startup_indexing should NOT be called in read-only mode
            mock_startup.assert_not_called()

    @pytest.mark.asyncio
    async def test_readonly_stop_does_not_delete_foreign_lock(self, tmp_path: Path):
        """Stopping a read-only runtime should not delete the lock file."""
        config = _make_mock_config(tmp_path)

        # Create a lock file held by the current process
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text(f"{os.getpid()}\n{datetime.now(UTC).isoformat()}\n")

        runtime = ServerRuntime()

        with (
            patch("mrcis.server_runtime.initialize_services") as mock_init,
            patch("mrcis.server_runtime.shutdown_services") as mock_shutdown,
            patch("mrcis.server_runtime.configure_logging"),
        ):
            mock_context = _make_mock_context()
            mock_init.return_value = mock_context
            mock_shutdown.return_value = None

            await runtime.start(config, Path("/tmp/config.yaml"))
            assert runtime.is_writer is False

            await runtime.stop()

            # Lock should still exist (belongs to another instance)
            assert lock_path.exists()


class TestServerRuntimePromotion:
    """Tests for promotion from read-only to writer."""

    @pytest.mark.asyncio
    async def test_promote_to_writer(self, tmp_path: Path):
        """A read-only instance should be able to promote when the lock becomes stale."""
        config = _make_mock_config(tmp_path)

        # Create a stale lock file (dead PID)
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text(f"4000000000\n{datetime.now(UTC).isoformat()}\n")

        runtime = ServerRuntime()

        with (
            patch("mrcis.server_runtime.initialize_services") as mock_init,
            patch("mrcis.server_runtime.configure_logging"),
            patch("mrcis.server_runtime.startup_indexing") as mock_startup,
        ):
            mock_context = _make_mock_context()
            mock_init.return_value = mock_context

            await runtime.start(config, Path("/tmp/config.yaml"))

            # Should have taken over the stale lock immediately
            assert runtime.is_writer is True
            assert mock_context.is_writer is True
            mock_startup.assert_called_once()
