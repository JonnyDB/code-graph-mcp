"""Integration smoke tests for Neo4j storage backend.

These tests require a running Neo4j instance.
Run with: uv run pytest tests/integration/test_neo4j_backend.py -v

Skip with: uv run pytest tests/ -m "not integration"
"""

import asyncio
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from mrcis.config.models import Neo4jConfig
from mrcis.models.entities import EntityType
from mrcis.storage.neo4j_graph import Neo4jRelationGraph
from mrcis.storage.neo4j_vectors import Neo4jVectorStore


def _neo4j_available() -> bool:
    """Check if Neo4j is reachable."""

    async def _check() -> bool:
        driver = AsyncGraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "mrcis1234!"),
        )
        try:
            result = await driver.execute_query("RETURN 1 AS ok")
            return len(result.records) == 1
        except Exception:
            return False
        finally:
            await driver.close()

    try:
        return asyncio.get_event_loop().run_until_complete(_check())
    except Exception:
        return False


# Skip all tests if Neo4j is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _neo4j_available(), reason="Neo4j not available at bolt://localhost:7687"
    ),
]


@pytest.fixture
def neo4j_config() -> Neo4jConfig:
    """Create Neo4j config for testing."""
    return Neo4jConfig(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="mrcis1234!",
        database="neo4j",
        vector_dimensions=1024,
        vector_index_name="test_code_vectors",
    )


@pytest.fixture
async def neo4j_graph(neo4j_config):
    """Create and initialize Neo4jRelationGraph, clean up after test."""
    graph = Neo4jRelationGraph(neo4j_config)
    await graph.initialize()

    yield graph

    # Cleanup: delete all test data and drop test vector index
    async with graph._driver.session(database=neo4j_config.database) as session:
        await session.run("MATCH (n) DETACH DELETE n")
        await session.run(f"DROP INDEX {neo4j_config.vector_index_name} IF EXISTS")

    await graph.close()


@pytest.fixture
async def neo4j_vectors(neo4j_config):
    """Create and initialize Neo4jVectorStore, clean up after test."""
    store = Neo4jVectorStore(neo4j_config)
    await store.initialize()

    yield store

    # Cleanup: delete all test data
    async with store._driver.session(database=neo4j_config.database) as session:
        await session.run("MATCH (n) DETACH DELETE n")

    await store.close()


@pytest.mark.integration
class TestNeo4jRelationGraphSmoke:
    """Smoke tests for Neo4jRelationGraph against live Neo4j."""

    async def test_add_and_get_entity(self, neo4j_graph):
        """Round-trip: add entity then retrieve by qualified name."""
        repo_id = str(uuid4())
        file_id = str(uuid4())

        entity_id = await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="mymodule.MyClass",
            simple_name="MyClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=20,
            signature="class MyClass:",
            docstring="A test class.",
            visibility="public",
        )

        assert entity_id is not None

        entity = await neo4j_graph.get_entity_by_qualified_name("mymodule.MyClass")
        assert entity is not None
        assert entity.simple_name == "MyClass"
        assert entity.entity_type == EntityType.CLASS
        assert entity.language == "python"
        assert entity.signature == "class MyClass:"

    async def test_add_and_get_relation(self, neo4j_graph):
        """Round-trip: add two entities with a relation."""
        repo_id = str(uuid4())
        file_id = str(uuid4())

        source_id = await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="mymodule.caller",
            simple_name="caller",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=1,
            line_end=5,
        )

        target_id = await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="mymodule.callee",
            simple_name="callee",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=10,
            line_end=15,
        )

        rel_id = await neo4j_graph.add_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type="calls",
            line_number=3,
            context_snippet="callee()",
        )
        assert rel_id is not None

        outgoing = await neo4j_graph.get_outgoing_relations(source_id)
        assert len(outgoing) == 1
        assert outgoing[0].relation_type == "calls"
        assert outgoing[0].target_id == target_id

        incoming = await neo4j_graph.get_incoming_relations(target_id)
        assert len(incoming) == 1
        assert incoming[0].source_id == source_id

    async def test_suffix_search(self, neo4j_graph):
        """Suffix search should find entities by name ending."""
        repo_id = str(uuid4())
        file_id = str(uuid4())

        await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="pkg.mod.UserService",
            simple_name="UserService",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=50,
        )

        results = await neo4j_graph.get_entities_by_suffix("UserService")
        assert len(results) == 1
        assert results[0].qualified_name == "pkg.mod.UserService"

    async def test_pending_reference_lifecycle(self, neo4j_graph):
        """Add, retrieve, and resolve a pending reference."""
        repo_id = str(uuid4())
        file_id = str(uuid4())

        # Create source entity
        source_id = await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="mymodule.importer",
            simple_name="importer",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=1,
            line_end=5,
        )

        # Create target entity
        target_id = await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="other.target_func",
            simple_name="target_func",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=1,
            line_end=5,
        )

        # Add pending reference
        ref_id = await neo4j_graph.add_pending_reference(
            source_entity_id=source_id,
            source_qualified_name="mymodule.importer",
            source_repository_id=repo_id,
            target_qualified_name="other.target_func",
            relation_type="calls",
            line_number=3,
        )
        assert ref_id is not None

        # Get pending
        pending = await neo4j_graph.get_pending_references()
        assert len(pending) >= 1
        ref_ids = [str(p.id) for p in pending]
        assert ref_id in ref_ids

        # Resolve it
        await neo4j_graph.resolve_reference(ref_id, target_id)

        # Should no longer be pending
        pending_after = await neo4j_graph.get_pending_references()
        remaining_ids = [str(p.id) for p in pending_after]
        assert ref_id not in remaining_ids

    async def test_delete_entities_for_file(self, neo4j_graph):
        """Delete entities for a file should remove them."""
        repo_id = str(uuid4())
        file_id = str(uuid4())

        await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="to_delete.Foo",
            simple_name="Foo",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        count = await neo4j_graph.delete_entities_for_file(file_id)
        assert count == 1

        entity = await neo4j_graph.get_entity_by_qualified_name("to_delete.Foo")
        assert entity is None


