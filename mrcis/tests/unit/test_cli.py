"""Tests for CLI entry point."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from mrcis.__main__ import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


def test_cli_help(runner: CliRunner) -> None:
    """Test CLI help command."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Multi-Repository Code Intelligence System" in result.output
    assert "serve" in result.output
    assert "init" in result.output
    assert "status" in result.output
    assert "reindex" in result.output


def test_cli_version(runner: CliRunner) -> None:
    """Test CLI version command."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_serve_command_help(runner: CliRunner) -> None:
    """Test serve command help text."""
    result = runner.invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    assert "Start the MCP server" in result.output
    assert "--config" in result.output
    assert "--transport" in result.output


def test_serve_command_invalid_transport(runner: CliRunner) -> None:
    """Test serve command with invalid transport."""
    result = runner.invoke(cli, ["serve", "--transport", "invalid"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output or "Error" in result.output


@patch("mrcis.config.loader.load_config")
@patch("mrcis.storage.state_db.StateDB")
def test_init_command(
    mock_state_db: MagicMock,
    mock_load_config: MagicMock,
    runner: CliRunner,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Test init command."""
    # Setup mocks
    mock_config = MagicMock()
    mock_config.storage.data_directory = tmp_path / "data"
    mock_config.storage.state_db_name = "test.db"
    mock_config.repositories = []
    mock_load_config.return_value = mock_config

    mock_db = AsyncMock()
    mock_state_db.return_value = mock_db

    result = runner.invoke(cli, ["init"])

    assert result.exit_code == 0
    assert "Database initialized" in result.output
    mock_load_config.assert_called_once_with(None)
    mock_db.initialize.assert_called_once()
    mock_db.close.assert_called_once()


@patch("mrcis.config.loader.load_config")
@patch("mrcis.storage.state_db.StateDB")
def test_status_command_no_db(
    mock_state_db: MagicMock,  # noqa: ARG001
    mock_load_config: MagicMock,
    runner: CliRunner,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Test status command when database doesn't exist."""
    # Setup mocks
    mock_config = MagicMock()
    mock_config.storage.data_directory = tmp_path / "data"
    mock_config.storage.state_db_name = "test.db"
    mock_load_config.return_value = mock_config

    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "Database not initialized" in result.output


@patch("mrcis.config.loader.load_config")
@patch("mrcis.storage.state_db.StateDB")
def test_status_command_no_repos(
    mock_state_db: MagicMock,
    mock_load_config: MagicMock,
    runner: CliRunner,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Test status command when no repositories exist."""
    # Setup mocks
    db_path = tmp_path / "data" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch()

    mock_config = MagicMock()
    mock_config.storage.data_directory = db_path.parent
    mock_config.storage.state_db_name = "test.db"
    mock_load_config.return_value = mock_config

    mock_db = AsyncMock()
    mock_db.get_all_repositories.return_value = []
    mock_state_db.return_value = mock_db

    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "No repositories found" in result.output
    mock_db.initialize.assert_called_once()
    mock_db.close.assert_called_once()


@patch("mrcis.config.loader.load_config")
@patch("mrcis.storage.state_db.StateDB")
def test_reindex_command_no_db(
    mock_state_db: MagicMock,  # noqa: ARG001
    mock_load_config: MagicMock,
    runner: CliRunner,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Test reindex command when database doesn't exist."""
    # Setup mocks
    mock_config = MagicMock()
    mock_config.storage.data_directory = tmp_path / "data"
    mock_config.storage.state_db_name = "test.db"
    mock_load_config.return_value = mock_config

    result = runner.invoke(cli, ["reindex", "test-repo"])

    assert result.exit_code == 0
    assert "Database not initialized" in result.output


@patch("mrcis.config.loader.load_config")
@patch("mrcis.storage.state_db.StateDB")
def test_reindex_command_repo_not_found(
    mock_state_db: MagicMock,
    mock_load_config: MagicMock,
    runner: CliRunner,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Test reindex command when repository doesn't exist."""
    # Setup mocks
    db_path = tmp_path / "data" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch()

    mock_config = MagicMock()
    mock_config.storage.data_directory = db_path.parent
    mock_config.storage.state_db_name = "test.db"
    mock_load_config.return_value = mock_config

    mock_db = AsyncMock()
    mock_db.get_repository_by_name.return_value = None
    mock_state_db.return_value = mock_db

    result = runner.invoke(cli, ["reindex", "test-repo"])

    assert result.exit_code == 0
    assert "Repository not found" in result.output
    mock_db.initialize.assert_called_once()
    mock_db.close.assert_called_once()


@patch("mrcis.config.loader.load_config")
@patch("mrcis.storage.state_db.StateDB")
def test_reindex_queues_all_files_without_force(
    mock_state_db: MagicMock,
    mock_load_config: MagicMock,
    runner: CliRunner,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Reindex without --force should still set ALL files to pending and queue them."""
    db_path = tmp_path / "data" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch()

    mock_config = MagicMock()
    mock_config.storage.data_directory = db_path.parent
    mock_config.storage.state_db_name = "test.db"
    mock_load_config.return_value = mock_config

    mock_repo = MagicMock()
    mock_repo.id = "repo-123"
    mock_repo.name = "test-repo"

    mock_db = AsyncMock()
    mock_db.get_repository_by_name.return_value = mock_repo
    mock_db.mark_repository_files_pending.return_value = 10
    mock_db.enqueue_pending_files.return_value = 10
    mock_state_db.return_value = mock_db

    result = runner.invoke(cli, ["reindex", "test-repo"])

    assert result.exit_code == 0
    assert "Marked 10 files as pending" in result.output
    assert "Enqueued 10 files for reindexing" in result.output

    # Verify new public API methods were called
    mock_db.mark_repository_files_pending.assert_called_once_with("repo-123", reset_failures=False)
    mock_db.enqueue_pending_files.assert_called_once_with("repo-123")


@patch("mrcis.config.loader.load_config")
@patch("mrcis.storage.state_db.StateDB")
def test_reindex_force_resets_failure_counts(
    mock_state_db: MagicMock,
    mock_load_config: MagicMock,
    runner: CliRunner,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Reindex with --force should also reset failure counts."""
    db_path = tmp_path / "data" / "test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch()

    mock_config = MagicMock()
    mock_config.storage.data_directory = db_path.parent
    mock_config.storage.state_db_name = "test.db"
    mock_load_config.return_value = mock_config

    mock_repo = MagicMock()
    mock_repo.id = "repo-123"
    mock_repo.name = "test-repo"

    mock_db = AsyncMock()
    mock_db.get_repository_by_name.return_value = mock_repo
    mock_db.mark_repository_files_pending.return_value = 10
    mock_db.enqueue_pending_files.return_value = 10
    mock_state_db.return_value = mock_db

    result = runner.invoke(cli, ["reindex", "test-repo", "--force"])

    assert result.exit_code == 0
    assert "Failure counts reset" in result.output

    # Verify new public API method was called with reset_failures=True
    mock_db.mark_repository_files_pending.assert_called_once_with("repo-123", reset_failures=True)
    mock_db.enqueue_pending_files.assert_called_once_with("repo-123")
