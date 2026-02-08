"""Storage backend factory.

Instantiates the correct RelationGraph and VectorStore implementations
based on config.storage.backend.
"""

from typing import Any

from mrcis.config.models import Config
from mrcis.storage.relation_graph import RelationGraph
from mrcis.storage.vector_store import VectorStore


class StorageBackendFactory:
    """Factory for creating storage backend instances.

    Reads config.storage.backend and returns the appropriate
    RelationGraph and VectorStore implementations.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def backend(self) -> str:
        """Return the configured backend name."""
        return self._config.storage.backend

    def create_relation_graph(self, state_db: Any = None) -> Any:
        """Create the relation graph implementation.

        Args:
            state_db: Required for sqlite_lancedb backend (passed as DbSessionPort).
                      Ignored for neo4j backend.

        Returns:
            An object implementing RelationGraphPort.
        """
        if self.backend == "neo4j":
            from mrcis.storage.neo4j_graph import Neo4jRelationGraph

            return Neo4jRelationGraph(self._config.neo4j)
        else:
            if state_db is None:
                raise ValueError("state_db is required for sqlite_lancedb backend")
            return RelationGraph(state_db)

    def create_vector_store(self) -> Any:
        """Create the vector store implementation.

        Returns:
            An object implementing VectorStorePort.
        """
        if self.backend == "neo4j":
            from mrcis.storage.neo4j_vectors import Neo4jVectorStore

            return Neo4jVectorStore(self._config.neo4j)
        else:
            return VectorStore(
                str(self._config.storage.data_directory / "vectors"),
                self._config.storage.vector_table_name,
                self._config.embedding.dimensions,
            )
