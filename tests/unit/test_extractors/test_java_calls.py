"""Tests for JavaExtractor call-site extraction."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.java import JavaExtractor


@pytest.fixture
def extractor():
    """Provide JavaExtractor instance."""
    return JavaExtractor()


@pytest.fixture
def write_java_file(tmp_path: Path):
    """Factory fixture to write Java files."""

    def _write(content: str, name: str = "TestClass.java") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestJavaCallExtraction:
    """Tests for method call extraction."""

    @pytest.mark.asyncio
    async def test_extract_method_invocation(self, extractor, write_java_file) -> None:
        """Method invocation inside a method produces pending references."""
        code = """package com.example;

public class Service {
    public void run() {
        processData();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        method = next(m for m in result.methods if m.name == "run")
        assert "processData" in method.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "processData" for r in call_refs)

    @pytest.mark.asyncio
    async def test_extract_new_uses_instantiates(self, extractor, write_java_file) -> None:
        """new ClassName() uses INSTANTIATES relation type."""
        code = """package com.example;

public class Factory {
    public void create() {
        User user = new User();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        method = next(m for m in result.methods if m.name == "create")
        assert "User" in method.calls

        inst_refs = [r for r in result.pending_references if r.relation_type == "instantiates"]
        assert any(r.target_qualified_name == "User" for r in inst_refs)

    @pytest.mark.asyncio
    async def test_this_method_resolves_to_class(self, extractor, write_java_file) -> None:
        """this.method() resolves to ClassName.method."""
        code = """package com.example;

public class MyClass {
    public void run() {
        this.helper();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        method = next(m for m in result.methods if m.name == "run")
        assert "MyClass.helper" in method.calls

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "MyClass.helper" for r in call_refs)

    @pytest.mark.asyncio
    async def test_method_qualified_name_not_doubled(self, extractor, write_java_file) -> None:
        """Method qualified_name should not have doubled package prefix."""
        code = """package com.example;

public class MyClass {
    public void myMethod() {
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        method = result.methods[0]
        # qualified_name should be com.example.MyClass.myMethod
        assert method.qualified_name == "com.example.MyClass.myMethod"
        assert method.qualified_name.count("com.example") == 1

    @pytest.mark.asyncio
    async def test_calls_in_constructor(self, extractor, write_java_file) -> None:
        """Calls inside constructor are captured."""
        code = """package com.example;

public class Service {
    public Service() {
        initialize();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        constructor = next(m for m in result.methods if m.is_constructor)
        assert "initialize" in constructor.calls

    @pytest.mark.asyncio
    async def test_no_duplicate_calls(self, extractor, write_java_file) -> None:
        """Same callee called multiple times produces one pending reference."""
        code = """package com.example;

public class Worker {
    public void process() {
        helper();
        helper();
        helper();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        method = next(m for m in result.methods if m.name == "process")
        assert method.calls.count("helper") == 1

    @pytest.mark.asyncio
    async def test_pending_ref_source_matches_entity(self, extractor, write_java_file) -> None:
        """Pending reference source_entity_id matches the containing method."""
        code = """package com.example;

public class Caller {
    public void invoke() {
        targetMethod();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        method = next(m for m in result.methods if m.name == "invoke")
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        assert call_refs[0].source_entity_id == method.id
        assert call_refs[0].source_qualified_name == method.qualified_name


class TestJavaReceiverExtraction:
    """Test receiver expression extraction for Java."""

    @pytest.mark.asyncio
    async def test_method_call_receiver(self, extractor, write_java_file) -> None:
        """Test: obj.method() captures receiver 'obj'."""
        code = """
public class Main {
    public void process() {
        writer.write();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        # Should have one pending reference
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "writer.write"
        assert ref.receiver_expr == "writer"

    @pytest.mark.asyncio
    async def test_chained_method_call_receiver(self, extractor, write_java_file) -> None:
        """Test: ctx.redis.get() captures receiver 'ctx.redis'."""
        code = """
public class Main {
    public void process() {
        ctx.redis.get();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "ctx.redis.get"
        assert ref.receiver_expr == "ctx.redis"

    @pytest.mark.asyncio
    async def test_no_receiver_direct_call(self, extractor, write_java_file) -> None:
        """Test: doWork() has no receiver."""
        code = """
public class Main {
    public void process() {
        doWork();
    }
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "doWork"
        assert ref.receiver_expr is None

    @pytest.mark.asyncio
    async def test_this_method_call_no_receiver(self, extractor, write_java_file) -> None:
        """Test: this.helper() has no receiver (already resolved to ClassName.method)."""
        code = """
public class Service {
    public void run() {
        this.helper();
    }

    public void helper() {}
}
"""
        result = await extractor.extract(write_java_file(code), uuid4(), uuid4())

        # Find the call from 'run' to 'helper'
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert len(call_refs) == 1
        ref = call_refs[0]
        assert ref.target_qualified_name == "Service.helper"
        assert ref.receiver_expr is None  # this calls don't have receiver_expr
