"""Language detection from file paths.

Maps file extensions to programming language identifiers.
"""

from pathlib import Path
from typing import ClassVar


class LanguageDetector:
    """Detects programming language from file extensions.

    Provides a mapping from file extensions to language identifiers
    used throughout the indexing system.
    """

    # Extension to language mapping
    _EXTENSION_MAP: ClassVar[dict[str, str]] = {
        ".py": "python",
        ".pyi": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".rb": "ruby",
        ".rake": "ruby",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".kt": "kotlin",
    }

    # Special filenames without extensions
    _FILENAME_MAP: ClassVar[dict[str, str]] = {
        "rakefile": "ruby",
    }

    def detect(self, path: Path) -> str | None:
        """Detect language from file extension.

        Args:
            path: File path to analyze

        Returns:
            Language identifier string (e.g., "python", "typescript"),
            or None if language cannot be determined
        """
        # Check by filename first (case-insensitive)
        filename_lower = path.name.lower()
        if filename_lower in self._FILENAME_MAP:
            return self._FILENAME_MAP[filename_lower]

        # Fall back to extension
        return self._EXTENSION_MAP.get(path.suffix.lower())
