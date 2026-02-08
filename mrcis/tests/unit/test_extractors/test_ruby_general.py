"""Tests for Ruby extractor: modules, visibility, constants, docstrings, mixins."""

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


class TestRubyModuleEntity:
    """Tests that modules use ModuleEntity instead of ClassEntity."""

    @pytest.mark.asyncio
    async def test_module_uses_module_entity(self, extractor, write_rb_file) -> None:
        """Modules produce ModuleEntity in result.modules."""
        code = """module Helpers
  def help_method
    puts "Help"
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        assert len(result.modules) == 1
        assert len(result.classes) == 0
        mod = result.modules[0]
        assert mod.name == "Helpers"

    @pytest.mark.asyncio
    async def test_module_entity_type_is_module(self, extractor, write_rb_file) -> None:
        """Module entity_type is 'module'."""
        code = """module Serializable
  def to_json
    # serialize
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        mod = result.modules[0]
        assert mod.entity_type == "module"

    @pytest.mark.asyncio
    async def test_module_exports_method_names(self, extractor, write_rb_file) -> None:
        """Module exports list contains method names."""
        code = """module Helpers
  def method_a
  end

  def method_b
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        mod = result.modules[0]
        assert "method_a" in mod.exports
        assert "method_b" in mod.exports


class TestRubyVisibility:
    """Tests for method visibility tracking."""

    @pytest.mark.asyncio
    async def test_method_visibility_private_block(self, extractor, write_rb_file) -> None:
        """Methods after 'private' have visibility=private."""
        code = """class User
  def public_method
  end

  private

  def secret_method
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        methods = {m.name: m for m in result.methods}
        assert methods["public_method"].visibility == "public"
        assert methods["secret_method"].visibility == "private"

    @pytest.mark.asyncio
    async def test_method_visibility_protected_block(self, extractor, write_rb_file) -> None:
        """Methods after 'protected' have visibility=protected."""
        code = """class Account
  def open_method
  end

  protected

  def guarded_method
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        methods = {m.name: m for m in result.methods}
        assert methods["open_method"].visibility == "public"
        assert methods["guarded_method"].visibility == "protected"

    @pytest.mark.asyncio
    async def test_method_visibility_default_public(self, extractor, write_rb_file) -> None:
        """Methods before any visibility modifier are public."""
        code = """class Simple
  def method_a
  end

  def method_b
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        for method in result.methods:
            assert method.visibility == "public"


class TestRubyConstants:
    """Tests for constant extraction."""

    @pytest.mark.asyncio
    async def test_extract_class_constant(self, extractor, write_rb_file) -> None:
        """Constants inside class produce VariableEntity with is_constant=True."""
        code = """class Config
  MAX_RETRIES = 3
  TIMEOUT = 30
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        constants = [v for v in result.variables if v.is_constant]
        assert len(constants) == 2
        names = {c.name for c in constants}
        assert "MAX_RETRIES" in names
        assert "TIMEOUT" in names

    @pytest.mark.asyncio
    async def test_constant_has_parent_class(self, extractor, write_rb_file) -> None:
        """Constants inside a class have parent_class set."""
        code = """class Settings
  VERSION = "1.0"
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        constants = [v for v in result.variables if v.is_constant]
        assert len(constants) == 1
        assert constants[0].parent_class == "Settings"


class TestRubyDocstrings:
    """Tests for Ruby comment docstring extraction."""

    @pytest.mark.asyncio
    async def test_ruby_comment_docstring(self, extractor, write_rb_file) -> None:
        """Comment above method becomes docstring."""
        code = """class User
  # Greet the user
  def greet
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        method = result.methods[0]
        assert method.docstring is not None
        assert "Greet the user" in method.docstring

    @pytest.mark.asyncio
    async def test_ruby_multiline_comment_docstring(self, extractor, write_rb_file) -> None:
        """Consecutive comments joined as docstring."""
        code = """class User
  # First line
  # Second line
  def greet
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        method = result.methods[0]
        assert method.docstring is not None
        assert "First line" in method.docstring
        assert "Second line" in method.docstring

    @pytest.mark.asyncio
    async def test_no_docstring_when_no_comment(self, extractor, write_rb_file) -> None:
        """Method without comment has docstring=None."""
        code = """class User
  def greet
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        method = result.methods[0]
        assert method.docstring is None

    @pytest.mark.asyncio
    async def test_class_docstring(self, extractor, write_rb_file) -> None:
        """Comment above class becomes class docstring."""
        code = """# Represents a user in the system
class User
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        cls = result.classes[0]
        assert cls.docstring is not None
        assert "Represents a user" in cls.docstring


class TestRubyMixins:
    """Tests for include/extend/prepend mixin extraction."""

    @pytest.mark.asyncio
    async def test_extract_include_module(self, extractor, write_rb_file) -> None:
        """include produces PendingReference with IMPLEMENTS relation."""
        code = """class User
  include Comparable
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        impl_refs = [r for r in result.pending_references if r.relation_type == "implements"]
        assert len(impl_refs) == 1
        assert impl_refs[0].target_qualified_name == "Comparable"

    @pytest.mark.asyncio
    async def test_include_populates_mixins(self, extractor, write_rb_file) -> None:
        """include populates ClassEntity.mixins list."""
        code = """class User
  include Serializable
  include Loggable
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        cls = result.classes[0]
        assert "Serializable" in cls.mixins
        assert "Loggable" in cls.mixins

    @pytest.mark.asyncio
    async def test_extend_produces_reference(self, extractor, write_rb_file) -> None:
        """extend produces PendingReference."""
        code = """class User
  extend ClassMethods
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        impl_refs = [r for r in result.pending_references if r.relation_type == "implements"]
        assert any(r.target_qualified_name == "ClassMethods" for r in impl_refs)


class TestRubyFileSupport:
    """Tests for extended file support."""

    def test_supports_rake_extension(self, extractor) -> None:
        """Extractor supports .rake files."""
        assert extractor.supports(Path("tasks.rake"))

    def test_supports_gemspec_extension(self, extractor) -> None:
        """Extractor supports .gemspec files."""
        assert extractor.supports(Path("mygem.gemspec"))

    def test_supports_rakefile(self, extractor) -> None:
        """Extractor supports Rakefile."""
        assert extractor.supports(Path("Rakefile"))

    def test_supports_gemfile(self, extractor) -> None:
        """Extractor supports Gemfile."""
        assert extractor.supports(Path("Gemfile"))
