"""Tests for PathNormalizer service."""

from pathlib import Path

from mrcis.services.pathing import PathNormalizer


class TestPathNormalizer:
    """Tests for PathNormalizer class."""

    def test_to_repo_relative_with_absolute_path(self, tmp_path):
        """Convert absolute path to repo-relative path."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        file_path = repo_root / "src" / "module.py"
        file_path.parent.mkdir(parents=True)
        file_path.touch()

        normalizer = PathNormalizer(repo_root)
        result = normalizer.to_repo_relative(file_path)

        assert result == "src/module.py"

    def test_to_repo_relative_with_relative_path(self, tmp_path):
        """Handle already-relative paths."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        normalizer = PathNormalizer(repo_root)
        file_path = Path("src/module.py")
        result = normalizer.to_repo_relative(file_path)

        # Should preserve relative path
        assert result == "src/module.py"

    def test_to_repo_relative_normalizes_backslashes(self, tmp_path):
        """Convert Windows backslashes to forward slashes."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        normalizer = PathNormalizer(repo_root)
        # Simulate Windows-style path
        file_path = Path("src\\subdir\\file.py")
        result = normalizer.to_repo_relative(file_path)

        # Should use forward slashes
        assert "\\" not in result
        assert "/" in result or result == file_path.name

    def test_to_repo_relative_outside_repo(self, tmp_path):
        """Handle paths outside repository gracefully."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        other_dir = tmp_path / "other"
        other_dir.mkdir()
        file_path = other_dir / "file.py"
        file_path.touch()

        normalizer = PathNormalizer(repo_root)
        result = normalizer.to_repo_relative(file_path)

        # Should return something reasonable (original path or relative form)
        assert result is not None
        assert isinstance(result, str)

    def test_to_repo_relative_nested_directories(self, tmp_path):
        """Handle deeply nested directory structures."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        nested_file = repo_root / "a" / "b" / "c" / "d" / "file.py"
        nested_file.parent.mkdir(parents=True)
        nested_file.touch()

        normalizer = PathNormalizer(repo_root)
        result = normalizer.to_repo_relative(nested_file)

        assert result == "a/b/c/d/file.py"

    def test_to_repo_relative_at_repo_root(self, tmp_path):
        """Handle files at repository root."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        file_path = repo_root / "README.md"
        file_path.touch()

        normalizer = PathNormalizer(repo_root)
        result = normalizer.to_repo_relative(file_path)

        assert result == "README.md"
