"""Tests for EmbeddingConfig model."""

import pytest
from pydantic import ValidationError

from mrcis.config.models import EmbeddingConfig


def test_embedding_config_defaults() -> None:
    """Test EmbeddingConfig has correct defaults."""
    config = EmbeddingConfig()
    assert config.provider == "openai_compatible"
    assert config.api_url == "http://localhost:11434/v1"
    assert config.api_key == "ollama"
    assert config.model == "mxbai-embed-large"
    assert config.dimensions == 1024
    assert config.batch_size == 100
    assert config.timeout_seconds == 30.0
    assert config.append_eos_token is False
    assert config.eos_token == "</s>"


def test_embedding_config_custom_values() -> None:
    """Test EmbeddingConfig accepts custom values."""
    config = EmbeddingConfig(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="text-embedding-3-small",
        dimensions=1536,
        batch_size=50,
    )
    assert config.api_url == "https://api.openai.com/v1"
    assert config.api_key == "sk-test"
    assert config.model == "text-embedding-3-small"
    assert config.dimensions == 1536
    assert config.batch_size == 50


def test_embedding_config_url_validation() -> None:
    """Test EmbeddingConfig validates URL format."""
    # Valid URLs
    EmbeddingConfig(api_url="http://localhost:11434/v1")
    EmbeddingConfig(api_url="https://api.openai.com/v1")

    # Invalid URLs
    with pytest.raises(ValidationError):
        EmbeddingConfig(api_url="not-a-url")
    with pytest.raises(ValidationError):
        EmbeddingConfig(api_url="ftp://invalid.com")


def test_embedding_config_strips_trailing_slash() -> None:
    """Test EmbeddingConfig strips trailing slash from URL."""
    config = EmbeddingConfig(api_url="http://localhost:11434/v1/")
    assert config.api_url == "http://localhost:11434/v1"


def test_embedding_config_dimensions_range() -> None:
    """Test EmbeddingConfig validates dimensions range."""
    # Valid dimensions
    EmbeddingConfig(dimensions=64)
    EmbeddingConfig(dimensions=4096)

    # Invalid dimensions
    with pytest.raises(ValidationError):
        EmbeddingConfig(dimensions=63)
    with pytest.raises(ValidationError):
        EmbeddingConfig(dimensions=4097)


def test_embedding_config_batch_size_range() -> None:
    """Test EmbeddingConfig validates batch size range."""
    # Valid batch sizes
    EmbeddingConfig(batch_size=1)
    EmbeddingConfig(batch_size=1000)

    # Invalid batch sizes
    with pytest.raises(ValidationError):
        EmbeddingConfig(batch_size=0)
    with pytest.raises(ValidationError):
        EmbeddingConfig(batch_size=1001)
