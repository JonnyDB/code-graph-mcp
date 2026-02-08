"""Tests for FileEventRouter service."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mrcis.config.models import RepositoryConfig
from mrcis.models.state import FileStatus, IndexedFile, Repository
from mrcis.services.file_event_router import FileEventRouter
from mrcis.services.watcher import FileEvent


@pytest.fixture
def mock_state_db():
    """Mock StatePort."""
    return AsyncMock()


@pytest.fixture
def mock_indexer():
    """Mock IndexingService."""
    return AsyncMock()


@pytest.fixture
def mock_relation_graph():
    """Mock RelationGraphPort."""
    return AsyncMock()


@pytest.fixture
def mock_vector_store():
    """Mock VectorStorePort."""
    return AsyncMock()


@pytest.fixture
def repo_config(tmp_path):
    """Test repository configuration."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    return RepositoryConfig(
        name="test-repo",
        path=repo_path,
        branch="main",
    )


@pytest.fixture
def repo_configs(repo_config):
    """Repository configurations dict."""
    return {repo_config.name: repo_config}


@pytest.fixture
def router(mock_state_db, mock_indexer, mock_relation_graph, mock_vector_store, repo_configs):
    """FileEventRouter instance with mocked dependencies."""
    return FileEventRouter(
        state_db=mock_state_db,
        indexer=mock_indexer,
        relation_graph=mock_relation_graph,
        vector_store=mock_vector_store,
        repo_configs=repo_configs,
    )


class TestFileEventRouterHandle:
    """Tests for FileEventRouter.handle() method."""

    async def test_handle_unknown_repository(self, router, mock_state_db, mock_indexer):
        """Test handling event for unknown repository."""
        mock_state_db.get_repository_by_name.return_value = None

        event = FileEvent(
            type="modified",
            path=Path("/repos/unknown/file.py"),
            repository="unknown-repo",
        )

        await router.handle(event)

        # Should not call indexer
        mock_indexer.index_file.assert_not_called()

    async def test_handle_no_repo_config(self, router, mock_state_db, mock_indexer):
        """Test handling event when repo config is missing."""
        repo_id = uuid4()
        mock_state_db.get_repository_by_name.return_value = Repository(
            id=repo_id,
            name="test-repo",
            path="/repos/test-repo",
            branch="main",
        )

        # Remove repo config
        router.repo_configs.clear()

        event = FileEvent(
            type="modified",
            path=Path("/repos/test-repo/file.py"),
            repository="test-repo",
        )

        await router.handle(event)

        # Should not call indexer
        mock_indexer.index_file.assert_not_called()

    async def test_handle_created_file(self, router, mock_state_db, mock_indexer, repo_config):
        """Test handling created file event."""
        repo_id = uuid4()
        mock_state_db.get_repository_by_name.return_value = Repository(
            id=repo_id,
            name="test-repo",
            path="/repos/test-repo",
            branch="main",
        )

        event = FileEvent(
            type="created",
            path=Path("/repos/test-repo/src/module.py"),
            repository="test-repo",
        )

        await router.handle(event)

        # Should queue for indexing
        mock_indexer.index_file.assert_called_once_with(
            event.path, str(repo_id), repo_root=repo_config.path
        )

    async def test_handle_modified_file(self, router, mock_state_db, mock_indexer, repo_config):
        """Test handling modified file event."""
        repo_id = uuid4()
        mock_state_db.get_repository_by_name.return_value = Repository(
            id=repo_id,
            name="test-repo",
            path="/repos/test-repo",
            branch="main",
        )

        event = FileEvent(
            type="modified",
            path=Path("/repos/test-repo/src/module.py"),
            repository="test-repo",
        )

        await router.handle(event)

        # Should queue for indexing
        mock_indexer.index_file.assert_called_once_with(
            event.path, str(repo_id), repo_root=repo_config.path
        )

    async def test_handle_deleted_file_atomic_save(
        self, router, mock_state_db, mock_indexer, tmp_path
    ):
        """Test handling deleted file that still exists (atomic save)."""
        repo_id = uuid4()
        mock_state_db.get_repository_by_name.return_value = Repository(
            id=repo_id,
            name="test-repo",
            path=str(tmp_path),
            branch="main",
        )

        # Create a file that exists
        file_path = tmp_path / "file.py"
        file_path.write_text("content")

        # Update repo_config to use tmp_path
        router.repo_configs["test-repo"].path = tmp_path

        event = FileEvent(
            type="deleted",
            path=file_path,
            repository="test-repo",
        )

        await router.handle(event)

        # Should queue for indexing (atomic save detected)
        mock_indexer.index_file.assert_called_once_with(file_path, str(repo_id), repo_root=tmp_path)

    async def test_handle_deleted_file_real_deletion(
        self, router, mock_state_db, mock_indexer, mock_relation_graph, mock_vector_store, tmp_path
    ):
        """Test handling deleted file that doesn't exist (real deletion)."""
        repo_id = uuid4()
        file_id = uuid4()

        mock_state_db.get_repository_by_name.return_value = Repository(
            id=repo_id,
            name="test-repo",
            path=str(tmp_path),
            branch="main",
        )

        # File doesn't exist
        file_path = tmp_path / "deleted.py"

        # Update repo_config to use tmp_path
        router.repo_configs["test-repo"].path = tmp_path

        # Mock file lookup
        mock_state_db.get_file_by_path.return_value = IndexedFile(
            id=file_id,
            repository_id=repo_id,
            path="deleted.py",
            checksum="abc123",
            status=FileStatus.INDEXED,
            file_size=1024,
            last_modified_at=datetime.now(),
        )

        event = FileEvent(
            type="deleted",
            path=file_path,
            repository="test-repo",
        )

        await router.handle(event)

        # Should delete from index
        mock_indexer.index_file.assert_not_called()
        mock_relation_graph.delete_entities_for_file.assert_called_once_with(str(file_id))
        mock_vector_store.delete_by_file.assert_called_once_with(str(file_id))
        mock_state_db.update_file_status.assert_called_once_with(str(file_id), FileStatus.DELETED)

    async def test_handle_deleted_file_not_in_db(
        self, router, mock_state_db, mock_indexer, mock_relation_graph, mock_vector_store, tmp_path
    ):
        """Test handling deleted file that's not in database."""
        repo_id = uuid4()

        mock_state_db.get_repository_by_name.return_value = Repository(
            id=repo_id,
            name="test-repo",
            path=str(tmp_path),
            branch="main",
        )

        # File doesn't exist
        file_path = tmp_path / "deleted.py"

        # Update repo_config to use tmp_path
        router.repo_configs["test-repo"].path = tmp_path

        # File not in DB
        mock_state_db.get_file_by_path.return_value = None

        event = FileEvent(
            type="deleted",
            path=file_path,
            repository="test-repo",
        )

        await router.handle(event)

        # Should not attempt deletion
        mock_indexer.index_file.assert_not_called()
        mock_relation_graph.delete_entities_for_file.assert_not_called()
        mock_vector_store.delete_by_file.assert_not_called()
        mock_state_db.update_file_status.assert_not_called()
