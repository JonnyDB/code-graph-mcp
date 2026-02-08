"""Tests for path utilities."""

from pathlib import Path

import pytest

from mrcis.utils.paths import GitignoreFilter, normalize_path


class TestGitignoreFilter:
    """Test GitignoreFilter class."""

    @pytest.fixture
    def repo_with_gitignore(self, tmp_path: Path) -> Path:
        """Create a repo with .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            """
# Python
__pycache__/
*.pyc
.venv/

# Node
node_modules/

# IDE
.idea/
.vscode/
"""
        )
        return tmp_path

    def test_ignores_pycache(self, repo_with_gitignore: Path) -> None:
        """Should ignore __pycache__ directories."""
        filter_ = GitignoreFilter(repo_with_gitignore)
        pycache_file = repo_with_gitignore / "__pycache__" / "module.cpython-311.pyc"

        assert filter_.is_ignored(pycache_file) is True

    def test_ignores_pyc_files(self, repo_with_gitignore: Path) -> None:
        """Should ignore .pyc files."""
        filter_ = GitignoreFilter(repo_with_gitignore)
        pyc_file = repo_with_gitignore / "module.pyc"

        assert filter_.is_ignored(pyc_file) is True

    def test_ignores_node_modules(self, repo_with_gitignore: Path) -> None:
        """Should ignore node_modules directory."""
        filter_ = GitignoreFilter(repo_with_gitignore)
        node_file = repo_with_gitignore / "node_modules" / "lodash" / "index.js"

        assert filter_.is_ignored(node_file) is True

    def test_allows_normal_files(self, repo_with_gitignore: Path) -> None:
        """Should allow normal source files."""
        filter_ = GitignoreFilter(repo_with_gitignore)
        py_file = repo_with_gitignore / "src" / "main.py"

        assert filter_.is_ignored(py_file) is False

    def test_handles_no_gitignore(self, tmp_path: Path) -> None:
        """Should handle repos without .gitignore."""
        filter_ = GitignoreFilter(tmp_path)
        any_file = tmp_path / "any_file.py"

        assert filter_.is_ignored(any_file) is False

    def test_always_ignores_git_directory(self, tmp_path: Path) -> None:
        """Should always ignore .git directory."""
        filter_ = GitignoreFilter(tmp_path)
        git_file = tmp_path / ".git" / "config"

        assert filter_.is_ignored(git_file) is True

    def test_always_ignores_mrcis_data_directory(self, tmp_path: Path) -> None:
        """Should always ignore .mrcis data directory."""
        filter_ = GitignoreFilter(tmp_path)
        mrcis_file = tmp_path / ".mrcis" / "vectors" / "code_vectors.lance" / "foo.txn"

        assert filter_.is_ignored(mrcis_file) is True

    def test_finds_gitignore_at_git_root(self, tmp_path: Path) -> None:
        """Should load .gitignore from git root when repo_root is a subdirectory."""
        # Simulate: git root is tmp_path, repo root is tmp_path/subdir
        (tmp_path / ".git").mkdir()
        (tmp_path / ".gitignore").write_text("*.log\nbuild/\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        filter_ = GitignoreFilter(subdir)

        # Pattern from git root's .gitignore should apply
        assert filter_.is_ignored(subdir / "debug.log") is True
        assert filter_.is_ignored(subdir / "build" / "output.js") is True
        # Normal files should pass
        assert filter_.is_ignored(subdir / "main.py") is False

    def test_loads_both_git_root_and_repo_root_gitignore(self, tmp_path: Path) -> None:
        """Should load .gitignore from both git root and repo root."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".gitignore").write_text("*.log\n")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / ".gitignore").write_text("*.tmp\n")

        filter_ = GitignoreFilter(subdir)

        # Pattern from git root .gitignore
        assert filter_.is_ignored(subdir / "debug.log") is True
        # Pattern from repo root .gitignore
        assert filter_.is_ignored(subdir / "scratch.tmp") is True
        # Normal files pass
        assert filter_.is_ignored(subdir / "main.py") is False

    def test_git_root_equals_repo_root(self, tmp_path: Path) -> None:
        """Should work when git root and repo root are the same."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".gitignore").write_text("*.log\n")

        filter_ = GitignoreFilter(tmp_path)

        assert filter_.is_ignored(tmp_path / "debug.log") is True
        assert filter_.is_ignored(tmp_path / "main.py") is False


class TestNormalizePath:
    """Test normalize_path function."""

    def test_normalizes_absolute_path(self, tmp_path: Path) -> None:
        """Should normalize absolute paths."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        file_path = repo_root / "src" / "main.py"

        result = normalize_path(file_path, repo_root)

        assert result == "src/main.py"

    def test_handles_relative_path(self, tmp_path: Path) -> None:
        """Should handle already relative paths."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        result = normalize_path(Path("src/main.py"), repo_root)

        assert result == "src/main.py"

    def test_normalizes_path_separators(self, tmp_path: Path) -> None:
        """Should use forward slashes."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Even on Windows, should normalize to forward slashes
        result = normalize_path(Path("src") / "utils" / "main.py", repo_root)

        assert "/" in result or result == "src/utils/main.py"
