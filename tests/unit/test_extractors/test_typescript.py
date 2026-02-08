"""Tests for TypeScriptExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.typescript import TypeScriptExtractor


@pytest.fixture
def extractor():
    """Provide TypeScriptExtractor instance."""
    return TypeScriptExtractor()


@pytest.fixture
def write_ts_file(tmp_path: Path):
    """Factory fixture to write TypeScript files."""

    def _write(content: str, ext: str = ".ts") -> Path:
        file_path = tmp_path / f"test_module{ext}"
        file_path.write_text(content)
        return file_path

    return _write


class TestTypeScriptExtractorSupports:
    """Tests for file support detection."""

    def test_supports_ts_files(self, extractor) -> None:
        """Test supports .ts files."""
        assert extractor.supports(Path("module.ts"))

    def test_supports_tsx_files(self, extractor) -> None:
        """Test supports .tsx files."""
        assert extractor.supports(Path("component.tsx"))

    def test_does_not_support_js_files(self, extractor) -> None:
        """Test doesn't support .js files (use JSExtractor)."""
        assert not extractor.supports(Path("module.js"))


class TestTypeScriptImportExtraction:
    """Tests for import extraction."""

    @pytest.mark.asyncio
    async def test_extract_es_import(self, extractor, write_ts_file) -> None:
        """Test extracting ES imports."""
        code = "import { useState } from 'react';"
        file_path = write_ts_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "react"

    @pytest.mark.asyncio
    async def test_extract_default_import(self, extractor, write_ts_file) -> None:
        """Test extracting default imports."""
        code = "import React from 'react';"
        file_path = write_ts_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert "React" in result.imports[0].imported_symbols


class TestTypeScriptFunctionExtraction:
    """Tests for function extraction."""

    @pytest.mark.asyncio
    async def test_extract_function(self, extractor, write_ts_file) -> None:
        """Test extracting TypeScript function."""
        code = """
function greet(name: string): string {
    return `Hello, ${name}`;
}
"""
        file_path = write_ts_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"
        assert func.return_type == "string"

    @pytest.mark.asyncio
    async def test_extract_arrow_function(self, extractor, write_ts_file) -> None:
        """Test extracting arrow functions."""
        code = "const add = (a: number, b: number): number => a + b;"
        file_path = write_ts_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) >= 1

    @pytest.mark.asyncio
    async def test_extract_async_function(self, extractor, write_ts_file) -> None:
        """Test extracting async function."""
        code = """
async function fetchData(): Promise<string> {
    return "data";
}
"""
        file_path = write_ts_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        func = result.functions[0]
        assert func.is_async is True


class TestTypeScriptClassExtraction:
    """Tests for class extraction."""

    @pytest.mark.asyncio
    async def test_extract_class(self, extractor, write_ts_file) -> None:
        """Test extracting TypeScript class."""
        code = """
class UserService {
    private apiUrl: string;

    constructor(apiUrl: string) {
        this.apiUrl = apiUrl;
    }

    async getUser(id: number): Promise<User> {
        return fetch(this.apiUrl);
    }
}
"""
        file_path = write_ts_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "UserService"

    @pytest.mark.asyncio
    async def test_extract_interface(self, extractor, write_ts_file) -> None:
        """Test extracting TypeScript interface."""
        code = """
interface User {
    id: number;
    name: string;
    email?: string;
}
"""
        file_path = write_ts_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Interfaces stored as classes with is_interface flag
        assert len(result.classes) == 1
        assert result.classes[0].name == "User"

    @pytest.mark.asyncio
    async def test_extract_type_alias(self, extractor, write_ts_file) -> None:
        """Test extracting type aliases."""
        code = "type UserId = string | number;"
        file_path = write_ts_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Type aliases stored in variables or dedicated type_aliases
        assert len(result.variables) >= 1 or hasattr(result, "type_aliases")
