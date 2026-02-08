"""Code entity models for MRCIS."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    """All supported code entity types."""

    # Core code constructs
    MODULE = "module"
    PACKAGE = "package"
    CLASS = "class"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    PARAMETER = "parameter"

    # Type system
    TYPE_ALIAS = "type_alias"
    ENUM = "enum"
    ENUM_MEMBER = "enum_member"

    # Imports
    IMPORT = "import"
    EXPORT = "export"

    # Documentation
    DOCSTRING = "docstring"
    COMMENT = "comment"

    # Configuration (for TOML, YAML, JSON)
    CONFIG_SECTION = "config_section"
    CONFIG_KEY = "config_key"

    # Database (for SQL)
    TABLE = "table"
    COLUMN = "column"
    INDEX = "index"

    # Web (for HTML, JSX)
    COMPONENT = "component"
    ELEMENT = "element"

    # Infrastructure (for Docker, Bash)
    STAGE = "stage"
    TASK = "task"


class Visibility(StrEnum):
    """Visibility/access modifiers."""

    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    INTERNAL = "internal"


class CodeEntity(BaseModel):
    """
    Base class for all code entities.

    Every entity extracted from source code inherits from this.
    Provides common fields for identification, location, and tracking.
    """

    # Identity
    id: UUID = Field(default_factory=uuid4)
    name: str
    qualified_name: str
    entity_type: EntityType

    # Location
    repository_id: UUID
    file_id: UUID
    file_path: str
    line_start: int
    line_end: int
    col_start: int | None = None
    col_end: int | None = None

    # Source
    source_text: str | None = None
    language: str

    # Documentation
    docstring: str | None = None
    comments: list[str] = Field(default_factory=list)

    # Metadata
    is_exported: bool = False
    visibility: Visibility = Visibility.PUBLIC
    decorators: list[str] = Field(default_factory=list)
    annotations: dict[str, str] = Field(default_factory=dict)

    # Tracking
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # For vector storage
    embedding_text: str | None = None
    vector_id: str | None = None

    model_config = {"use_enum_values": True}


class ClassEntity(CodeEntity):
    """
    Represents a class, struct, or similar type definition.

    Tracks inheritance, decorators, and contained members.
    """

    entity_type: EntityType = EntityType.CLASS

    # Inheritance (qualified names for cross-repo resolution)
    base_classes: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    mixins: list[str] = Field(default_factory=list)

    # Class characteristics
    is_abstract: bool = False
    is_dataclass: bool = False
    is_frozen: bool = False

    # Generic type parameters
    type_parameters: list[str] = Field(default_factory=list)

    # Contained members (for quick access, full details in separate entities)
    method_names: list[str] = Field(default_factory=list)
    property_names: list[str] = Field(default_factory=list)
    class_variable_names: list[str] = Field(default_factory=list)


class ParameterEntity(BaseModel):
    """
    Represents a function/method parameter.

    Not a full CodeEntity since parameters don't exist independently.
    """

    name: str
    type_annotation: str | None = None
    default_value: str | None = None

    # Parameter kind
    is_rest: bool = False
    is_keyword_only: bool = False
    is_positional_only: bool = False
    is_optional: bool = False


class FunctionEntity(CodeEntity):
    """
    Represents a function or standalone callable.

    Not a method (which belongs to a class).
    """

    entity_type: EntityType = EntityType.FUNCTION

    # Signature
    parameters: list[ParameterEntity] = Field(default_factory=list)
    return_type: str | None = None

    # Characteristics
    is_async: bool = False
    is_generator: bool = False
    is_lambda: bool = False

    # Type parameters for generics
    type_parameters: list[str] = Field(default_factory=list)

    # Calls made by this function (for CALLS edges)
    calls: list[str] = Field(default_factory=list)

    # Types used (for USES_TYPE edges)
    type_references: list[str] = Field(default_factory=list)

    # Signature string (e.g., "def func(x: int) -> str")
    signature: str | None = None


class MethodEntity(FunctionEntity):
    """
    Represents a method within a class.

    Extends FunctionEntity with class-specific attributes.
    """

    entity_type: EntityType = EntityType.METHOD

    # Parent class (qualified name for cross-repo resolution)
    parent_class: str

    # Method characteristics
    is_static: bool = False
    is_classmethod: bool = False
    is_property: bool = False
    is_abstract: bool = False
    is_constructor: bool = False
    is_destructor: bool = False

    # Override tracking
    overrides: str | None = None


class ImportEntity(CodeEntity):
    """
    Represents an import statement.

    Critical for cross-repository reference resolution.
    """

    entity_type: EntityType = EntityType.IMPORT

    # What is being imported
    source_module: str
    imported_symbols: list[str] = Field(default_factory=list)

    # Import style
    is_wildcard: bool = False
    is_default: bool = False
    is_namespace: bool = False
    alias: str | None = None

    # For resolution
    is_relative: bool = False
    relative_level: int = 0


class VariableEntity(CodeEntity):
    """
    Represents a variable, constant, or class attribute.
    """

    entity_type: EntityType = EntityType.VARIABLE

    type_annotation: str | None = None
    initial_value: str | None = None

    is_constant: bool = False
    is_class_variable: bool = False
    is_instance_variable: bool = False

    # Parent scope
    parent_class: str | None = None
    parent_function: str | None = None


class ModuleEntity(CodeEntity):
    """
    Represents a module, package, or namespace.
    """

    entity_type: EntityType = EntityType.MODULE

    package_name: str | None = None
    is_package: bool = False
    exports: list[str] = Field(default_factory=list)


class TypeAliasEntity(CodeEntity):
    """
    Represents a type alias or typedef.
    """

    entity_type: EntityType = EntityType.TYPE_ALIAS

    aliased_type: str
    type_parameters: list[str] = Field(default_factory=list)
    is_union: bool = False
    is_intersection: bool = False
