"""Tests for StateDB class."""

from pathlib import Path

import aiosqlite
import pytest

from mrcis.storage.state_db import StateDB


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "state.db"


class TestStateDBInitialization:
    """Tests for StateDB initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, db_path: Path) -> None:
        """Test initialize creates database file."""
        db = StateDB(db_path)
        await db.initialize()

        assert db_path.exists()
        await db.close()

    @pytest.mark.asyncio
    async def test_initialize_applies_migrations(self, db_path: Path) -> None:
        """Test initialize applies schema migrations."""
        db = StateDB(db_path)
        await db.initialize()

        # Verify tables exist
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cursor.fetchall()]

        assert "repositories" in tables
        assert "indexed_files" in tables
        assert "entities" in tables
        await db.close()

    @pytest.mark.asyncio
    async def test_close_closes_connection(self, db_path: Path) -> None:
        """Test close properly closes connection."""
        db = StateDB(db_path)
        await db.initialize()
        await db.close()

        # Should not raise
        assert True


class TestStateDBTransactions:
    """Tests for StateDB transaction handling."""

    @pytest.mark.asyncio
    async def test_transaction_commits_on_success(self, db_path: Path) -> None:
        """Test transaction commits when no error."""
        db = StateDB(db_path)
        await db.initialize()

        async with db.transaction():
            await db.execute(
                "INSERT INTO repositories (id, name) VALUES (?, ?)",
                ["test-id", "test-repo"],
            )

        # Should be committed
        row = await db.fetchone("SELECT name FROM repositories WHERE id = ?", ["test-id"])
        assert row is not None
        assert row["name"] == "test-repo"
        await db.close()

    @pytest.mark.asyncio
    async def test_transaction_rollbacks_on_error(self, db_path: Path) -> None:
        """Test transaction rollbacks when error occurs."""
        db = StateDB(db_path)
        await db.initialize()

        try:
            async with db.transaction():
                await db.execute(
                    "INSERT INTO repositories (id, name) VALUES (?, ?)",
                    ["test-id", "test-repo"],
                )
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Should be rolled back
        row = await db.fetchone("SELECT name FROM repositories WHERE id = ?", ["test-id"])
        assert row is None
        await db.close()
