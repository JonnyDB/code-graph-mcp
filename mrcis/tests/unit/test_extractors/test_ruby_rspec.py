"""Tests for RSpec DSL extraction in RubyExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.ruby import RubyExtractor


@pytest.fixture
def extractor():
    """Provide RubyExtractor instance."""
    return RubyExtractor()


@pytest.fixture
def write_spec_file(tmp_path: Path):
    """Factory fixture to write Ruby spec files."""

    def _write(content: str, name: str = "user_spec.rb") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestRSpecDescribe:
    """Tests for describe/context block extraction."""

    @pytest.mark.asyncio
    async def test_extract_rspec_describe_class(self, extractor, write_spec_file) -> None:
        """RSpec.describe User produces ClassEntity."""
        code = """RSpec.describe User do
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        # Should have at least one class from the describe block
        describe_classes = [c for c in result.classes if "describe" in c.decorators]
        assert len(describe_classes) == 1
        assert describe_classes[0].name == "User"

    @pytest.mark.asyncio
    async def test_extract_rspec_describe_string(self, extractor, write_spec_file) -> None:
        """describe 'User registration' produces ClassEntity."""
        code = """RSpec.describe 'User registration' do
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        describe_classes = [c for c in result.classes if "describe" in c.decorators]
        assert len(describe_classes) == 1
        assert describe_classes[0].name == "User registration"

    @pytest.mark.asyncio
    async def test_extract_rspec_context(self, extractor, write_spec_file) -> None:
        """context 'when logged in' produces ClassEntity with context decorator."""
        code = """RSpec.describe User do
  context 'when logged in' do
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        context_classes = [c for c in result.classes if "context" in c.decorators]
        assert len(context_classes) == 1
        assert context_classes[0].name == "when logged in"

    @pytest.mark.asyncio
    async def test_describe_creates_reference_to_class(self, extractor, write_spec_file) -> None:
        """RSpec.describe User creates PendingReference to 'User'."""
        code = """RSpec.describe User do
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        refs = [r for r in result.pending_references if r.relation_type == "references"]
        assert any(r.target_qualified_name == "User" for r in refs)

    @pytest.mark.asyncio
    async def test_nested_describe_context(self, extractor, write_spec_file) -> None:
        """Nested describe/context creates properly scoped entities."""
        code = """RSpec.describe User do
  describe '#save' do
    context 'with valid data' do
    end
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        # Should have 3 class entities: User, #save, with valid data
        rspec_classes = [
            c for c in result.classes if c.decorators and c.decorators[0] in ("describe", "context")
        ]
        assert len(rspec_classes) == 3


class TestRSpecExamples:
    """Tests for it/specify/example block extraction."""

    @pytest.mark.asyncio
    async def test_extract_rspec_it(self, extractor, write_spec_file) -> None:
        """it 'returns true' produces MethodEntity."""
        code = """RSpec.describe User do
  it 'returns true' do
    expect(true).to be_truthy
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        example_methods = [m for m in result.methods if "example" in m.decorators]
        assert len(example_methods) == 1
        assert example_methods[0].name == "returns true"

    @pytest.mark.asyncio
    async def test_extract_rspec_specify(self, extractor, write_spec_file) -> None:
        """specify 'works' produces MethodEntity."""
        code = """RSpec.describe User do
  specify 'it works' do
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        example_methods = [m for m in result.methods if "example" in m.decorators]
        assert len(example_methods) == 1

    @pytest.mark.asyncio
    async def test_example_has_parent_class(self, extractor, write_spec_file) -> None:
        """Example methods have parent_class set to describe context."""
        code = """RSpec.describe User do
  it 'is valid' do
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        example_methods = [m for m in result.methods if "example" in m.decorators]
        assert example_methods[0].parent_class == "User"


class TestRSpecLet:
    """Tests for let/let!/subject extraction."""

    @pytest.mark.asyncio
    async def test_extract_rspec_let(self, extractor, write_spec_file) -> None:
        """let(:user) produces VariableEntity."""
        code = """RSpec.describe User do
  let(:user) { User.new }
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        let_vars = [v for v in result.variables if v.decorators and "let" in v.decorators]
        assert len(let_vars) == 1
        assert let_vars[0].name == "user"

    @pytest.mark.asyncio
    async def test_extract_rspec_let_bang(self, extractor, write_spec_file) -> None:
        """let!(:user) produces VariableEntity with 'let!' decorator."""
        code = """RSpec.describe User do
  let!(:user) { User.create }
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        let_vars = [v for v in result.variables if v.decorators and "let!" in v.decorators]
        assert len(let_vars) == 1

    @pytest.mark.asyncio
    async def test_extract_rspec_subject(self, extractor, write_spec_file) -> None:
        """subject { described_class.new } produces VariableEntity."""
        code = """RSpec.describe User do
  subject { described_class.new }
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        subject_vars = [v for v in result.variables if v.decorators and "subject" in v.decorators]
        assert len(subject_vars) == 1


