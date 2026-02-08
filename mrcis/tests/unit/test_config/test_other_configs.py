"""Tests for ParserConfig, IndexingConfig, and LoggingConfig models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from mrcis.config.models import IndexingConfig, LoggingConfig, ParserConfig


class TestParserConfig:
    """Tests for ParserConfig."""

    def test_parser_config_defaults(self) -> None:
        """Test ParserConfig has correct defaults."""
        config = ParserConfig()
        assert config.max_chunk_chars == 4000
        assert config.chunk_overlap_chars == 200
        assert config.extract_docstrings is True
        assert config.extract_comments is False

    def test_parser_config_custom_values(self) -> None:
        """Test ParserConfig accepts custom values."""
        config = ParserConfig(
            max_chunk_chars=8000,
            chunk_overlap_chars=500,
            extract_docstrings=False,
            extract_comments=True,
        )
        assert config.max_chunk_chars == 8000
        assert config.chunk_overlap_chars == 500

    def test_parser_config_chunk_range(self) -> None:
        """Test ParserConfig validates chunk size range."""
        # Valid
        ParserConfig(max_chunk_chars=500)
        ParserConfig(max_chunk_chars=32000)

        # Invalid
        with pytest.raises(ValidationError):
            ParserConfig(max_chunk_chars=499)
        with pytest.raises(ValidationError):
            ParserConfig(max_chunk_chars=32001)


class TestIndexingConfig:
    """Tests for IndexingConfig."""

    def test_indexing_config_defaults(self) -> None:
        """Test IndexingConfig has correct defaults."""
        config = IndexingConfig()
        assert config.batch_size == 50
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 5.0
        assert config.resolution_interval_seconds == 60
        assert config.watch_debounce_ms == 500

    def test_indexing_config_custom_values(self) -> None:
        """Test IndexingConfig accepts custom values."""
        config = IndexingConfig(
            batch_size=100,
            max_retries=5,
            resolution_interval_seconds=120,
        )
        assert config.batch_size == 100
        assert config.max_retries == 5
        assert config.resolution_interval_seconds == 120

    def test_indexing_config_batch_range(self) -> None:
        """Test IndexingConfig validates batch size range."""
        # Valid
        IndexingConfig(batch_size=1)
        IndexingConfig(batch_size=500)

        # Invalid
        with pytest.raises(ValidationError):
            IndexingConfig(batch_size=0)
        with pytest.raises(ValidationError):
            IndexingConfig(batch_size=501)


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_logging_config_defaults(self) -> None:
        """Test LoggingConfig has correct defaults."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "console"
        assert config.file is None
        assert config.rotation == "10 MB"
        assert config.retention == "7 days"

    def test_logging_config_custom_values(self) -> None:
        """Test LoggingConfig accepts custom values."""
        config = LoggingConfig(
            level="DEBUG",
            format="json",
            file=Path("/var/log/mrcis.log"),
            rotation="50 MB",
            retention="30 days",
        )
        assert config.level == "DEBUG"
        assert config.format == "json"
        assert config.file == Path("/var/log/mrcis.log")

    def test_logging_config_level_validation(self) -> None:
        """Test LoggingConfig validates log level."""
        # Valid levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            LoggingConfig(level=level)

        # Invalid level
        with pytest.raises(ValidationError):
            LoggingConfig(level="TRACE")
