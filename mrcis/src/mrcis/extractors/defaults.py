"""Default extractor instances for the registry.

This module provides the standard set of built-in extractors.
Separating defaults from the registry allows the registry to follow
the Open/Closed Principle - open for extension (add new extractors)
but closed for modification (don't need to edit registry code).
"""

from mrcis.extractors.adapter import LegacyExtractorAdapter
from mrcis.extractors.base import ExtractorProtocol
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


def get_default_extractors() -> list[ExtractorProtocol]:
    """Get the default set of built-in extractors.

    Returns:
        List of extractor instances for all supported languages and file types.

    Note:
        This list can be extended by users to add custom extractors without
        modifying the registry or this module. Simply call:

            registry = ExtractorRegistry()
            extractors = get_default_extractors()
            extractors.append(MyCustomExtractor())
            registry.register_many(extractors)
    """
    return [
        # Language-specific extractors (TreeSitterExtractor-based, already support context)
        PythonExtractor(),
        TypeScriptExtractor(),
        JavaScriptExtractor(),
        GoExtractor(),
        RustExtractor(),
        RubyExtractor(),
        JavaExtractor(),
        KotlinExtractor(),
        DockerfileExtractor(),
        # Configuration extractors (wrapped for compatibility)
        LegacyExtractorAdapter(JSONExtractor()),
        LegacyExtractorAdapter(YAMLExtractor()),
        LegacyExtractorAdapter(TOMLExtractor()),
        # Markup extractors (wrapped for compatibility)
        LegacyExtractorAdapter(HTMLExtractor()),
        LegacyExtractorAdapter(MarkdownExtractor()),
    ]
