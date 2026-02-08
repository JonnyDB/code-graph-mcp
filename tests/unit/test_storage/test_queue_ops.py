"""Tests for indexing queue operations in StateDB."""

from datetime import datetime
from pathlib import Path

import pytest

from mrcis.models.state import FileStatus, IndexedFile
from mrcis.storage.state_db import StateDB


@pytest.fixture
async def db(tmp_path: Path):
    """Provide initialized StateDB with repository and files."""

    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.initialize()

    # Create test repository
    repo_id = await state_db.create_repository(name="test-repo")
    state_db._test_repo_id = repo_id

    # Create test files
    state_db._test_files = []
    for i, name in enumerate(["a.py", "b.py", "c.py"]):
        file = IndexedFile(
            repository_id=repo_id,
            path=f"src/{name}",
            checksum=f"hash{i}",
            file_size=100 * (i + 1),
            last_modified_at=datetime.utcnow(),
        )
        file_id = await state_db.upsert_file(file)
        state_db._test_files.append(file_id)

    yield state_db
    await state_db.close()


class TestQueueOperations:
    """Tests for indexing queue operations."""

    @pytest.mark.asyncio
    async def test_enqueue_file(self, db) -> None:
        """Test enqueueing a file."""
        file_id = db._test_files[0]

        await db.enqueue_file(file_id, db._test_repo_id)

        # Check queue has the file
        queued = await db.fetchone("SELECT * FROM indexing_queue WHERE file_id = ?", [file_id])
        assert queued is not None
        assert queued["file_id"] == file_id

    @pytest.mark.asyncio
    async def test_enqueue_file_ignores_duplicate(self, db) -> None:
        """Test enqueueing same file twice is idempotent."""
        file_id = db._test_files[0]

        await db.enqueue_file(file_id, db._test_repo_id)
        await db.enqueue_file(file_id, db._test_repo_id)  # Should not error

        # Count should be 1
        row = await db.fetchone(
            "SELECT COUNT(*) as cnt FROM indexing_queue WHERE file_id = ?",
            [file_id],
        )
        assert row["cnt"] == 1

    @pytest.mark.asyncio
    async def test_dequeue_next_file_fifo(self, db) -> None:
        """Test dequeuing returns files in FIFO order."""
        # Enqueue in order
        for file_id in db._test_files:
            await db.enqueue_file(file_id, db._test_repo_id)

        # Dequeue should return in same order
        for expected_file_id in db._test_files:
            file = await db.dequeue_next_file()
            assert file is not None
            assert str(file.id) == expected_file_id

    @pytest.mark.asyncio
    async def test_dequeue_next_file_returns_none_when_empty(self, db) -> None:
        """Test dequeue returns None when queue is empty."""
        file = await db.dequeue_next_file()
        assert file is None

    @pytest.mark.asyncio
    async def test_dequeue_removes_from_queue(self, db) -> None:
        """Test dequeue removes file from queue."""
        file_id = db._test_files[0]
        await db.enqueue_file(file_id, db._test_repo_id)

        await db.dequeue_next_file()

        # Queue should be empty
        row = await db.fetchone(
            "SELECT COUNT(*) as cnt FROM indexing_queue WHERE file_id = ?",
            [file_id],
        )
        assert row["cnt"] == 0

    @pytest.mark.asyncio
    async def test_get_retryable_failed_files_returns_failed(self, db) -> None:
        """get_retryable_failed_files should return files with 'failed' status."""
        file_id = db._test_files[0]
        await db.update_file_failure(file_id, FileStatus.FAILED, 1, "some error")

        result = await db.get_retryable_failed_files()
        assert len(result) == 1
        assert str(result[0].id) == file_id
        assert result[0].status == FileStatus.FAILED

    @pytest.mark.asyncio
    async def test_get_retryable_failed_files_excludes_permanent_failure(self, db) -> None:
        """get_retryable_failed_files should not return permanent_failure files."""
        await db.update_file_failure(db._test_files[0], FileStatus.PERMANENT_FAILURE, 3, "gave up")
        await db.update_file_failure(db._test_files[1], FileStatus.FAILED, 1, "transient")

        result = await db.get_retryable_failed_files()
        assert len(result) == 1
        assert str(result[0].id) == db._test_files[1]

    @pytest.mark.asyncio
    async def test_get_retryable_failed_files_returns_empty_when_none(self, db) -> None:
        """get_retryable_failed_files should return empty list when no failures."""
        result = await db.get_retryable_failed_files()
        assert result == []

    @pytest.mark.asyncio
    async def test_enqueue_with_priority(self, db) -> None:
        """Test high priority files are dequeued first."""
        # Enqueue low priority first
        await db.enqueue_file(db._test_files[0], db._test_repo_id, priority=0)
        await db.enqueue_file(db._test_files[1], db._test_repo_id, priority=0)
        # Then high priority
        await db.enqueue_file(db._test_files[2], db._test_repo_id, priority=10)

        # High priority should come first
        file = await db.dequeue_next_file()
        assert str(file.id) == db._test_files[2]
