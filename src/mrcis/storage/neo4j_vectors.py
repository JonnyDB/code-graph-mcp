"""Neo4j-backed vector storage for MRCIS.

Stores embeddings as properties on Entity nodes in Neo4j and uses
Neo4j's vector index for similarity search. This co-locates vectors
with the graph, enabling combined graph+vector queries.
"""

from dataclasses import dataclass
from typing import Any

from loguru import logger
from neo4j import AsyncGraphDatabase

from mrcis.config.models import Neo4jConfig


@dataclass
class Neo4jCodeVector:
    """Vector data model compatible with VectorStorePort's model property.

    Mirrors the LanceDB CodeVector schema so the IndexingService can
    create instances identically regardless of backend.
    """

    id: str
    repository_id: str
    file_id: str
    qualified_name: str
    simple_name: str
    entity_type: str
    language: str
    file_path: str
    line_start: int
    line_end: int
    vector: list[float]
    embedding_text: str
    visibility: str = "public"
    is_exported: bool = False
    has_docstring: bool = False
    signature: str | None = None
    docstring: str | None = None

    def model_dump(self) -> dict[str, Any]:
        """Return dict representation (matches Pydantic LanceModel API)."""
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "file_id": self.file_id,
            "qualified_name": self.qualified_name,
            "simple_name": self.simple_name,
            "entity_type": self.entity_type,
            "language": self.language,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "vector": self.vector,
            "embedding_text": self.embedding_text,
            "visibility": self.visibility,
            "is_exported": self.is_exported,
            "has_docstring": self.has_docstring,
            "signature": self.signature,
            "docstring": self.docstring,
        }


class Neo4jVectorStore:
    """Neo4j implementation of VectorStorePort.

    Stores embedding vectors directly on Entity nodes and uses
    Neo4j's vector index for similarity search.
    """

    def __init__(self, config: Neo4jConfig) -> None:
        self._config = config
        self._driver: Any = None

    @property
    def model(self) -> type[Neo4jCodeVector]:
        """Return the vector model class."""
        return Neo4jCodeVector

    async def initialize(self) -> None:
        """Initialize Neo4j driver. Vector index is created by Neo4jRelationGraph."""
        self._driver = AsyncGraphDatabase.driver(
            self._config.uri,
            auth=(self._config.username, self._config.password),
            max_connection_pool_size=self._config.max_connection_pool_size,
            connection_timeout=self._config.connection_timeout_seconds,
            notifications_disabled_categories=["PERFORMANCE"],
        )
        logger.debug("Neo4jVectorStore initialized")

    async def close(self) -> None:
        """Close the driver."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    def _session(self) -> Any:
        if not self._driver:
            raise RuntimeError("Neo4j driver not initialized")
        return self._driver.session(database=self._config.database)

    async def upsert_vectors(self, vectors: list[Any]) -> int:
        """Store embeddings on Entity nodes.

        The Entity nodes already exist (created by Neo4jRelationGraph.add_entity).
        This method sets the ``embedding`` and ``embedding_text`` properties.
        """
        if not vectors:
            return 0

        logger.debug("neo4j upsert_vectors: count={}", len(vectors))

        async with self._session() as session:
            for v in vectors:
                data = v.model_dump() if hasattr(v, "model_dump") else v
                logger.debug(
                    "neo4j upsert_vectors: entity_id={} keys={} vector_len={}",
                    data.get("id"),
                    list(data.keys()),
                    len(data.get("vector", [])),
                )
                await session.run(
                    """
                    MATCH (e:Entity {vector_id: $vector_id})
                    SET e.embedding = $vector,
                        e.embedding_text = $embedding_text,
                        e.file_path = $file_path,
                        e.has_docstring = $has_docstring
                    """,
                    {
                        "vector_id": data["id"],
                        "vector": data["vector"],
                        "embedding_text": data["embedding_text"],
                        "file_path": data["file_path"],
                        "has_docstring": data.get("has_docstring", False),
                    },
                )

        return len(vectors)

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors using Neo4j vector index.

        Uses ``db.index.vector.queryNodes()`` for ANN search, then
        applies property-based filters in Cypher.
        """
        index_name = self._config.vector_index_name

        # Build WHERE clause for post-search filtering
        where_clauses: list[str] = []
        params: dict[str, Any] = {
            "query_vector": query_vector,
            "top_k": limit * 3,  # over-fetch for post-filtering
            "min_score": min_score,
            "limit": limit,
        }

        if filters:
            for key, value in filters.items():
                param_name = f"filter_{key}"
                where_clauses.append(f"node.{key} = ${param_name}")
                params[param_name] = value

        where_clause = " AND ".join(where_clauses)
        if where_clause:
            where_clause = f"WHERE {where_clause} AND score >= $min_score"
        else:
            where_clause = "WHERE score >= $min_score"

        query = f"""
            CALL db.index.vector.queryNodes('{index_name}', $top_k, $query_vector)
            YIELD node, score
            {where_clause}
            RETURN node, score
            ORDER BY score DESC
            LIMIT $limit
        """

        logger.debug("neo4j search: index={} limit={} filters={}", index_name, limit, filters)

        async with self._session() as session:
            result = await session.run(query, params)
            records = await result.data()

        logger.debug("neo4j search: got {} raw records", len(records))
        if records:
            first = records[0]
            logger.debug(
                "neo4j search: first record keys={} node_type={}",
                list(first.keys()),
                type(first.get("node")).__name__,
            )

        results: list[dict[str, Any]] = []
        for record in records:
            node = record["node"]
            score = record["score"]
            results.append(
                {
                    "id": node.get("vector_id") or node["id"],
                    "entity_id": node["id"],
                    "repository_id": node["repository_id"],
                    "file_id": node["file_id"],
                    "qualified_name": node["qualified_name"],
                    "simple_name": node["simple_name"],
                    "entity_type": node["entity_type"],
                    "language": node["language"],
                    "file_path": node.get("file_path", ""),
                    "line_start": node["line_start"],
                    "line_end": node["line_end"],
                    "embedding_text": node.get("embedding_text", ""),
                    "signature": node.get("signature"),
                    "docstring": node.get("docstring"),
                    "_distance": 1.0 - score,
                }
            )

        return results

    async def delete_by_file(self, file_id: str) -> int:
        """Remove embeddings from Entity nodes for a file.

        Note: Does NOT delete the entity nodes -- just clears the vector data.
        Entity deletion is handled by ``Neo4jRelationGraph.delete_entities_for_file()``.
        """
        logger.debug("neo4j delete_by_file: file_id={}", file_id)
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (e:Entity {file_id: $file_id})
                WHERE e.embedding IS NOT NULL
                SET e.embedding = null, e.embedding_text = null
                RETURN count(e) AS updated
                """,
                {"file_id": file_id},
            )
            record = await result.single()
            return record["updated"] if record else 0

    async def delete_by_repository(self, repository_id: str) -> int:
        """Remove embeddings from Entity nodes for a repository."""
        logger.debug("neo4j delete_by_repository: repo_id={}", repository_id)
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (e:Entity {repository_id: $repo_id})
                WHERE e.embedding IS NOT NULL
                SET e.embedding = null, e.embedding_text = null
                RETURN count(e) AS updated
                """,
                {"repo_id": repository_id},
            )
            record = await result.single()
            return record["updated"] if record else 0
