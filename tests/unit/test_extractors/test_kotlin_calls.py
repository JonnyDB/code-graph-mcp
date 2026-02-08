"""Tests for KotlinExtractor call-site extraction."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.kotlin import KotlinExtractor


@pytest.fixture
def extractor():
    """Provide KotlinExtractor instance."""
    return KotlinExtractor()


@pytest.fixture
def write_kt_file(tmp_path: Path):
    """Factory fixture to write Kotlin files."""

    def _write(content: str, name: str = "TestClass.kt") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestKotlinCallExtraction:
    """Tests for function/method call extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_function_call(self, extractor, write_kt_file) -> None:
        """Calls inside a function body produce pending references."""
        code = """package com.example

fun main() {
    processData()
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "processData" in func.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "processData" for r in call_refs)

    @pytest.mark.asyncio
    async def test_this_method_resolves_to_class(self, extractor, write_kt_file) -> None:
        """this.method() resolves to ClassName.method."""
        code = """package com.example

class MyClass {
    fun run() {
        this.helper()
    }
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        method = next(m for m in result.methods if m.name == "run")
        assert "MyClass.helper" in method.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "MyClass.helper" for r in call_refs)

    @pytest.mark.asyncio
    async def test_uppercase_first_uses_instantiates(self, extractor, write_kt_file) -> None:
        """Uppercase-first callee uses INSTANTIATES relation type."""
        code = """package com.example

fun create() {
    val user = User()
    val path = Path("/tmp")
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        inst_refs = [r for r in result.pending_references if r.relation_type == "instantiates"]
        targets = {r.target_qualified_name for r in inst_refs}
        assert "User" in targets
        assert "Path" in targets

    @pytest.mark.asyncio
    async def test_skip_builtin_calls(self, extractor, write_kt_file) -> None:
        """Built-in calls are not captured."""
        code = """package com.example

fun show() {
    println("hello")
    print("world")
    val items = listOf(1, 2, 3)
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls == []

        call_refs = [
            r for r in result.pending_references if r.relation_type in ("calls", "instantiates")
        ]
        assert len(call_refs) == 0

    @pytest.mark.asyncio
    async def test_calls_in_method(self, extractor, write_kt_file) -> None:
        """Calls inside a class method body produce pending references."""
        code = """package com.example

class Service {
    fun execute() {
        doWork()
    }
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        method = next(m for m in result.methods if m.name == "execute")
        assert "doWork" in method.calls

    @pytest.mark.asyncio
    async def test_no_duplicate_calls(self, extractor, write_kt_file) -> None:
        """Same callee called multiple times produces one pending reference."""
        code = """package com.example

fun process() {
    helper()
    helper()
    helper()
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls.count("helper") == 1

    @pytest.mark.asyncio
    async def test_pending_ref_source_matches_entity(self, extractor, write_kt_file) -> None:
        """Pending reference source_entity_id matches the containing function."""
        code = """package com.example

fun caller() {
    targetFunc()
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        func = result.functions[0]
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].source_entity_id == func.id
        assert call_refs[0].source_qualified_name == func.qualified_name


class TestKotlinReceiverExtraction:
    """Test receiver expression extraction for Kotlin."""

    @pytest.mark.asyncio
    async def test_method_call_receiver(self, extractor, write_kt_file) -> None:
        """Test: obj.method() captures receiver 'obj'."""
        code = """package com.example

fun process() {
    writer.write()
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        # Should have one pending reference
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "writer.write"
        assert ref.receiver_expr == "writer"

    @pytest.mark.asyncio
    async def test_chained_method_call_receiver(self, extractor, write_kt_file) -> None:
        """Test: ctx.redis.get() captures receiver 'ctx.redis'."""
        code = """package com.example

fun process() {
    ctx.redis.get()
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "ctx.redis.get"
        assert ref.receiver_expr == "ctx.redis"

    @pytest.mark.asyncio
    async def test_no_receiver_direct_call(self, extractor, write_kt_file) -> None:
        """Test: doWork() has no receiver."""
        code = """package com.example

fun process() {
    doWork()
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "doWork"
        assert ref.receiver_expr is None

    @pytest.mark.asyncio
    async def test_this_method_call_no_receiver(self, extractor, write_kt_file) -> None:
        """Test: this.helper() has no receiver (already resolved to ClassName.method)."""
        code = """package com.example

class Service {
    fun run() {
        this.helper()
    }

    fun helper() {}
}
"""
        result = await extractor.extract(write_kt_file(code), uuid4(), uuid4())

        # Find the call from 'run' to 'helper'
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "Service.helper"
        assert ref.receiver_expr is None  # this calls don't have receiver_expr
