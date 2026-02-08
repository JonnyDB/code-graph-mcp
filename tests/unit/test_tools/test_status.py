"""Tests for status MCP tools."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mrcis.models.responses import IndexStatusResponse, ReindexResponse
from mrcis.tools.status import get_index_status, reindex_repository


@pytest.fixture
def mock_state_db() -> AsyncMock:
    """Create mock state database."""
    db = AsyncMock()
    db.get_all_repositories = AsyncMock(return_value=[])
    db.get_repository_by_name = AsyncMock(return_value=None)
    db.count_pending_files = AsyncMock(return_value=0)
    db.count_failed_files = AsyncMock(return_value=0)
    db.count_indexed_files = AsyncMock(return_value=0)
    return db


@pytest.fixture
def mock_relation_graph() -> AsyncMock:
    """Create mock relation graph."""
    rg = AsyncMock()
    rg.count_entities = AsyncMock(return_value=0)
    rg.count_relations = AsyncMock(return_value=0)
    return rg


@pytest.fixture
def mock_indexer() -> AsyncMock:
    """Create mock indexer."""
    indexer = AsyncMock()
    indexer.queue_repository = AsyncMock(return_value=0)
    return indexer


class TestGetIndexStatus:
    """Test get_index_status tool."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_repos(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """Should return empty status when no repositories."""
        result = await get_index_status(state_db=mock_state_db, relation_graph=mock_relation_graph)

        assert isinstance(result, IndexStatusResponse)
        assert len(result.repositories) == 0
        assert result.total_files == 0

    @pytest.mark.asyncio
    async def test_returns_status_for_all_repos(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """Should return status for all repositories."""
        # Setup mock repositories
        mock_repo = MagicMock()
        mock_repo.id = str(uuid4())
        mock_repo.name = "test-repo"
        mock_repo.status = "watching"
        mock_repo.file_count = 100
        mock_repo.entity_count = 500
        mock_repo.relation_count = 200
        mock_repo.last_indexed_at = "2026-02-02T12:00:00Z"
        mock_repo.last_indexed_commit = "abc123"

        mock_state_db.get_all_repositories.return_value = [mock_repo]
        mock_state_db.count_pending_files.return_value = 5
        mock_state_db.count_failed_files.return_value = 2
        mock_state_db.count_indexed_files.return_value = 100
        mock_relation_graph.count_entities.return_value = 500
        mock_relation_graph.count_relations.return_value = 200

        result = await get_index_status(state_db=mock_state_db, relation_graph=mock_relation_graph)

        assert len(result.repositories) == 1
        assert result.repositories[0].repository == "test-repo"
        assert result.repositories[0].status == "watching"
        assert result.repositories[0].file_count == 100
        assert result.repositories[0].entity_count == 500
        assert result.repositories[0].relation_count == 200
        assert result.total_files == 100
        assert result.total_entities == 500
        assert result.total_relations == 200

    @pytest.mark.asyncio
    async def test_uses_live_counts_not_repo_attributes(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """Should use live DB counts instead of stale repo attributes."""
        mock_repo = MagicMock()
        mock_repo.id = str(uuid4())
        mock_repo.name = "test-repo"
        mock_repo.status = "watching"
        # Stale values on repo object
        mock_repo.file_count = 0
        mock_repo.entity_count = 0
        mock_repo.relation_count = 0
        mock_repo.last_indexed_at = None
        mock_repo.last_indexed_commit = None

        mock_state_db.get_all_repositories.return_value = [mock_repo]
        mock_state_db.count_pending_files.return_value = 0
        mock_state_db.count_failed_files.return_value = 0
        # Live counts differ from stale repo attributes
        mock_state_db.count_indexed_files.return_value = 42
        mock_relation_graph.count_entities.return_value = 123
        mock_relation_graph.count_relations.return_value = 77

        result = await get_index_status(state_db=mock_state_db, relation_graph=mock_relation_graph)

        # Should use live counts, not repo.file_count etc.
        assert result.repositories[0].file_count == 42
        assert result.repositories[0].entity_count == 123
        assert result.repositories[0].relation_count == 77
        assert result.total_files == 42
        assert result.total_entities == 123
        assert result.total_relations == 77

    @pytest.mark.asyncio
    async def test_filters_by_repository(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """Should filter by repository name."""
        mock_repo = MagicMock()
        mock_repo.id = str(uuid4())
        mock_repo.name = "test-repo"
        mock_repo.status = "watching"
        mock_repo.file_count = 100
        mock_repo.entity_count = 500
        mock_repo.relation_count = 200
        mock_repo.last_indexed_at = None
        mock_repo.last_indexed_commit = None

        mock_state_db.get_repository_by_name.return_value = mock_repo
        mock_state_db.count_pending_files.return_value = 0
        mock_state_db.count_failed_files.return_value = 0
        mock_state_db.count_indexed_files.return_value = 100
        mock_relation_graph.count_entities.return_value = 500
        mock_relation_graph.count_relations.return_value = 200

        await get_index_status(
            state_db=mock_state_db,
            repository="test-repo",
            relation_graph=mock_relation_graph,
        )

        mock_state_db.get_repository_by_name.assert_called_once_with("test-repo")


class TestReindexRepository:
    """Test reindex_repository tool."""

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_repo(
        self,
        mock_state_db: AsyncMock,
        mock_indexer: AsyncMock,
    ) -> None:
        """Should return error when repository not found."""
        result = await reindex_repository(
            repository="nonexistent",
            state_db=mock_state_db,
            indexer=mock_indexer,
        )

        assert isinstance(result, ReindexResponse)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_queues_repository_for_reindex(
        self,
        mock_state_db: AsyncMock,
        mock_indexer: AsyncMock,
    ) -> None:
        """Should queue repository files for reindexing."""
        mock_repo = MagicMock()
        mock_repo.id = str(uuid4())
        mock_repo.name = "test-repo"
        mock_state_db.get_repository_by_name.return_value = mock_repo
        mock_indexer.queue_repository.return_value = 50

        result = await reindex_repository(
            repository="test-repo",
            state_db=mock_state_db,
            indexer=mock_indexer,
        )

        assert result.status == "queued"
        assert result.files_queued == 50
