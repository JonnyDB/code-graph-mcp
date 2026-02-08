"""Tests for PythonExtractor call-site extraction."""

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

    def _write(content: str, name: str = "test_module.py") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestPythonCallExtraction:
    """Tests for function/method call extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_function_call(self, extractor, write_py_file) -> None:
        """Calls inside a function body produce pending references."""
        code = """
def main():
    process_data()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "process_data" in func.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].target_qualified_name == "process_data"

    @pytest.mark.asyncio
    async def test_extract_method_call_on_self(self, extractor, write_py_file) -> None:
        """self.method() resolves to ClassName.method."""
        code = """
class MyClass:
    def run(self):
        self.helper()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert "MyClass.helper" in method.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "MyClass.helper" for r in call_refs)

    @pytest.mark.asyncio
    async def test_extract_cls_method_call(self, extractor, write_py_file) -> None:
        """cls.method() resolves to ClassName.method."""
        code = """
class Factory:
    @classmethod
    def create(cls):
        cls.validate()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert "Factory.validate" in method.calls

    @pytest.mark.asyncio
    async def test_extract_dotted_call(self, extractor, write_py_file) -> None:
        """module.func() captures full dotted name."""
        code = """
def process():
    os.path.join("a", "b")
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "os.path.join" in func.calls

    @pytest.mark.asyncio
    async def test_skip_builtin_calls(self, extractor, write_py_file) -> None:
        """Built-in calls are not captured."""
        code = """
def process():
    print("hello")
    x = len([1, 2])
    isinstance(x, int)
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls == []

        call_refs = [
            r for r in result.pending_references if r.relation_type in ("calls", "instantiates")
        ]
        assert len(call_refs) == 0

    @pytest.mark.asyncio
    async def test_instantiation_detection(self, extractor, write_py_file) -> None:
        """Uppercase-first names use INSTANTIATES relation type."""
        code = """
def create():
    obj = MyClass()
    path = Path("/tmp")
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        inst_refs = [r for r in result.pending_references if r.relation_type == "instantiates"]
        targets = {r.target_qualified_name for r in inst_refs}
        assert "MyClass" in targets
        assert "Path" in targets

    @pytest.mark.asyncio
    async def test_no_duplicate_calls(self, extractor, write_py_file) -> None:
        """Same callee called multiple times produces one pending reference."""
        code = """
def process():
    helper()
    helper()
    helper()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls.count("helper") == 1

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1

    @pytest.mark.asyncio
    async def test_calls_in_constructor(self, extractor, write_py_file) -> None:
        """Calls inside __init__ are captured."""
        code = """
class Service:
    def __init__(self):
        self.setup()
        configure()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        init_method = next(m for m in result.methods if m.name == "__init__")
        assert "Service.setup" in init_method.calls
        assert "configure" in init_method.calls

    @pytest.mark.asyncio
    async def test_calls_populate_entity_calls_list(self, extractor, write_py_file) -> None:
        """entity.calls field is populated with callee names."""
        code = """
def orchestrate():
    fetch_data()
    transform()
    save_results()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert set(func.calls) == {"fetch_data", "transform", "save_results"}

    @pytest.mark.asyncio
    async def test_pending_ref_source_matches_entity(self, extractor, write_py_file) -> None:
        """Pending reference source_entity_id matches the containing function."""
        code = """
def caller():
    target_func()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        func = result.functions[0]
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].source_entity_id == func.id
        assert call_refs[0].source_qualified_name == func.qualified_name


class TestPythonQualifiedNames:
    """Regression tests for method qualified name correctness."""

    @pytest.mark.asyncio
    async def test_method_qualified_name_not_doubled(self, extractor, write_py_file) -> None:
        """Method qualified_name should be module.Class.method, not module.module.Class.method."""
        code = """
class MyClass:
    def my_method(self):
        pass
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        method = result.methods[0]
        # File is test_module.py, so module_name = "test_module"
        assert method.qualified_name == "test_module.MyClass.my_method"
        assert method.qualified_name.count("test_module") == 1

    @pytest.mark.asyncio
    async def test_top_level_function_qualified_name(self, extractor, write_py_file) -> None:
        """Top-level function qualified_name should be module.func."""
        code = """
def my_func():
    pass
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.qualified_name == "test_module.my_func"


class TestPythonReceiverExtraction:
    """Tests for receiver expression extraction."""

    @pytest.mark.asyncio
    async def test_simple_function_call_no_receiver(self, extractor, write_py_file) -> None:
        """Direct function calls have no receiver."""
        code = """
def main():
    process_data()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].receiver_expr is None

    @pytest.mark.asyncio
    async def test_method_call_on_object_has_receiver(self, extractor, write_py_file) -> None:
        """obj.method() captures 'obj' as receiver_expr."""
        code = """
def main():
    chart_writer.get("field")
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].receiver_expr == "chart_writer"

    @pytest.mark.asyncio
    async def test_chained_method_call_receiver(self, extractor, write_py_file) -> None:
        """ctx.redis.get() captures 'ctx.redis' as receiver_expr."""
        code = """
def main():
    ctx.redis.get("key")
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].receiver_expr == "ctx.redis"

    @pytest.mark.asyncio
    async def test_self_call_receiver_is_class_name(self, extractor, write_py_file) -> None:
        """self.method() receiver_expr should be None (already resolved to ClassName.method)."""
        code = """
class MyClass:
    def run(self):
        self.helper()
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        # self/cls calls are already resolved to ClassName.method, no receiver needed
        assert call_refs[0].receiver_expr is None

    @pytest.mark.asyncio
    async def test_module_call_receiver(self, extractor, write_py_file) -> None:
        """os.path.join() captures 'os.path' as receiver_expr."""
        code = """
def main():
    os.path.join("a", "b")
"""
        result = await extractor.extract(write_py_file(code), uuid4(), uuid4())
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].receiver_expr == "os.path"
