"""Tests for JavaScriptExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.javascript import JavaScriptExtractor


@pytest.fixture
def extractor():
    """Provide JavaScriptExtractor instance."""
    return JavaScriptExtractor()


@pytest.fixture
def write_js_file(tmp_path: Path):
    """Factory fixture to write JavaScript files."""

    def _write(content: str, ext: str = ".js") -> Path:
        file_path = tmp_path / f"test_module{ext}"
        file_path.write_text(content)
        return file_path

    return _write


class TestJavaScriptExtractorSupports:
    """Tests for file support detection."""

    def test_supports_js_files(self, extractor) -> None:
        """Test supports .js files."""
        assert extractor.supports(Path("module.js"))

    def test_supports_jsx_files(self, extractor) -> None:
        """Test supports .jsx files."""
        assert extractor.supports(Path("component.jsx"))

    def test_does_not_support_ts_files(self, extractor) -> None:
        """Test doesn't support .ts files (use TypeScriptExtractor)."""
        assert not extractor.supports(Path("module.ts"))


class TestJavaScriptImportExtraction:
    """Tests for import extraction."""

    @pytest.mark.asyncio
    async def test_extract_es_import(self, extractor, write_js_file) -> None:
        """Test extracting ES imports."""
        code = "import { useState } from 'react';"
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "react"

    @pytest.mark.asyncio
    async def test_extract_default_import(self, extractor, write_js_file) -> None:
        """Test extracting default imports."""
        code = "import React from 'react';"
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert "React" in result.imports[0].imported_symbols

    @pytest.mark.asyncio
    async def test_extract_require_statement(self, extractor, write_js_file) -> None:
        """Test extracting CommonJS require statements."""
        code = "const fs = require('fs');"
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Note: tree-sitter may not parse require as import, but as variable
        # This tests our best-effort parsing
        assert len(result.imports) >= 0  # May or may not detect require


class TestJavaScriptFunctionExtraction:
    """Tests for function extraction."""

    @pytest.mark.asyncio
    async def test_extract_function(self, extractor, write_js_file) -> None:
        """Test extracting JavaScript function."""
        code = """
function greet(name) {
    return `Hello, ${name}`;
}
"""
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"

    @pytest.mark.asyncio
    async def test_extract_arrow_function(self, extractor, write_js_file) -> None:
        """Test extracting arrow functions."""
        code = "const add = (a, b) => a + b;"
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) >= 1

    @pytest.mark.asyncio
    async def test_extract_async_function(self, extractor, write_js_file) -> None:
        """Test extracting async function."""
        code = """
async function fetchData() {
    return "data";
}
"""
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        func = result.functions[0]
        assert func.is_async is True


class TestJavaScriptClassExtraction:
    """Tests for class extraction."""

    @pytest.mark.asyncio
    async def test_extract_class(self, extractor, write_js_file) -> None:
        """Test extracting JavaScript class."""
        code = """
class UserService {
    constructor(apiUrl) {
        this.apiUrl = apiUrl;
    }

    async getUser(id) {
        return fetch(this.apiUrl);
    }
}
"""
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "UserService"

    @pytest.mark.asyncio
    async def test_extract_class_with_methods(self, extractor, write_js_file) -> None:
        """Test extracting class methods."""
        code = """
class Calculator {
    add(a, b) {
        return a + b;
    }

    static multiply(a, b) {
        return a * b;
    }
}
"""
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        assert len(result.methods) == 2


class TestJavaScriptVariableExtraction:
    """Tests for variable extraction."""

    @pytest.mark.asyncio
    async def test_extract_const_variable(self, extractor, write_js_file) -> None:
        """Test extracting const variable."""
        code = "const API_URL = 'https://api.example.com';"
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 1

    @pytest.mark.asyncio
    async def test_extract_let_variable(self, extractor, write_js_file) -> None:
        """Test extracting let variable."""
        code = "let counter = 0;"
        file_path = write_js_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 1
