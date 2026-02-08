"""Tests for VectorStore class."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.storage.vector_store import CodeVector, VectorStore


@pytest.fixture
def vector_path(tmp_path: Path) -> Path:
    """Provide path for vector database."""
    return tmp_path / "vectors"


class TestVectorStoreInitialization:
    """Tests for VectorStore initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_table(self, vector_path: Path) -> None:
        """Test initialize creates the vectors table."""

        store = VectorStore(
            db_path=str(vector_path),
            table_name="test_vectors",
            dimensions=1024,
        )
        await store.initialize()

        # Table should exist
        tables_response = store._db.list_tables()
        existing_tables = (
            tables_response.tables if hasattr(tables_response, "tables") else tables_response
        )
        assert "test_vectors" in existing_tables

    @pytest.mark.asyncio
    async def test_initialize_opens_existing_table(self, vector_path: Path) -> None:
        """Test initialize opens existing table."""

        # Create first time
        store1 = VectorStore(
            db_path=str(vector_path),
            table_name="test_vectors",
            dimensions=1024,
        )
        await store1.initialize()

        # Open second time
        store2 = VectorStore(
            db_path=str(vector_path),
            table_name="test_vectors",
            dimensions=1024,
        )
        await store2.initialize()

        assert store2._table is not None


class TestVectorStoreOperations:
    """Tests for VectorStore CRUD operations."""

    @pytest.fixture
    async def store(self, vector_path: Path):
        """Provide initialized VectorStore."""

        store = VectorStore(
            db_path=str(vector_path),
            table_name="code_vectors",
            dimensions=4,  # Small for testing
        )
        await store.initialize()
        yield store

    @pytest.mark.asyncio
    async def test_upsert_vectors(self, store) -> None:
        """Test upserting vectors."""

        vectors = [
            CodeVector(
                id=str(uuid4()),
                repository_id=str(uuid4()),
                file_id=str(uuid4()),
                qualified_name="module.func",
                simple_name="func",
                entity_type="function",
                language="python",
                file_path="src/module.py",
                line_start=1,
                line_end=10,
                vector=[0.1, 0.2, 0.3, 0.4],
                embedding_text="test function",
            )
        ]

        count = await store.upsert_vectors(vectors)
        assert count == 1

    @pytest.mark.asyncio
    async def test_search_returns_similar(self, store) -> None:
        """Test search returns similar vectors."""

        repo_id = str(uuid4())
        file_id = str(uuid4())

        # Insert vectors
        vectors = [
            CodeVector(
                id=str(uuid4()),
                repository_id=repo_id,
                file_id=file_id,
                qualified_name="module.func1",
                simple_name="func1",
                entity_type="function",
                language="python",
                file_path="src/module.py",
                line_start=1,
                line_end=10,
                vector=[0.9, 0.1, 0.0, 0.0],
                embedding_text="function one",
            ),
            CodeVector(
                id=str(uuid4()),
                repository_id=repo_id,
                file_id=file_id,
                qualified_name="module.func2",
                simple_name="func2",
                entity_type="function",
                language="python",
                file_path="src/module.py",
                line_start=11,
                line_end=20,
                vector=[0.0, 0.0, 0.9, 0.1],
                embedding_text="function two",
            ),
        ]
        await store.upsert_vectors(vectors)

        # Search for similar to first vector
        results = await store.search(
            query_vector=[0.8, 0.2, 0.0, 0.0],
            limit=1,
        )

        assert len(results) == 1
        assert results[0]["qualified_name"] == "module.func1"

    @pytest.mark.asyncio
    async def test_delete_by_file(self, store) -> None:
        """Test deleting vectors by file."""

        repo_id = str(uuid4())
        file_id = str(uuid4())

        vectors = [
            CodeVector(
                id=str(uuid4()),
                repository_id=repo_id,
                file_id=file_id,
                qualified_name="module.func",
                simple_name="func",
                entity_type="function",
                language="python",
                file_path="src/module.py",
                line_start=1,
                line_end=10,
                vector=[0.1, 0.2, 0.3, 0.4],
                embedding_text="test",
            )
        ]
        await store.upsert_vectors(vectors)

        # Delete
        await store.delete_by_file(file_id)

        # Search should return nothing
        results = await store.search([0.1, 0.2, 0.3, 0.4], limit=10)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_upsert_does_not_wipe_table(self, store) -> None:
        """Test that upserting new vectors does not remove existing ones."""
        repo_id = str(uuid4())
        file_id = str(uuid4())

        # Insert first vector
        vector1 = CodeVector(
            id="vector-1",
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="module.func1",
            simple_name="func1",
            entity_type="function",
            language="python",
            file_path="src/module.py",
            line_start=1,
            line_end=10,
            vector=[0.9, 0.1, 0.0, 0.0],
            embedding_text="function one",
        )
        await store.upsert_vectors([vector1])

        # Insert second vector (different ID)
        vector2 = CodeVector(
            id="vector-2",
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="module.func2",
            simple_name="func2",
            entity_type="function",
            language="python",
            file_path="src/module.py",
            line_start=11,
            line_end=20,
            vector=[0.0, 0.0, 0.9, 0.1],
            embedding_text="function two",
        )
        await store.upsert_vectors([vector2])

        # Both vectors should exist
        results = await store.search([0.5, 0.5, 0.5, 0.5], limit=10)
        assert len(results) == 2
        qualified_names = {r["qualified_name"] for r in results}
        assert qualified_names == {"module.func1", "module.func2"}

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_vector(self, store) -> None:
        """Test that upserting with same ID updates the vector."""
        repo_id = str(uuid4())
        file_id = str(uuid4())
        vector_id = "same-id"

        # Insert initial vector
        vector1 = CodeVector(
            id=vector_id,
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="module.old_func",
            simple_name="old_func",
            entity_type="function",
            language="python",
            file_path="src/module.py",
            line_start=1,
            line_end=10,
            vector=[0.9, 0.1, 0.0, 0.0],
            embedding_text="old function",
        )
        await store.upsert_vectors([vector1])

        # Upsert with same ID but different name
        vector2 = CodeVector(
            id=vector_id,
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="module.new_func",
            simple_name="new_func",
            entity_type="function",
            language="python",
            file_path="src/module.py",
            line_start=1,
            line_end=10,
            vector=[0.9, 0.1, 0.0, 0.0],
            embedding_text="new function",
        )
        await store.upsert_vectors([vector2])

        # Should have only one vector with updated name
        results = await store.search([0.9, 0.1, 0.0, 0.0], limit=10)
        assert len(results) == 1
        assert results[0]["qualified_name"] == "module.new_func"
