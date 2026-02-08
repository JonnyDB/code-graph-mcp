"""Extractor registry for routing files to appropriate extractors."""

from pathlib import Path
from uuid import UUID

from mrcis.extractors.base import ExtractorProtocol
from mrcis.extractors.context import ExtractionContext
from mrcis.extractors.defaults import get_default_extractors
from mrcis.models.extraction import ExtractionResult


class GenericExtractor:
    """Fallback extractor for unsupported file types."""

    def get_supported_extensions(self) -> set[str]:
        """Return empty set - matches nothing."""
        return set()

    def supports(self, _file_path: Path) -> bool:
        """Always returns False - use as fallback only."""
        return False

    async def extract_with_context(self, context: ExtractionContext) -> ExtractionResult:
        """Return empty extraction result."""
        return ExtractionResult(
            file_id=context.file_id,
            file_path=str(context.file_path),
            repository_id=context.repository_id,
            language="unknown",
        )

    async def extract(self, file_path: Path, file_id: UUID, repo_id: UUID) -> ExtractionResult:
        """Return empty extraction result (legacy method)."""
        context = ExtractionContext(
            file_path=file_path,
            file_id=file_id,
            repository_id=repo_id,
        )
        return await self.extract_with_context(context)


class ExtractorRegistry:
    """
    Registry for language-specific extractors.

    Routes files to appropriate extractors based on extension.
    Falls back to GenericExtractor for unsupported types.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._extractors: list[ExtractorProtocol] = []
        self._extension_map: dict[str, ExtractorProtocol] = {}
        self._fallback = GenericExtractor()

    def register(self, extractor: ExtractorProtocol) -> None:
        """Register an extractor."""
        self._extractors.append(extractor)
        for ext in extractor.get_supported_extensions():
            self._extension_map[ext.lower()] = extractor

    def register_many(self, extractors: list[ExtractorProtocol]) -> None:
        """Register multiple extractors at once.

        Args:
            extractors: List of extractor instances to register.
        """
        for extractor in extractors:
            self.register(extractor)

    def get_extractor(self, file_path: Path) -> ExtractorProtocol:
        """Get appropriate extractor for a file."""
        # First try extension-based lookup (fast path)
        ext = file_path.suffix.lower()
        if ext in self._extension_map:
            return self._extension_map[ext]

        # Fall back to checking supports() for extractors without extensions
        # (e.g., Dockerfile, Makefile, etc.)
        for extractor in self._extractors:
            if extractor.supports(file_path):
                return extractor

        return self._fallback

    def get_supported_extensions(self) -> set[str]:
        """Get all supported file extensions."""
        return set(self._extension_map.keys())

    @classmethod
    def create_default(cls) -> "ExtractorRegistry":
        """Create registry with all built-in extractors.

        Uses get_default_extractors() to obtain the standard set of extractors.
        This allows users to extend the defaults without modifying the registry.
        """
        registry = cls()
        registry.register_many(get_default_extractors())
        return registry
