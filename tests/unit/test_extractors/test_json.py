"""Tests for JSONExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.json_extractor import JSONExtractor


@pytest.fixture
def extractor():
    """Provide JSONExtractor instance."""
    return JSONExtractor()


@pytest.fixture
def write_json_file(tmp_path: Path):
    """Factory fixture to write JSON files."""

    def _write(content: str, filename: str = "test.json") -> Path:
        file_path = tmp_path / filename
        file_path.write_text(content)
        return file_path

    return _write


class TestJSONSupport:
    """Tests for file support detection."""

    def test_supports_json_extension(self, extractor) -> None:
        """Test .json extension is supported."""
        assert extractor.supports(Path("config.json"))

    def test_supports_uppercase_extension(self, extractor) -> None:
        """Test .JSON extension is supported."""
        assert extractor.supports(Path("config.JSON"))

    def test_rejects_other_extensions(self, extractor) -> None:
        """Test non-JSON files are rejected."""
        assert not extractor.supports(Path("config.yaml"))
        assert not extractor.supports(Path("config.toml"))

    def test_get_supported_extensions(self, extractor) -> None:
        """Test supported extensions list."""
        exts = extractor.get_supported_extensions()
        assert ".json" in exts


class TestJSONExtraction:
    """Tests for JSON key extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_keys(self, extractor, write_json_file) -> None:
        """Test extracting top-level keys."""
        content = """
{
    "name": "test",
    "version": "1.0.0",
    "debug": true
}
"""
        file_path = write_json_file(content)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.variables) == 3
        names = {v.name for v in result.variables}
        assert names == {"name", "version", "debug"}

    @pytest.mark.asyncio
    async def test_extract_nested_keys(self, extractor, write_json_file) -> None:
        """Test extracting nested keys."""
        content = """
{
    "server": {
        "host": "localhost",
        "port": 8080
    }
}
"""
        file_path = write_json_file(content)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.variables) == 3
        qualified_names = {v.qualified_name for v in result.variables}
        assert "server" in qualified_names
        assert "server.host" in qualified_names
        assert "server.port" in qualified_names

    @pytest.mark.asyncio
    async def test_extract_deeply_nested(self, extractor, write_json_file) -> None:
        """Test extracting deeply nested keys (respects max depth)."""
        content = """
{
    "level1": {
        "level2": {
            "level3": {
                "level4": {
                    "deep": "value"
                }
            }
        }
    }
}
"""
        file_path = write_json_file(content)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Max depth is 3, so we should get level1, level2, level3, level4
        # but not "deep" (which is at depth 4)
        qualified_names = {v.qualified_name for v in result.variables}
        assert "level1" in qualified_names
        assert "level1.level2" in qualified_names
        assert "level1.level2.level3" in qualified_names
        assert "level1.level2.level3.level4" in qualified_names
        # "deep" is at depth 4, should not be extracted
        assert "level1.level2.level3.level4.deep" not in qualified_names

    @pytest.mark.asyncio
    async def test_extract_array_nested_objects(self, extractor, write_json_file) -> None:
        """Test extracting keys from objects inside arrays."""
        content = """
{
    "users": [
        {
            "name": "Alice",
            "age": 30
        }
    ]
}
"""
        file_path = write_json_file(content)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        qualified_names = {v.qualified_name for v in result.variables}
        assert "users" in qualified_names
        # Array contents should be traversed
        assert "users.name" in qualified_names
        assert "users.age" in qualified_names

    @pytest.mark.asyncio
    async def test_extract_empty_json(self, extractor, write_json_file) -> None:
        """Test extracting from empty JSON object."""
        content = "{}"
        file_path = write_json_file(content)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.variables) == 0
        assert result.language == "json"

    @pytest.mark.asyncio
    async def test_extract_json_array_root(self, extractor, write_json_file) -> None:
        """Test extracting from JSON array at root."""
        content = """
[
    {"id": 1},
    {"id": 2}
]
"""
        file_path = write_json_file(content)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should extract keys from array elements
        qualified_names = {v.qualified_name for v in result.variables}
        assert "id" in qualified_names

    @pytest.mark.asyncio
    async def test_invalid_json(self, extractor, write_json_file) -> None:
        """Test handling of invalid JSON."""
        content = '{"invalid": json}'
        file_path = write_json_file(content)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.parse_errors) == 1
        assert "JSON parse error" in result.parse_errors[0]

    @pytest.mark.asyncio
    async def test_metadata_fields(self, extractor, write_json_file) -> None:
        """Test that metadata fields are set correctly."""
        content = '{"key": "value"}'
        file_path = write_json_file(content)
        file_id = uuid4()
        repo_id = uuid4()

        result = await extractor.extract(file_path, file_id, repo_id)

        assert result.file_id == file_id
        assert result.repository_id == repo_id
        assert result.language == "json"
        assert str(file_path) in result.file_path

        var = result.variables[0]
        assert var.file_id == file_id
        assert var.repository_id == repo_id
        assert var.language == "json"
        assert str(file_path) in var.file_path
