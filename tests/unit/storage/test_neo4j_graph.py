"""Unit tests for Neo4jRelationGraph.

These tests mock the Neo4j driver to test the adapter logic
without requiring a running Neo4j instance.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mrcis.config.models import Neo4jConfig
from mrcis.models.entities import EntityType
from mrcis.storage.neo4j_graph import Neo4jRelationGraph


@pytest.fixture
def neo4j_config() -> Neo4jConfig:
    return Neo4jConfig(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="testpass",
    )


@pytest.fixture
def mock_driver() -> MagicMock:
    """Create a mock Neo4j async driver.

    The real Neo4j driver's .session() is a synchronous method that returns
    an AsyncSession (async context manager). We use MagicMock for the driver
    so .session() is sync, and AsyncMock for the session so it supports
    async context manager and async .run() calls.
    """
    driver = MagicMock()
    session = AsyncMock()
    driver.session.return_value = session
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return driver


@pytest.fixture
def graph(neo4j_config: Neo4jConfig, mock_driver: MagicMock) -> Neo4jRelationGraph:
    """Create a Neo4jRelationGraph with mocked driver."""
    g = Neo4jRelationGraph(neo4j_config)
    g._driver = mock_driver
    return g


class TestNeo4jRelationGraphAddEntity:
    """Tests for add_entity."""

    async def test_add_entity_returns_id(self, graph: Neo4jRelationGraph) -> None:
        entity_id = await graph.add_entity(
            repository_id="repo-1",
            file_id="file-1",
            qualified_name="module.MyClass",
            simple_name="MyClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=10,
            line_end=50,
        )
        assert isinstance(entity_id, str)
        assert len(entity_id) > 0

    async def test_add_entity_with_explicit_id(self, graph: Neo4jRelationGraph) -> None:
        entity_id = await graph.add_entity(
            repository_id="repo-1",
            file_id="file-1",
            qualified_name="module.func",
            simple_name="func",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=1,
            line_end=5,
            entity_id="custom-id-123",
        )
        assert entity_id == "custom-id-123"

    async def test_add_entity_with_vector_id(self, graph: Neo4jRelationGraph) -> None:
        entity_id = await graph.add_entity(
            repository_id="repo-1",
            file_id="file-1",
            qualified_name="module.func",
            simple_name="func",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=1,
            line_end=5,
            vector_id="vec-456",
        )
        assert isinstance(entity_id, str)


class TestNeo4jRelationGraphGetEntity:
    """Tests for get_entity and lookups."""

    async def test_get_entity_returns_none_when_not_found(
        self, graph: Neo4jRelationGraph, mock_driver: MagicMock
    ) -> None:
        session = mock_driver.session.return_value
        result = AsyncMock()
        result.single = AsyncMock(return_value=None)
        session.run = AsyncMock(return_value=result)

        entity = await graph.get_entity("nonexistent-id")
        assert entity is None


class TestNeo4jRelationGraphAddRelation:
    """Tests for add_relation."""

    async def test_add_relation_returns_id(self, graph: Neo4jRelationGraph) -> None:
        source_entity = MagicMock()
        source_entity.id = "src-1"
        source_entity.qualified_name = "mod.Source"
        source_entity.entity_type = EntityType.CLASS
        source_entity.repository_id = "repo-1"

        target_entity = MagicMock()
        target_entity.id = "tgt-1"
        target_entity.qualified_name = "mod.Target"
        target_entity.entity_type = EntityType.CLASS
        target_entity.repository_id = "repo-1"

        graph.get_entity = AsyncMock(side_effect=[source_entity, target_entity])  # type: ignore[method-assign]

        relation_id = await graph.add_relation(
            source_id="src-1",
            target_id="tgt-1",
            relation_type="extends",
        )
        assert isinstance(relation_id, str)


class TestNeo4jRelationGraphPendingReferences:
    """Tests for pending reference operations."""

    async def test_add_pending_reference_returns_id(self, graph: Neo4jRelationGraph) -> None:
        ref_id = await graph.add_pending_reference(
            source_entity_id="ent-1",
            source_qualified_name="mod.Source",
            source_repository_id="repo-1",
            target_qualified_name="mod.Target",
            relation_type="calls",
        )
        assert isinstance(ref_id, str)
