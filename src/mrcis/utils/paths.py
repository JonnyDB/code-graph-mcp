"""Path utilities for file handling and gitignore filtering."""

from pathlib import Path
from typing import ClassVar

import pathspec


class GitignoreFilter:
    """
    Filter files based on .gitignore patterns.

    Uses pathspec library for gitignore-style pattern matching.
    Walks up from repo_root to find the git root and loads
    .gitignore files from both locations.
    """

    # Patterns that are always excluded regardless of .gitignore
    BUILTIN_PATTERNS: ClassVar[list[str]] = [".git/", ".mrcis/"]

    def __init__(self, repo_root: Path) -> None:
        """
        Initialize filter with repository root.

        Args:
            repo_root: Root directory of the repository.
        """
        self.repo_root = repo_root.resolve()
        self._git_root = self._find_git_root()
        self._specs: list[tuple[Path, pathspec.PathSpec]] = []
        self._load_gitignore()

    def _find_git_root(self) -> Path | None:
        """Find the git root by walking up from repo_root."""
        current = self.repo_root
        while True:
            if (current / ".git").exists():
                return current
            parent = current.parent
            if parent == current:
                return None
            current = parent

    def _load_gitignore(self) -> None:
        """Load .gitignore patterns from git root and repo root."""
        dirs: list[Path] = []
        if self._git_root is not None:
            dirs.append(self._git_root)
        if self.repo_root not in dirs:
            dirs.append(self.repo_root)

        for base_dir in dirs:
            patterns = list(self.BUILTIN_PATTERNS)
            gitignore_path = base_dir / ".gitignore"
            if gitignore_path.exists():
                with gitignore_path.open() as f:
                    for raw_line in f:
                        stripped_line = raw_line.strip()
                        if stripped_line and not stripped_line.startswith("#"):
                            patterns.append(stripped_line)
            spec = pathspec.PathSpec.from_lines("gitignore", patterns)
            self._specs.append((base_dir, spec))

    def is_ignored(self, file_path: Path) -> bool:
        """
        Check if a file should be ignored.

        Args:
            file_path: Path to check (can be absolute or relative).

        Returns:
            True if the file matches a gitignore pattern.
        """
        if not self._specs:
            return False

        resolved = file_path.resolve()

        for base_dir, spec in self._specs:
            try:
                relative = resolved.relative_to(base_dir)
            except ValueError:
                continue
            if spec.match_file(str(relative)):
                return True

        return False


def normalize_path(file_path: Path, repo_root: Path) -> str:
    """
    Normalize a file path to be relative to repository root.

    Args:
        file_path: Path to normalize.
        repo_root: Repository root directory.

    Returns:
        Relative path as string with forward slashes.
    """
    try:
        resolved = file_path.resolve()
        relative = resolved.relative_to(repo_root.resolve())
    except ValueError:
        # Already relative or not under repo root
        relative = file_path

    # Always use forward slashes (POSIX style)
    return str(relative).replace("\\", "/")
