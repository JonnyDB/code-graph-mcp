"""State models for MRCIS persistence."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RepositoryStatus(StrEnum):
    """Repository indexing status."""

    PENDING = "pending"
    INDEXING = "indexing"
    WATCHING = "watching"
    ERROR = "error"
    PAUSED = "paused"


class FileStatus(StrEnum):
    """File indexing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    PERMANENT_FAILURE = "permanent_failure"
    DELETED = "deleted"


class Repository(BaseModel):
    """
    Represents a monitored code repository's state.

    Note: Configuration (path, branch, patterns) comes from config file.
    This model only stores indexing state.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str

    # Status
    status: RepositoryStatus = RepositoryStatus.PENDING
    last_indexed_commit: str | None = None
    last_indexed_at: datetime | None = None

    # Statistics
    file_count: int = 0
    entity_count: int = 0
    relation_count: int = 0

    # Error tracking
    error_message: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"use_enum_values": True}


class IndexedFile(BaseModel):
    """
    Represents an indexed source file's state.

    Tracks indexing status, checksums for change detection,
    and failure counts for retry logic.
    """

    id: UUID = Field(default_factory=uuid4)
    repository_id: UUID

    # File identity (path is relative to repo root per Decision D1.1)
    path: str
    checksum: str
    file_size: int

    # Parsing metadata
    language: str | None = None
    status: FileStatus = FileStatus.PENDING
    failure_count: int = 0
    error_message: str | None = None

    # Statistics
    entity_count: int = 0

    # Timestamps
    last_modified_at: datetime
    last_indexed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"use_enum_values": True}
