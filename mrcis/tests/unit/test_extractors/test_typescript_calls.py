"""Tests for TypeScriptExtractor call-site extraction."""

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

    def _write(content: str, name: str = "test_module.ts") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestTypeScriptCallExtraction:
    """Tests for function/method call extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_function_call(self, extractor, write_ts_file) -> None:
        """Calls inside a function body produce pending references."""
        code = """
function main() {
    processData();
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "processData" in func.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].target_qualified_name == "processData"

    @pytest.mark.asyncio
    async def test_extract_method_call_on_this(self, extractor, write_ts_file) -> None:
        """this.method() resolves to ClassName.method."""
        code = """
class MyClass {
    run(): void {
        this.helper();
    }
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert "MyClass.helper" in method.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "MyClass.helper" for r in call_refs)

    @pytest.mark.asyncio
    async def test_extract_new_expression_instantiates(self, extractor, write_ts_file) -> None:
        """new MyClass() uses INSTANTIATES relation type."""
        code = """
function create() {
    const obj = new MyClass();
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "MyClass" in func.calls

        inst_refs = [r for r in result.pending_references if r.relation_type == "instantiates"]
        assert len(inst_refs) == 1
        assert inst_refs[0].target_qualified_name == "MyClass"

    @pytest.mark.asyncio
    async def test_console_methods_skipped(self, extractor, write_ts_file) -> None:
        """Console methods are not captured."""
        code = """
function debug() {
    console.log("hello");
    console.error("oops");
    console.warn("warning");
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls == []

        call_refs = [
            r for r in result.pending_references if r.relation_type in ("calls", "instantiates")
        ]
        assert len(call_refs) == 0

    @pytest.mark.asyncio
    async def test_method_qualified_name_not_doubled(self, extractor, write_ts_file) -> None:
        """Method qualified_name should be module.Class.method, not module.module.Class.method."""
        code = """
class MyClass {
    myMethod(): void {
        // empty
    }
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())

        method = result.methods[0]
        # File is test_module.ts, so module_name = "test_module"
        assert method.qualified_name == "test_module.MyClass.myMethod"
        assert method.qualified_name.count("test_module") == 1


class TestTypeScriptCallDetails:
    """Additional tests for TypeScript call extraction details."""

    @pytest.mark.asyncio
    async def test_no_duplicate_calls(self, extractor, write_ts_file) -> None:
        """Same callee called multiple times produces one pending reference."""
        code = """
function process() {
    helper();
    helper();
    helper();
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls.count("helper") == 1

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1

    @pytest.mark.asyncio
    async def test_calls_populate_entity_calls_list(self, extractor, write_ts_file) -> None:
        """entity.calls field is populated with callee names."""
        code = """
function orchestrate() {
    fetchData();
    transform();
    saveResults();
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert set(func.calls) == {"fetchData", "transform", "saveResults"}

    @pytest.mark.asyncio
    async def test_pending_ref_source_matches_entity(self, extractor, write_ts_file) -> None:
        """Pending reference source_entity_id matches the containing function."""
        code = """
function caller() {
    targetFunc();
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())

        func = result.functions[0]
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].source_entity_id == func.id
        assert call_refs[0].source_qualified_name == func.qualified_name


class TestTypeScriptReceiverExtraction:
    """Tests for receiver expression extraction in TypeScript."""

    @pytest.mark.asyncio
    async def test_member_call_receiver(self, extractor, write_ts_file) -> None:
        """obj.method() captures 'obj' as receiver_expr."""
        code = """
function main() {
    logger.info("test");
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        matching = [r for r in call_refs if r.target_qualified_name.endswith("info")]
        assert len(matching) == 1
        assert matching[0].receiver_expr == "logger"

    @pytest.mark.asyncio
    async def test_this_call_no_receiver(self, extractor, write_ts_file) -> None:
        """this.method() should have no receiver_expr."""
        code = """
class Service {
    run() {
        this.helper();
    }
}
"""
        result = await extractor.extract(write_ts_file(code), uuid4(), uuid4())
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        matching = [r for r in call_refs if "helper" in r.target_qualified_name]
        assert len(matching) == 1
        assert matching[0].receiver_expr is None
