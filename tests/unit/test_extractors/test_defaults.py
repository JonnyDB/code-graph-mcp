"""Tests for default extractor configuration."""

from mrcis.extractors.defaults import get_default_extractors
from mrcis.extractors.dockerfile import DockerfileExtractor
from mrcis.extractors.go import GoExtractor
from mrcis.extractors.html_extractor import HTMLExtractor
from mrcis.extractors.java import JavaExtractor
from mrcis.extractors.javascript import JavaScriptExtractor
from mrcis.extractors.json_extractor import JSONExtractor
from mrcis.extractors.kotlin import KotlinExtractor
from mrcis.extractors.markdown import MarkdownExtractor
from mrcis.extractors.python import PythonExtractor
from mrcis.extractors.ruby import RubyExtractor
from mrcis.extractors.rust import RustExtractor
from mrcis.extractors.toml_extractor import TOMLExtractor
from mrcis.extractors.typescript import TypeScriptExtractor
from mrcis.extractors.yaml_extractor import YAMLExtractor


class TestGetDefaultExtractors:
    """Tests for get_default_extractors function."""

    def test_returns_list_of_extractors(self) -> None:
        """Should return a list of extractor instances."""
        extractors = get_default_extractors()

        assert isinstance(extractors, list)
        assert len(extractors) > 0

    def test_includes_language_extractors(self) -> None:
        """Should include all language-specific extractors."""
        extractors = get_default_extractors()
        extractor_types = [type(e) for e in extractors]

        # Check for language extractors
        assert PythonExtractor in extractor_types
        assert TypeScriptExtractor in extractor_types
        assert JavaScriptExtractor in extractor_types
        assert GoExtractor in extractor_types
        assert RustExtractor in extractor_types
        assert RubyExtractor in extractor_types
        assert JavaExtractor in extractor_types
        assert KotlinExtractor in extractor_types

    def test_includes_config_extractors(self) -> None:
        """Should include configuration file extractors (wrapped in adapters)."""
        extractors = get_default_extractors()

        # Config extractors are wrapped in LegacyExtractorAdapter
        # Check by inspecting wrapped extractors
        wrapped_types = []
        for e in extractors:
            if hasattr(e, "_extractor"):
                wrapped_types.append(type(e._extractor))

        assert JSONExtractor in wrapped_types
        assert YAMLExtractor in wrapped_types
        assert TOMLExtractor in wrapped_types

    def test_includes_markup_extractors(self) -> None:
        """Should include markup file extractors (wrapped in adapters)."""
        extractors = get_default_extractors()

        # Markup extractors are wrapped in LegacyExtractorAdapter
        # Check by inspecting wrapped extractors
        wrapped_types = []
        for e in extractors:
            if hasattr(e, "_extractor"):
                wrapped_types.append(type(e._extractor))

        assert HTMLExtractor in wrapped_types
        assert MarkdownExtractor in wrapped_types

    def test_includes_specialized_extractors(self) -> None:
        """Should include specialized extractors."""
        extractors = get_default_extractors()
        extractor_types = [type(e) for e in extractors]

        assert DockerfileExtractor in extractor_types

    def test_returns_14_extractors(self) -> None:
        """Should return exactly 14 default extractors."""
        extractors = get_default_extractors()

        # 8 language + 3 config + 2 markup + 1 specialized = 14
        assert len(extractors) == 14

    def test_returns_new_instances_each_call(self) -> None:
        """Should return new extractor instances on each call."""
        extractors1 = get_default_extractors()
        extractors2 = get_default_extractors()

        # Different lists
        assert extractors1 is not extractors2

        # Different instances (first extractor as example)
        assert extractors1[0] is not extractors2[0]
