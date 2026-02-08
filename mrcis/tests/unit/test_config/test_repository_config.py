"""Tests for RepositoryConfig model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from mrcis.config.models import RepositoryConfig


@pytest.fixture
def existing_path(tmp_path: Path) -> Path:
    """Create a directory that exists."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    return repo_path


def test_repository_config_required_fields(existing_path: Path) -> None:
    """Test RepositoryConfig requires name and path."""
    config = RepositoryConfig(name="my-repo", path=existing_path)
    assert config.name == "my-repo"
    assert config.path == existing_path


def test_repository_config_defaults(existing_path: Path) -> None:
    """Test RepositoryConfig has correct defaults."""
    config = RepositoryConfig(name="my-repo", path=existing_path)
    assert config.branch == "main"
    assert config.depends_on == []
    assert config.include_patterns is None
    assert config.exclude_patterns is None


def test_repository_config_validates_path_exists(tmp_path: Path) -> None:
    """Test RepositoryConfig validates path exists."""
    nonexistent = tmp_path / "does_not_exist"

    with pytest.raises(ValidationError) as exc_info:
        RepositoryConfig(name="my-repo", path=nonexistent)
    assert "does not exist" in str(exc_info.value)


def test_repository_config_name_length() -> None:
    """Test RepositoryConfig validates name length."""
    # Empty name should fail
    with pytest.raises(ValidationError):
        RepositoryConfig(name="", path=Path("/tmp"))

    # Name over 100 chars should fail
    with pytest.raises(ValidationError):
        RepositoryConfig(name="a" * 101, path=Path("/tmp"))


def test_repository_config_expands_path(existing_path: Path) -> None:
    """Test RepositoryConfig expands and resolves path."""
    config = RepositoryConfig(name="my-repo", path=existing_path)
    assert config.path.is_absolute()


def test_repository_config_with_depends_on(existing_path: Path) -> None:
    """Test RepositoryConfig accepts depends_on list."""
    config = RepositoryConfig(
        name="user-service",
        path=existing_path,
        depends_on=["shared-sdk", "common-utils"],
    )
    assert config.depends_on == ["shared-sdk", "common-utils"]


def test_repository_config_with_patterns(existing_path: Path) -> None:
    """Test RepositoryConfig accepts include/exclude patterns."""
    config = RepositoryConfig(
        name="my-repo",
        path=existing_path,
        include_patterns=["**/*.py"],
        exclude_patterns=["**/test_*.py"],
    )
    assert config.include_patterns == ["**/*.py"]
    assert config.exclude_patterns == ["**/test_*.py"]
