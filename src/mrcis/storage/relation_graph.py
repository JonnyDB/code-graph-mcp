"""Relation graph for entity and reference management.

Provides query interface over SQLite entities, relations,
and pending_references tables. Complements StateDB which
handles repositories, files, and queue operations.
"""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from loguru import logger

if TYPE_CHECKING:
    from mrcis.ports.db_session import DbSessionPort

from mrcis.models.entities import EntityType


@dataclass
class Entity:
    """Entity record from database."""

    id: str
    repository_id: str
    file_id: str
    qualified_name: str
    simple_name: str
    entity_type: EntityType
    language: str
    line_start: int
    line_end: int
    col_start: int | None = None
    col_end: int | None = None
    signature: str | None = None
    docstring: str | None = None
    source_text: str | None = None
    visibility: str = "public"
    is_exported: bool = False
    vector_id: str | None = None
    decorators: list[str] | None = None

    @property
    def name(self) -> str:
        """Alias for simple_name (compatibility with CodeEntity)."""
        return self.simple_name


@dataclass
class Relation:
    """Relation record from database."""

    id: str
    source_id: str
    source_qualified_name: str
    source_entity_type: str
    source_repository_id: str
    target_id: str
    target_qualified_name: str
    target_entity_type: str
    target_repository_id: str
    relation_type: str
    is_cross_repository: bool = False
    line_number: int | None = None
    context_snippet: str | None = None
    weight: float = 1.0


@dataclass
class PendingReference:
    """Pending reference record from database."""

    id: str
    source_entity_id: str
    source_qualified_name: str
    source_repository_id: str
    target_qualified_name: str
    relation_type: str
    status: str = "pending"
    attempts: int = 0
    resolved_target_id: str | None = None
    line_number: int | None = None
    context_snippet: str | None = None
    receiver_expr: str | None = None


