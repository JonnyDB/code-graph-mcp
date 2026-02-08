"""Port interface for vector storage services."""

from typing import Any, Protocol


class VectorStorePort(Protocol):
    """Protocol for vector storage and retrieval.

    Implementations must provide methods to store vectors and perform
    similarity search operations.
    """

    @property
    def model(self) -> Any:
        """Get the vector model class for creating vectors."""
        ...

    async def upsert_vectors(self, vectors: list[Any]) -> int:
        """Insert or update vectors in the store.

        Args:
            vectors: List of vector model instances (LanceModel or similar)

        Returns:
            Number of vectors successfully upserted

        Raises:
            VectorStoreError: If upsert operation fails
        """
        ...

    async def search(
        self,
        query_vector: list[float],
        *,
        limit: int,
        filters: dict[str, Any] | None = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search for vectors similar to the query.

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results to return
            filters: Optional metadata filters
            min_score: Minimum similarity score threshold

        Returns:
            List of matching records with scores and metadata

        Raises:
            VectorStoreError: If search operation fails
        """
        ...

    async def delete_by_file(self, file_id: str) -> int:
        """Delete all vectors associated with a file.

        Args:
            file_id: ID of the file whose vectors should be deleted

        Returns:
            Number of vectors deleted

        Raises:
            VectorStoreError: If delete operation fails
        """
        ...

    async def delete_by_repository(self, repository_id: str) -> int:
        """Delete all vectors associated with a repository.

        Args:
            repository_id: ID of the repository whose vectors should be deleted

        Returns:
            Number of vectors deleted

        Raises:
            VectorStoreError: If delete operation fails
        """
        ...