class TestRSpecShared:
    """Tests for shared_examples/shared_context extraction."""

    @pytest.mark.asyncio
    async def test_extract_shared_examples(self, extractor, write_spec_file) -> None:
        """shared_examples produces FunctionEntity."""
        code = """RSpec.shared_examples 'a valid model' do
  it 'is valid' do
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        shared = [f for f in result.functions if "shared_examples" in f.decorators]
        assert len(shared) == 1
        assert shared[0].name == "a valid model"

    @pytest.mark.asyncio
    async def test_extract_it_behaves_like(self, extractor, write_spec_file) -> None:
        """it_behaves_like produces PendingReference."""
        code = """RSpec.describe User do
  it_behaves_like 'a valid model'
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        refs = [r for r in result.pending_references if r.target_qualified_name == "a valid model"]
        assert len(refs) == 1


class TestRSpecHooks:
    """Tests for before/after/around hook extraction."""

    @pytest.mark.asyncio
    async def test_extract_before_hook(self, extractor, write_spec_file) -> None:
        """before(:each) produces MethodEntity."""
        code = """RSpec.describe User do
  before(:each) do
    @user = User.new
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        hooks = [m for m in result.methods if "before" in m.decorators]
        assert len(hooks) == 1
        assert hooks[0].name == "before_each"

    @pytest.mark.asyncio
    async def test_extract_after_hook(self, extractor, write_spec_file) -> None:
        """after(:all) produces MethodEntity."""
        code = """RSpec.describe User do
  after(:all) do
    cleanup
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())
        hooks = [m for m in result.methods if "after" in m.decorators]
        assert len(hooks) == 1
        assert hooks[0].name == "after_all"


class TestRSpecFullFile:
    """Integration test with a comprehensive spec file."""

    @pytest.mark.asyncio
    async def test_extract_full_spec_file(self, extractor, write_spec_file) -> None:
        """Full spec file produces non-zero entities."""
        code = """require 'spec_helper'

RSpec.describe User do
  let(:user) { User.new(name: 'Alice') }
  subject { user }

  before(:each) do
    DatabaseCleaner.start
  end

  describe '#valid?' do
    context 'with valid attributes' do
      it 'returns true' do
        expect(subject).to be_valid
      end
    end

    context 'without name' do
      it 'returns false' do
        user.name = nil
        expect(subject).not_to be_valid
      end
    end
  end
end
"""
        result = await extractor.extract(write_spec_file(code), uuid4(), uuid4())

        # Should have imports
        assert len(result.imports) >= 1

        # Should have describe/context classes
        assert len(result.classes) >= 3  # User, #valid?, with valid attributes, without name

        # Should have it examples
        example_methods = [m for m in result.methods if "example" in m.decorators]
        assert len(example_methods) >= 2

        # Should have let/subject variables
        assert len(result.variables) >= 2

        # Should have hooks
        hooks = [m for m in result.methods if "before" in m.decorators]
        assert len(hooks) >= 1

        # Total entities should be > 0
        assert result.entity_count() > 0
