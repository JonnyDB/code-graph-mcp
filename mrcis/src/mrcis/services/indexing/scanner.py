"""Repository scanner for discovering indexable files.

Handles file discovery with include/exclude patterns, size limits,
and gitignore filtering.
"""

from collections.abc import Generator
from pathlib import Path

from loguru import logger

from mrcis.config.models import FilesConfig
from mrcis.services.file_filter import FileInclusionPolicy


class RepositoryScanner:
    """Scans repository for files matching configured criteria.

    Attributes:
        repo_path: Root directory of the repository
        config: File filtering configuration
        file_filter: File inclusion policy for gitignore and extension filtering
    """

    def __init__(self, repo_path: Path, config: FilesConfig):
        """Initialize scanner.

        Args:
            repo_path: Root directory of the repository
            config: File filtering configuration
        """
        self.repo_path = repo_path.resolve()
        self.config = config
        self.file_filter = FileInclusionPolicy(repo_path)

    def iter_files(self) -> Generator[Path, None, None]:
        """Iterate over all indexable files in the repository.

        Yields files that match include patterns, don't match exclude patterns,
        are under max file size, and optionally respect gitignore.

        Yields:
            Path objects for files that should be indexed
        """
        include_patterns = self.config.include_patterns or ["**/*.py"]
        exclude_patterns = self.config.exclude_patterns or []
        max_size_bytes = self.config.max_file_size_kb * 1024

        # Process each include pattern
        for pattern in include_patterns:
            for file_path in self.repo_path.glob(pattern):
                # Skip directories
                if not file_path.is_file():
                    continue

                # Check exclude patterns
                if self._matches_exclude(file_path, exclude_patterns):
                    continue

                # Check file size
                try:
                    if file_path.stat().st_size > max_size_bytes:
                        logger.debug("Skipping large file: {}", file_path)
                        continue
                except OSError as e:
                    logger.warning("Cannot stat file {}: {}", file_path, e)
                    continue

                # Check gitignore and extension filtering
                if self.config.respect_gitignore and not self.file_filter.should_index(file_path):
                    continue

                yield file_path

    def _matches_exclude(self, file_path: Path, exclude_patterns: list[str]) -> bool:
        """Check if file matches any exclude pattern.

        Args:
            file_path: File to check
            exclude_patterns: List of glob patterns to exclude

        Returns:
            True if file matches any exclude pattern
        """
        for pattern in exclude_patterns:
            # Convert to string for matching
            file_str = str(file_path.relative_to(self.repo_path))
            # Use Path.match for glob pattern matching
            if file_path.match(pattern) or Path(file_str).match(pattern):
                return True
        return False
