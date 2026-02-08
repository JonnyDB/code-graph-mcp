"""Tests for StorageBackendFactory."""

from unittest.mock import MagicMock

import pytest

from mrcis.config.models import Config, StorageConfig
from mrcis.storage.factory import StorageBackendFactory
from mrcis.storage.neo4j_graph import Neo4jRelationGraph
from mrcis.storage.neo4j_vectors import Neo4jVectorStore
from mrcis.storage.relation_graph import RelationGraph
from mrcis.storage.vector_store import VectorStore


class TestStorageBackendFactorySqliteLancedb:
    """Tests for sqlite_lancedb backend."""

    def test_default_backend_creates_sqlite_lancedb(self) -> None:
        config = Config()
        factory = StorageBackendFactory(config)
        assert factory.backend == "sqlite_lancedb"

    def test_create_relation_graph_returns_sqlite_graph(self) -> None:
        config = Config()
        factory = StorageBackendFactory(config)
        state_db = MagicMock()
        graph = factory.create_relation_graph(state_db)
        assert isinstance(graph, RelationGraph)

    def test_create_vector_store_returns_lancedb_store(self) -> None:
        config = Config()
        factory = StorageBackendFactory(config)
        store = factory.create_vector_store()
        assert isinstance(store, VectorStore)

    def test_create_relation_graph_requires_state_db(self) -> None:
        config = Config()
        factory = StorageBackendFactory(config)
        with pytest.raises(ValueError, match="state_db is required"):
            factory.create_relation_graph()


class TestStorageBackendFactoryNeo4j:
    """Tests for neo4j backend."""

    def test_neo4j_backend_detected(self) -> None:
        config = Config(storage=StorageConfig(backend="neo4j"))
        factory = StorageBackendFactory(config)
        assert factory.backend == "neo4j"

    def test_create_relation_graph_returns_neo4j_graph(self) -> None:
        config = Config(storage=StorageConfig(backend="neo4j"))
        factory = StorageBackendFactory(config)
        graph = factory.create_relation_graph()
        assert isinstance(graph, Neo4jRelationGraph)

    def test_create_vector_store_returns_neo4j_store(self) -> None:
        config = Config(storage=StorageConfig(backend="neo4j"))
        factory = StorageBackendFactory(config)
        store = factory.create_vector_store()
        assert isinstance(store, Neo4jVectorStore)

    def test_neo4j_shares_config(self) -> None:
        """Neo4j graph and vector store should share the same config."""
        config = Config(storage=StorageConfig(backend="neo4j"))
        factory = StorageBackendFactory(config)
        graph = factory.create_relation_graph()
        store = factory.create_vector_store()
        assert graph._config == store._config  # type: ignore[union-attr]

    def test_neo4j_ignores_state_db(self) -> None:
        """Neo4j backend should ignore the state_db parameter."""
        config = Config(storage=StorageConfig(backend="neo4j"))
        factory = StorageBackendFactory(config)
        state_db = MagicMock()
        graph = factory.create_relation_graph(state_db)
        assert isinstance(graph, Neo4jRelationGraph)
