"""Tests for FilesConfig model."""

import pytest
from pydantic import ValidationError

from mrcis.config.models import FilesConfig


def test_files_config_defaults() -> None:
    """Test FilesConfig has correct defaults."""
    config = FilesConfig()

    # Check include patterns have common languages
    assert "**/*.py" in config.include_patterns
    assert "**/*.ts" in config.include_patterns
    assert "**/*.tsx" in config.include_patterns
    assert "**/*.js" in config.include_patterns
    assert "**/*.go" in config.include_patterns
    assert "**/*.rs" in config.include_patterns
    assert "**/*.rb" in config.include_patterns

    # Check exclude patterns
    assert "**/node_modules/**" in config.exclude_patterns
    assert "**/.git/**" in config.exclude_patterns
    assert "**/__pycache__/**" in config.exclude_patterns

    # Check other defaults
    assert config.respect_gitignore is True
    assert config.max_file_size_kb == 1024


def test_files_config_custom_patterns() -> None:
    """Test FilesConfig accepts custom patterns."""
    config = FilesConfig(
        include_patterns=["**/*.py", "**/*.md"],
        exclude_patterns=["**/test/**"],
        respect_gitignore=False,
        max_file_size_kb=512,
    )

    assert config.include_patterns == ["**/*.py", "**/*.md"]
    assert config.exclude_patterns == ["**/test/**"]
    assert config.respect_gitignore is False
    assert config.max_file_size_kb == 512


def test_files_config_max_file_size_range() -> None:
    """Test FilesConfig validates max file size range."""
    # Valid sizes
    FilesConfig(max_file_size_kb=1)
    FilesConfig(max_file_size_kb=10240)

    # Invalid sizes
    with pytest.raises(ValidationError):
        FilesConfig(max_file_size_kb=0)
    with pytest.raises(ValidationError):
        FilesConfig(max_file_size_kb=10241)
