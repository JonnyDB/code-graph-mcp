"""File inclusion filtering service.

Determines which files should be indexed based on gitignore patterns,
file extensions, and built-in exclusion rules.
"""

from pathlib import Path
from typing import ClassVar

from mrcis.utils.paths import GitignoreFilter


class FileInclusionPolicy:
    """Policy for determining which files should be indexed.

    Combines:
    - Gitignore-based filtering
    - File extension filtering
    - Built-in exclusion patterns
    """

    # File extensions that should be indexed
    INDEXABLE_EXTENSIONS: ClassVar[set[str]] = {
        ".py",  # Python
        ".js",
        ".jsx",
        ".ts",
        ".tsx",  # JavaScript/TypeScript
        ".rb",  # Ruby
        ".go",  # Go
        ".rs",  # Rust
        ".java",  # Java
        ".c",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",  # C/C++
        ".cs",  # C#
        ".php",  # PHP
        ".swift",  # Swift
        ".kt",
        ".kts",  # Kotlin
        ".scala",  # Scala
        ".clj",
        ".cljs",  # Clojure
        ".ex",
        ".exs",  # Elixir
        ".erl",  # Erlang
        ".hs",  # Haskell
        ".ml",
        ".mli",  # OCaml
        ".lua",  # Lua
        ".r",
        ".R",  # R
        ".m",  # Objective-C/MATLAB
        ".sh",
        ".bash",  # Shell
        ".sql",  # SQL
        ".proto",  # Protocol Buffers
        ".graphql",
        ".gql",  # GraphQL
        ".yaml",
        ".yml",  # YAML
        ".json",  # JSON
        ".toml",  # TOML
        ".xml",  # XML
        ".md",  # Markdown
        ".rst",  # reStructuredText
    }

    # Patterns that indicate binary or non-indexable files
    EXCLUDED_EXTENSIONS: ClassVar[set[str]] = {
        ".pyc",
        ".pyo",  # Python bytecode
        ".so",
        ".dylib",
        ".dll",  # Shared libraries
        ".exe",
        ".bin",  # Executables
        ".o",
        ".a",  # Object files
        ".class",  # Java bytecode
        ".jar",
        ".war",  # Java archives
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",  # Images
        ".pdf",  # Documents
        ".zip",
        ".tar",
        ".gz",
        ".bz2",  # Archives
        ".whl",
        ".egg",  # Python packages
    }

    # Directory patterns that should always be excluded
    EXCLUDED_DIRS: ClassVar[set[str]] = {
        "__pycache__",
        ".git",
        ".mrcis",
        "node_modules",
        ".pytest_cache",
    }

    def __init__(self, repo_root: Path) -> None:
        """Initialize policy with repository root.

        Args:
            repo_root: Root directory of the repository.
        """
        self.repo_root = repo_root
        self.gitignore_filter = GitignoreFilter(repo_root)

    def should_index(self, file_path: Path) -> bool:
        """Determine if a file should be indexed.

        Args:
            file_path: Path to check (can be absolute or relative).

        Returns:
            True if the file should be indexed, False otherwise.
        """
        # Check if in excluded directory
        for part in file_path.parts:
            if part in self.EXCLUDED_DIRS:
                return False

        # Check file extension
        suffix = file_path.suffix.lower()

        # Explicitly excluded extensions
        if suffix in self.EXCLUDED_EXTENSIONS:
            return False

        # Must have an indexable extension (or no extension for files like Makefile)
        if suffix and suffix not in self.INDEXABLE_EXTENSIONS:
            return False

        # Check gitignore
        return not self.gitignore_filter.is_ignored(file_path)
