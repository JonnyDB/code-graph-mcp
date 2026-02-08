"""Integration test fixtures."""

import hashlib
from pathlib import Path

import pytest


class MockEmbeddingService:
    """Deterministic embedder for testing."""

    def __init__(self, dimensions: int = 1024):
        self.dimensions = dimensions
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def close(self) -> None:
        self._initialized = False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic embeddings based on text hash."""
        return [self._hash_to_vector(t) for t in texts]

    async def embed_single(self, text: str) -> list[float]:
        """Embed single text."""
        return self._hash_to_vector(text)

    def _hash_to_vector(self, text: str) -> list[float]:
        """Convert text to deterministic vector."""
        h = hashlib.sha256(text.encode()).digest()
        # Extend hash to fill dimensions
        extended = h * (self.dimensions // len(h) + 1)
        # Convert to floats in [-1, 1]
        vector = [(b / 127.5) - 1.0 for b in extended[: self.dimensions]]
        # Normalize
        magnitude = sum(x * x for x in vector) ** 0.5
        return [x / magnitude for x in vector]


@pytest.fixture
def mock_embedder():
    """Create mock embedding service."""
    return MockEmbeddingService(dimensions=1024)


@pytest.fixture
def sample_python_repo(tmp_path: Path) -> Path:
    """Create a sample Python repository for testing."""
    repo = tmp_path / "sample_repo"
    repo.mkdir()

    # Create main module
    main_py = repo / "main.py"
    main_py.write_text('''
"""Main module for sample application."""

from utils import helper_function


class Application:
    """Main application class."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self) -> str:
        """Run the application."""
        result = helper_function(self.name)
        return f"Running {result}"


def main() -> None:
    """Entry point."""
    app = Application("test")
    print(app.run())


if __name__ == "__main__":
    main()
''')

    # Create utils module
    utils_py = repo / "utils.py"
    utils_py.write_text('''
"""Utility functions."""


def helper_function(value: str) -> str:
    """Process a value."""
    return value.upper()


def format_output(text: str, prefix: str = "") -> str:
    """Format output text."""
    return f"{prefix}{text}"


CONSTANT = "default"
''')

    return repo
