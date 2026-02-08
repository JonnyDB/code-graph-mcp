"""Tests for database migrations."""

from pathlib import Path

import aiosqlite
import pytest

from mrcis.storage.migrations import v001_initial, v002_receiver_expr


@pytest.fixture
async def temp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "test.db"


class TestInitialMigration:
    """Tests for v001_initial migration."""

    @pytest.mark.asyncio
    async def test_migration_creates_repositories_table(self, temp_db_path: Path) -> None:
        """Test migration creates repositories table."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            # Check table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='repositories'"
            )
            result = await cursor.fetchone()
            assert result is not None

    @pytest.mark.asyncio
    async def test_migration_creates_indexed_files_table(self, temp_db_path: Path) -> None:
        """Test migration creates indexed_files table."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='indexed_files'"
            )
            result = await cursor.fetchone()
            assert result is not None

    @pytest.mark.asyncio
    async def test_migration_creates_entities_table(self, temp_db_path: Path) -> None:
        """Test migration creates entities table."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
            )
            result = await cursor.fetchone()
            assert result is not None

    @pytest.mark.asyncio
    async def test_migration_creates_relations_table(self, temp_db_path: Path) -> None:
        """Test migration creates relations table."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='relations'"
            )
            result = await cursor.fetchone()
            assert result is not None

    @pytest.mark.asyncio
    async def test_migration_creates_pending_references_table(self, temp_db_path: Path) -> None:
        """Test migration creates pending_references table."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pending_references'"
            )
            result = await cursor.fetchone()
            assert result is not None

    @pytest.mark.asyncio
    async def test_migration_creates_indexing_queue_table(self, temp_db_path: Path) -> None:
        """Test migration creates indexing_queue table."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='indexing_queue'"
            )
            result = await cursor.fetchone()
            assert result is not None

    @pytest.mark.asyncio
    async def test_migration_creates_schema_version_table(self, temp_db_path: Path) -> None:
        """Test migration creates schema_version table."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            cursor = await db.execute("SELECT version FROM schema_version")
            result = await cursor.fetchone()
            assert result is not None
            assert result[0] == 1

    @pytest.mark.asyncio
    async def test_migration_is_idempotent(self, temp_db_path: Path) -> None:
        """Test migration can be run multiple times safely."""
        async with aiosqlite.connect(temp_db_path) as db:
            # Run migration twice
            await v001_initial.apply_migration(db)
            await v001_initial.apply_migration(db)

            # Should still work
            cursor = await db.execute("SELECT version FROM schema_version")
            result = await cursor.fetchone()
            assert result[0] == 1

    @pytest.mark.asyncio
    async def test_migration_creates_fts_triggers(self, temp_db_path: Path) -> None:
        """Test migration creates FTS sync triggers for entities table."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            # Check that all three triggers exist
            cursor = await db.execute(
                """SELECT name FROM sqlite_master
                WHERE type='trigger' AND name LIKE 'entities_fts_%'
                ORDER BY name"""
            )
            triggers = [row[0] for row in await cursor.fetchall()]
            assert "entities_fts_delete" in triggers
            assert "entities_fts_insert" in triggers
            assert "entities_fts_update" in triggers

    @pytest.mark.asyncio
    async def test_fts_triggers_sync_on_insert(self, temp_db_path: Path) -> None:
        """Test FTS is updated when entity is inserted."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            # Create a test repository and file first (for foreign keys)
            await db.execute("INSERT INTO repositories (id, name) VALUES ('repo1', 'test-repo')")
            await db.execute(
                """INSERT INTO indexed_files
                (id, repository_id, path, checksum, file_size, last_modified_at)
                VALUES ('file1', 'repo1', 'test.py', 'abc123', 100, datetime('now'))"""
            )

            # Insert an entity
            await db.execute(
                """INSERT INTO entities
                (id, repository_id, file_id, qualified_name, simple_name,
                 entity_type, language, line_start, line_end, docstring)
                VALUES ('ent1', 'repo1', 'file1', 'module.MyClass', 'MyClass',
                        'class', 'python', 1, 10, 'A test class')"""
            )
            await db.commit()

            # Verify FTS was updated
            cursor = await db.execute(
                "SELECT qualified_name FROM entities_fts WHERE entities_fts MATCH 'MyClass'"
            )
            result = await cursor.fetchone()
            assert result is not None
            assert result[0] == "module.MyClass"

    @pytest.mark.asyncio
    async def test_fts_triggers_sync_on_update(self, temp_db_path: Path) -> None:
        """Test FTS is updated when entity is modified."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            # Create test data
            await db.execute("INSERT INTO repositories (id, name) VALUES ('repo1', 'test-repo')")
            await db.execute(
                """INSERT INTO indexed_files
                (id, repository_id, path, checksum, file_size, last_modified_at)
                VALUES ('file1', 'repo1', 'test.py', 'abc123', 100, datetime('now'))"""
            )
            await db.execute(
                """INSERT INTO entities
                (id, repository_id, file_id, qualified_name, simple_name,
                 entity_type, language, line_start, line_end, docstring)
                VALUES ('ent1', 'repo1', 'file1', 'module.OldName', 'OldName',
                        'class', 'python', 1, 10, 'Old docstring')"""
            )
            await db.commit()

            # Update the entity
            await db.execute(
                """UPDATE entities
                SET qualified_name = 'module.NewName', simple_name = 'NewName',
                    docstring = 'New docstring'
                WHERE id = 'ent1'"""
            )
            await db.commit()

            # Old name should not be found
            cursor = await db.execute(
                "SELECT * FROM entities_fts WHERE entities_fts MATCH 'OldName'"
            )
            old_result = await cursor.fetchone()
            assert old_result is None

            # New name should be found
            cursor = await db.execute(
                "SELECT qualified_name FROM entities_fts WHERE entities_fts MATCH 'NewName'"
            )
            new_result = await cursor.fetchone()
            assert new_result is not None
            assert new_result[0] == "module.NewName"

    @pytest.mark.asyncio
    async def test_fts_triggers_sync_on_delete(self, temp_db_path: Path) -> None:
        """Test FTS is updated when entity is deleted."""
        async with aiosqlite.connect(temp_db_path) as db:
            await v001_initial.apply_migration(db)

            # Create test data
            await db.execute("INSERT INTO repositories (id, name) VALUES ('repo1', 'test-repo')")
            await db.execute(
                """INSERT INTO indexed_files
                (id, repository_id, path, checksum, file_size, last_modified_at)
                VALUES ('file1', 'repo1', 'test.py', 'abc123', 100, datetime('now'))"""
            )
            await db.execute(
                """INSERT INTO entities
                (id, repository_id, file_id, qualified_name, simple_name,
                 entity_type, language, line_start, line_end, docstring)
                VALUES ('ent1', 'repo1', 'file1', 'module.DeleteMe', 'DeleteMe',
                        'class', 'python', 1, 10, 'To be deleted')"""
            )
            await db.commit()

            # Verify it exists in FTS first
            cursor = await db.execute(
                "SELECT * FROM entities_fts WHERE entities_fts MATCH 'DeleteMe'"
            )
            assert await cursor.fetchone() is not None

            # Delete the entity
            await db.execute("DELETE FROM entities WHERE id = 'ent1'")
            await db.commit()

            # Should not be in FTS anymore
            cursor = await db.execute(
                "SELECT * FROM entities_fts WHERE entities_fts MATCH 'DeleteMe'"
            )
            result = await cursor.fetchone()
            assert result is None


