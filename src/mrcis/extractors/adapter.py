"""Adapter for legacy extractors using old signature.

Provides backward compatibility during migration to context-based interface.
"""

from pathlib import Path
from typing import Any

from mrcis.extractors.context import ExtractionContext
from mrcis.models.extraction import ExtractionResult


class LegacyExtractorAdapter:
    """Adapts legacy extractors to use the new context-based interface.

    Wraps extractors that use the old signature:
        async def extract(file_path: Path, file_id: UUID, repo_id: UUID)

    And provides the new signature:
        async def extract_with_context(context: ExtractionContext)

    This enables gradual migration - new code can use the context-based
    interface while old extractors continue to work during migration.

    Usage:
        legacy_extractor = PythonExtractor()
        adapted = LegacyExtractorAdapter(legacy_extractor)
        result = await adapted.extract_with_context(context)
    """

    def __init__(self, legacy_extractor: Any) -> None:
        """Initialize adapter with legacy extractor.

        Args:
            legacy_extractor: Extractor using old extract(path, file_id, repo_id) signature.
        """
        self._extractor = legacy_extractor

    async def extract_with_context(self, context: ExtractionContext) -> ExtractionResult:
        """Extract using context object by unpacking to legacy signature.

        Args:
            context: ExtractionContext with file information.

        Returns:
            ExtractionResult from the legacy extractor.
        """
        # Unpack context to legacy signature
        result: ExtractionResult = await self._extractor.extract(
            context.file_path,
            context.file_id,
            context.repository_id,
        )
        return result

    def supports(self, file_path: Path) -> bool:
        """Delegate to legacy extractor."""
        result: bool = self._extractor.supports(file_path)
        return result

    def get_supported_extensions(self) -> set[str]:
        """Delegate to legacy extractor."""
        extensions: set[str] = self._extractor.get_supported_extensions()
        return extensions