class RelationGraph:
    """
    Query interface for entities, relations, and pending references.

    Complements StateDB - both share the same database connection.
    StateDB handles: repositories, files, queue
    RelationGraph handles: entities, relations, pending_references
    """

    def __init__(self, db_session: "DbSessionPort") -> None:
        """
        Initialize RelationGraph.

        Args:
            db_session: Database session port for SQL operations.
        """
        self._db = db_session

    async def initialize(self) -> None:
        """Initialize RelationGraph. Schema already exists from StateDB."""
        logger.debug("RelationGraph initialized")

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
        """
        Add entity to database.

        Args:
            entity_id: Optional caller-provided ID. Generated if not provided.
            vector_id: Optional vector store ID for this entity.

        Returns:
            Entity ID.
        """

        entity_id = entity_id or str(uuid4())
        entity_type_str = entity_type.value if hasattr(entity_type, "value") else entity_type

        async with self._db.transaction():
            await self._db.execute(
                """
                INSERT INTO entities (
                    id, repository_id, file_id, qualified_name, simple_name,
                    entity_type, language, line_start, line_end, col_start, col_end,
                    signature, docstring, source_text, visibility, is_exported,
                    decorators_json, metadata_json, vector_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    entity_id,
                    repository_id,
                    file_id,
                    qualified_name,
                    simple_name,
                    entity_type_str,
                    language,
                    line_start,
                    line_end,
                    col_start,
                    col_end,
                    signature,
                    docstring,
                    source_text,
                    visibility,
                    1 if is_exported else 0,
                    json.dumps(decorators) if decorators else None,
                    json.dumps(metadata) if metadata else None,
                    vector_id,
                ],
            )

        return entity_id

    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        row = await self._db.fetchone("SELECT * FROM entities WHERE id = ?", [entity_id])
        return self._row_to_entity(row) if row else None

    async def get_entity_by_qualified_name(self, qualified_name: str) -> Entity | None:
        """Get entity by exact qualified name."""
        row = await self._db.fetchone(
            "SELECT * FROM entities WHERE qualified_name = ?", [qualified_name]
        )
        return self._row_to_entity(row) if row else None

    async def get_entities_by_suffix(self, suffix: str, limit: int = 10) -> list[Entity]:
        """
        Get entities matching name suffix.

        Useful for partial name resolution (e.g., "MyClass" finds "module.MyClass").
        """
        rows = await self._db.fetchall(
            """
            SELECT * FROM entities
            WHERE qualified_name LIKE ? OR simple_name = ?
            ORDER BY LENGTH(qualified_name) ASC
            LIMIT ?
            """,
            [f"%{suffix}", suffix, limit],
        )
        return [self._row_to_entity(row) for row in rows]

    async def get_entities_for_file(self, file_id: str) -> list[Entity]:
        """Get all entities in a file."""
        rows = await self._db.fetchall(
            "SELECT * FROM entities WHERE file_id = ? ORDER BY line_start",
            [file_id],
        )
        return [self._row_to_entity(row) for row in rows]

    async def delete_entities_for_file(self, file_id: str) -> int:
        """
        Delete all entities for a file.

        Returns:
            Number of entities deleted.
        """
        async with self._db.transaction():
            cursor = await self._db.execute("DELETE FROM entities WHERE file_id = ?", [file_id])
        return int(cursor.rowcount)

    async def update_entity_vector_id(self, entity_id: str, vector_id: str) -> None:
        """Update entity with vector store ID."""
        async with self._db.transaction():
            await self._db.execute(
                "UPDATE entities SET vector_id = ? WHERE id = ?",
                [vector_id, entity_id],
            )

    def _row_to_entity(self, row: Any) -> Entity:
        """Convert database row to Entity."""
        decorators = None
        if row["decorators_json"]:
            decorators = json.loads(row["decorators_json"])

        return Entity(
            id=row["id"],
            repository_id=row["repository_id"],
            file_id=row["file_id"],
            qualified_name=row["qualified_name"],
            simple_name=row["simple_name"],
            entity_type=EntityType(row["entity_type"]),
            language=row["language"],
            line_start=row["line_start"],
            line_end=row["line_end"],
            col_start=row["col_start"],
            col_end=row["col_end"],
            signature=row["signature"],
            docstring=row["docstring"],
            source_text=row["source_text"],
            visibility=row["visibility"],
            is_exported=bool(row["is_exported"]),
            vector_id=row["vector_id"],
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
        """
        Add relation between entities.

        Returns:
            Relation ID.
        """

        # Get source and target entities for denormalized fields
        source = await self.get_entity(source_id)
        target = await self.get_entity(target_id)

        if not source or not target:
            raise ValueError("Source or target entity not found")

        relation_id = str(uuid4())
        is_cross_repo = source.repository_id != target.repository_id

        async with self._db.transaction():
            await self._db.execute(
                """
                INSERT INTO relations (
                    id, source_id, source_qualified_name, source_entity_type,
                    source_repository_id, target_id, target_qualified_name,
                    target_entity_type, target_repository_id, relation_type,
                    is_cross_repository, line_number, context_snippet, weight,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    relation_id,
                    source_id,
                    source.qualified_name,
                    source.entity_type.value,
                    source.repository_id,
                    target_id,
                    target.qualified_name,
                    target.entity_type.value,
                    target.repository_id,
                    relation_type,
                    1 if is_cross_repo else 0,
                    line_number,
                    context_snippet,
                    weight,
                    json.dumps(metadata) if metadata else None,
                ],
            )

        return relation_id

    async def get_incoming_relations(self, entity_id: str) -> list[Relation]:
        """Get relations pointing TO this entity."""
        rows = await self._db.fetchall("SELECT * FROM relations WHERE target_id = ?", [entity_id])
        return [self._row_to_relation(row) for row in rows]

    async def get_outgoing_relations(self, entity_id: str) -> list[Relation]:
        """Get relations pointing FROM this entity."""
        rows = await self._db.fetchall("SELECT * FROM relations WHERE source_id = ?", [entity_id])
        return [self._row_to_relation(row) for row in rows]

    def _row_to_relation(self, row: Any) -> Relation:
        """Convert database row to Relation."""
        return Relation(
            id=row["id"],
            source_id=row["source_id"],
            source_qualified_name=row["source_qualified_name"],
            source_entity_type=row["source_entity_type"],
            source_repository_id=row["source_repository_id"],
            target_id=row["target_id"],
            target_qualified_name=row["target_qualified_name"],
            target_entity_type=row["target_entity_type"],
            target_repository_id=row["target_repository_id"],
            relation_type=row["relation_type"],
            is_cross_repository=bool(row["is_cross_repository"]),
            line_number=row["line_number"],
            context_snippet=row["context_snippet"],
            weight=row["weight"],
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
        """
        Add pending reference for deferred resolution.

        Returns:
            Reference ID.
        """
        ref_id = str(uuid4())

        async with self._db.transaction():
            await self._db.execute(
                """
                INSERT INTO pending_references (
                    id, source_entity_id, source_qualified_name, source_repository_id,
                    target_qualified_name, relation_type, line_number, context_snippet,
                    receiver_expr
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ref_id,
                    source_entity_id,
                    source_qualified_name,
                    source_repository_id,
                    target_qualified_name,
                    relation_type,
                    line_number,
                    context_snippet,
                    receiver_expr,
                ],
            )

        return ref_id

    async def get_pending_references(self, limit: int = 100) -> list[PendingReference]:
        """Get pending references for resolution."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM pending_references
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            [limit],
        )
        return [self._row_to_pending_reference(row) for row in rows]

    async def resolve_reference(self, ref_id: str, target_entity_id: str) -> None:
        """
        Mark reference as resolved and create relation.

        Args:
            ref_id: Pending reference ID.
            target_entity_id: Resolved target entity ID.
        """
        # Get the pending reference
        row = await self._db.fetchone("SELECT * FROM pending_references WHERE id = ?", [ref_id])
        if not row:
            raise ValueError(f"Pending reference not found: {ref_id}")

        ref = self._row_to_pending_reference(row)

        # Create the relation
        await self.add_relation(
            source_id=ref.source_entity_id,
            target_id=target_entity_id,
            relation_type=ref.relation_type,
            line_number=ref.line_number,
            context_snippet=ref.context_snippet,
        )

        # Mark as resolved
        async with self._db.transaction():
            await self._db.execute(
                """
                UPDATE pending_references
                SET status = 'resolved',
                    resolved_target_id = ?,
                    resolved_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                [target_entity_id, ref_id],
            )

    async def mark_reference_unresolved(self, ref_id: str, max_attempts: int = 3) -> None:
        """
        Increment attempt count, mark unresolved if max reached.

        Args:
            ref_id: Pending reference ID.
            max_attempts: Maximum resolution attempts.
        """
        async with self._db.transaction():
            await self._db.execute(
                """
                UPDATE pending_references
                SET attempts = attempts + 1,
                    status = CASE
                        WHEN attempts + 1 >= ? THEN 'unresolved'
                        ELSE status
                    END,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                [max_attempts, ref_id],
            )

    def _row_to_pending_reference(self, row: Any) -> PendingReference:
        """Convert database row to PendingReference."""
        return PendingReference(
            id=row["id"],
            source_entity_id=row["source_entity_id"],
            source_qualified_name=row["source_qualified_name"],
            source_repository_id=row["source_repository_id"],
            target_qualified_name=row["target_qualified_name"],
            relation_type=row["relation_type"],
            status=row["status"],
            attempts=row["attempts"],
            resolved_target_id=row["resolved_target_id"],
            line_number=row["line_number"],
            context_snippet=row["context_snippet"],
            receiver_expr=row["receiver_expr"],
        )
