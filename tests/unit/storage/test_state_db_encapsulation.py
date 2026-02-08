"""Tests for StateDB encapsulation improvements."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.models.state import FileStatus, IndexedFile
from mrcis.storage.state_db import StateDB


@pytest.fixture
async def state_db(tmp_path: Path):
    """Create initialized StateDB."""
    db = StateDB(tmp_path / "test.db")
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_list_files_by_repository(state_db: StateDB):
    """Test listing all files in a repository."""
    # Create a repository
    repo_id = await state_db.create_repository("test-repo")

    # Add some files
    file1 = IndexedFile(
        id=uuid4(),
        repository_id=repo_id,
        path="src/main.py",
        checksum="abc123",
        file_size=100,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.INDEXED,
    )
    file2 = IndexedFile(
        id=uuid4(),
        repository_id=repo_id,
        path="src/utils.py",
        checksum="def456",
        file_size=200,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.PENDING,
    )

    await state_db.upsert_file(file1)
    await state_db.upsert_file(file2)

    # List files - this method doesn't exist yet
    files = await state_db.list_files_by_repository(repo_id)

    assert len(files) == 2
    assert {f.path for f in files} == {"src/main.py", "src/utils.py"}


@pytest.mark.asyncio
async def test_mark_repository_files_pending(state_db: StateDB):
    """Test marking all repository files as pending."""
    repo_id = await state_db.create_repository("test-repo")

    # Add files with different statuses
    file1 = IndexedFile(
        id=uuid4(),
        repository_id=repo_id,
        path="src/main.py",
        checksum="abc123",
        file_size=100,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.INDEXED,
    )
    file2 = IndexedFile(
        id=uuid4(),
        repository_id=repo_id,
        path="src/utils.py",
        checksum="def456",
        file_size=200,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.FAILED,
        failure_count=2,
        error_message="Parse error",
    )

    await state_db.upsert_file(file1)
    await state_db.upsert_file(file2)

    # Mark as pending without reset
    count = await state_db.mark_repository_files_pending(repo_id, reset_failures=False)
    assert count == 2

    # Verify status changed but failure info preserved
    files = await state_db.list_files_by_repository(repo_id)
    assert all(f.status == FileStatus.PENDING for f in files)

    failed_file = next(f for f in files if f.path == "src/utils.py")
    assert failed_file.failure_count == 2
    assert failed_file.error_message == "Parse error"


@pytest.mark.asyncio
async def test_mark_repository_files_pending_with_reset(state_db: StateDB):
    """Test marking files pending with failure reset."""
    repo_id = await state_db.create_repository("test-repo")

    file = IndexedFile(
        id=uuid4(),
        repository_id=repo_id,
        path="src/main.py",
        checksum="abc123",
        file_size=100,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.FAILED,
        failure_count=3,
        error_message="Error",
    )

    await state_db.upsert_file(file)

    # Mark as pending with reset
    count = await state_db.mark_repository_files_pending(repo_id, reset_failures=True)
    assert count == 1

    # Verify failure info cleared
    updated = await state_db.get_file_by_path(repo_id, "src/main.py")
    assert updated.status == FileStatus.PENDING
    assert updated.failure_count == 0
    assert updated.error_message is None


@pytest.mark.asyncio
async def test_enqueue_pending_files(state_db: StateDB):
    """Test enqueueing all pending files for a repository."""
    repo_id = await state_db.create_repository("test-repo")

    # Add pending and non-pending files
    pending1 = IndexedFile(
        id=uuid4(),
        repository_id=repo_id,
        path="src/main.py",
        checksum="abc123",
        file_size=100,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.PENDING,
    )
    pending2 = IndexedFile(
        id=uuid4(),
        repository_id=repo_id,
        path="src/utils.py",
        checksum="def456",
        file_size=200,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.PENDING,
    )
    indexed = IndexedFile(
        id=uuid4(),
        repository_id=repo_id,
        path="src/done.py",
        checksum="ghi789",
        file_size=300,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.INDEXED,
    )

    await state_db.upsert_file(pending1)
    await state_db.upsert_file(pending2)
    await state_db.upsert_file(indexed)

    # Enqueue pending files
    count = await state_db.enqueue_pending_files(repo_id)
    assert count == 2

    # Verify queue length
    queue_len = await state_db.get_queue_length()
    assert queue_len == 2


@pytest.mark.asyncio
async def test_transaction_context_manager_commit(state_db: StateDB):
    """Test transaction commits on success."""
    # Use low-level execute to test transaction directly
    repo_id = str(uuid4())

    async with state_db.transaction():
        await state_db.execute(
            """
            INSERT INTO repositories (id, name, status)
            VALUES (?, ?, ?)
            """,
            [repo_id, "test-repo", "pending"],
        )

    # Verify commit happened
    retrieved = await state_db.get_repository(repo_id)
    assert retrieved is not None
    assert retrieved.name == "test-repo"


@pytest.mark.asyncio
async def test_transaction_context_manager_rollback(state_db: StateDB):
    """Test transaction rolls back on exception."""
    repo_id = str(uuid4())

    with pytest.raises(ValueError):
        async with state_db.transaction():
            await state_db.execute(
                """
                INSERT INTO repositories (id, name, status)
                VALUES (?, ?, ?)
                """,
                [repo_id, "test-repo", "pending"],
            )
            raise ValueError("Simulated error")

    # Verify rollback happened
    retrieved = await state_db.get_repository(repo_id)
    assert retrieved is None
