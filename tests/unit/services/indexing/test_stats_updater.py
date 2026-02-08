"""Tests for RepositoryStatsUpdater."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from mrcis.services.indexing.stats_updater import RepositoryStatsUpdater

if TYPE_CHECKING:
    from mrcis.ports import IndexingStatePort


@pytest.fixture
def state_db() -> "IndexingStatePort":
    """Create mock state database."""
    db = AsyncMock()
    db.count_indexed_files = AsyncMock(return_value=42)
    db.count_entities = AsyncMock(return_value=150)
    db.count_relations = AsyncMock(return_value=75)
    db.count_pending_files = AsyncMock(return_value=5)
    db.update_repository_stats = AsyncMock()
    return db


class TestRepositoryStatsUpdater:
    """Tests for RepositoryStatsUpdater class."""

    async def test_updates_all_stats_after_file_indexed(
        self, state_db: "IndexingStatePort"
    ) -> None:
        """Updater should query all counts and update repository stats."""
        updater = RepositoryStatsUpdater(state_db)
        repo_id = str(uuid4())

        await updater.update_after_file_indexed(repo_id)

        # Should query all counts
        state_db.count_indexed_files.assert_awaited_once_with(repo_id)
        state_db.count_entities.assert_awaited_once_with(repo_id)
        state_db.count_relations.assert_awaited_once_with(repo_id)
        state_db.count_pending_files.assert_awaited_once_with(repo_id)

        # Should update stats with counts
        state_db.update_repository_stats.assert_awaited_once()
        call_kwargs = state_db.update_repository_stats.await_args[1]
        assert call_kwargs["file_count"] == 42
        assert call_kwargs["entity_count"] == 150
        assert call_kwargs["relation_count"] == 75
        assert "last_indexed_at" in call_kwargs

    async def test_sets_status_to_watching_when_no_pending_files(
        self, state_db: "IndexingStatePort"
    ) -> None:
        """Updater should set status to 'watching' when no pending files remain."""
        state_db.count_pending_files = AsyncMock(return_value=0)
        updater = RepositoryStatsUpdater(state_db)
        repo_id = str(uuid4())

        await updater.update_after_file_indexed(repo_id)

        call_kwargs = state_db.update_repository_stats.await_args[1]
        assert call_kwargs["status"] == "watching"

    async def test_sets_status_to_indexing_when_pending_files_remain(
        self, state_db: "IndexingStatePort"
    ) -> None:
        """Updater should set status to 'indexing' when pending files remain."""
        state_db.count_pending_files = AsyncMock(return_value=10)
        updater = RepositoryStatsUpdater(state_db)
        repo_id = str(uuid4())

        await updater.update_after_file_indexed(repo_id)

        call_kwargs = state_db.update_repository_stats.await_args[1]
        assert call_kwargs["status"] == "indexing"

    async def test_includes_current_timestamp(self, state_db: "IndexingStatePort") -> None:
        """Updater should include current timestamp in last_indexed_at."""
        updater = RepositoryStatsUpdater(state_db)
        repo_id = str(uuid4())

        before = datetime.now(UTC)
        await updater.update_after_file_indexed(repo_id)
        after = datetime.now(UTC)

        call_kwargs = state_db.update_repository_stats.await_args[1]
        timestamp_str = call_kwargs["last_indexed_at"]
        timestamp = datetime.fromisoformat(timestamp_str)

        # Verify timestamp is within reasonable bounds
        assert before <= timestamp <= after

    async def test_updates_relation_count_only_after_resolution(
        self, state_db: "IndexingStatePort"
    ) -> None:
        """Updater should only update relation count after reference resolution."""
        state_db.count_relations = AsyncMock(return_value=100)
        updater = RepositoryStatsUpdater(state_db)
        repo_id = str(uuid4())

        await updater.update_after_resolution(repo_id)

        # Should only query relation count (not all counts)
        state_db.count_relations.assert_awaited_once_with(repo_id)
        state_db.count_indexed_files.assert_not_awaited()
        state_db.count_entities.assert_not_awaited()
        state_db.count_pending_files.assert_not_awaited()

        # Should update only relation count
        state_db.update_repository_stats.assert_awaited_once()
        call_kwargs = state_db.update_repository_stats.await_args[1]
        assert call_kwargs["relation_count"] == 100
        assert "file_count" not in call_kwargs
        assert "entity_count" not in call_kwargs
        assert "status" not in call_kwargs
