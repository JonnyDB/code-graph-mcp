"""Tests for RubyExtractor call-site extraction."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.ruby import RubyExtractor


@pytest.fixture
def extractor():
    """Provide RubyExtractor instance."""
    return RubyExtractor()


@pytest.fixture
def write_rb_file(tmp_path: Path):
    """Factory fixture to write Ruby files."""

    def _write(content: str, name: str = "test_module.rb") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestRubyCallExtraction:
    """Tests for function/method call extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_method_call(self, extractor, write_rb_file) -> None:
        """Calls inside a method body produce pending references."""
        code = """class Service
  def run
    process_data()
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert "process_data" in method.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "process_data" for r in call_refs)

    @pytest.mark.asyncio
    async def test_extract_self_method_call(self, extractor, write_rb_file) -> None:
        """self.method() resolves to ClassName.method."""
        code = """class MyClass
  def run
    self.helper
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert "MyClass.helper" in method.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "MyClass.helper" for r in call_refs)

    @pytest.mark.asyncio
    async def test_extract_new_call_uses_instantiates(self, extractor, write_rb_file) -> None:
        """.new call uses INSTANTIATES relation type."""
        code = """class Factory
  def create
    User.new
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert "User.new" in method.calls

        inst_refs = [r for r in result.pending_references if r.relation_type == "instantiates"]
        assert any(r.target_qualified_name == "User.new" for r in inst_refs)

    @pytest.mark.asyncio
    async def test_skip_builtin_calls(self, extractor, write_rb_file) -> None:
        """Built-in calls are not captured."""
        code = """class Printer
  def show
    puts "hello"
    print "world"
    p 42
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert method.calls == []

        call_refs = [
            r for r in result.pending_references if r.relation_type in ("calls", "instantiates")
        ]
        assert len(call_refs) == 0

    @pytest.mark.asyncio
    async def test_calls_in_top_level_function(self, extractor, write_rb_file) -> None:
        """Calls inside a top-level function body produce pending references."""
        code = """def main
  do_work()
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())

        func = result.functions[0]
        assert "do_work" in func.calls

    @pytest.mark.asyncio
    async def test_no_duplicate_calls(self, extractor, write_rb_file) -> None:
        """Same callee called multiple times produces one pending reference."""
        code = """class Worker
  def process
    helper()
    helper()
    helper()
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())

        method = result.methods[0]
        assert method.calls.count("helper") == 1

    @pytest.mark.asyncio
    async def test_pending_ref_source_matches_entity(self, extractor, write_rb_file) -> None:
        """Pending reference source_entity_id matches the containing method."""
        code = """class Caller
  def invoke
    target_method()
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())

        method = result.methods[0]
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].source_entity_id == method.id
        assert call_refs[0].source_qualified_name == method.qualified_name