class TestReceiverExprMigration:
    """Tests for v002_receiver_expr migration."""

    @pytest.mark.asyncio
    async def test_migration_adds_receiver_expr_column(self, temp_db_path: Path) -> None:
        """Test v002 migration adds receiver_expr column to pending_references."""
        async with aiosqlite.connect(temp_db_path) as db:
            # Apply v001 first
            await v001_initial.apply_migration(db)

            # Apply v002
            await v002_receiver_expr.apply_migration(db)

            # Check column exists by querying table schema
            cursor = await db.execute("PRAGMA table_info(pending_references)")
            columns = {row[1]: row[2] for row in await cursor.fetchall()}

            assert "receiver_expr" in columns
            assert columns["receiver_expr"] == "TEXT"

    @pytest.mark.asyncio
    async def test_migration_updates_schema_version(self, temp_db_path: Path) -> None:
        """Test v002 migration updates schema version to 2."""
        async with aiosqlite.connect(temp_db_path) as db:
            # Apply v001 first
            await v001_initial.apply_migration(db)

            # Verify version is 1
            cursor = await db.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            result = await cursor.fetchone()
            assert result[0] == 1

            # Apply v002
            await v002_receiver_expr.apply_migration(db)

            # Verify version is now 2
            cursor = await db.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            result = await cursor.fetchone()
            assert result[0] == 2

    @pytest.mark.asyncio
    async def test_existing_pending_references_have_null_receiver_expr(
        self, temp_db_path: Path
    ) -> None:
        """Test that existing pending references get NULL receiver_expr after migration."""
        async with aiosqlite.connect(temp_db_path) as db:
            # Apply v001 first
            await v001_initial.apply_migration(db)

            # Create test data
            await db.execute("INSERT INTO repositories (id, name) VALUES ('repo1', 'test-repo')")
            await db.execute(
                """INSERT INTO indexed_files
                (id, repository_id, path, checksum, file_size, last_modified_at)
                VALUES ('file1', 'repo1', 'test.py', 'abc123', 100, datetime('now'))"""
            )
            await db.execute(
                """INSERT INTO entities
                (id, repository_id, file_id, qualified_name, simple_name,
                 entity_type, language, line_start, line_end)
                VALUES ('ent1', 'repo1', 'file1', 'module.MyClass', 'MyClass',
                        'class', 'python', 1, 10)"""
            )

            # Add a pending reference before migration
            await db.execute(
                """INSERT INTO pending_references
                (id, source_entity_id, source_qualified_name, source_repository_id,
                 target_qualified_name, relation_type)
                VALUES ('ref1', 'ent1', 'module.MyClass', 'repo1', 'other.Target', 'calls')"""
            )
            await db.commit()

            # Apply v002
            await v002_receiver_expr.apply_migration(db)

            # Check that receiver_expr is NULL for existing record
            cursor = await db.execute(
                "SELECT receiver_expr FROM pending_references WHERE id = 'ref1'"
            )
            result = await cursor.fetchone()
            assert result is not None
            assert result[0] is None  # receiver_expr should be NULL
