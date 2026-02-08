"""Tests for RustExtractor call-site extraction and import pending references."""

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

    def _write(content: str, name: str = "lib.rs") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestRustCallExtraction:
    """Tests for function/method call extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_function_call(self, extractor, write_rust_file) -> None:
        """Calls inside a function body produce pending references."""
        code = """
fn main() {
    process_data();
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "process_data" in func.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].target_qualified_name == "process_data"

    @pytest.mark.asyncio
    async def test_extract_self_method_call(self, extractor, write_rust_file) -> None:
        """self.method() resolves to StructName.method."""
        code = """
struct MyService {
    value: i32,
}

impl MyService {
    fn run(&self) {
        self.helper();
    }

    fn helper(&self) {}
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        run_method = next(m for m in result.methods if m.name == "run")
        assert "MyService.helper" in run_method.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "MyService.helper" for r in call_refs)

    @pytest.mark.asyncio
    async def test_extract_scoped_call(self, extractor, write_rust_file) -> None:
        """Scoped calls like Vec::new() are captured."""
        code = """
fn create() {
    let v = Vec::new();
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "Vec::new" in func.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "Vec::new" for r in call_refs)

    @pytest.mark.asyncio
    async def test_skip_macro_calls(self, extractor, write_rust_file) -> None:
        """Macro invocations like println! are not captured as call_expression."""
        code = """
fn greet() {
    println!("Hello");
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        func = result.functions[0]
        # println! is a macro, not a call_expression, so should not appear
        assert func.calls == []

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_calls(self, extractor, write_rust_file) -> None:
        """Same callee called multiple times produces one pending reference."""
        code = """
fn process() {
    helper();
    helper();
    helper();
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls.count("helper") == 1

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1

    @pytest.mark.asyncio
    async def test_calls_populate_entity_calls_list(self, extractor, write_rust_file) -> None:
        """entity.calls field is populated with callee names."""
        code = """
fn orchestrate() {
    fetch_data();
    transform();
    save_results();
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert set(func.calls) == {"fetch_data", "transform", "save_results"}

    @pytest.mark.asyncio
    async def test_pending_ref_source_matches_entity(self, extractor, write_rust_file) -> None:
        """Pending reference source_entity_id matches the containing function."""
        code = """
fn caller() {
    target_func();
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        func = result.functions[0]
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].source_entity_id == func.id
        assert call_refs[0].source_qualified_name == func.qualified_name


class TestRustImportPendingReferences:
    """Tests for import pending reference creation."""

    @pytest.mark.asyncio
    async def test_import_creates_pending_reference(self, extractor, write_rust_file) -> None:
        """Each use statement creates a pending reference with IMPORTS relation type."""
        code = "use std::collections::HashMap;"
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        assert len(result.imports) == 1
        import_refs = [r for r in result.pending_references if r.relation_type == "imports"]
        assert len(import_refs) == 1
        assert import_refs[0].source_entity_id == result.imports[0].id
        assert "HashMap" in import_refs[0].target_qualified_name

    @pytest.mark.asyncio
    async def test_multiple_imports_create_pending_references(
        self, extractor, write_rust_file
    ) -> None:
        """Multiple use statements each create a pending reference."""
        code = """
use std::io;
use std::fs;
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        assert len(result.imports) == 2
        import_refs = [r for r in result.pending_references if r.relation_type == "imports"]
        assert len(import_refs) == 2


class TestRustReceiverExtraction:
    """Test receiver expression extraction for Rust."""

    @pytest.mark.asyncio
    async def test_method_call_receiver(self, extractor, write_rust_file) -> None:
        """Test: obj.method() captures receiver 'obj'."""
        code = """
fn process() {
    writer.write();
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        # Should have one pending reference
        assert len(result.pending_references) == 1
        ref = result.pending_references[0]
        assert ref.target_qualified_name == "writer.write"
        assert ref.relation_type == "calls"
        assert ref.receiver_expr == "writer"

    @pytest.mark.asyncio
    async def test_chained_method_call_receiver(self, extractor, write_rust_file) -> None:
        """Test: ctx.redis.get() captures receiver 'ctx.redis'."""
        code = """
fn process() {
    ctx.redis.get();
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        assert len(result.pending_references) == 1
        ref = result.pending_references[0]
        assert ref.target_qualified_name == "ctx.redis.get"
        assert ref.receiver_expr == "ctx.redis"

    @pytest.mark.asyncio
    async def test_no_receiver_direct_call(self, extractor, write_rust_file) -> None:
        """Test: do_work() has no receiver."""
        code = """
fn process() {
    do_work();
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        assert len(result.pending_references) == 1
        ref = result.pending_references[0]
        assert ref.target_qualified_name == "do_work"
        assert ref.receiver_expr is None

    @pytest.mark.asyncio
    async def test_self_method_call_no_receiver(self, extractor, write_rust_file) -> None:
        """Test: self.helper() has no receiver (already resolved to ClassName.method)."""
        code = """
struct Service;

impl Service {
    fn run(&self) {
        self.helper();
    }

    fn helper(&self) {}
}
"""
        result = await extractor.extract(write_rust_file(code), uuid4(), uuid4())

        # Find the call from 'run' to 'helper' with correct target_qualified_name
        call_refs = [
            r
            for r in result.pending_references
            if r.relation_type == "calls" and r.target_qualified_name == "Service.helper"
        ]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "Service.helper"
        assert ref.receiver_expr is None  # self calls don't have receiver_expr
