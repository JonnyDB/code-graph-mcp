"""Tests for IndexedFile CRUD operations in StateDB."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.models.state import FileStatus, IndexedFile
from mrcis.storage.state_db import StateDB


@pytest.fixture
async def db(tmp_path: Path):
    """Provide initialized StateDB with a repository."""

    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.initialize()

    # Create a test repository
    state_db._test_repo_id = await state_db.create_repository(name="test-repo")

    yield state_db
    await state_db.close()


class TestIndexedFileCRUD:
    """Tests for file CRUD operations."""

    @pytest.mark.asyncio
    async def test_upsert_file_creates_new(self, db) -> None:
        """Test upserting a new file."""

        file = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/main.py",
            checksum="abc123",
            file_size=1024,
            language="python",
            last_modified_at=datetime.utcnow(),
        )

        file_id = await db.upsert_file(file)
        assert file_id is not None

        retrieved = await db.get_file(file_id)
        assert retrieved is not None
        assert retrieved.path == "src/main.py"
        assert retrieved.checksum == "abc123"

    @pytest.mark.asyncio
    async def test_upsert_file_updates_existing(self, db) -> None:
        """Test upserting updates existing file."""

        file1 = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/main.py",
            checksum="abc123",
            file_size=1024,
            last_modified_at=datetime.utcnow(),
        )
        file_id = await db.upsert_file(file1)

        # Update with new checksum
        file2 = IndexedFile(
            id=file_id,
            repository_id=db._test_repo_id,
            path="src/main.py",
            checksum="xyz789",
            file_size=2048,
            last_modified_at=datetime.utcnow(),
        )
        await db.upsert_file(file2)

        retrieved = await db.get_file(file_id)
        assert retrieved.checksum == "xyz789"
        assert retrieved.file_size == 2048

    @pytest.mark.asyncio
    async def test_get_file_by_path(self, db) -> None:
        """Test getting file by path."""

        file = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/utils.py",
            checksum="abc123",
            file_size=512,
            last_modified_at=datetime.utcnow(),
        )
        await db.upsert_file(file)

        retrieved = await db.get_file_by_path(db._test_repo_id, "src/utils.py")
        assert retrieved is not None
        assert retrieved.path == "src/utils.py"

    @pytest.mark.asyncio
    async def test_update_file_status(self, db) -> None:
        """Test updating file status."""

        file = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/main.py",
            checksum="abc123",
            file_size=1024,
            last_modified_at=datetime.utcnow(),
        )
        file_id = await db.upsert_file(file)

        await db.update_file_status(file_id, FileStatus.PROCESSING)

        retrieved = await db.get_file(file_id)
        assert retrieved.status == FileStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_update_file_indexed(self, db) -> None:
        """Test marking file as indexed."""

        file = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/main.py",
            checksum="abc123",
            file_size=1024,
            last_modified_at=datetime.utcnow(),
        )
        file_id = await db.upsert_file(file)

        await db.update_file_indexed(file_id, entity_count=10)

        retrieved = await db.get_file(file_id)
        assert retrieved.status == FileStatus.INDEXED
        assert retrieved.entity_count == 10
        assert retrieved.last_indexed_at is not None

    @pytest.mark.asyncio
    async def test_update_file_failure(self, db) -> None:
        """Test recording file failure."""

        file = IndexedFile(
            repository_id=db._test_repo_id,
            path="src/bad.py",
            checksum="abc123",
            file_size=1024,
            last_modified_at=datetime.utcnow(),
        )
        file_id = await db.upsert_file(file)

        await db.update_file_failure(
            file_id,
            status=FileStatus.FAILED,
            failure_count=1,
            error_message="Parse error",
        )

        retrieved = await db.get_file(file_id)
        assert retrieved.status == FileStatus.FAILED
        assert retrieved.failure_count == 1
        assert retrieved.error_message == "Parse error"

    @pytest.mark.asyncio
    async def test_upsert_file_returns_existing_id_on_conflict(self, db) -> None:
        """Test that upsert returns the existing row's ID on conflict."""
        # Insert first file
        file1 = IndexedFile(
            id=str(uuid4()),
            repository_id=db._test_repo_id,
            path="src/same_path.py",
            checksum="abc123",
            file_size=1024,
            last_modified_at=datetime.utcnow(),
        )
        original_id = await db.upsert_file(file1)

        # Try to insert a different file with same repo+path (conflict)
        file2 = IndexedFile(
            id=str(uuid4()),  # Different ID
            repository_id=db._test_repo_id,
            path="src/same_path.py",  # Same path = conflict
            checksum="xyz789",
            file_size=2048,
            last_modified_at=datetime.utcnow(),
        )
        returned_id = await db.upsert_file(file2)

        # Should return the original ID, not file2's ID
        assert returned_id == original_id
        assert returned_id != str(file2.id)

        # Verify the data was updated
        retrieved = await db.get_file(returned_id)
        assert retrieved.checksum == "xyz789"
        assert retrieved.file_size == 2048
