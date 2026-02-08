"""Tests for Repository and IndexedFile state models."""

from datetime import datetime
from uuid import uuid4

from mrcis.models.state import FileStatus, IndexedFile, Repository, RepositoryStatus


class TestRepositoryStatus:
    """Tests for RepositoryStatus enum."""

    def test_repository_status_values(self) -> None:
        """Test RepositoryStatus has required values."""

        assert RepositoryStatus.PENDING == "pending"
        assert RepositoryStatus.INDEXING == "indexing"
        assert RepositoryStatus.WATCHING == "watching"
        assert RepositoryStatus.ERROR == "error"
        assert RepositoryStatus.PAUSED == "paused"


class TestFileStatus:
    """Tests for FileStatus enum."""

    def test_file_status_values(self) -> None:
        """Test FileStatus has required values."""

        assert FileStatus.PENDING == "pending"
        assert FileStatus.PROCESSING == "processing"
        assert FileStatus.INDEXED == "indexed"
        assert FileStatus.FAILED == "failed"
        assert FileStatus.PERMANENT_FAILURE == "permanent_failure"
        assert FileStatus.DELETED == "deleted"


class TestRepository:
    """Tests for Repository model."""

    def test_repository_required_fields(self) -> None:
        """Test Repository requires name."""

        repo = Repository(name="my-repo")

        assert repo.name == "my-repo"
        assert repo.status == RepositoryStatus.PENDING

    def test_repository_defaults(self) -> None:
        """Test Repository has correct defaults."""

        repo = Repository(name="my-repo")

        assert repo.status == RepositoryStatus.PENDING
        assert repo.last_indexed_commit is None
        assert repo.last_indexed_at is None
        assert repo.file_count == 0
        assert repo.entity_count == 0
        assert repo.relation_count == 0
        assert repo.error_message is None

    def test_repository_with_stats(self) -> None:
        """Test Repository with statistics."""

        repo = Repository(
            name="my-repo",
            status=RepositoryStatus.WATCHING,
            file_count=100,
            entity_count=500,
            relation_count=200,
        )

        assert repo.file_count == 100
        assert repo.entity_count == 500
        assert repo.relation_count == 200


class TestIndexedFile:
    """Tests for IndexedFile model."""

    def test_indexed_file_required_fields(self) -> None:
        """Test IndexedFile requires essential fields."""

        file = IndexedFile(
            repository_id=uuid4(),
            path="src/module.py",
            checksum="abc123",
            file_size=1024,
            last_modified_at=datetime.now(),
        )

        assert file.path == "src/module.py"
        assert file.checksum == "abc123"
        assert file.file_size == 1024

    def test_indexed_file_defaults(self) -> None:
        """Test IndexedFile has correct defaults."""

        file = IndexedFile(
            repository_id=uuid4(),
            path="src/module.py",
            checksum="abc123",
            file_size=1024,
            last_modified_at=datetime.now(),
        )

        assert file.status == FileStatus.PENDING
        assert file.language is None
        assert file.failure_count == 0
        assert file.error_message is None
        assert file.entity_count == 0
        assert file.last_indexed_at is None

    def test_indexed_file_with_failure(self) -> None:
        """Test IndexedFile tracking failures."""

        file = IndexedFile(
            repository_id=uuid4(),
            path="src/bad.py",
            checksum="xyz789",
            file_size=500,
            last_modified_at=datetime.now(),
            status=FileStatus.FAILED,
            failure_count=2,
            error_message="Parse error",
        )

        assert file.status == FileStatus.FAILED
        assert file.failure_count == 2
        assert file.error_message == "Parse error"
