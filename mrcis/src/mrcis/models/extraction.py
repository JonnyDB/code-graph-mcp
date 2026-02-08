"""Extraction result models for code analysis pipeline.

These models represent the output of language-specific extractors and are
used internally within the indexing pipeline. They are separate from MCP
response DTOs to follow the Single Responsibility Principle.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from mrcis.models.entities import (
    ClassEntity,
    CodeEntity,
    EntityType,
    FunctionEntity,
    ImportEntity,
    MethodEntity,
    ModuleEntity,
    TypeAliasEntity,
    VariableEntity,
)
from mrcis.models.relations import CodeRelation, PendingReference


class EnumEntity(CodeEntity):
    """Enum entity for languages that support enumerations."""

    entity_type: EntityType = EntityType.ENUM


class InterfaceEntity(CodeEntity):
    """Interface entity for languages that support interfaces (TypeScript, Java, etc.)."""

    entity_type: EntityType = EntityType.INTERFACE


class ExtractionResult(BaseModel):
    """
    Container for all entities and relations extracted from a single file.

    Returned by language-specific extractors and consumed by the indexing
    pipeline. This is a domain model, not an API response DTO.
    """

    file_id: UUID
    file_path: str
    repository_id: UUID
    language: str

    # Extracted entities by type
    modules: list[ModuleEntity] = Field(default_factory=list)
    classes: list[ClassEntity] = Field(default_factory=list)
    interfaces: list[InterfaceEntity] = Field(default_factory=list)
    functions: list[FunctionEntity] = Field(default_factory=list)
    methods: list[MethodEntity] = Field(default_factory=list)
    variables: list[VariableEntity] = Field(default_factory=list)
    imports: list[ImportEntity] = Field(default_factory=list)
    type_aliases: list[TypeAliasEntity] = Field(default_factory=list)
    enums: list[EnumEntity] = Field(default_factory=list)

    # Extracted relationships
    relations: list[CodeRelation] = Field(default_factory=list)

    # Pending references (for deferred resolution)
    pending_references: list[PendingReference] = Field(default_factory=list)

    # Extraction metadata
    parse_errors: list[str] = Field(default_factory=list)
    extraction_time_ms: float = 0.0

    def all_entities(self) -> list[CodeEntity]:
        """Return all entities as a flat list."""
        return (
            list(self.modules)
            + list(self.classes)
            + list(self.interfaces)
            + list(self.functions)
            + list(self.methods)
            + list(self.variables)
            + list(self.imports)
            + list(self.type_aliases)
            + list(self.enums)
        )

    def entity_count(self) -> int:
        """Total number of entities extracted."""
        return len(self.all_entities())
