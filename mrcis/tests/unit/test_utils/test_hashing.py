"""Tests for hashing utilities."""

from pathlib import Path

import pytest

from mrcis.utils.hashing import compute_content_checksum, compute_file_checksum


class TestComputeFileChecksum:
    """Test compute_file_checksum function."""

    @pytest.mark.asyncio
    async def test_computes_sha256_hash(self, tmp_path: Path) -> None:
        """Should compute SHA-256 hash of file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("hello world")

        checksum = await compute_file_checksum(file_path)

        # SHA-256 of "hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert checksum == expected

    @pytest.mark.asyncio
    async def test_different_content_different_hash(self, tmp_path: Path) -> None:
        """Different content should produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content one")
        file2.write_text("content two")

        checksum1 = await compute_file_checksum(file1)
        checksum2 = await compute_file_checksum(file2)

        assert checksum1 != checksum2

    @pytest.mark.asyncio
    async def test_same_content_same_hash(self, tmp_path: Path) -> None:
        """Same content should produce same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("identical content")
        file2.write_text("identical content")

        checksum1 = await compute_file_checksum(file1)
        checksum2 = await compute_file_checksum(file2)

        assert checksum1 == checksum2

    @pytest.mark.asyncio
    async def test_handles_binary_files(self, tmp_path: Path) -> None:
        """Should handle binary file content."""
        file_path = tmp_path / "binary.bin"
        file_path.write_bytes(bytes([0x00, 0x01, 0x02, 0xFF]))

        checksum = await compute_file_checksum(file_path)

        assert len(checksum) == 64  # SHA-256 hex length


class TestComputeContentChecksum:
    """Test compute_content_checksum function."""

    def test_computes_sha256_of_string(self) -> None:
        """Should compute SHA-256 hash of string content."""
        checksum = compute_content_checksum("hello world")

        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert checksum == expected

    def test_computes_sha256_of_bytes(self) -> None:
        """Should compute SHA-256 hash of bytes content."""
        checksum = compute_content_checksum(b"hello world")

        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert checksum == expected
