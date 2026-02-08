"""Tests for ExtractorRegistry."""

from pathlib import Path

from mrcis.extractors.python import PythonExtractor
from mrcis.extractors.registry import ExtractorRegistry


class TestExtractorRegistry:
    """Tests for ExtractorRegistry."""

    def test_create_default_registry(self) -> None:
        """Test creating default registry with built-in extractors."""
        registry = ExtractorRegistry.create_default()

        # Should have at least Python extractor
        extractor = registry.get_extractor(Path("module.py"))
        assert extractor is not None

    def test_get_extractor_for_python(self) -> None:
        """Test getting extractor for Python file."""
        registry = ExtractorRegistry.create_default()
        extractor = registry.get_extractor(Path("module.py"))

        assert isinstance(extractor, PythonExtractor)

    def test_get_extractor_for_unknown_returns_fallback(self) -> None:
        """Test unknown extension returns fallback extractor."""
        registry = ExtractorRegistry.create_default()
        extractor = registry.get_extractor(Path("file.xyz"))

        # Should return fallback, not None
        assert extractor is not None

    def test_register_custom_extractor(self) -> None:
        """Test registering a custom extractor."""
        registry = ExtractorRegistry()

        # Create a mock extractor
        class MockExtractor:
            def get_supported_extensions(self) -> set[str]:
                return {".custom"}

            def supports(self, path: Path) -> bool:
                return path.suffix == ".custom"

        mock = MockExtractor()
        registry.register(mock)

        extractor = registry.get_extractor(Path("file.custom"))
        assert extractor is mock

    def test_get_supported_extensions(self) -> None:
        """Test getting all supported extensions."""
        registry = ExtractorRegistry.create_default()
        extensions = registry.get_supported_extensions()

        assert ".py" in extensions
        assert ".pyi" in extensions

    def test_register_many_with_empty_list(self) -> None:
        """Test register_many with empty list."""
        registry = ExtractorRegistry()
        registry.register_many([])

        # Should have no extractors registered
        extensions = registry.get_supported_extensions()
        assert len(extensions) == 0

    def test_register_many_with_single_extractor(self) -> None:
        """Test register_many with a single extractor."""
        registry = ExtractorRegistry()

        class MockExtractor:
            def get_supported_extensions(self) -> set[str]:
                return {".mock"}

            def supports(self, path: Path) -> bool:
                return path.suffix == ".mock"

        mock = MockExtractor()
        registry.register_many([mock])

        extractor = registry.get_extractor(Path("file.mock"))
        assert extractor is mock

    def test_register_many_with_multiple_extractors(self) -> None:
        """Test register_many with multiple extractors."""
        registry = ExtractorRegistry()

        class MockExtractor1:
            def get_supported_extensions(self) -> set[str]:
                return {".mock1"}

            def supports(self, path: Path) -> bool:
                return path.suffix == ".mock1"

        class MockExtractor2:
            def get_supported_extensions(self) -> set[str]:
                return {".mock2"}

            def supports(self, path: Path) -> bool:
                return path.suffix == ".mock2"

        mock1 = MockExtractor1()
        mock2 = MockExtractor2()
        registry.register_many([mock1, mock2])

        # Both extractors should be registered
        extractor1 = registry.get_extractor(Path("file.mock1"))
        extractor2 = registry.get_extractor(Path("file.mock2"))
        assert extractor1 is mock1
        assert extractor2 is mock2

    def test_register_many_equivalent_to_multiple_register(self) -> None:
        """Test register_many produces same result as multiple register calls."""
        registry1 = ExtractorRegistry()
        registry2 = ExtractorRegistry()

        class MockExtractor1:
            def get_supported_extensions(self) -> set[str]:
                return {".mock1"}

            def supports(self, path: Path) -> bool:
                return path.suffix == ".mock1"

        class MockExtractor2:
            def get_supported_extensions(self) -> set[str]:
                return {".mock2"}

            def supports(self, path: Path) -> bool:
                return path.suffix == ".mock2"

        mock1 = MockExtractor1()
        mock2 = MockExtractor2()

        # Register individually
        registry1.register(mock1)
        registry1.register(mock2)

        # Register using register_many
        registry2.register_many([mock1, mock2])

        # Should have same supported extensions
        assert registry1.get_supported_extensions() == registry2.get_supported_extensions()
