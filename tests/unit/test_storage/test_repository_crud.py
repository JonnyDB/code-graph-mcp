"""Tests for Repository CRUD operations in StateDB."""

from pathlib import Path

import pytest

from mrcis.storage.state_db import StateDB


@pytest.fixture
async def db(tmp_path: Path):
    """Provide initialized StateDB."""

    db_path = tmp_path / "state.db"
    state_db = StateDB(db_path)
    await state_db.initialize()
    yield state_db
    await state_db.close()


class TestRepositoryCRUD:
    """Tests for repository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_repository(self, db) -> None:
        """Test creating a repository."""
        repo_id = await db.create_repository(name="my-repo")

        assert repo_id is not None
        repo = await db.get_repository(repo_id)
        assert repo is not None
        assert repo.name == "my-repo"
        assert repo.status == "pending"

    @pytest.mark.asyncio
    async def test_create_repository_with_status(self, db) -> None:
        """Test creating a repository with custom status."""
        repo_id = await db.create_repository(name="my-repo", status="watching")

        repo = await db.get_repository(repo_id)
        assert repo.status == "watching"

    @pytest.mark.asyncio
    async def test_get_repository_by_name(self, db) -> None:
        """Test getting repository by name."""
        await db.create_repository(name="my-repo")

        repo = await db.get_repository_by_name("my-repo")
        assert repo is not None
        assert repo.name == "my-repo"

    @pytest.mark.asyncio
    async def test_get_repository_by_name_not_found(self, db) -> None:
        """Test getting non-existent repository returns None."""
        repo = await db.get_repository_by_name("nonexistent")
        assert repo is None

    @pytest.mark.asyncio
    async def test_get_all_repositories(self, db) -> None:
        """Test getting all repositories."""
        await db.create_repository(name="repo-1")
        await db.create_repository(name="repo-2")
        await db.create_repository(name="repo-3")

        repos = await db.get_all_repositories()
        assert len(repos) == 3
        names = [r.name for r in repos]
        assert "repo-1" in names
        assert "repo-2" in names
        assert "repo-3" in names

    @pytest.mark.asyncio
    async def test_update_repository_status(self, db) -> None:
        """Test updating repository status."""
        repo_id = await db.create_repository(name="my-repo")

        await db.update_repository_status(repo_id, "indexing")

        repo = await db.get_repository(repo_id)
        assert repo.status == "indexing"

    @pytest.mark.asyncio
    async def test_update_repository_stats(self, db) -> None:
        """Test updating repository statistics."""
        repo_id = await db.create_repository(name="my-repo")

        await db.update_repository_stats(
            repo_id, file_count=100, entity_count=500, relation_count=200
        )

        repo = await db.get_repository(repo_id)
        assert repo.file_count == 100
        assert repo.entity_count == 500
        assert repo.relation_count == 200

    @pytest.mark.asyncio
    async def test_delete_repository(self, db) -> None:
        """Test deleting a repository."""
        repo_id = await db.create_repository(name="my-repo")

        await db.delete_repository(repo_id)

        repo = await db.get_repository(repo_id)
        assert repo is None
