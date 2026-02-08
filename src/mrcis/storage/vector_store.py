"""LanceDB vector storage for MRCIS."""

from typing import Any

import lancedb  # type: ignore[import-untyped]
from lancedb.pydantic import LanceModel, Vector  # type: ignore[import-untyped]


class CodeVector(LanceModel):  # type: ignore[misc]
    """
    Vector storage schema for code chunks.

    Each row represents an embeddable unit of code with
    rich metadata for filtering and retrieval.
    """

    # Identity
    id: str
    repository_id: str
    file_id: str

    # Content
    qualified_name: str
    simple_name: str
    entity_type: str
    language: str

    # Location
    file_path: str
    line_start: int
    line_end: int

    # Embedding (dimension set dynamically)
    vector: Vector(4)  # type: ignore[valid-type]  # Default, will be overridden
    embedding_text: str

    # Metadata for filtering
    visibility: str = "public"
    is_exported: bool = False
    has_docstring: bool = False

    # Searchable text fields
    signature: str | None = None
    docstring: str | None = None


def create_code_vector_model(dimensions: int) -> type[LanceModel]:
    """Create CodeVector model with specific dimensions."""

    class DynamicCodeVector(LanceModel):  # type: ignore[misc]
        """Code vector with dynamic dimensions."""

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
        vector: Vector(dimensions)  # type: ignore[valid-type]
        embedding_text: str
        visibility: str = "public"
        is_exported: bool = False
        has_docstring: bool = False
        signature: str | None = None
        docstring: str | None = None

    return DynamicCodeVector


def _escape_filter_value(value: Any) -> str:
    """
    Escape a value for use in LanceDB filter expressions.

    Escapes single quotes by doubling them to prevent SQL injection.

    Args:
        value: The value to escape.

    Returns:
        Escaped string value safe for filter expressions.
    """
    str_value = str(value)
    # Escape single quotes by doubling them (SQL standard)
    return str_value.replace("'", "''")


class VectorStore:
    """LanceDB vector storage operations."""

    def __init__(self, db_path: str, table_name: str, dimensions: int) -> None:
        """
        Initialize VectorStore.

        Args:
            db_path: Path to LanceDB directory.
            table_name: Name of the vectors table.
            dimensions: Embedding vector dimensions.
        """
        self.db_path = db_path
        self.table_name = table_name
        self.dimensions = dimensions
        self._db: lancedb.DBConnection | None = None
        self._table: lancedb.table.Table | None = None
        self._model = create_code_vector_model(dimensions)
        self.model = self._model

    def _get_table(self) -> lancedb.table.Table:
        """Get table, raising if not initialized."""
        if self._table is None:
            raise RuntimeError("VectorStore not initialized")
        return self._table

    async def initialize(self) -> None:
        """Create or open the vectors table."""
        self._db = lancedb.connect(self.db_path)

        # list_tables() returns ListTablesResponse with .tables attribute (list of strings)
        tables_response = self._db.list_tables()
        existing_tables = (
            tables_response.tables if hasattr(tables_response, "tables") else tables_response
        )
        if self.table_name not in existing_tables:
            # Create empty table with schema
            self._table = self._db.create_table(
                self.table_name,
                schema=self._model,
                mode="overwrite",
            )
        else:
            self._table = self._db.open_table(self.table_name)

    async def upsert_vectors(self, vectors: list[LanceModel]) -> int:
        """
        Insert or update vectors.

        Args:
            vectors: List of CodeVector instances.

        Returns:
            Number of vectors upserted.
        """
        if not vectors:
            return 0

        # Convert to dictionaries
        data = [v.model_dump() for v in vectors]

        table = self._get_table()

        # Delete existing vectors by ID before inserting new ones
        # This ensures proper upsert semantics without wiping the table
        ids = [v.id for v in vectors]
        for vector_id in ids:
            # Escape single quotes in ID to prevent injection
            escaped_id = vector_id.replace("'", "''")
            table.delete(f"id = '{escaped_id}'")

        # Insert the new/updated vectors
        table.add(data)
        return len(vectors)

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors.

        Args:
            query_vector: Query embedding.
            limit: Maximum results.
            filters: Column filters (e.g., {"language": "python"}).
            min_score: Minimum similarity score (0.0-1.0).

        Returns:
            List of results with _distance field.
        """
        table = self._get_table()
        query = table.search(query_vector).limit(limit)

        if filters:
            # Escape filter values to prevent injection
            filter_str = " AND ".join(
                f"{k} = '{_escape_filter_value(v)}'" for k, v in filters.items()
            )
            query = query.where(filter_str)

        results = query.to_list()

        # Filter by score (distance is inverse of similarity)
        return [r for r in results if (1 - r.get("_distance", 0)) >= min_score]

    async def delete_by_file(self, file_id: str) -> int:
        """Delete all vectors for a file."""
        table = self._get_table()
        escaped_file_id = _escape_filter_value(file_id)
        table.delete(f"file_id = '{escaped_file_id}'")
        return 0  # LanceDB doesn't easily return delete count

    async def delete_by_repository(self, repository_id: str) -> int:
        """Delete all vectors for a repository."""
        table = self._get_table()
        escaped_repo_id = _escape_filter_value(repository_id)
        table.delete(f"repository_id = '{escaped_repo_id}'")
        return 0
