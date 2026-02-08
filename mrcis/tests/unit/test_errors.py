"""Tests for MRCIS error types."""

from mrcis.errors import (
    ConfigurationError,
    EmbeddingError,
    ExtractionError,
    MRCISError,
    ResolutionError,
    StorageError,
)


class TestErrorHierarchy:
    """Test error class hierarchy."""

    def test_all_errors_inherit_from_mrcis_error(self) -> None:
        """All custom errors should inherit from MRCISError."""
        assert issubclass(ConfigurationError, MRCISError)
        assert issubclass(StorageError, MRCISError)
        assert issubclass(ExtractionError, MRCISError)
        assert issubclass(EmbeddingError, MRCISError)
        assert issubclass(ResolutionError, MRCISError)

    def test_mrcis_error_inherits_from_exception(self) -> None:
        """MRCISError should inherit from Exception."""
        assert issubclass(MRCISError, Exception)


class TestExtractionError:
    """Test ExtractionError specifics."""

    def test_extraction_error_with_file_path(self) -> None:
        """ExtractionError should store file path."""
        error = ExtractionError("Parse failed", "/path/to/file.py")
        assert error.file_path == "/path/to/file.py"
        assert str(error) == "Parse failed"

    def test_extraction_error_recoverable_default(self) -> None:
        """ExtractionError should default to recoverable."""
        error = ExtractionError("Parse failed", "/path/to/file.py")
        assert error.recoverable is True

    def test_extraction_error_not_recoverable(self) -> None:
        """ExtractionError can be marked as not recoverable."""
        error = ExtractionError("Binary file", "/path/to/file.bin", recoverable=False)
        assert error.recoverable is False


class TestEmbeddingError:
    """Test EmbeddingError specifics."""

    def test_embedding_error_retryable_default(self) -> None:
        """EmbeddingError should default to retryable."""
        error = EmbeddingError("API timeout")
        assert error.retryable is True

    def test_embedding_error_not_retryable(self) -> None:
        """EmbeddingError can be marked as not retryable."""
        error = EmbeddingError("Invalid model", retryable=False)
        assert error.retryable is False
