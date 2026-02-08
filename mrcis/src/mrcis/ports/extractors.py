"""Port interfaces for code extraction services."""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from mrcis.models.extraction import ExtractionResult

if TYPE_CHECKING:
    from mrcis.extractors.base import ExtractorProtocol


class ExtractorPort(Protocol):
    """Protocol for code extractors.

    Extractors parse source files and extract code entities and relationships.
    """

    @property
    def language(self) -> str:
        """Language this extractor handles (e.g., 'python', 'typescript')."""
        ...

    async def extract(
        self,
        file_path: Path,
        file_id: str | UUID,
        repository_id: str | UUID,
        *,
        content: str | None = None,
    ) -> ExtractionResult:
        """Extract entities and relations from a file.

        Args:
            file_path: Path to the file
            file_id: File's database ID
            repository_id: Repository's database ID
            content: Optional file content (reads from disk if None)

        Returns:
            Extraction result with entities and relations

        Raises:
            ExtractionError: If extraction fails
        """
        ...


class ExtractorRegistryPort(Protocol):
    """Protocol for extractor registry.

    Registry manages available extractors and dispatches to the
    appropriate extractor based on file type.
    """

    def register(self, extractor: "ExtractorProtocol") -> None:
        """Register an extractor."""
        ...

    def get_extractor(self, file_path: Path) -> "ExtractorProtocol | None":
        """Get extractor for a file path."""
        ...

    def get_supported_extensions(self) -> set[str]:
        """Get all supported file extensions."""
        ...
