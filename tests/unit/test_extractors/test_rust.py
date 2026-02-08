"""Tests for RustExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.rust import RustExtractor


@pytest.fixture
def extractor():
    """Provide RustExtractor instance."""
    return RustExtractor()


@pytest.fixture
def write_rust_file(tmp_path: Path):
    """Factory fixture to write Rust files."""

    def _write(content: str) -> Path:
        file_path = tmp_path / "lib.rs"
        file_path.write_text(content)
        return file_path

    return _write


class TestRustExtractorSupports:
    """Tests for file support detection."""

    def test_supports_rs_files(self, extractor) -> None:
        """Test supports .rs files."""
        assert extractor.supports(Path("main.rs"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support non-Rust files."""
        assert not extractor.supports(Path("main.py"))


class TestRustImportExtraction:
    """Tests for use statement extraction."""

    @pytest.mark.asyncio
    async def test_extract_use_statement(self, extractor, write_rust_file) -> None:
        """Test extracting use statements."""
        code = "use std::collections::HashMap;"
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "std::collections"

    @pytest.mark.asyncio
    async def test_extract_use_with_alias(self, extractor, write_rust_file) -> None:
        """Test extracting use statements with aliases."""
        code = "use std::collections::HashMap as Map;"
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert "Map" in result.imports[0].imported_symbols

    @pytest.mark.asyncio
    async def test_extract_use_glob(self, extractor, write_rust_file) -> None:
        """Test extracting use glob statements."""
        code = "use std::collections::*;"
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1


class TestRustStructExtraction:
    """Tests for struct extraction."""

    @pytest.mark.asyncio
    async def test_extract_struct(self, extractor, write_rust_file) -> None:
        """Test extracting struct definitions."""
        code = """
struct User {
    id: u64,
    name: String,
}
"""
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        assert result.classes[0].name == "User"

    @pytest.mark.asyncio
    async def test_extract_tuple_struct(self, extractor, write_rust_file) -> None:
        """Test extracting tuple structs."""
        code = "struct Point(i32, i32);"
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        assert result.classes[0].name == "Point"


class TestRustEnumExtraction:
    """Tests for enum extraction."""

    @pytest.mark.asyncio
    async def test_extract_enum(self, extractor, write_rust_file) -> None:
        """Test extracting enum definitions."""
        code = """
enum Status {
    Active,
    Inactive,
}
"""
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) >= 1
        # Enums are stored as classes
        enum_names = [c.name for c in result.classes]
        assert "Status" in enum_names


class TestRustTraitExtraction:
    """Tests for trait extraction."""

    @pytest.mark.asyncio
    async def test_extract_trait(self, extractor, write_rust_file) -> None:
        """Test extracting trait definitions."""
        code = """
trait Greet {
    fn greet(&self) -> String;
}
"""
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) >= 1
        # Traits are stored as abstract classes
        trait_names = [c.name for c in result.classes if c.is_abstract]
        assert "Greet" in trait_names


class TestRustFunctionExtraction:
    """Tests for function extraction."""

    @pytest.mark.asyncio
    async def test_extract_function(self, extractor, write_rust_file) -> None:
        """Test extracting function definitions."""
        code = """
fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "add"
        assert func.return_type == "i32"

    @pytest.mark.asyncio
    async def test_extract_pub_function(self, extractor, write_rust_file) -> None:
        """Test extracting public functions."""
        code = """
pub fn greet(name: &str) -> String {
    format!("Hello, {}", name)
}
"""
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        assert result.functions[0].name == "greet"


class TestRustImplExtraction:
    """Tests for impl block extraction."""

    @pytest.mark.asyncio
    async def test_extract_impl_methods(self, extractor, write_rust_file) -> None:
        """Test extracting methods from impl blocks."""
        code = """
struct User {
    name: String,
}

impl User {
    fn new(name: String) -> Self {
        User { name }
    }

    fn greet(&self) -> String {
        format!("Hello, {}", self.name)
    }
}
"""
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) >= 2
        method_names = [m.name for m in result.methods]
        assert "new" in method_names
        assert "greet" in method_names

    @pytest.mark.asyncio
    async def test_extract_trait_impl(self, extractor, write_rust_file) -> None:
        """Test extracting trait implementations."""
        code = """
trait Display {
    fn display(&self) -> String;
}

struct User {
    name: String,
}

impl Display for User {
    fn display(&self) -> String {
        self.name.clone()
    }
}
"""
        file_path = write_rust_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract both the trait and the impl methods
        assert len(result.classes) >= 2  # trait and struct
        assert len(result.methods) >= 1  # impl method
