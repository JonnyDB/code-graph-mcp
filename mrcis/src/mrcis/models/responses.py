"""MCP response models for MRCIS.

This module contains Data Transfer Objects (DTOs) used for MCP tool responses.
For internal domain models used in the extraction pipeline, see models.extraction.
"""

from pydantic import BaseModel, Field

# MCP Response Models


class SearchResult(BaseModel):
    """A single search result."""

    id: str = Field(description="Unique identifier for this code entity")
    repository: str = Field(description="Name of the repository containing this result")
    file_path: str = Field(description="Path to the file within the repository")
    qualified_name: str = Field(
        description="Fully qualified name of the entity (e.g., 'module.ClassName.method_name')"
    )
    simple_name: str = Field(description="Simple name without qualification (e.g., 'method_name')")
    entity_type: str = Field(
        description="Type of code entity: 'class', 'function', 'method', 'variable', etc."
    )
    line_start: int = Field(description="Starting line number (1-indexed)")
    line_end: int = Field(description="Ending line number (1-indexed)")
    score: float = Field(ge=0.0, le=1.0, description="Relevance score from 0.0 to 1.0")

    # Optional details
    signature: str | None = Field(
        default=None, description="Function/method signature if applicable"
    )
    docstring: str | None = Field(default=None, description="Documentation string if present")
    snippet: str | None = Field(
        default=None, description="Source code snippet (truncated to 2000 chars)"
    )


class SearchResponse(BaseModel):
    """Response from search_code tool."""

    results: list[SearchResult] = Field(
        description="List of matching code entities ranked by relevance"
    )
    total_count: int = Field(description="Total number of results returned")
    query: str = Field(description="The original search query")
    filters_applied: dict[str, str] | None = Field(
        default=None, description="Filters that were applied to the search"
    )


class SymbolInfo(BaseModel):
    """Detailed information about a symbol."""

    id: str = Field(description="Unique identifier for this code entity")
    repository: str = Field(description="Name of the repository containing this symbol")
    file_path: str = Field(description="Path to the file within the repository")
    qualified_name: str = Field(
        description="Fully qualified name (e.g., 'module.ClassName.method_name')"
    )
    simple_name: str = Field(description="Simple name without qualification")
    entity_type: str = Field(
        description="Type of code entity: 'class', 'function', 'method', 'variable', etc."
    )
    language: str = Field(description="Programming language (e.g., 'python', 'typescript')")
    line_start: int = Field(description="Starting line number (1-indexed)")
    line_end: int = Field(description="Ending line number (1-indexed)")

    # Content
    signature: str | None = Field(
        default=None, description="Function/method signature if applicable"
    )
    docstring: str | None = Field(default=None, description="Documentation string if present")
    source_text: str | None = Field(
        default=None, description="Full source code text (only included when requested)"
    )

    # Metadata
    visibility: str = Field(
        default="public", description="Visibility: 'public', 'private', or 'protected'"
    )
    is_exported: bool = Field(
        default=False, description="Whether the symbol is exported from its module"
    )
    decorators: list[str] | None = Field(
        default=None, description="List of decorators/annotations applied"
    )

    # Type-specific fields
    base_classes: list[str] | None = Field(
        default=None, description="Base classes for class entities"
    )
    parameters: list[dict[str, str]] | None = Field(
        default=None, description="Function/method parameters with name and type info"
    )
    return_type: str | None = Field(default=None, description="Return type annotation if present")


class SymbolResponse(BaseModel):
    """Response from find_symbol tool."""

    symbol: SymbolInfo | None = Field(default=None, description="Symbol details if found")
    found: bool = Field(default=False, description="Whether the symbol was found")
    message: str | None = Field(default=None, description="Error or informational message")


class ReferenceInfo(BaseModel):
    """Information about a reference to a symbol."""

    file_path: str = Field(description="Path to the file containing this reference")
    repository: str = Field(description="Name of the repository")
    line_number: int = Field(description="Line number where the reference occurs")
    relation_type: str = Field(
        description="Type of reference: 'calls', 'imports', 'extends', 'implements', 'uses', etc."
    )
    context_snippet: str | None = Field(
        default=None, description="Code snippet showing the reference in context"
    )
    source_entity: str | None = Field(
        default=None, description="Qualified name of the entity making the reference"
    )


class ReferencesResponse(BaseModel):
    """Response from get_symbol_references tool."""

    symbol: str = Field(description="Qualified name of the symbol being referenced")
    references: list[ReferenceInfo] = Field(description="List of references to this symbol")
    total_count: int = Field(description="Total number of references found")
    incoming: int = Field(
        default=0, description="Count of incoming references (symbols that reference this one)"
    )
    outgoing: int = Field(
        default=0, description="Count of outgoing references (symbols this one references)"
    )


class MCPRepositoryStatus(BaseModel):
    """Status of a single repository for MCP responses."""

    name: str
    path: str
    status: str  # pending, indexing, watching, error, paused
    file_count: int = 0
    entity_count: int = 0
    relation_count: int = 0
    error_message: str | None = None
    last_indexed_at: str | None = None


class IndexStatus(BaseModel):
    """Index status for a repository."""

    repository: str = Field(description="Name of the repository")
    status: str = Field(
        description="Current status: 'pending', 'indexing', 'watching', 'error', 'paused'"
    )
    file_count: int = Field(description="Number of indexed files")
    entity_count: int = Field(description="Number of code entities (classes, functions, etc.)")
    relation_count: int = Field(description="Number of relationships between entities")
    pending_files: int = Field(default=0, description="Number of files queued for indexing")
    failed_files: int = Field(default=0, description="Number of files that failed to index")
    last_indexed_at: str | None = Field(
        default=None, description="ISO timestamp of last indexing run"
    )
    last_indexed_commit: str | None = Field(
        default=None, description="Git commit SHA of last indexed state"
    )


class IndexStatusResponse(BaseModel):
    """Response from get_index_status tool."""

    repositories: list[IndexStatus] = Field(description="Status for each repository")
    total_files: int = Field(default=0, description="Aggregate file count across all repositories")
    total_entities: int = Field(
        default=0, description="Aggregate entity count across all repositories"
    )
    total_relations: int = Field(
        default=0, description="Aggregate relation count across all repositories"
    )
    is_writer: bool = Field(
        default=True,
        description="Whether this server instance holds the writer lock (indexing/watching)",
    )


class ReindexResponse(BaseModel):
    """Response from reindex_repository tool."""

    repository: str = Field(description="Name of the repository")
    status: str = Field(description="Result status: 'queued' or 'error'")
    files_queued: int = Field(description="Number of files queued for reindexing")
    message: str | None = Field(default=None, description="Status or error message")
