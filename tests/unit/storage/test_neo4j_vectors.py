"""Unit tests for Neo4jVectorStore."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mrcis.config.models import Neo4jConfig
from mrcis.storage.neo4j_vectors import Neo4jVectorStore


@pytest.fixture
def neo4j_config() -> Neo4jConfig:
    return Neo4jConfig(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="testpass",
        vector_dimensions=64,
    )


@pytest.fixture
def mock_driver() -> MagicMock:
    driver = MagicMock()
    session = AsyncMock()
    # session() is sync in real neo4j driver, returns an async context manager
    driver.session.return_value = session
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return driver


@pytest.fixture
def store(neo4j_config: Neo4jConfig, mock_driver: MagicMock) -> Neo4jVectorStore:
    s = Neo4jVectorStore(neo4j_config)
    s._driver = mock_driver
    return s


class TestNeo4jVectorStoreModel:
    """Test the model property."""

    def test_model_returns_class(self, store: Neo4jVectorStore) -> None:
        model = store.model
        assert model is not None

    def test_model_can_instantiate(self, store: Neo4jVectorStore) -> None:
        model = store.model
        instance = model(
            id="v1",
            repository_id="r1",
            file_id="f1",
            qualified_name="mod.func",
            simple_name="func",
            entity_type="function",
            language="python",
            file_path="mod.py",
            line_start=1,
            line_end=5,
            vector=[0.1, 0.2, 0.3, 0.4],
            embedding_text="function: mod.func",
        )
        assert instance.id == "v1"


class TestNeo4jVectorStoreUpsert:
    """Tests for upsert_vectors."""

    async def test_upsert_empty_returns_zero(self, store: Neo4jVectorStore) -> None:
        count = await store.upsert_vectors([])
        assert count == 0

    async def test_upsert_returns_count(self, store: Neo4jVectorStore) -> None:
        model = store.model
        vectors = [
            model(
                id="v1",
                repository_id="r1",
                file_id="f1",
                qualified_name="mod.func",
                simple_name="func",
                entity_type="function",
                language="python",
                file_path="mod.py",
                line_start=1,
                line_end=5,
                vector=[0.1, 0.2, 0.3, 0.4],
                embedding_text="function: mod.func",
            )
        ]
        count = await store.upsert_vectors(vectors)
        assert count == 1


class TestNeo4jVectorStoreDelete:
    """Tests for delete operations."""

    async def test_delete_by_file(self, store: Neo4jVectorStore, mock_driver: MagicMock) -> None:
        session = mock_driver.session.return_value
        result = AsyncMock()
        result.single = AsyncMock(return_value={"updated": 3})
        session.run = AsyncMock(return_value=result)

        count = await store.delete_by_file("file-1")
        assert isinstance(count, int)

    async def test_delete_by_repository(
        self, store: Neo4jVectorStore, mock_driver: MagicMock
    ) -> None:
        session = mock_driver.session.return_value
        result = AsyncMock()
        result.single = AsyncMock(return_value={"updated": 5})
        session.run = AsyncMock(return_value=result)

        count = await store.delete_by_repository("repo-1")
        assert isinstance(count, int)
