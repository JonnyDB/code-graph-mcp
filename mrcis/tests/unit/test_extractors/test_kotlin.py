"""Tests for KotlinExtractor."""

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

    def _write(content: str) -> Path:
        file_path = tmp_path / "TestClass.kt"
        file_path.write_text(content)
        return file_path

    return _write


class TestKotlinExtractorSupports:
    """Tests for file support detection."""

    def test_supports_kt_files(self, extractor) -> None:
        """Test supports .kt files."""
        assert extractor.supports(Path("Main.kt"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support other files."""
        assert not extractor.supports(Path("Main.java"))
        assert not extractor.supports(Path("Main.py"))


class TestKotlinPackageExtraction:
    """Tests for package declaration extraction."""

    @pytest.mark.asyncio
    async def test_extract_package(self, extractor, write_kt_file) -> None:
        """Test extracting package declaration."""
        code = """package com.example.app

class Main {
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Package name should be used as module name in qualified names
        assert len(result.classes) == 1
        assert "com.example.app" in result.classes[0].qualified_name


class TestKotlinImportExtraction:
    """Tests for import extraction."""

    @pytest.mark.asyncio
    async def test_extract_single_import(self, extractor, write_kt_file) -> None:
        """Test extracting single import."""
        code = """package com.example

import kotlin.collections.List

class Main {
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "kotlin.collections.List"

    @pytest.mark.asyncio
    async def test_extract_wildcard_import(self, extractor, write_kt_file) -> None:
        """Test extracting wildcard import."""
        code = """package com.example

import kotlin.collections.*

class Main {
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "kotlin.collections.*"

    @pytest.mark.asyncio
    async def test_extract_aliased_import(self, extractor, write_kt_file) -> None:
        """Test extracting import with alias."""
        code = """package com.example

import kotlin.collections.List as KList

class Main {
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert "kotlin.collections.List" in result.imports[0].source_module


class TestKotlinClassExtraction:
    """Tests for class extraction."""

    @pytest.mark.asyncio
    async def test_extract_class(self, extractor, write_kt_file) -> None:
        """Test extracting basic class."""
        code = """package com.example

class User(val name: String, val age: Int) {
    fun greet() {
        println("Hello, $name")
    }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "User"
        assert "com.example" in cls.qualified_name

    @pytest.mark.asyncio
    async def test_extract_data_class(self, extractor, write_kt_file) -> None:
        """Test extracting data class."""
        code = """package com.example

data class User(val name: String, val email: String)
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "User"

    @pytest.mark.asyncio
    async def test_extract_class_with_inheritance(self, extractor, write_kt_file) -> None:
        """Test extracting class with inheritance."""
        code = """package com.example

open class Person(val name: String)

class Employee(name: String, val jobTitle: String) : Person(name)
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 2
        employee = next(c for c in result.classes if c.name == "Employee")
        assert "Person" in employee.base_classes

    @pytest.mark.asyncio
    async def test_extract_abstract_class(self, extractor, write_kt_file) -> None:
        """Test extracting abstract class."""
        code = """package com.example

abstract class Shape {
    abstract fun area(): Double
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "Shape"
        assert cls.is_abstract is True

    @pytest.mark.asyncio
    async def test_extract_interface(self, extractor, write_kt_file) -> None:
        """Test extracting interface."""
        code = """package com.example

interface Drawable {
    fun draw()
    fun erase()
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        interface = result.classes[0]
        assert interface.name == "Drawable"
        assert interface.is_abstract is True

    @pytest.mark.asyncio
    async def test_extract_object_declaration(self, extractor, write_kt_file) -> None:
        """Test extracting object declaration (singleton)."""
        code = """package com.example

object Database {
    fun connect() {
        println("Connecting...")
    }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        obj = result.classes[0]
        assert obj.name == "Database"

    @pytest.mark.asyncio
    async def test_extract_companion_object(self, extractor, write_kt_file) -> None:
        """Test extracting companion object."""
        code = """package com.example

class User {
    companion object {
        fun create(name: String) = User()
    }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract the main class at minimum
        assert len(result.classes) >= 1
        assert result.classes[0].name == "User"


class TestKotlinFunctionExtraction:
    """Tests for function extraction."""

    @pytest.mark.asyncio
    async def test_extract_function(self, extractor, write_kt_file) -> None:
        """Test extracting top-level function."""
        code = """package com.example

fun greet(name: String): String {
    return "Hello, $name"
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"
        assert func.return_type == "String"

    @pytest.mark.asyncio
    async def test_extract_function_with_default_params(self, extractor, write_kt_file) -> None:
        """Test extracting function with default parameters."""
        code = """package com.example

fun greet(name: String = "World"): String {
    return "Hello, $name"
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"
        assert len(func.parameters) == 1

    @pytest.mark.asyncio
    async def test_extract_extension_function(self, extractor, write_kt_file) -> None:
        """Test extracting extension function."""
        code = """package com.example

fun String.isPalindrome(): Boolean {
    return this == this.reversed()
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "isPalindrome"

    @pytest.mark.asyncio
    async def test_extract_suspend_function(self, extractor, write_kt_file) -> None:
        """Test extracting suspend function."""
        code = """package com.example

suspend fun fetchData(): String {
    return "data"
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.is_async is True

    @pytest.mark.asyncio
    async def test_extract_inline_function(self, extractor, write_kt_file) -> None:
        """Test extracting inline function."""
        code = """package com.example

inline fun measure(block: () -> Unit) {
    block()
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "measure"


class TestKotlinMethodExtraction:
    """Tests for method extraction."""

    @pytest.mark.asyncio
    async def test_extract_method(self, extractor, write_kt_file) -> None:
        """Test extracting method."""
        code = """package com.example

class Calculator {
    fun add(a: Int, b: Int): Int {
        return a + b
    }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.name == "add"
        assert method.return_type == "Int"
        assert len(method.parameters) == 2

    @pytest.mark.asyncio
    async def test_extract_method_with_receiver(self, extractor, write_kt_file) -> None:
        """Test extracting method (class member function)."""
        code = """package com.example

class User(val name: String) {
    fun greet(): String {
        return "Hello, $name"
    }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        methods = [m for m in result.methods if m.name == "greet"]
        assert len(methods) == 1
        assert "User" in methods[0].parent_class

    @pytest.mark.asyncio
    async def test_extract_override_method(self, extractor, write_kt_file) -> None:
        """Test extracting override method."""
        code = """package com.example

open class Base {
    open fun process() {}
}

class Derived : Base() {
    override fun process() {
        println("Processing")
    }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract methods from both classes
        assert len(result.methods) >= 2

    @pytest.mark.asyncio
    async def test_extract_suspend_method(self, extractor, write_kt_file) -> None:
        """Test extracting suspend method."""
        code = """package com.example

class Repository {
    suspend fun fetchData(): String {
        return "data"
    }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.is_async is True


class TestKotlinPropertyExtraction:
    """Tests for property extraction."""

    @pytest.mark.asyncio
    async def test_extract_property(self, extractor, write_kt_file) -> None:
        """Test extracting property declarations."""
        code = """package com.example

class User {
    val name: String = "John"
    var age: Int = 30
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Properties stored as variables
        assert len(result.variables) >= 2

    @pytest.mark.asyncio
    async def test_extract_lateinit_property(self, extractor, write_kt_file) -> None:
        """Test extracting lateinit property."""
        code = """package com.example

class Service {
    lateinit var client: HttpClient
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 1

    @pytest.mark.asyncio
    async def test_extract_lazy_property(self, extractor, write_kt_file) -> None:
        """Test extracting lazy property."""
        code = """package com.example

class Config {
    val value: String by lazy { "initialized" }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 1


class TestKotlinComplexScenarios:
    """Tests for complex Kotlin scenarios."""

    @pytest.mark.asyncio
    async def test_extract_sealed_class(self, extractor, write_kt_file) -> None:
        """Test extracting sealed class."""
        code = """package com.example

sealed class Result {
    data class Success(val data: String) : Result()
    data class Error(val message: String) : Result()
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract sealed class and subclasses
        assert len(result.classes) >= 1

    @pytest.mark.asyncio
    async def test_extract_enum_class(self, extractor, write_kt_file) -> None:
        """Test extracting enum class."""
        code = """package com.example

enum class Direction {
    NORTH, SOUTH, EAST, WEST
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        enum = result.classes[0]
        assert enum.name == "Direction"

    @pytest.mark.asyncio
    async def test_extract_generic_class(self, extractor, write_kt_file) -> None:
        """Test extracting generic class."""
        code = """package com.example

class Box<T>(val value: T) {
    fun get(): T = value
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "Box"

    @pytest.mark.asyncio
    async def test_extract_annotation_class(self, extractor, write_kt_file) -> None:
        """Test extracting annotation class."""
        code = """package com.example

annotation class Route(val path: String)
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        annotation = result.classes[0]
        assert annotation.name == "Route"

    @pytest.mark.asyncio
    async def test_extract_nested_class(self, extractor, write_kt_file) -> None:
        """Test extracting nested class."""
        code = """package com.example

class Outer {
    class Nested {
        fun nestedMethod() {}
    }

    fun outerMethod() {}
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract both outer and nested classes
        assert len(result.classes) >= 1

    @pytest.mark.asyncio
    async def test_extract_inner_class(self, extractor, write_kt_file) -> None:
        """Test extracting inner class."""
        code = """package com.example

class Outer {
    inner class Inner {
        fun innerMethod() {}
    }
}
"""
        file_path = write_kt_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract both outer and inner classes
        assert len(result.classes) >= 1
