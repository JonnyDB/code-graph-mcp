"""Tests for FileWatcher service."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mrcis.config.models import RepositoryConfig
from mrcis.services.watcher import FileChangeHandler, FileEvent, FileWatcher


@pytest.fixture
def repo_config(tmp_path: Path) -> RepositoryConfig:
    """Create test repository config."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    return RepositoryConfig(
        name="test-repo",
        path=repo_path,
        branch="main",
    )


@pytest.fixture
def repo_configs(repo_config: RepositoryConfig) -> dict[str, RepositoryConfig]:
    """Create repo configs dict."""
    return {repo_config.name: repo_config}


class TestFileEvent:
    """Test FileEvent dataclass."""

    def test_creates_file_event(self, tmp_path: Path) -> None:
        """Should create FileEvent with all fields."""
        event = FileEvent(
            type="created",
            path=tmp_path / "file.py",
            repository="test-repo",
        )

        assert event.type == "created"
        assert event.path == tmp_path / "file.py"
        assert event.repository == "test-repo"


class TestFileWatcher:
    """Test FileWatcher service."""

    def test_creates_with_config(self, repo_configs: dict[str, RepositoryConfig]) -> None:
        """Should create watcher with repo configs."""
        watcher = FileWatcher(repo_configs, debounce_ms=500)

        assert watcher.repo_configs == repo_configs
        assert watcher.debounce_ms == 500

    def test_register_callback(self, repo_configs: dict[str, RepositoryConfig]) -> None:
        """Should register change callbacks."""
        watcher = FileWatcher(repo_configs)

        async def callback(event: FileEvent) -> None:
            pass

        watcher.on_change(callback)

        assert callback in watcher._callbacks

    @pytest.mark.asyncio
    async def test_stop_sets_shutdown_event(
        self, repo_configs: dict[str, RepositoryConfig]
    ) -> None:
        """stop should set shutdown event."""
        watcher = FileWatcher(repo_configs)

        await watcher.stop()

        assert watcher._shutdown_event.is_set()


class TestFileChangeHandler:
    """Test FileChangeHandler."""

    def test_ignores_directory_events(self, repo_config: RepositoryConfig) -> None:
        """Should ignore directory events."""
        queue: asyncio.Queue[FileEvent] = asyncio.Queue()
        handler = FileChangeHandler(queue, repo_config)

        # Create mock directory event
        event = MagicMock()
        event.is_directory = True
        event.src_path = str(repo_config.path / "subdir")
        event.event_type = "created"

        # Process event
        with patch.object(handler, "_loop", MagicMock()):
            handler.on_any_event(event)

        # Queue should be empty
        assert queue.empty()
