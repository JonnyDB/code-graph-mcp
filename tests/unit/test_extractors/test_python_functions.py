"""Tests for PythonExtractor function extraction."""

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


class TestPythonFunctionExtraction:
    """Tests for function extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_function(self, extractor, write_py_file) -> None:
        """Test extracting a simple function."""
        code = """
def hello():
    pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "hello"
        assert func.parameters == []

    @pytest.mark.asyncio
    async def test_extract_function_with_params(self, extractor, write_py_file) -> None:
        """Test extracting function with parameters."""
        code = """
def add(x, y):
    return x + y
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        func = result.functions[0]
        assert len(func.parameters) == 2
        assert func.parameters[0].name == "x"
        assert func.parameters[1].name == "y"

    @pytest.mark.asyncio
    async def test_extract_function_with_typed_params(self, extractor, write_py_file) -> None:
        """Test extracting function with typed parameters."""
        code = """
def process(data: str, count: int) -> bool:
    return True
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        func = result.functions[0]
        assert func.parameters[0].type_annotation == "str"
        assert func.parameters[1].type_annotation == "int"
        assert func.return_type == "bool"

    @pytest.mark.asyncio
    async def test_extract_async_function(self, extractor, write_py_file) -> None:
        """Test extracting async function."""
        code = """
async def fetch_data():
    pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        func = result.functions[0]
        assert func.is_async is True

    @pytest.mark.asyncio
    async def test_extract_function_docstring(self, extractor, write_py_file) -> None:
        """Test extracting function docstring."""
        code = '''
def helper():
    """This is the helper function."""
    pass
'''
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        func = result.functions[0]
        assert func.docstring == "This is the helper function."


class TestPythonMethodExtraction:
    """Tests for method extraction."""

    @pytest.mark.asyncio
    async def test_extract_method(self, extractor, write_py_file) -> None:
        """Test extracting a method within class."""
        code = """
class MyClass:
    def my_method(self):
        pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.name == "my_method"
        assert "MyClass" in method.parent_class

    @pytest.mark.asyncio
    async def test_extract_init_as_constructor(self, extractor, write_py_file) -> None:
        """Test __init__ is marked as constructor."""
        code = """
class MyClass:
    def __init__(self, value):
        self.value = value
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        method = result.methods[0]
        assert method.name == "__init__"
        assert method.is_constructor is True

    @pytest.mark.asyncio
    async def test_extract_static_method(self, extractor, write_py_file) -> None:
        """Test extracting staticmethod."""
        code = """
class MyClass:
    @staticmethod
    def static_method():
        pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        method = result.methods[0]
        assert method.is_static is True

    @pytest.mark.asyncio
    async def test_extract_classmethod(self, extractor, write_py_file) -> None:
        """Test extracting classmethod."""
        code = """
class MyClass:
    @classmethod
    def class_method(cls):
        pass
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        method = result.methods[0]
        assert method.is_classmethod is True

    @pytest.mark.asyncio
    async def test_extract_property(self, extractor, write_py_file) -> None:
        """Test extracting property."""
        code = """
class MyClass:
    @property
    def value(self):
        return self._value
"""
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        method = result.methods[0]
        assert method.is_property is True


class TestSourceText:
    """Tests that source_text is populated on extracted entities."""

    @pytest.mark.asyncio
    async def test_function_has_source_text(self, extractor, write_py_file) -> None:
        """Extracted functions should include their source text."""
        code = 'def greet(name: str) -> str:\n    """Say hello."""\n    return f"Hello {name}"\n'
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        func = result.functions[0]
        assert func.source_text is not None
        assert "def greet" in func.source_text
        assert "return f" in func.source_text

    @pytest.mark.asyncio
    async def test_method_has_source_text(self, extractor, write_py_file) -> None:
        """Extracted methods should include their source text."""
        code = "class Foo:\n    def bar(self) -> None:\n        pass\n"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        method = result.methods[0]
        assert method.source_text is not None
        assert "def bar" in method.source_text

    @pytest.mark.asyncio
    async def test_class_has_source_text(self, extractor, write_py_file) -> None:
        """Extracted classes should include their source text."""
        code = "class MyClass:\n    x = 1\n"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        cls = result.classes[0]
        assert cls.source_text is not None
        assert "class MyClass" in cls.source_text

    @pytest.mark.asyncio
    async def test_decorated_function_includes_decorator(self, extractor, write_py_file) -> None:
        """Source text for decorated functions should include the decorator."""
        code = "@staticmethod\ndef helper() -> None:\n    pass\n"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        func = result.functions[0]
        assert func.source_text is not None
        assert "@staticmethod" in func.source_text
        assert "def helper" in func.source_text
