"""Tests for TOMLExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.toml_extractor import TOMLExtractor


@pytest.fixture
def extractor():
    """Provide TOMLExtractor instance."""
    return TOMLExtractor()


@pytest.fixture
def write_toml_file(tmp_path: Path):
    """Factory fixture to write TOML files."""

    def _write(content: str) -> Path:
        file_path = tmp_path / "test_config.toml"
        file_path.write_text(content)
        return file_path

    return _write


class TestTOMLExtractorSupports:
    """Tests for file support detection."""

    def test_supports_toml_files(self, extractor) -> None:
        """Test supports .toml files."""
        assert extractor.supports(Path("config.toml"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support non-TOML files."""
        assert not extractor.supports(Path("config.json"))
        assert not extractor.supports(Path("config.yaml"))


class TestTOMLKeyExtraction:
    """Tests for key-value extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_key(self, extractor, write_toml_file) -> None:
        """Test extracting simple key-value pairs."""
        content = """
title = "TOML Example"
version = "1.0.0"
"""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.variables) >= 2
        names = {v.name for v in result.variables}
        assert "title" in names
        assert "version" in names

    @pytest.mark.asyncio
    async def test_extract_nested_keys(self, extractor, write_toml_file) -> None:
        """Test extracting nested key-value pairs."""
        content = """
[owner]
name = "Tom Preston-Werner"
dob = 1979-05-27T07:32:00-08:00
"""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        qualified_names = {v.qualified_name for v in result.variables}
        assert "owner" in qualified_names
        assert "owner.name" in qualified_names
        assert "owner.dob" in qualified_names


class TestTOMLTableExtraction:
    """Tests for table extraction."""

    @pytest.mark.asyncio
    async def test_extract_table(self, extractor, write_toml_file) -> None:
        """Test extracting table sections."""
        content = """
[database]
server = "192.168.1.1"
port = 5432

[servers]
alpha = "10.0.0.1"
beta = "10.0.0.2"
"""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        qualified_names = {v.qualified_name for v in result.variables}
        assert "database" in qualified_names
        assert "database.server" in qualified_names
        assert "database.port" in qualified_names
        assert "servers" in qualified_names
        assert "servers.alpha" in qualified_names
        assert "servers.beta" in qualified_names

    @pytest.mark.asyncio
    async def test_extract_nested_tables(self, extractor, write_toml_file) -> None:
        """Test extracting nested tables."""
        content = """
[a.b.c]
answer = 42

[a.b]
question = "What is the answer?"
"""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        qualified_names = {v.qualified_name for v in result.variables}
        assert "a.b.c" in qualified_names
        assert "a.b.c.answer" in qualified_names
        assert "a.b" in qualified_names
        assert "a.b.question" in qualified_names


class TestTOMLArrayExtraction:
    """Tests for array extraction."""

    @pytest.mark.asyncio
    async def test_extract_array(self, extractor, write_toml_file) -> None:
        """Test extracting arrays."""
        content = """
colors = ["red", "yellow", "green"]

[fruit]
apples = ["red delicious", "granny smith"]
"""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        qualified_names = {v.qualified_name for v in result.variables}
        assert "colors" in qualified_names
        assert "fruit" in qualified_names
        assert "fruit.apples" in qualified_names


class TestTOMLArrayOfTables:
    """Tests for array of tables extraction."""

    @pytest.mark.asyncio
    async def test_extract_array_of_tables(self, extractor, write_toml_file) -> None:
        """Test extracting array of tables."""
        content = """
[[products]]
name = "Hammer"
sku = 738594937

[[products]]
name = "Nail"
sku = 284758393
"""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        qualified_names = {v.qualified_name for v in result.variables}
        assert "products[0]" in qualified_names
        assert "products[0].name" in qualified_names
        assert "products[0].sku" in qualified_names
        assert "products[1]" in qualified_names
        assert "products[1].name" in qualified_names
        assert "products[1].sku" in qualified_names


class TestTOMLComplexStructure:
    """Tests for complex TOML structures."""

    @pytest.mark.asyncio
    async def test_extract_pyproject_structure(self, extractor, write_toml_file) -> None:
        """Test extracting structure similar to pyproject.toml."""
        content = """
[project]
name = "mrcis"
version = "0.1.0"
requires-python = ">=3.11"

[project.dependencies]
pydantic = "^2.0"

[tool.uv]
dev-dependencies = [
    "pytest",
    "ruff",
]
"""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        qualified_names = {v.qualified_name for v in result.variables}
        assert "project" in qualified_names
        assert "project.name" in qualified_names
        assert "project.dependencies" in qualified_names
        assert "project.dependencies.pydantic" in qualified_names
        assert "tool.uv" in qualified_names
        assert "tool.uv.dev-dependencies" in qualified_names


class TestTOMLErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_invalid_toml(self, extractor, write_toml_file) -> None:
        """Test handling of invalid TOML."""
        content = """
[invalid
missing_bracket = true
"""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.parse_errors) > 0
        assert "TOML parse error" in result.parse_errors[0]

    @pytest.mark.asyncio
    async def test_empty_toml(self, extractor, write_toml_file) -> None:
        """Test handling of empty TOML file."""
        content = ""
        file_path = write_toml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Empty TOML is valid, should have no errors
        assert len(result.parse_errors) == 0
        assert len(result.variables) == 0
