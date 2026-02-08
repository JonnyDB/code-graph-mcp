"""Tests for JavaExtractor."""

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

    def _write(content: str) -> Path:
        file_path = tmp_path / "TestClass.java"
        file_path.write_text(content)
        return file_path

    return _write


class TestJavaExtractorSupports:
    """Tests for file support detection."""

    def test_supports_java_files(self, extractor) -> None:
        """Test supports .java files."""
        assert extractor.supports(Path("Main.java"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support other files."""
        assert not extractor.supports(Path("Main.kt"))
        assert not extractor.supports(Path("Main.py"))


class TestJavaPackageExtraction:
    """Tests for package declaration extraction."""

    @pytest.mark.asyncio
    async def test_extract_package(self, extractor, write_java_file) -> None:
        """Test extracting package declaration."""
        code = """package com.example.app;

public class Main {
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Package name should be used as module name in qualified names
        assert len(result.classes) == 1
        assert "com.example.app" in result.classes[0].qualified_name


class TestJavaImportExtraction:
    """Tests for import extraction."""

    @pytest.mark.asyncio
    async def test_extract_single_import(self, extractor, write_java_file) -> None:
        """Test extracting single import."""
        code = """package com.example;

import java.util.List;

public class Main {
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "java.util.List"

    @pytest.mark.asyncio
    async def test_extract_wildcard_import(self, extractor, write_java_file) -> None:
        """Test extracting wildcard import."""
        code = """package com.example;

import java.util.*;

public class Main {
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "java.util.*"

    @pytest.mark.asyncio
    async def test_extract_static_import(self, extractor, write_java_file) -> None:
        """Test extracting static import."""
        code = """package com.example;

import static java.lang.Math.PI;

public class Main {
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert "java.lang.Math" in result.imports[0].source_module


class TestJavaClassExtraction:
    """Tests for class extraction."""

    @pytest.mark.asyncio
    async def test_extract_class(self, extractor, write_java_file) -> None:
        """Test extracting basic class."""
        code = """package com.example;

public class User {
    private String name;
    private int age;

    public User(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() {
        return name;
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "User"
        assert "com.example" in cls.qualified_name

    @pytest.mark.asyncio
    async def test_extract_class_with_inheritance(self, extractor, write_java_file) -> None:
        """Test extracting class with inheritance."""
        code = """package com.example;

public class Employee extends Person implements Worker {
    private String jobTitle;
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "Employee"
        assert "Person" in cls.base_classes
        # Note: Java interfaces stored separately from base classes

    @pytest.mark.asyncio
    async def test_extract_abstract_class(self, extractor, write_java_file) -> None:
        """Test extracting abstract class."""
        code = """package com.example;

public abstract class Shape {
    public abstract double area();
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "Shape"
        assert cls.is_abstract is True

    @pytest.mark.asyncio
    async def test_extract_interface(self, extractor, write_java_file) -> None:
        """Test extracting interface."""
        code = """package com.example;

public interface Drawable {
    void draw();
    void erase();
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        interface = result.classes[0]
        assert interface.name == "Drawable"
        assert interface.is_abstract is True

    @pytest.mark.asyncio
    async def test_extract_enum(self, extractor, write_java_file) -> None:
        """Test extracting enum."""
        code = """package com.example;

public enum Day {
    MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        enum = result.classes[0]
        assert enum.name == "Day"


class TestJavaMethodExtraction:
    """Tests for method extraction."""

    @pytest.mark.asyncio
    async def test_extract_method(self, extractor, write_java_file) -> None:
        """Test extracting method."""
        code = """package com.example;

public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.name == "add"
        assert method.return_type == "int"
        assert len(method.parameters) == 2
        assert method.parameters[0].name == "a"
        assert method.parameters[0].type_annotation == "int"

    @pytest.mark.asyncio
    async def test_extract_constructor(self, extractor, write_java_file) -> None:
        """Test extracting constructor."""
        code = """package com.example;

public class User {
    private String name;

    public User(String name) {
        this.name = name;
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Constructors are methods in Java
        constructors = [m for m in result.methods if m.is_constructor]
        assert len(constructors) == 1
        assert constructors[0].name == "User"

    @pytest.mark.asyncio
    async def test_extract_static_method(self, extractor, write_java_file) -> None:
        """Test extracting static method."""
        code = """package com.example;

public class Utils {
    public static String format(String text) {
        return text.toUpperCase();
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.is_static is True

    @pytest.mark.asyncio
    async def test_extract_method_with_annotations(self, extractor, write_java_file) -> None:
        """Test extracting method with annotations."""
        code = """package com.example;

public class Service {
    @Override
    @Deprecated
    public void process() {
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        # Annotations are stored in decorators
        assert len(method.decorators) >= 1


class TestJavaFieldExtraction:
    """Tests for field extraction."""

    @pytest.mark.asyncio
    async def test_extract_field(self, extractor, write_java_file) -> None:
        """Test extracting field declarations."""
        code = """package com.example;

public class User {
    private String name;
    private int age;
    public static final int MAX_AGE = 150;
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Fields stored as variables
        assert len(result.variables) >= 2


class TestJavaFunctionExtraction:
    """Tests for standalone function extraction."""

    @pytest.mark.asyncio
    async def test_extract_generic_method(self, extractor, write_java_file) -> None:
        """Test extracting method with generics."""
        code = """package com.example;

public class Box<T> {
    private T value;

    public T getValue() {
        return value;
    }

    public void setValue(T value) {
        this.value = value;
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        assert len(result.methods) >= 2

    @pytest.mark.asyncio
    async def test_extract_varargs_method(self, extractor, write_java_file) -> None:
        """Test extracting method with varargs."""
        code = """package com.example;

public class Utils {
    public static int sum(int... numbers) {
        int total = 0;
        for (int n : numbers) {
            total += n;
        }
        return total;
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.name == "sum"


class TestJavaComplexScenarios:
    """Tests for complex Java scenarios."""

    @pytest.mark.asyncio
    async def test_extract_nested_class(self, extractor, write_java_file) -> None:
        """Test extracting nested class."""
        code = """package com.example;

public class Outer {
    private String outerField;

    public class Inner {
        private String innerField;

        public void innerMethod() {
        }
    }

    public void outerMethod() {
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract both outer and inner classes
        assert len(result.classes) >= 1

    @pytest.mark.asyncio
    async def test_extract_anonymous_inner_class(self, extractor, write_java_file) -> None:
        """Test handling anonymous inner classes."""
        code = """package com.example;

public class Test {
    public void run() {
        Runnable r = new Runnable() {
            public void run() {
                System.out.println("Running");
            }
        };
    }
}
"""
        file_path = write_java_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should at least extract the outer class
        assert len(result.classes) >= 1
        assert result.classes[0].name == "Test"
