"""Tests for root Config model."""

from pathlib import Path

import pytest

from mrcis.config.models import Config, RepositoryConfig


@pytest.fixture
def existing_repo_path(tmp_path: Path) -> Path:
    """Create a directory that exists."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    return repo_path


def test_config_defaults() -> None:
    """Test Config has correct defaults for all sections."""
    config = Config()

    # Check all sections exist with defaults
    assert config.server.transport == "sse"
    assert config.embedding.provider == "openai_compatible"
    assert config.storage.vector_table_name == "code_vectors"
    assert config.repositories == []
    assert config.files.respect_gitignore is True
    assert config.parser.extract_docstrings is True
    assert config.indexing.batch_size == 50
    assert config.logging.level == "INFO"


def test_config_with_repositories(existing_repo_path: Path) -> None:
    """Test Config with repository list."""
    repo = RepositoryConfig(name="my-repo", path=existing_repo_path)
    config = Config(repositories=[repo])

    assert len(config.repositories) == 1
    assert config.repositories[0].name == "my-repo"


def test_config_env_prefix() -> None:
    """Test Config supports environment variable prefix."""
    # Config should have MRCIS_ prefix for env vars
    assert Config.model_config.get("env_prefix") == "MRCIS_"


def test_config_nested_env_delimiter() -> None:
    """Test Config supports nested env delimiter."""
    # Config should use __ for nested env vars
    assert Config.model_config.get("env_nested_delimiter") == "__"
