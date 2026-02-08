"""Port interface for relation graph operations."""

from typing import Any, Protocol
from uuid import UUID

from mrcis.models.entities import CodeEntity, EntityType
from mrcis.models.relations import CodeRelation, PendingReference


class RelationGraphPort(Protocol):
    """Protocol for code entity and relationship graph operations."""

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
        """Add a code entity to the graph. Returns entity ID."""
        ...

    async def get_entity(self, entity_id: str | UUID | None) -> CodeEntity | None:
        """Get entity by ID."""
        ...

    async def get_entity_by_qualified_name(self, qualified_name: str) -> CodeEntity | None:
        """Get entity by qualified name."""
        ...

    async def get_entities_by_suffix(self, suffix: str, limit: int = 10) -> list[CodeEntity]:
        """Get entities whose qualified name ends with suffix."""
        ...

    async def get_entities_for_file(self, file_id: str) -> list[CodeEntity]:
        """Get all entities defined in a file."""
        ...

    async def delete_entities_for_file(self, file_id: str) -> int:
        """Delete all entities for a file. Returns count deleted."""
        ...

    async def update_entity_vector_id(self, entity_id: str, vector_id: str) -> None:
        """Update the vector store ID for an entity."""
        ...

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
        """Add a relationship between entities. Returns relation ID."""
        ...

    async def get_incoming_relations(self, entity_id: str | UUID) -> list[CodeRelation]:
        """Get all relations where entity is the target."""
        ...

    async def get_outgoing_relations(self, entity_id: str | UUID) -> list[CodeRelation]:
        """Get all relations where entity is the source."""
        ...

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
        """Add an unresolved cross-file reference. Returns reference ID."""
        ...

    async def get_pending_references(self, *, limit: int | None = None) -> list[PendingReference]:
        """Get pending references to resolve."""
        ...

    async def resolve_reference(self, reference_id: str | UUID, target_entity_id: str) -> None:
        """Mark a reference as resolved and create relation to target."""
        ...

    async def count_entities(self, repo_id: str) -> int:
        """Count entities in a repository."""
        ...

    async def count_relations(self, repo_id: str) -> int:
        """Count relations in a repository (as source or target)."""
        ...

    async def mark_reference_unresolved(self, ref_id: str | UUID, max_attempts: int = 3) -> None:
        """Increment attempts for a reference, mark as failed if max reached."""
        ...
