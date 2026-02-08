"""Tests for GoExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.go import GoExtractor


@pytest.fixture
def extractor():
    return GoExtractor()


@pytest.fixture
def write_go_file(tmp_path: Path):
    def _write(content: str) -> Path:
        file_path = tmp_path / "main.go"
        file_path.write_text(content)
        return file_path

    return _write


class TestGoExtractorSupports:
    def test_supports_go_files(self, extractor) -> None:
        assert extractor.supports(Path("main.go"))

    def test_does_not_support_other_files(self, extractor) -> None:
        assert not extractor.supports(Path("main.py"))


class TestGoImportExtraction:
    @pytest.mark.asyncio
    async def test_extract_single_import(self, extractor, write_go_file) -> None:
        code = """package main

import "fmt"
"""
        file_path = write_go_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "fmt"

    @pytest.mark.asyncio
    async def test_extract_import_block(self, extractor, write_go_file) -> None:
        code = """package main

import (
    "fmt"
    "strings"
)
"""
        file_path = write_go_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 2


class TestGoStructExtraction:
    @pytest.mark.asyncio
    async def test_extract_struct(self, extractor, write_go_file) -> None:
        code = """package main

type User struct {
    ID   int
    Name string
}
"""
        file_path = write_go_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        assert result.classes[0].name == "User"


class TestGoFunctionExtraction:
    @pytest.mark.asyncio
    async def test_extract_function(self, extractor, write_go_file) -> None:
        code = """package main

func greet(name string) string {
    return "Hello, " + name
}
"""
        file_path = write_go_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"
        assert func.return_type == "string"

    @pytest.mark.asyncio
    async def test_extract_method_with_receiver(self, extractor, write_go_file) -> None:
        code = """package main

type User struct {
    Name string
}

func (u *User) Greet() string {
    return "Hello, " + u.Name
}
"""
        file_path = write_go_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.name == "Greet"
        assert "User" in method.parent_class
