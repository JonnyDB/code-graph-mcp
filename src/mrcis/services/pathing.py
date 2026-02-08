"""Path normalization service.

Provides consistent path handling across the codebase.
"""

from pathlib import Path


class PathNormalizer:
    """Normalizes file paths relative to repository root.

    Handles:
    - Converting absolute paths to repo-relative paths
    - Normalizing path separators (always forward slashes)
    - Handling paths outside repository boundaries
    """

    def __init__(self, repo_root: Path) -> None:
        """Initialize normalizer with repository root.

        Args:
            repo_root: Root directory of the repository.
        """
        self.repo_root = repo_root.resolve()

    def to_repo_relative(self, file_path: Path) -> str:
        """Convert a file path to be relative to repository root.

        Args:
            file_path: Path to normalize (can be absolute or relative).

        Returns:
            Relative path as string with forward slashes.
        """
        try:
            # Try to resolve and make relative to repo root
            resolved = file_path.resolve()
            relative = resolved.relative_to(self.repo_root)
        except ValueError:
            # Path is outside repo or already relative
            relative = file_path

        # Always use forward slashes (POSIX style)
        return str(relative).replace("\\", "/")
