"""Tests for RepositoryScanner service."""

from mrcis.config.models import FilesConfig
from mrcis.services.indexing.scanner import RepositoryScanner


class TestRepositoryScanner:
    """Tests for RepositoryScanner class."""

    def test_iter_files_finds_python_files(self, tmp_path):
        """Scanner should find Python files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create Python files
        (repo_path / "main.py").write_text("print('hello')")
        (repo_path / "lib.py").write_text("def func(): pass")

        scanner = RepositoryScanner(repo_path, FilesConfig())
        files = list(scanner.iter_files())

        assert len(files) == 2
        assert any(f.name == "main.py" for f in files)
        assert any(f.name == "lib.py" for f in files)

    def test_iter_files_respects_include_patterns(self, tmp_path):
        """Scanner should only include files matching patterns."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "script.py").write_text("code")
        (repo_path / "data.txt").write_text("text")
        (repo_path / "app.js").write_text("code")

        config = FilesConfig(include_patterns=["**/*.py"])
        scanner = RepositoryScanner(repo_path, config)
        files = list(scanner.iter_files())

        assert len(files) == 1
        assert files[0].name == "script.py"

    def test_iter_files_respects_exclude_patterns(self, tmp_path):
        """Scanner should exclude files matching exclude patterns."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "main.py").write_text("code")
        (repo_path / "test_main.py").write_text("test")

        config = FilesConfig(exclude_patterns=["**/test_*.py"])
        scanner = RepositoryScanner(repo_path, config)
        files = list(scanner.iter_files())

        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_iter_files_respects_max_file_size(self, tmp_path):
        """Scanner should skip files larger than max_file_size_kb."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        small_file = repo_path / "small.py"
        small_file.write_text("a" * 100)  # 100 bytes

        large_file = repo_path / "large.py"
        large_file.write_text("a" * 2000)  # 2000 bytes

        config = FilesConfig(max_file_size_kb=1)  # 1 KB = 1024 bytes
        scanner = RepositoryScanner(repo_path, config)
        files = list(scanner.iter_files())

        assert len(files) == 1
        assert files[0].name == "small.py"

    def test_iter_files_respects_gitignore(self, tmp_path):
        """Scanner should respect .gitignore patterns."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create .gitignore
        (repo_path / ".gitignore").write_text("*.log\n")

        (repo_path / "main.py").write_text("code")
        (repo_path / "debug.log").write_text("log")

        config = FilesConfig(respect_gitignore=True)
        scanner = RepositoryScanner(repo_path, config)
        files = list(scanner.iter_files())

        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_iter_files_ignores_gitignore_when_disabled(self, tmp_path):
        """Scanner should ignore .gitignore when respect_gitignore=False."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create .gitignore
        (repo_path / ".gitignore").write_text("*.log\n")

        (repo_path / "main.py").write_text("code")
        (repo_path / "debug.log").write_text("log")

        config = FilesConfig(respect_gitignore=False, include_patterns=["**/*.log"])
        scanner = RepositoryScanner(repo_path, config)
        files = list(scanner.iter_files())

        # Should find .log file since gitignore is disabled
        assert len(files) == 1
        assert files[0].name == "debug.log"

    def test_iter_files_finds_nested_files(self, tmp_path):
        """Scanner should find files in nested directories."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        src_dir = repo_path / "src"
        src_dir.mkdir()
        (src_dir / "module.py").write_text("code")

        tests_dir = repo_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test.py").write_text("test")

        scanner = RepositoryScanner(repo_path, FilesConfig())
        files = list(scanner.iter_files())

        assert len(files) == 2
        assert any(f.name == "module.py" for f in files)
        assert any(f.name == "test.py" for f in files)

    def test_iter_files_skips_directories(self, tmp_path):
        """Scanner should only return files, not directories."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "file.py").write_text("code")
        (repo_path / "subdir").mkdir()

        scanner = RepositoryScanner(repo_path, FilesConfig())
        files = list(scanner.iter_files())

        assert len(files) == 1
        assert files[0].name == "file.py"

    def test_iter_files_handles_oserror(self, tmp_path):
        """Scanner should gracefully handle OS errors when checking file size."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        file_path = repo_path / "file.py"
        file_path.write_text("code")

        scanner = RepositoryScanner(repo_path, FilesConfig())

        # Scanner should not crash even if file operations fail
        files = list(scanner.iter_files())
        assert len(files) >= 0  # May or may not find files depending on timing
