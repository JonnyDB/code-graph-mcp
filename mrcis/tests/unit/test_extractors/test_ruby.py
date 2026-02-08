"""Tests for RubyExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.ruby import RubyExtractor


@pytest.fixture
def extractor():
    """Provide RubyExtractor instance."""
    return RubyExtractor()


@pytest.fixture
def write_ruby_file(tmp_path: Path):
    """Factory fixture to write Ruby files."""

    def _write(content: str) -> Path:
        file_path = tmp_path / "test_module.rb"
        file_path.write_text(content)
        return file_path

    return _write


class TestRubyExtractorSupports:
    """Tests for file support detection."""

    def test_supports_rb_files(self, extractor) -> None:
        """Test supports .rb files."""
        assert extractor.supports(Path("module.rb"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support other files."""
        assert not extractor.supports(Path("module.py"))


class TestRubyImportExtraction:
    """Tests for require/require_relative extraction."""

    @pytest.mark.asyncio
    async def test_extract_require(self, extractor, write_ruby_file) -> None:
        """Test extracting require statement."""
        code = "require 'json'"
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "json"
        assert result.imports[0].is_relative is False

    @pytest.mark.asyncio
    async def test_extract_require_relative(self, extractor, write_ruby_file) -> None:
        """Test extracting require_relative statement."""
        code = "require_relative 'user_service'"
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "user_service"
        assert result.imports[0].is_relative is True

    @pytest.mark.asyncio
    async def test_extract_multiple_requires(self, extractor, write_ruby_file) -> None:
        """Test extracting multiple require statements."""
        code = """require 'json'
require 'net/http'
require_relative 'helpers'
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 3


class TestRubyClassExtraction:
    """Tests for class extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_class(self, extractor, write_ruby_file) -> None:
        """Test extracting simple class."""
        code = """class User
  def initialize(name)
    @name = name
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "User"

    @pytest.mark.asyncio
    async def test_extract_class_with_inheritance(self, extractor, write_ruby_file) -> None:
        """Test extracting class with inheritance."""
        code = """class AdminUser < User
  def admin_method
    puts "Admin"
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "AdminUser"
        assert "User" in cls.base_classes

    @pytest.mark.asyncio
    async def test_extract_class_with_namespace(self, extractor, write_ruby_file) -> None:
        """Test extracting class with namespace."""
        code = """class User::Profile
  def display
    puts "Profile"
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "User::Profile"


class TestRubyModuleExtraction:
    """Tests for module extraction."""

    @pytest.mark.asyncio
    async def test_extract_module(self, extractor, write_ruby_file) -> None:
        """Test extracting module."""
        code = """module Helpers
  def help_method
    puts "Help"
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.modules) == 1
        mod = result.modules[0]
        assert mod.name == "Helpers"

    @pytest.mark.asyncio
    async def test_extract_module_with_namespace(self, extractor, write_ruby_file) -> None:
        """Test extracting module with namespace."""
        code = """module App::Helpers
  def utility_method
    puts "Utility"
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.modules) == 1
        mod = result.modules[0]
        assert mod.name == "App::Helpers"


class TestRubyMethodExtraction:
    """Tests for method extraction."""

    @pytest.mark.asyncio
    async def test_extract_instance_method(self, extractor, write_ruby_file) -> None:
        """Test extracting instance method."""
        code = """class User
  def greet(name)
    puts "Hello, #{name}"
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.name == "greet"
        assert method.parent_class == "User"

    @pytest.mark.asyncio
    async def test_extract_class_method(self, extractor, write_ruby_file) -> None:
        """Test extracting class method (self.method_name)."""
        code = """class User
  def self.find(id)
    # Find user by id
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Class methods can be extracted as methods or functions
        assert len(result.methods) >= 1 or len(result.functions) >= 1

    @pytest.mark.asyncio
    async def test_extract_method_with_parameters(self, extractor, write_ruby_file) -> None:
        """Test extracting method with parameters."""
        code = """class Calculator
  def add(a, b)
    a + b
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.name == "add"
        assert len(method.parameters) == 2

    @pytest.mark.asyncio
    async def test_extract_initialize_method(self, extractor, write_ruby_file) -> None:
        """Test extracting initialize (constructor) method."""
        code = """class User
  def initialize(name, email)
    @name = name
    @email = email
  end
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.methods) == 1
        method = result.methods[0]
        assert method.name == "initialize"
        assert method.is_constructor is True


class TestRubyAttrExtraction:
    """Tests for attr_* accessor extraction."""

    @pytest.mark.asyncio
    async def test_extract_attr_reader(self, extractor, write_ruby_file) -> None:
        """Test extracting attr_reader."""
        code = """class User
  attr_reader :name, :email
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # attr_reader creates getter methods
        assert len(result.variables) >= 2 or len(result.methods) >= 2

    @pytest.mark.asyncio
    async def test_extract_attr_writer(self, extractor, write_ruby_file) -> None:
        """Test extracting attr_writer."""
        code = """class User
  attr_writer :password
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # attr_writer creates setter methods
        assert len(result.variables) >= 1 or len(result.methods) >= 1

    @pytest.mark.asyncio
    async def test_extract_attr_accessor(self, extractor, write_ruby_file) -> None:
        """Test extracting attr_accessor."""
        code = """class User
  attr_accessor :name, :email, :age
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # attr_accessor creates both getters and setters
        assert len(result.variables) >= 3 or len(result.methods) >= 3


class TestRubyFunctionExtraction:
    """Tests for top-level function extraction."""

    @pytest.mark.asyncio
    async def test_extract_function(self, extractor, write_ruby_file) -> None:
        """Test extracting top-level function."""
        code = """def greet(name)
  puts "Hello, #{name}"
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"

    @pytest.mark.asyncio
    async def test_extract_function_with_default_params(self, extractor, write_ruby_file) -> None:
        """Test extracting function with default parameters."""
        code = """def greet(name = "World")
  puts "Hello, #{name}"
end
"""
        file_path = write_ruby_file(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.functions) == 1
        func = result.functions[0]
        assert func.name == "greet"
