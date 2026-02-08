"""SQLite state database for MRCIS."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from mrcis.models.state import FileStatus, IndexedFile, Repository, RepositoryStatus
from mrcis.storage.migrations import v001_initial, v002_receiver_expr


class StateDB:
    """
    SQLite database for indexing state and relationships.

    Handles:
    - Repository and file state tracking
    - Entity (symbol) registry
    - Relationship graph storage
    - Indexing queue management
    """

    def __init__(self, db_path: Path | str) -> None:
        """
        Initialize StateDB.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """
        Initialize database connection and apply migrations.

        Creates the database file if it doesn't exist.
        """
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect and configure
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        # Enable foreign keys and WAL mode for concurrent reader support
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA journal_mode = WAL")

        # Apply migrations
        await self._apply_migrations()

    async def _apply_migrations(self) -> None:
        """
        Apply database migrations incrementally based on current schema version.
        """
        conn = self._get_conn()

        # Check if schema_version table exists
        cursor = await conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_version'
            """
        )
        table_exists = await cursor.fetchone()

        current_version = 0
        if table_exists:
            # Get current schema version
            cursor = await conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            current_version = row[0] if row else 0

        # Apply migrations in order
        if current_version < 1:
            await v001_initial.apply_migration(conn)
            current_version = 1

        if current_version < 2:
            await v002_receiver_expr.apply_migration(conn)
            current_version = 2

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    def _get_conn(self) -> aiosqlite.Connection:
        """Get database connection, raising if not initialized."""
        if not self._conn:
            raise RuntimeError("Database not initialized")
        return self._conn

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """
        Context manager for database transactions.

        Commits on success, rollbacks on exception.
        """
        conn = self._get_conn()

        try:
            yield
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    async def execute(self, sql: str, params: list[Any] | None = None) -> aiosqlite.Cursor:
        """Execute a SQL statement."""
        conn = self._get_conn()
        return await conn.execute(sql, params or [])

    async def executemany(self, sql: str, params_list: list[list[Any]]) -> aiosqlite.Cursor:
        """Execute a SQL statement with multiple parameter sets."""
        conn = self._get_conn()
        return await conn.executemany(sql, params_list)

    async def fetchone(self, sql: str, params: list[Any] | None = None) -> aiosqlite.Row | None:
        """Execute query and fetch one row."""
        cursor = await self.execute(sql, params)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params: list[Any] | None = None) -> list[aiosqlite.Row]:
        """Execute query and fetch all rows."""
        cursor = await self.execute(sql, params)
        result = await cursor.fetchall()
        return list(result) if result else []

    # =========================================================================
    # Repository Operations
    # =========================================================================

    async def create_repository(self, name: str, status: str = "pending") -> str:
        """
        Create a new repository record.

        Args:
            name: Repository name (must be unique).
            status: Initial status (default: pending).

        Returns:
            Repository ID (UUID string).
        """
        repo_id = str(uuid4())
        await self.execute(
            """
            INSERT INTO repositories (id, name, status)
            VALUES (?, ?, ?)
            """,
            [repo_id, name, status],
        )
        conn = self._get_conn()
        await conn.commit()
        return repo_id

    async def get_repository(self, repo_id: str) -> "Repository | None":
        """Get repository by ID."""
        row = await self.fetchone("SELECT * FROM repositories WHERE id = ?", [repo_id])
        if row is None:
            return None
        return self._row_to_repository(row)

    async def get_repository_by_name(self, name: str) -> "Repository | None":
        """Get repository by name."""
        row = await self.fetchone("SELECT * FROM repositories WHERE name = ?", [name])
        if row is None:
            return None
        return self._row_to_repository(row)

    async def get_all_repositories(self) -> list["Repository"]:
        """Get all repositories."""
        rows = await self.fetchall("SELECT * FROM repositories ORDER BY name")
        return [self._row_to_repository(row) for row in rows]

    async def update_repository_status(
        self, repo_id: str, status: str, error_message: str | None = None
    ) -> None:
        """Update repository status."""
        await self.execute(
            """
            UPDATE repositories
            SET status = ?, error_message = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            [status, error_message, repo_id],
        )
        conn = self._get_conn()
        await conn.commit()

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
        updates: list[str] = []
        params: list[Any] = []

        if file_count is not None:
            updates.append("file_count = ?")
            params.append(file_count)
        if entity_count is not None:
            updates.append("entity_count = ?")
            params.append(entity_count)
        if relation_count is not None:
            updates.append("relation_count = ?")
            params.append(relation_count)
        if last_indexed_at is not None:
            updates.append("last_indexed_at = ?")
            params.append(last_indexed_at)
        if last_indexed_commit is not None:
            updates.append("last_indexed_commit = ?")
            params.append(last_indexed_commit)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(repo_id)
            conn = self._get_conn()
            await conn.execute(
                f"UPDATE repositories SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            await conn.commit()

    async def delete_repository(self, repo_id: str) -> None:
        """Delete repository and all related data (cascades)."""
        await self.execute("DELETE FROM repositories WHERE id = ?", [repo_id])
        conn = self._get_conn()
        await conn.commit()

    def _row_to_repository(self, row: aiosqlite.Row) -> "Repository":
        """Convert database row to Repository model."""
        return Repository(
            id=row["id"],
            name=row["name"],
            status=RepositoryStatus(row["status"]),
            last_indexed_commit=row["last_indexed_commit"],
            last_indexed_at=(
                datetime.fromisoformat(row["last_indexed_at"]) if row["last_indexed_at"] else None
            ),
            file_count=row["file_count"],
            entity_count=row["entity_count"],
            relation_count=row["relation_count"],
            error_message=row["error_message"],
        )

    # =========================================================================
    # IndexedFile Operations
    # =========================================================================

    async def upsert_file(self, file: "IndexedFile") -> str:
        """
        Insert or update an indexed file record.

        Args:
            file: IndexedFile model instance.

        Returns:
            File ID (UUID string) - the actual ID in the database.
            On conflict, returns the existing row's ID, not the caller's ID.
        """
        file_id = str(file.id)
        repo_id = str(file.repository_id)

        await self.execute(
            """
            INSERT INTO indexed_files (
                id, repository_id, path, checksum, file_size, language,
                status, failure_count, error_message, entity_count,
                last_modified_at, last_indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repository_id, path) DO UPDATE SET
                checksum = excluded.checksum,
                file_size = excluded.file_size,
                language = excluded.language,
                last_modified_at = excluded.last_modified_at,
                updated_at = datetime('now')
            """,
            [
                file_id,
                repo_id,
                file.path,
                file.checksum,
                file.file_size,
                file.language,
                file.status.value if hasattr(file.status, "value") else file.status,
                file.failure_count,
                file.error_message,
                file.entity_count,
                file.last_modified_at.isoformat(),
                file.last_indexed_at.isoformat() if file.last_indexed_at else None,
            ],
        )
        conn = self._get_conn()
        await conn.commit()

        # Query the actual ID from the database (handles conflict case)
        row = await self.fetchone(
            "SELECT id FROM indexed_files WHERE repository_id = ? AND path = ?",
            [repo_id, file.path],
        )
        return row["id"] if row else file_id

    async def get_file(self, file_id: str) -> "IndexedFile | None":
        """Get file by ID."""
        row = await self.fetchone("SELECT * FROM indexed_files WHERE id = ?", [file_id])
        if row is None:
            return None
        return self._row_to_indexed_file(row)

    async def get_file_by_path(self, repo_id: str, path: str) -> "IndexedFile | None":
        """Get file by repository and path."""
        row = await self.fetchone(
            "SELECT * FROM indexed_files WHERE repository_id = ? AND path = ?",
            [repo_id, path],
        )
        if row is None:
            return None
        return self._row_to_indexed_file(row)

    async def list_files_by_repository(self, repo_id: str) -> list[IndexedFile]:
        """List all indexed files in a repository.

        Args:
            repo_id: Repository ID

        Returns:
            List of IndexedFile objects ordered by path
        """
        conn = self._get_conn()
        cursor = await conn.execute(
            "SELECT * FROM indexed_files WHERE repository_id = ? ORDER BY path",
            [repo_id],
        )
        rows = await cursor.fetchall()
        return [self._row_to_indexed_file(row) for row in rows]

    async def mark_repository_files_pending(
        self, repo_id: str, *, reset_failures: bool = False
    ) -> int:
        """Mark all files in a repository as pending reindex.

        Args:
            repo_id: Repository ID
            reset_failures: If True, reset failure_count and error_message

        Returns:
            Number of files marked pending
        """
        conn = self._get_conn()

        if reset_failures:
            await conn.execute(
                """
                UPDATE indexed_files
                SET status = ?,
                    failure_count = 0,
                    error_message = NULL
                WHERE repository_id = ?
                """,
                [FileStatus.PENDING.value, repo_id],
            )
        else:
            await conn.execute(
                """
                UPDATE indexed_files
                SET status = ?
                WHERE repository_id = ?
                """,
                [FileStatus.PENDING.value, repo_id],
            )

        await conn.commit()

        # Return count of affected rows
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM indexed_files WHERE repository_id = ? AND status = ?",
            [repo_id, FileStatus.PENDING.value],
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def enqueue_pending_files(self, repo_id: str) -> int:
        """Enqueue all pending files in a repository.

        Args:
            repo_id: Repository ID

        Returns:
            Number of files enqueued
        """
        conn = self._get_conn()

        # Get all pending file IDs
        cursor = await conn.execute(
            """
            SELECT id FROM indexed_files
            WHERE repository_id = ? AND status = ?
            """,
            [repo_id, FileStatus.PENDING.value],
        )
        rows = await cursor.fetchall()

        # Enqueue each file
        count = 0
        for row in rows:
            file_id = row[0]
            await conn.execute(
                "INSERT OR IGNORE INTO indexing_queue "
                "(file_id, repository_id, priority) VALUES (?, ?, ?)",
                [file_id, repo_id, 0],
            )
            count += 1

        await conn.commit()
        return count

    async def update_file_status(self, file_id: str, status: "FileStatus") -> None:
        """Update file status."""
        status_value = status.value if hasattr(status, "value") else status
        await self.execute(
            """
            UPDATE indexed_files
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            [status_value, file_id],
        )
        conn = self._get_conn()
        await conn.commit()

    async def update_file_indexed(self, file_id: str, entity_count: int) -> None:
        """Mark file as indexed with entity count."""
        await self.execute(
            """
            UPDATE indexed_files
            SET status = 'indexed',
                entity_count = ?,
                last_indexed_at = datetime('now'),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            [entity_count, file_id],
        )
        conn = self._get_conn()
        await conn.commit()

    async def update_file_failure(
        self,
        file_id: str,
        status: "FileStatus",
        failure_count: int,
        error_message: str | None,
    ) -> None:
        """Update file with failure information."""
        status_value = status.value if hasattr(status, "value") else status
        await self.execute(
            """
            UPDATE indexed_files
            SET status = ?,
                failure_count = ?,
                error_message = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            [status_value, failure_count, error_message, file_id],
        )
        conn = self._get_conn()
        await conn.commit()

    def _row_to_indexed_file(self, row: aiosqlite.Row) -> "IndexedFile":
        """Convert database row to IndexedFile model."""
        return IndexedFile(
            id=row["id"],
            repository_id=row["repository_id"],
            path=row["path"],
            checksum=row["checksum"],
            file_size=row["file_size"],
            language=row["language"],
            status=FileStatus(row["status"]),
            failure_count=row["failure_count"],
            error_message=row["error_message"],
            entity_count=row["entity_count"],
            last_modified_at=datetime.fromisoformat(row["last_modified_at"]),
            last_indexed_at=(
                datetime.fromisoformat(row["last_indexed_at"]) if row["last_indexed_at"] else None
            ),
        )

    # =========================================================================
    # Queue Operations
    # =========================================================================

    async def enqueue_file(self, file_id: str, repo_id: str, priority: int = 0) -> None:
        """
        Add file to indexing queue.

        Uses INSERT OR IGNORE for idempotency.
        """
        await self.execute(
            """
            INSERT OR IGNORE INTO indexing_queue (file_id, repository_id, priority)
            VALUES (?, ?, ?)
            """,
            [file_id, repo_id, priority],
        )
        conn = self._get_conn()
        await conn.commit()

    async def dequeue_next_file(self) -> "IndexedFile | None":
        """
        Get and remove the next file from the queue (FIFO with priority).

        The DELETE...RETURNING statement is atomic within SQLite, so no
        explicit BEGIN is needed.  Avoiding an explicit transaction prevents
        conflicts with auto-transactions from concurrent coroutines that
        share this connection.

        Returns:
            IndexedFile if queue has items, None otherwise.
        """
        conn = self._get_conn()

        # Atomic delete with RETURNING to get the file_id in one operation
        cursor = await conn.execute(
            """
            DELETE FROM indexing_queue
            WHERE id = (
                SELECT id FROM indexing_queue
                ORDER BY priority DESC, id ASC
                LIMIT 1
            )
            RETURNING file_id
            """
        )
        queue_row = await cursor.fetchone()

        if queue_row is None:
            return None

        file_id = queue_row["file_id"]

        # Fetch the full file record
        cursor = await conn.execute("SELECT * FROM indexed_files WHERE id = ?", [file_id])
        row = await cursor.fetchone()

        await conn.commit()

        if row is None:
            return None

        return self._row_to_indexed_file(row)

    async def count_pending_files(self, repo_id: str) -> int:
        """Count files with pending status for a repository."""
        row = await self.fetchone(
            "SELECT COUNT(*) as cnt FROM indexed_files"
            " WHERE repository_id = ? AND status = 'pending'",
            [repo_id],
        )
        return row["cnt"] if row else 0

    async def get_retryable_failed_files(self) -> list["IndexedFile"]:
        """Get all files with 'failed' status (eligible for retry)."""
        rows = await self.fetchall("SELECT * FROM indexed_files WHERE status = 'failed'")
        return [self._row_to_indexed_file(row) for row in rows]

    async def count_failed_files(self, repo_id: str) -> int:
        """Count files with failed or permanent_failure status for a repository."""
        row = await self.fetchone(
            "SELECT COUNT(*) as cnt FROM indexed_files"
            " WHERE repository_id = ? AND status IN ('failed', 'permanent_failure')",
            [repo_id],
        )
        return row["cnt"] if row else 0

    async def count_indexed_files(self, repo_id: str) -> int:
        """Count files with indexed status for a repository."""
        row = await self.fetchone(
            "SELECT COUNT(*) as cnt FROM indexed_files"
            " WHERE repository_id = ? AND status = 'indexed'",
            [repo_id],
        )
        return row["cnt"] if row else 0

    async def get_queue_length(self) -> int:
        """Get number of files in queue."""
        row = await self.fetchone("SELECT COUNT(*) as cnt FROM indexing_queue")
        return row["cnt"] if row else 0

    # =========================================================================
    # Crash Recovery
    # =========================================================================

    async def recover_from_crash(self) -> int:
        """
        Reset interrupted operations after crash.

        Called during startup to ensure consistent state.

        Actions:
        1. Reset PROCESSING files to PENDING
        2. Re-queue PENDING files not already in queue

        Returns:
            Number of files recovered (reset from PROCESSING).
        """
        # Reset files stuck in PROCESSING
        cursor = await self.execute(
            """
            UPDATE indexed_files
            SET status = 'pending'
            WHERE status = 'processing'
            """
        )
        recovered_count = cursor.rowcount

        # Re-queue PENDING files not in queue
        await self.execute(
            """
            INSERT OR IGNORE INTO indexing_queue (file_id, repository_id)
            SELECT id, repository_id FROM indexed_files
            WHERE status = 'pending'
            AND id NOT IN (SELECT file_id FROM indexing_queue)
            """
        )

        # Reset repositories stuck in INDEXING
        await self.execute(
            """
            UPDATE repositories
            SET status = 'pending'
            WHERE status = 'indexing'
            """
        )

        conn = self._get_conn()
        await conn.commit()
        return recovered_count
