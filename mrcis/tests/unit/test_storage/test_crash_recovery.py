"""Tests for crash recovery operations in StateDB."""

from datetime import datetime
from pathlib import Path

import pytest

from mrcis.models.state import FileStatus, IndexedFile
from mrcis.storage.state_db import StateDB


@pytest.fixture
async def db(tmp_path: Path):
    """Provide initialized StateDB."""

    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.initialize()

    # Create test repository
    repo_id = await state_db.create_repository(name="test-repo")
    state_db._test_repo_id = repo_id

    yield state_db
    await state_db.close()


class TestCrashRecovery:
    """Tests for crash recovery operations."""

    @pytest.mark.asyncio
    async def test_recover_resets_processing_to_pending(self, db) -> None:
        """Test recovery resets PROCESSING files to PENDING."""

        # Create a file stuck in PROCESSING
        file = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/stuck.py",
            checksum="abc123",
            file_size=1024,
            status=FileStatus.PROCESSING,
            last_modified_at=datetime.utcnow(),
        )
        file_id = await db.upsert_file(file)
        await db.update_file_status(file_id, FileStatus.PROCESSING)

        # Run recovery
        count = await db.recover_from_crash()

        # Should have recovered 1 file
        assert count == 1

        # File should now be PENDING
        recovered = await db.get_file(file_id)
        assert recovered.status == FileStatus.PENDING

    @pytest.mark.asyncio
    async def test_recover_requeues_pending_files(self, db) -> None:
        """Test recovery re-queues PENDING files not in queue."""

        # Create a PENDING file not in queue (simulates crash)
        file = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/orphan.py",
            checksum="abc123",
            file_size=1024,
            status=FileStatus.PENDING,
            last_modified_at=datetime.utcnow(),
        )
        await db.upsert_file(file)

        # Verify not in queue
        queue_len = await db.get_queue_length()
        assert queue_len == 0

        # Run recovery
        await db.recover_from_crash()

        # Should now be in queue
        queue_len = await db.get_queue_length()
        assert queue_len == 1

    @pytest.mark.asyncio
    async def test_recover_does_not_affect_indexed_files(self, db) -> None:
        """Test recovery doesn't change INDEXED files."""

        # Create an INDEXED file
        file = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/good.py",
            checksum="abc123",
            file_size=1024,
            status=FileStatus.INDEXED,
            last_modified_at=datetime.utcnow(),
        )
        file_id = await db.upsert_file(file)
        await db.update_file_indexed(file_id, entity_count=5)

        # Run recovery
        await db.recover_from_crash()

        # File should still be INDEXED
        recovered = await db.get_file(file_id)
        assert recovered.status == FileStatus.INDEXED