@pytest.mark.integration
class TestNeo4jVectorStoreSmoke:
    """Smoke tests for Neo4jVectorStore against live Neo4j."""

    async def test_upsert_and_search(self, neo4j_vectors, neo4j_graph):
        """Round-trip: upsert a vector then search for it."""
        repo_id = str(uuid4())
        file_id = str(uuid4())

        # Create entity node first (vectors attach to entity nodes)
        # Use same ID for both entity and vector
        entity_id = str(uuid4())
        await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="vec_test.search_func",
            simple_name="search_func",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=1,
            line_end=5,
            entity_id=entity_id,
            vector_id=entity_id,  # Set vector_id so upsert can find it
        )

        # Create vector
        from mrcis.storage.neo4j_vectors import Neo4jCodeVector

        vec = Neo4jCodeVector(
            id=entity_id,
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="vec_test.search_func",
            simple_name="search_func",
            entity_type="function",
            language="python",
            file_path="vec_test.py",
            line_start=1,
            line_end=5,
            embedding_text="search function that finds things",
            vector=[0.1] * 1024,
        )

        count = await neo4j_vectors.upsert_vectors([vec])
        assert count == 1

        # Search with same vector
        results = await neo4j_vectors.search(
            query_vector=[0.1] * 1024,
            limit=5,
        )
        assert len(results) >= 1
        assert any(r["entity_id"] == entity_id for r in results)

    async def test_delete_by_file(self, neo4j_vectors, neo4j_graph):
        """Delete vectors by file_id should clear embeddings."""
        repo_id = str(uuid4())
        file_id = str(uuid4())

        # Use same ID for both entity and vector
        entity_id = str(uuid4())
        await neo4j_graph.add_entity(
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="vec_del.func",
            simple_name="func",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=1,
            line_end=5,
            entity_id=entity_id,
            vector_id=entity_id,  # Set vector_id so upsert can find it
        )

        from mrcis.storage.neo4j_vectors import Neo4jCodeVector

        vec = Neo4jCodeVector(
            id=entity_id,
            repository_id=repo_id,
            file_id=file_id,
            qualified_name="vec_del.func",
            simple_name="func",
            entity_type="function",
            language="python",
            file_path="vec_del.py",
            line_start=1,
            line_end=5,
            embedding_text="function to delete",
            vector=[0.2] * 1024,
        )
        await neo4j_vectors.upsert_vectors([vec])

        deleted = await neo4j_vectors.delete_by_file(file_id)
        assert deleted >= 1
