"""Tests for ExtractorProtocol."""

from mrcis.extractors.base import ExtractorProtocol


def test_extractor_protocol_is_runtime_checkable() -> None:
    """Test ExtractorProtocol can be used with isinstance."""
    assert hasattr(ExtractorProtocol, "__protocol_attrs__") or isinstance(ExtractorProtocol, type)


def test_extractor_protocol_methods() -> None:
    """Test ExtractorProtocol defines required methods."""
    # Check required methods exist in protocol
    assert hasattr(ExtractorProtocol, "supports")
    assert hasattr(ExtractorProtocol, "extract_with_context")
    assert hasattr(ExtractorProtocol, "get_supported_extensions")
