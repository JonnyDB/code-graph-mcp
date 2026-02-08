"""Tests for config loader."""

from pathlib import Path

import pytest

from mrcis.config.loader import load_config


@pytest.fixture
def sample_config_yaml(tmp_path: Path) -> Path:
    """Create a sample config YAML file."""
    config_content = """
server:
  transport: stdio
  port: 9000

embedding:
  api_url: http://localhost:1234/v1
  model: custom-embed

storage:
  data_directory: /tmp/mrcis

logging:
  level: DEBUG
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)
    return config_path


@pytest.fixture
def config_with_repos(tmp_path: Path) -> Path:
    """Create config with repository definitions."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    config_content = f"""
repositories:
  - name: test-repo
    path: {repo_path}
    branch: develop
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)
    return config_path


def test_load_config_defaults() -> None:
    """Test load_config returns defaults when no path given."""
    config = load_config(None)
    assert config.server.transport == "sse"
    assert config.embedding.model == "mxbai-embed-large"


def test_load_config_from_yaml(sample_config_yaml: Path) -> None:
    """Test load_config loads from YAML file."""
    config = load_config(sample_config_yaml)
    assert config.server.transport == "stdio"
    assert config.server.port == 9000
    assert config.embedding.api_url == "http://localhost:1234/v1"
    assert config.embedding.model == "custom-embed"
    assert config.logging.level == "DEBUG"


def test_load_config_with_repositories(config_with_repos: Path) -> None:
    """Test load_config loads repository definitions."""
    config = load_config(config_with_repos)
    assert len(config.repositories) == 1
    assert config.repositories[0].name == "test-repo"
    assert config.repositories[0].branch == "develop"


def test_load_config_file_not_found() -> None:
    """Test load_config raises error for missing file."""
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    """Test load_config raises error for invalid YAML."""
    config_path = tmp_path / "bad.yaml"
    config_path.write_text("invalid: yaml: content: [")

    with pytest.raises(ValueError) as exc_info:
        load_config(config_path)
    assert "Invalid YAML" in str(exc_info.value)
