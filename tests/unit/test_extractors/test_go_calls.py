"""Tests for GoExtractor call-site extraction and import pending references."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.go import GoExtractor


@pytest.fixture
def extractor():
    """Provide GoExtractor instance."""
    return GoExtractor()


@pytest.fixture
def write_go_file(tmp_path: Path):
    """Factory fixture to write Go files."""

    def _write(content: str, name: str = "main.go") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestGoCallExtraction:
    """Tests for function/method call extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_function_call(self, extractor, write_go_file) -> None:
        """Calls inside a function body produce pending references."""
        code = """package main

func main() {
    processData()
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "processData" in func.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].target_qualified_name == "processData"

    @pytest.mark.asyncio
    async def test_extract_package_qualified_call(self, extractor, write_go_file) -> None:
        """Package-qualified calls like strings.Contains() are captured."""
        code = """package main

import "strings"

func check(s string) bool {
    return strings.Contains(s, "hello")
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "strings.Contains" in func.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "strings.Contains" for r in call_refs)

    @pytest.mark.asyncio
    async def test_skip_builtin_calls(self, extractor, write_go_file) -> None:
        """Built-in calls are not captured."""
        code = """package main

func process() {
    s := make([]int, 10)
    n := len(s)
    _ = n
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls == []

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_calls(self, extractor, write_go_file) -> None:
        """Same callee called multiple times produces one pending reference."""
        code = """package main

func process() {
    helper()
    helper()
    helper()
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert func.calls.count("helper") == 1

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1

    @pytest.mark.asyncio
    async def test_calls_in_method(self, extractor, write_go_file) -> None:
        """Calls inside methods are captured."""
        code = """package main

type Service struct{}

func (s *Service) Run() {
    initialize()
    execute()
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert "initialize" in method.calls
        assert "execute" in method.calls

    @pytest.mark.asyncio
    async def test_pending_ref_source_matches_entity(self, extractor, write_go_file) -> None:
        """Pending reference source_entity_id matches the containing function."""
        code = """package main

func caller() {
    targetFunc()
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        func = result.functions[0]
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].source_entity_id == func.id
        assert call_refs[0].source_qualified_name == func.qualified_name


class TestGoImportPendingReferences:
    """Tests for import pending reference creation."""

    @pytest.mark.asyncio
    async def test_import_creates_pending_reference(self, extractor, write_go_file) -> None:
        """Each import creates a pending reference with IMPORTS relation type."""
        code = """package main

import "fmt"
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        assert len(result.imports) == 1
        import_refs = [r for r in result.pending_references if r.relation_type == "imports"]
        assert len(import_refs) == 1
        assert import_refs[0].target_qualified_name == "fmt"
        assert import_refs[0].source_entity_id == result.imports[0].id

    @pytest.mark.asyncio
    async def test_import_block_creates_pending_references(self, extractor, write_go_file) -> None:
        """Import block creates a pending reference for each import."""
        code = """package main

import (
    "fmt"
    "strings"
)
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        assert len(result.imports) == 2
        import_refs = [r for r in result.pending_references if r.relation_type == "imports"]
        assert len(import_refs) == 2
        targets = {r.target_qualified_name for r in import_refs}
        assert "fmt" in targets
        assert "strings" in targets


class TestGoReceiverExtraction:
    """Test receiver expression extraction for Go."""

    @pytest.mark.asyncio
    async def test_method_call_receiver(self, extractor, write_go_file) -> None:
        """Test: obj.Method() captures receiver 'obj'."""
        code = """package main

func Process() {
    writer.Write()
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        # Should have one pending reference
        assert len(result.pending_references) == 1
        ref = result.pending_references[0]
        assert ref.target_qualified_name == "writer.Write"
        assert ref.relation_type == "calls"
        assert ref.receiver_expr == "writer"

    @pytest.mark.asyncio
    async def test_chained_method_call_receiver(self, extractor, write_go_file) -> None:
        """Test: ctx.redis.Get() captures receiver 'ctx.redis'."""
        code = """package main

func Process() {
    ctx.redis.Get()
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        assert len(result.pending_references) == 1
        ref = result.pending_references[0]
        assert ref.target_qualified_name == "ctx.redis.Get"
        assert ref.receiver_expr == "ctx.redis"

    @pytest.mark.asyncio
    async def test_no_receiver_direct_call(self, extractor, write_go_file) -> None:
        """Test: DoWork() has no receiver."""
        code = """package main

func Process() {
    DoWork()
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        assert len(result.pending_references) == 1
        ref = result.pending_references[0]
        assert ref.target_qualified_name == "DoWork"
        assert ref.receiver_expr is None

    @pytest.mark.asyncio
    async def test_package_qualified_call(self, extractor, write_go_file) -> None:
        """Test: fmt.Println() captures receiver 'fmt'."""
        code = """package main

func Process() {
    fmt.Println("hello")
}
"""
        result = await extractor.extract(write_go_file(code), uuid4(), uuid4())

        assert len(result.pending_references) == 1
        ref = result.pending_references[0]
        assert ref.target_qualified_name == "fmt.Println"
        assert ref.receiver_expr == "fmt"
