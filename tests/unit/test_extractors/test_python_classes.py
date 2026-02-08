"""Tests for PythonExtractor class extraction."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.python import PythonExtractor


@pytest.fixture
def extractor():
    """Provide PythonExtractor instance."""
    return PythonExtractor()


@pytest.fixture
def write_py_file(tmp_path: Path):
    """Factory fixture to write Python files."""

    def _write(content: str) -> Path:
        file_path = tmp_path / "test_module.py"
        file_path.write_text(content)
        return file_path

    return _write


class TestPythonClassExtraction:
    """Tests for class extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_class(self, extractor, write_py_file) -> None:
        """Test extracting a simple class."""
        code = """
class MyClass:
    pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "MyClass"
        assert cls.base_classes == []

    @pytest.mark.asyncio
    async def test_extract_class_with_inheritance(self, extractor, write_py_file) -> None:
        """Test extracting class with base class."""
        code = """
class ChildClass(ParentClass):
    pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "ChildClass"
        assert "ParentClass" in cls.base_classes

    @pytest.mark.asyncio
    async def test_extract_class_with_multiple_bases(self, extractor, write_py_file) -> None:
        """Test extracting class with multiple inheritance."""
        code = """
class MyClass(BaseA, BaseB, BaseC):
    pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        cls = result.classes[0]
        assert len(cls.base_classes) == 3
        assert "BaseA" in cls.base_classes
        assert "BaseB" in cls.base_classes
        assert "BaseC" in cls.base_classes

    @pytest.mark.asyncio
    async def test_extract_class_with_docstring(self, extractor, write_py_file) -> None:
        """Test extracting class docstring."""
        code = '''
class MyClass:
    """This is my class docstring."""
    pass
'''
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        cls = result.classes[0]
        assert cls.docstring == "This is my class docstring."

    @pytest.mark.asyncio
    async def test_extract_dataclass(self, extractor, write_py_file) -> None:
        """Test extracting dataclass."""
        code = """
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        cls = result.classes[0]
        assert cls.name == "Point"
        assert cls.is_dataclass is True

    @pytest.mark.asyncio
    async def test_class_creates_pending_reference(self, extractor, write_py_file) -> None:
        """Test class inheritance creates pending reference."""
        code = """
class UserValidator(BaseValidator):
    pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should have pending reference for base class
        refs = [r for r in result.pending_references if r.target_qualified_name == "BaseValidator"]
        assert len(refs) == 1
        assert refs[0].relation_type == "extends"
