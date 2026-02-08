"""Port interfaces for state storage operations."""

from typing import Any, Protocol
from uuid import UUID

from mrcis.models.state import FileStatus, IndexedFile, Repository


class RepositoryReaderPort(Protocol):
    """Protocol for reading repository state."""

    async def get_repository(self, repo_id: str | UUID | None) -> Repository | None:
        """Get repository by ID."""
        ...

    async def get_repository_by_name(self, name: str) -> Repository | None:
        """Get repository by name."""
        ...

    async def list_repositories(self) -> list[Repository]:
        """List all repositories."""
        ...

    async def get_all_repositories(self) -> list[Repository]:
        """Get all repositories."""
        ...

    async def count_pending_files(self, repo_id: str) -> int:
        """Count pending files for a repository."""
        ...

    async def count_failed_files(self, repo_id: str) -> int:
        """Count failed files for a repository."""
        ...

    async def count_indexed_files(self, repo_id: str) -> int:
        """Count indexed files for a repository."""
        ...

    async def count_entities(self, repo_id: str) -> int:
        """Count entities in a repository."""
        ...

    async def count_relations(self, repo_id: str) -> int:
        """Count relations in a repository."""
        ...


class RepositoryWriterPort(Protocol):
    """Protocol for writing repository state."""

    async def add_repository(self, repository: Repository) -> None:
        """Add or update a repository."""
        ...

    async def update_repository_stats(
        self,
        repo_id: str,
        file_count: int | None = None,
        entity_count: int | None = None,
        relation_count: int | None = None,
        last_indexed_at: str | None = None,
        last_indexed_commit: str | None = None,
        status: str | None = None,
    ) -> None:
        """Update repository statistics and indexing metadata."""
        ...


class FileReaderPort(Protocol):
    """Protocol for reading file state."""

    async def get_file(self, file_id: str | UUID) -> IndexedFile | None:
        """Get file by ID."""
        ...

    async def get_file_by_path(self, repository_id: str, file_path: str) -> IndexedFile | None:
        """Get file by repository and path."""
        ...

    async def list_files_by_repository(self, repo_id: str) -> list[IndexedFile]:
        """List all indexed files in a repository."""
        ...

    async def get_retryable_failed_files(self) -> list[IndexedFile]:
        """Get files that can be retried after failure."""
        ...


class FileWriterPort(Protocol):
    """Protocol for writing file state."""

    async def upsert_file(self, file: IndexedFile) -> str:
        """Insert or update a file record. Returns file ID."""
        ...

    async def mark_files_pending(self, repo_id: str, *, reset_failures: bool = False) -> int:
        """Mark all files in a repository as pending reindex."""
        ...

    async def mark_repository_files_pending(
        self, repo_id: str, *, reset_failures: bool = False
    ) -> int:
        """Mark all files in a repository as pending reindex."""
        ...

    async def update_file_status(self, file_id: str, status: FileStatus) -> None:
        """Update file status."""
        ...

    async def update_file_indexed(self, file_id: str, entity_count: int) -> None:
        """Update file as successfully indexed with entity count."""
        ...

    async def update_file_failure(
        self,
        file_id: str,
        status: FileStatus,
        failure_count: int,
        error_message: str | None,
    ) -> None:
        """Update file with failure information."""
        ...


class QueuePort(Protocol):
    """Protocol for indexing queue operations."""

    async def enqueue_file(self, file_id: str, repo_id: str, priority: int = 0) -> None:
        """Add file to indexing queue."""
        ...

    async def enqueue_pending_files(self, repo_id: str) -> int:
        """Enqueue all pending files in a repository. Returns count."""
        ...

    async def dequeue_batch(self, limit: int) -> list[str]:
        """Dequeue up to limit file IDs."""
        ...

    async def dequeue_next_file(self) -> IndexedFile | None:
        """Dequeue next file from the queue."""
        ...

    async def get_queue_size(self) -> int:
        """Get current queue size."""
        ...

    async def get_queue_length(self) -> int:
        """Get current queue length."""
        ...


class IndexingStatePort(
    RepositoryReaderPort, RepositoryWriterPort, FileReaderPort, FileWriterPort, QueuePort
):
    """Combined protocol for indexing service state needs."""

    # Note: transaction() is decorated with @asynccontextmanager in implementations
    # but protocols can't use decorators, so we just specify the return type
    def transaction(self) -> Any:
        """Context manager for database transactions. Returns async context manager."""
        ...


class StatePort(
    RepositoryReaderPort,
    RepositoryWriterPort,
    FileReaderPort,
    FileWriterPort,
    QueuePort,
):
    """Full state storage protocol (all operations)."""

    async def initialize(self) -> None:
        """Initialize database connection and apply migrations."""
        ...

    async def close(self) -> None:
        """Close the database connection."""
        ...
