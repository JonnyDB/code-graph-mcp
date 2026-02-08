"""Relationship models for MRCIS."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from mrcis.models.entities import EntityType


class RelationType(StrEnum):
    """All supported relationship types between entities."""

    # Structural containment
    CONTAINS = "contains"
    DEFINED_IN = "defined_in"

    # Inheritance & implementation
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    OVERRIDES = "overrides"

    # Dependencies
    IMPORTS = "imports"
    EXPORTS = "exports"
    DEPENDS_ON = "depends_on"

    # Usage
    CALLS = "calls"
    INSTANTIATES = "instantiates"
    USES_TYPE = "uses_type"
    REFERENCES = "references"

    # Parameters
    HAS_PARAMETER = "has_parameter"
    RETURNS = "returns"

    # Decoration
    DECORATED_BY = "decorated_by"

    # Documentation
    DOCUMENTS = "documents"


class CodeRelation(BaseModel):
    """
    Represents a relationship between two code entities.

    This is the edge in our code graph. Supports both intra-repo
    and cross-repo relationships.
    """

    id: UUID = Field(default_factory=uuid4)

    # Source entity
    source_id: UUID
    source_qualified_name: str
    source_entity_type: EntityType | str
    source_repository_id: UUID

    # Target entity
    target_id: UUID | None = None
    target_qualified_name: str
    target_entity_type: EntityType | str | None = None
    target_repository_id: UUID | None = None

    # Relationship
    relation_type: RelationType

    # Cross-repository tracking
    is_cross_repository: bool = False
    resolution_status: str = "resolved"

    # Context
    line_number: int | None = None
    context_snippet: str | None = None

    # Metadata
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None

    model_config = {"use_enum_values": True}


class PendingReference(BaseModel):
    """
    A reference that couldn't be resolved during extraction.

    Queued for deferred cross-repository resolution.
    """

    id: UUID = Field(default_factory=uuid4)

    source_entity_id: UUID
    source_qualified_name: str
    source_repository_id: UUID
    target_qualified_name: str
    relation_type: RelationType
    line_number: int

    # Resolution tracking
    status: str = "pending"
    attempts: int = 0
    resolved_target_id: UUID | None = None
    resolved_at: datetime | None = None

    # Context
    context_snippet: str | None = None

    # Receiver context (for disambiguation of common method names)
    receiver_expr: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"use_enum_values": True}
