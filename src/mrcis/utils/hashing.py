"""Hashing utilities for checksum computation."""

import asyncio
import hashlib
from pathlib import Path


def _compute_file_checksum_sync(file_path: Path) -> str:
    """Synchronous file checksum computation."""
    sha256 = hashlib.sha256()

    # Read in chunks to handle large files
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


async def compute_file_checksum(file_path: Path) -> str:
    """
    Compute SHA-256 checksum of a file.

    Runs blocking I/O in a thread pool to avoid stalling the event loop.

    Args:
        file_path: Path to the file.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return await asyncio.to_thread(_compute_file_checksum_sync, file_path)


def compute_content_checksum(content: str | bytes) -> str:
    """
    Compute SHA-256 checksum of content.

    Args:
        content: String or bytes content.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    if isinstance(content, str):
        content = content.encode("utf-8")

    return hashlib.sha256(content).hexdigest()
