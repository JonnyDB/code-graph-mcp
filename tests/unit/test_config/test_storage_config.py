"""Tests for StorageConfig model."""

from pathlib import Path

from mrcis.config.models import StorageConfig


def test_storage_config_defaults() -> None:
    """Test StorageConfig has correct defaults."""
    config = StorageConfig()
    assert config.data_directory == Path("~/.mrcis").expanduser()
    assert config.vector_table_name == "code_vectors"
    assert config.state_db_name == "state.db"


def test_storage_config_custom_values() -> None:
    """Test StorageConfig accepts custom values."""
    config = StorageConfig(
        data_directory=Path("/tmp/mrcis"),
        vector_table_name="my_vectors",
        state_db_name="my_state.db",
    )
    assert config.data_directory == Path("/tmp/mrcis").resolve()
    assert config.vector_table_name == "my_vectors"
    assert config.state_db_name == "my_state.db"


def test_storage_config_expands_user_path() -> None:
    """Test StorageConfig expands ~ in paths."""
    config = StorageConfig(data_directory=Path("~/custom/path"))
    assert "~" not in str(config.data_directory)
    assert config.data_directory.is_absolute()
