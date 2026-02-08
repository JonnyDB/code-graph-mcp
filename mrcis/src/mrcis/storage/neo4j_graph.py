"""Neo4j-backed relation graph for entity and reference management.

Implements RelationGraphPort using Neo4j's async driver with Cypher queries.
Entities are stored as nodes, relations as edges, and pending references
as separate nodes linked to source entities.
"""

import json
from typing import Any
from uuid import uuid4

from loguru import logger
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ClientError, ServiceUnavailable

from mrcis.config.models import Neo4jConfig
from mrcis.models.entities import EntityType
from mrcis.storage.relation_graph import Entity, PendingReference, Relation


class Neo4jRelationGraph:
    """
    Neo4j implementation of RelationGraphPort.

    Node labels:
    - :Entity — code entities (functions, classes, etc.)
    - :PendingReference — unresolved cross-file references

    Relationship types:
    - :RELATES_TO {relation_type, line_number, context_snippet, weight} — resolved relations
    - :HAS_PENDING_REF — links an entity to its pending reference
    """

    def __init__(self, config: Neo4jConfig) -> None:
        self._config = config
        self._driver: Any = None

    async def initialize(self) -> None:
        """Initialize Neo4j driver and create constraints/indexes."""
        self._driver = AsyncGraphDatabase.driver(
            self._config.uri,
            auth=(self._config.username, self._config.password),
            max_connection_pool_size=self._config.max_connection_pool_size,
            connection_timeout=self._config.connection_timeout_seconds,
            notifications_disabled_categories=["PERFORMANCE"],
        )
        try:
            await self._create_constraints()
            await self._create_vector_index()
        except (ClientError, ServiceUnavailable, OSError) as e:
            await self.close()
            raise RuntimeError(
                f"Failed to connect to Neo4j at {self._config.uri}: {e}. "
                "Check that Neo4j is running and credentials are correct. "
                "If rate-limited, restart the Neo4j container: docker compose restart neo4j"
            ) from e
        logger.debug("Neo4jRelationGraph initialized")

    async def close(self) -> None:
        """Close the Neo4j driver."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def _create_constraints(self) -> None:
        """Create uniqueness constraints and indexes."""
        async with self._driver.session(database=self._config.database) as session:
            await session.run(
                "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE"
            )
            await session.run(
                "CREATE INDEX entity_qname IF NOT EXISTS FOR (e:Entity) ON (e.qualified_name)"
            )
            await session.run(
                "CREATE INDEX entity_sname IF NOT EXISTS FOR (e:Entity) ON (e.simple_name)"
            )
            await session.run(
                "CREATE INDEX entity_file IF NOT EXISTS FOR (e:Entity) ON (e.file_id)"
            )
            await session.run(
                "CREATE INDEX entity_vector_id IF NOT EXISTS FOR (e:Entity) ON (e.vector_id)"
            )
            await session.run(
                "CREATE CONSTRAINT pending_ref_id IF NOT EXISTS "
                "FOR (p:PendingReference) REQUIRE p.id IS UNIQUE"
            )

    async def _create_vector_index(self) -> None:
        """Create vector index on Entity nodes for similarity search.

        Neo4j's ``IF NOT EXISTS`` checks by label+property, not by name.
        If a vector index already exists on (Entity, embedding) under a
        different name, we drop it first so the correctly-named index is used.
        """
        index_name = self._config.vector_index_name
        async with self._driver.session(database=self._config.database) as session:
            # Check for existing vector index on Entity.embedding
            result = await session.run(
                "SHOW VECTOR INDEXES YIELD name, labelsOrTypes, properties "
                "WHERE labelsOrTypes = ['Entity'] AND properties = ['embedding']"
            )
            existing = await result.data()
            for idx in existing:
                if idx["name"] != index_name:
                    logger.info(
                        "Dropping stale vector index '{}' (expected '{}')",
                        idx["name"],
                        index_name,
                    )
                    await session.run(f"DROP INDEX {idx['name']} IF EXISTS")

            await session.run(
                f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
                "FOR (e:Entity) ON (e.embedding) "
                "OPTIONS {indexConfig: {"
                f" `vector.dimensions`: {self._config.vector_dimensions},"
                f" `vector.similarity_function`: '{self._config.vector_similarity_function}'"
                "}}"
            )
            logger.info("Vector index '{}' ready", index_name)

    def _session(self) -> Any:
        """Get a new session."""
        if not self._driver:
            raise RuntimeError("Neo4j driver not initialized")
        return self._driver.session(database=self._config.database)

    # =========================================================================
    # Entity Operations
    # =========================================================================

    async def add_entity(
        self,
        repository_id: str,
        file_id: str,
        qualified_name: str,
        simple_name: str,
        entity_type: EntityType,
        language: str,
        line_start: int,
        line_end: int,
        col_start: int | None = None,
        col_end: int | None = None,
        signature: str | None = None,
        docstring: str | None = None,
        source_text: str | None = None,
        visibility: str = "public",
        is_exported: bool = False,
        decorators: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        entity_id: str | None = None,
        vector_id: str | None = None,
    ) -> str:
        """Add entity as a Neo4j node."""
        entity_id = entity_id or str(uuid4())
        logger.debug(
            "neo4j add_entity: id={} qname={} type={} file={}",
            entity_id,
            qualified_name,
            entity_type,
            file_id,
        )
        entity_type_str = entity_type.value if hasattr(entity_type, "value") else entity_type

        async with self._session() as session:
            await session.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.repository_id = $repository_id,
                    e.file_id = $file_id,
                    e.qualified_name = $qualified_name,
                    e.simple_name = $simple_name,
                    e.entity_type = $entity_type,
                    e.language = $language,
                    e.line_start = $line_start,
                    e.line_end = $line_end,
                    e.col_start = $col_start,
                    e.col_end = $col_end,
                    e.signature = $signature,
                    e.docstring = $docstring,
                    e.source_text = $source_text,
                    e.visibility = $visibility,
                    e.is_exported = $is_exported,
                    e.decorators_json = $decorators_json,
                    e.metadata_json = $metadata_json,
                    e.vector_id = $vector_id
                """,
                {
                    "id": entity_id,
                    "repository_id": repository_id,
                    "file_id": file_id,
                    "qualified_name": qualified_name,
                    "simple_name": simple_name,
                    "entity_type": entity_type_str,
                    "language": language,
                    "line_start": line_start,
                    "line_end": line_end,
                    "col_start": col_start,
                    "col_end": col_end,
                    "signature": signature,
                    "docstring": docstring,
                    "source_text": source_text,
                    "visibility": visibility,
                    "is_exported": is_exported,
                    "decorators_json": json.dumps(decorators) if decorators else None,
                    "metadata_json": json.dumps(metadata) if metadata else None,
                    "vector_id": vector_id,
                },
            )

        logger.debug("neo4j add_entity: MERGED id={}", entity_id)
        return entity_id

    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        logger.debug("neo4j get_entity: id={}", entity_id)
        async with self._session() as session:
            result = await session.run(
                "MATCH (e:Entity {id: $id}) RETURN e",
                {"id": entity_id},
            )
            record = await result.single()
            if not record:
                logger.debug("neo4j get_entity: NOT FOUND id={}", entity_id)
                return None
            entity = self._node_to_entity(record["e"])
            logger.debug("neo4j get_entity: FOUND id={} qname={}", entity_id, entity.qualified_name)
            return entity

    async def get_entity_by_qualified_name(self, qualified_name: str) -> Entity | None:
        """Get entity by exact qualified name."""
        logger.debug("neo4j get_entity_by_qualified_name: qname={}", qualified_name)
        async with self._session() as session:
            result = await session.run(
                "MATCH (e:Entity {qualified_name: $qname}) RETURN e",
                {"qname": qualified_name},
            )
            record = await result.single()
            if not record:
                return None
            return self._node_to_entity(record["e"])

    async def get_entities_by_suffix(self, suffix: str, limit: int = 10) -> list[Entity]:
        """Get entities matching name suffix."""
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (e:Entity)
                WHERE e.qualified_name ENDS WITH $suffix OR e.simple_name = $suffix
                RETURN e
                ORDER BY size(e.qualified_name) ASC
                LIMIT $limit
                """,
                {"suffix": suffix, "limit": limit},
            )
            records = await result.data()
            return [self._node_to_entity(r["e"]) for r in records]

    async def get_entities_for_file(self, file_id: str) -> list[Entity]:
        """Get all entities in a file."""
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (e:Entity {file_id: $file_id})
                RETURN e ORDER BY e.line_start
                """,
                {"file_id": file_id},
            )
            records = await result.data()
            return [self._node_to_entity(r["e"]) for r in records]

    async def delete_entities_for_file(self, file_id: str) -> int:
        """Delete all entities for a file and their relationships."""
        logger.debug("neo4j delete_entities_for_file: file_id={}", file_id)
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (e:Entity {file_id: $file_id})
                DETACH DELETE e
                RETURN count(e) AS deleted
                """,
                {"file_id": file_id},
            )
            record = await result.single()
            return record["deleted"] if record else 0

    async def update_entity_vector_id(self, entity_id: str, vector_id: str) -> None:
        """Update entity with vector store ID."""
        async with self._session() as session:
            await session.run(
                "MATCH (e:Entity {id: $id}) SET e.vector_id = $vector_id",
                {"id": entity_id, "vector_id": vector_id},
            )

    def _node_to_entity(self, node: Any) -> Entity:
        """Convert Neo4j node to Entity dataclass."""
        decorators = None
        if node.get("decorators_json"):
            decorators = json.loads(node["decorators_json"])

        return Entity(
            id=node["id"],
            repository_id=node["repository_id"],
            file_id=node["file_id"],
            qualified_name=node["qualified_name"],
            simple_name=node["simple_name"],
            entity_type=EntityType(node["entity_type"]),
            language=node["language"],
            line_start=node["line_start"],
            line_end=node["line_end"],
            col_start=node.get("col_start"),
            col_end=node.get("col_end"),
            signature=node.get("signature"),
            docstring=node.get("docstring"),
            source_text=node.get("source_text"),
            visibility=node.get("visibility", "public"),
            is_exported=bool(node.get("is_exported", False)),
            vector_id=node.get("vector_id"),
            decorators=decorators,
        )

    # =========================================================================
    # Relation Operations
    # =========================================================================

    async def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        line_number: int | None = None,
        context_snippet: str | None = None,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add relation as a Neo4j relationship between entity nodes."""
        logger.debug(
            "neo4j add_relation: source={} target={} type={}",
            source_id,
            target_id,
            relation_type,
        )
        source = await self.get_entity(source_id)
        target = await self.get_entity(target_id)

        if not source or not target:
            raise ValueError("Source or target entity not found")

        relation_id = str(uuid4())
        is_cross_repo = source.repository_id != target.repository_id

        async with self._session() as session:
            await session.run(
                """
                MATCH (s:Entity {id: $source_id})
                MATCH (t:Entity {id: $target_id})
                CREATE (s)-[r:RELATES_TO {
                    id: $id,
                    relation_type: $relation_type,
                    source_qualified_name: $source_qname,
                    source_entity_type: $source_etype,
                    source_repository_id: $source_repo_id,
                    target_qualified_name: $target_qname,
                    target_entity_type: $target_etype,
                    target_repository_id: $target_repo_id,
                    is_cross_repository: $is_cross_repo,
                    line_number: $line_number,
                    context_snippet: $context_snippet,
                    weight: $weight,
                    metadata_json: $metadata_json
                }]->(t)
                """,
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "id": relation_id,
                    "relation_type": relation_type,
                    "source_qname": source.qualified_name,
                    "source_etype": source.entity_type.value,
                    "source_repo_id": source.repository_id,
                    "target_qname": target.qualified_name,
                    "target_etype": target.entity_type.value,
                    "target_repo_id": target.repository_id,
                    "is_cross_repo": is_cross_repo,
                    "line_number": line_number,
                    "context_snippet": context_snippet,
                    "weight": weight,
                    "metadata_json": json.dumps(metadata) if metadata else None,
                },
            )

        logger.debug("neo4j add_relation: CREATED id={}", relation_id)
        return relation_id

    async def get_incoming_relations(self, entity_id: str) -> list[Relation]:
        """Get relations pointing TO this entity."""
        logger.debug("neo4j get_incoming_relations: entity_id={}", entity_id)
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity {id: $id})
                RETURN properties(r) AS rel, s.id AS source_id, t.id AS target_id
                """,
                {"id": entity_id},
            )
            records = await result.data()
            logger.debug(
                "neo4j get_incoming_relations: got {} records",
                len(records),
            )
            return [
                self._rel_to_relation(r["rel"], r["source_id"], r["target_id"]) for r in records
            ]

    async def get_outgoing_relations(self, entity_id: str) -> list[Relation]:
        """Get relations pointing FROM this entity."""
        logger.debug("neo4j get_outgoing_relations: entity_id={}", entity_id)
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (s:Entity {id: $id})-[r:RELATES_TO]->(t:Entity)
                RETURN properties(r) AS rel, s.id AS source_id, t.id AS target_id
                """,
                {"id": entity_id},
            )
            records = await result.data()
            logger.debug(
                "neo4j get_outgoing_relations: got {} records",
                len(records),
            )
            return [
                self._rel_to_relation(r["rel"], r["source_id"], r["target_id"]) for r in records
            ]

    def _rel_to_relation(self, rel: dict[str, Any], source_id: str, target_id: str) -> Relation:
        """Convert Neo4j relationship to Relation dataclass."""
        return Relation(
            id=rel["id"],
            source_id=source_id,
            source_qualified_name=rel["source_qualified_name"],
            source_entity_type=rel["source_entity_type"],
            source_repository_id=rel["source_repository_id"],
            target_id=target_id,
            target_qualified_name=rel["target_qualified_name"],
            target_entity_type=rel["target_entity_type"],
            target_repository_id=rel["target_repository_id"],
            relation_type=rel["relation_type"],
            is_cross_repository=bool(rel.get("is_cross_repository", False)),
            line_number=rel.get("line_number"),
            context_snippet=rel.get("context_snippet"),
            weight=rel.get("weight", 1.0),
        )

    # =========================================================================
    # Pending Reference Operations
    # =========================================================================

    async def add_pending_reference(
        self,
        source_entity_id: str,
        source_qualified_name: str,
        source_repository_id: str,
        target_qualified_name: str,
        relation_type: str,
        line_number: int | None = None,
        context_snippet: str | None = None,
        receiver_expr: str | None = None,
    ) -> str:
        """Add pending reference as a Neo4j node."""
        ref_id = str(uuid4())
        logger.debug(
            "neo4j add_pending_reference: id={} source={} target={} type={}",
            ref_id,
            source_qualified_name,
            target_qualified_name,
            relation_type,
        )

        async with self._session() as session:
            await session.run(
                """
                CREATE (p:PendingReference {
                    id: $id,
                    source_entity_id: $source_entity_id,
                    source_qualified_name: $source_qname,
                    source_repository_id: $source_repo_id,
                    target_qualified_name: $target_qname,
                    relation_type: $relation_type,
                    status: 'pending',
                    attempts: 0,
                    resolved_target_id: null,
                    line_number: $line_number,
                    context_snippet: $context_snippet,
                    receiver_expr: $receiver_expr
                })
                """,
                {
                    "id": ref_id,
                    "source_entity_id": source_entity_id,
                    "source_qname": source_qualified_name,
                    "source_repo_id": source_repository_id,
                    "target_qname": target_qualified_name,
                    "relation_type": relation_type,
                    "line_number": line_number,
                    "context_snippet": context_snippet,
                    "receiver_expr": receiver_expr,
                },
            )

        return ref_id

    async def get_pending_references(self, limit: int = 100) -> list[PendingReference]:
        """Get pending references for resolution."""
        logger.debug("neo4j get_pending_references: limit={}", limit)
        async with self._session() as session:
            result = await session.run(
                """
                MATCH (p:PendingReference {status: 'pending'})
                RETURN p
                ORDER BY p.id
                LIMIT $limit
                """,
                {"limit": limit},
            )
            records = await result.data()
            return [self._node_to_pending_reference(r["p"]) for r in records]

    async def resolve_reference(self, ref_id: str, target_entity_id: str) -> None:
        """Mark reference as resolved and create relation."""
        logger.debug("neo4j resolve_reference: ref_id={} target={}", ref_id, target_entity_id)
        async with self._session() as session:
            result = await session.run(
                "MATCH (p:PendingReference {id: $id}) RETURN p",
                {"id": ref_id},
            )
            record = await result.single()
            if not record:
                raise ValueError(f"Pending reference not found: {ref_id}")

            ref = self._node_to_pending_reference(record["p"])

        await self.add_relation(
            source_id=ref.source_entity_id,
            target_id=target_entity_id,
            relation_type=ref.relation_type,
            line_number=ref.line_number,
            context_snippet=ref.context_snippet,
        )

        async with self._session() as session:
            await session.run(
                """
                MATCH (p:PendingReference {id: $id})
                SET p.status = 'resolved',
                    p.resolved_target_id = $target_id
                """,
                {"id": ref_id, "target_id": target_entity_id},
            )

    async def mark_reference_unresolved(self, ref_id: str, max_attempts: int = 3) -> None:
        """Increment attempt count, mark unresolved if max reached."""
        async with self._session() as session:
            await session.run(
                """
                MATCH (p:PendingReference {id: $id})
                SET p.attempts = p.attempts + 1,
                    p.status = CASE
                        WHEN p.attempts + 1 >= $max THEN 'unresolved'
                        ELSE p.status
                    END
                """,
                {"id": ref_id, "max": max_attempts},
            )

    def _node_to_pending_reference(self, node: Any) -> PendingReference:
        """Convert Neo4j node to PendingReference dataclass."""
        return PendingReference(
            id=node["id"],
            source_entity_id=node["source_entity_id"],
            source_qualified_name=node["source_qualified_name"],
            source_repository_id=node["source_repository_id"],
            target_qualified_name=node["target_qualified_name"],
            relation_type=node["relation_type"],
            status=node.get("status", "pending"),
            attempts=node.get("attempts", 0),
            resolved_target_id=node.get("resolved_target_id"),
            line_number=node.get("line_number"),
            context_snippet=node.get("context_snippet"),
            receiver_expr=node.get("receiver_expr"),
        )
