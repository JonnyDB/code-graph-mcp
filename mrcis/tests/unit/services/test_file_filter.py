"""Tests for FileInclusionPolicy service."""

from pathlib import Path

from mrcis.services.file_filter import FileInclusionPolicy


class TestFileInclusionPolicy:
    """Tests for FileInclusionPolicy class."""

    def test_should_index_python_file(self, tmp_path):
        """Python files should be included."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        policy = FileInclusionPolicy(repo_root)
        assert policy.should_index(Path("src/module.py")) is True

    def test_should_index_javascript_file(self, tmp_path):
        """JavaScript files should be included."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        policy = FileInclusionPolicy(repo_root)
        assert policy.should_index(Path("src/component.js")) is True

    def test_should_not_index_git_directory(self, tmp_path):
        """Files in .git should be excluded."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        policy = FileInclusionPolicy(repo_root)
        assert policy.should_index(Path(".git/config")) is False

    def test_should_not_index_mrcis_directory(self, tmp_path):
        """Files in .mrcis should be excluded."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        policy = FileInclusionPolicy(repo_root)
        assert policy.should_index(Path(".mrcis/state.db")) is False

    def test_should_not_index_pycache(self, tmp_path):
        """__pycache__ directories should be excluded."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        policy = FileInclusionPolicy(repo_root)
        assert policy.should_index(Path("src/__pycache__/module.pyc")) is False

    def test_respects_gitignore_patterns(self, tmp_path):
        """Should respect .gitignore patterns."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Create .gitignore
        gitignore = repo_root / ".gitignore"
        gitignore.write_text("*.log\\nbuild/\\n")

        policy = FileInclusionPolicy(repo_root)

        # .log files should be excluded
        assert policy.should_index(Path("debug.log")) is False

        # build/ directory should be excluded
        assert policy.should_index(Path("build/output.txt")) is False

        # Other files should be included
        assert policy.should_index(Path("src/main.py")) is True

    def test_should_index_with_absolute_path(self, tmp_path):
        """Should handle absolute paths."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        file_path = repo_root / "src" / "module.py"
        file_path.parent.mkdir(parents=True)
        file_path.touch()

        policy = FileInclusionPolicy(repo_root)
        assert policy.should_index(file_path) is True

    def test_should_not_index_binary_files(self, tmp_path):
        """Binary files like .pyc, .so should be excluded."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        policy = FileInclusionPolicy(repo_root)

        assert policy.should_index(Path("module.pyc")) is False
        assert policy.should_index(Path("lib.so")) is False
        assert policy.should_index(Path("app.exe")) is False

    def test_should_index_common_code_extensions(self, tmp_path):
        """Should include common programming language files."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        policy = FileInclusionPolicy(repo_root)

        # Python
        assert policy.should_index(Path("script.py")) is True

        # JavaScript/TypeScript
        assert policy.should_index(Path("app.js")) is True
        assert policy.should_index(Path("types.ts")) is True
        assert policy.should_index(Path("component.tsx")) is True

        # Ruby
        assert policy.should_index(Path("server.rb")) is True

        # Go
        assert policy.should_index(Path("main.go")) is True

        # Rust
        assert policy.should_index(Path("lib.rs")) is True

    def test_should_not_index_node_modules(self, tmp_path):
        """node_modules directory should be excluded."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Create a basic .gitignore that includes node_modules
        gitignore = repo_root / ".gitignore"
        gitignore.write_text("node_modules/\\n")

        policy = FileInclusionPolicy(repo_root)
        assert policy.should_index(Path("node_modules/package/index.js")) is False
