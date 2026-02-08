"""Tests for LegacyExtractorAdapter."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from mrcis.extractors.adapter import LegacyExtractorAdapter
from mrcis.extractors.context import ExtractionContext
from mrcis.models.extraction import ExtractionResult


class MockLegacyExtractor:
    """Mock extractor using old signature."""

    def __init__(self) -> None:
        self.extract_called_with: tuple[Path, UUID, UUID] | None = None

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix == ".mock"

    async def extract(self, file_path: Path, file_id: UUID, repo_id: UUID) -> ExtractionResult:
        """Old-style extract method."""
        self.extract_called_with = (file_path, file_id, repo_id)
        return ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="mock",
        )

    def get_supported_extensions(self) -> set[str]:
        return {".mock"}


class TestLegacyExtractorAdapter:
    """Tests for LegacyExtractorAdapter class."""

    @pytest.mark.asyncio
    async def test_adapter_calls_legacy_extract(self) -> None:
        """Adapter should call legacy extract() method with unpacked context."""
        legacy = MockLegacyExtractor()
        adapter = LegacyExtractorAdapter(legacy)

        file_path = Path("/repo/test.mock")
        file_id = uuid4()
        repo_id = uuid4()
        context = ExtractionContext(
            file_path=file_path,
            file_id=file_id,
            repository_id=repo_id,
        )

        result = await adapter.extract_with_context(context)

        # Should have called legacy extract with unpacked values
        assert legacy.extract_called_with == (file_path, file_id, repo_id)
        assert result.file_id == file_id
        assert result.repository_id == repo_id
        assert result.language == "mock"

    @pytest.mark.asyncio
    async def test_adapter_returns_extraction_result(self) -> None:
        """Adapter should return the result from legacy extractor."""
        legacy = MockLegacyExtractor()
        adapter = LegacyExtractorAdapter(legacy)

        context = ExtractionContext(
            file_path=Path("/repo/test.mock"),
            file_id=uuid4(),
            repository_id=uuid4(),
        )

        result = await adapter.extract_with_context(context)

        assert isinstance(result, ExtractionResult)
        assert result.language == "mock"

    def test_adapter_delegates_supports(self) -> None:
        """Adapter should delegate supports() to legacy extractor."""
        legacy = MockLegacyExtractor()
        adapter = LegacyExtractorAdapter(legacy)

        assert adapter.supports(Path("test.mock")) is True
        assert adapter.supports(Path("test.py")) is False

    def test_adapter_delegates_get_supported_extensions(self) -> None:
        """Adapter should delegate get_supported_extensions() to legacy extractor."""
        legacy = MockLegacyExtractor()
        adapter = LegacyExtractorAdapter(legacy)

        extensions = adapter.get_supported_extensions()
        assert extensions == {".mock"}

    @pytest.mark.asyncio
    async def test_adapter_works_with_context_containing_language(self) -> None:
        """Adapter should work even when context has language field."""
        legacy = MockLegacyExtractor()
        adapter = LegacyExtractorAdapter(legacy)

        context = ExtractionContext(
            file_path=Path("/repo/test.mock"),
            file_id=uuid4(),
            repository_id=uuid4(),
            language="python",  # Extra field ignored by legacy extractor
        )

        result = await adapter.extract_with_context(context)
        assert isinstance(result, ExtractionResult)

    @pytest.mark.asyncio
    async def test_adapter_works_with_context_containing_source_bytes(self) -> None:
        """Adapter should work even when context has source_bytes field."""
        legacy = MockLegacyExtractor()
        adapter = LegacyExtractorAdapter(legacy)

        context = ExtractionContext(
            file_path=Path("/repo/test.mock"),
            file_id=uuid4(),
            repository_id=uuid4(),
            source_bytes=b"print('hello')",  # Extra field ignored
        )

        result = await adapter.extract_with_context(context)
        assert isinstance(result, ExtractionResult)
