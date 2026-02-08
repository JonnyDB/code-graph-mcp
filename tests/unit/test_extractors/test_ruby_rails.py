"""Tests for Rails DSL extraction in RubyExtractor."""

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

    def _write(content: str, name: str = "user.rb") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestRailsAssociations:
    """Tests for has_many/has_one/belongs_to extraction."""

    @pytest.mark.asyncio
    async def test_extract_has_many(self, extractor, write_rb_file) -> None:
        """has_many produces PendingReference with REFERENCES relation."""
        code = """class User < ApplicationRecord
  has_many :posts
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        refs = [r for r in result.pending_references if r.relation_type == "references"]
        assert any(r.target_qualified_name == "Post" for r in refs)

    @pytest.mark.asyncio
    async def test_extract_belongs_to(self, extractor, write_rb_file) -> None:
        """belongs_to produces PendingReference."""
        code = """class Post < ApplicationRecord
  belongs_to :user
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        refs = [r for r in result.pending_references if r.relation_type == "references"]
        assert any(r.target_qualified_name == "User" for r in refs)

    @pytest.mark.asyncio
    async def test_extract_has_one(self, extractor, write_rb_file) -> None:
        """has_one produces PendingReference."""
        code = """class User < ApplicationRecord
  has_one :profile
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        refs = [r for r in result.pending_references if r.relation_type == "references"]
        assert any(r.target_qualified_name == "Profile" for r in refs)


class TestRailsValidations:
    """Tests for validates/validate extraction."""

    @pytest.mark.asyncio
    async def test_extract_validates(self, extractor, write_rb_file) -> None:
        """validates stored as decorator on ClassEntity."""
        code = """class User < ApplicationRecord
  validates :email, presence: true
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        cls = result.classes[0]
        assert any("validates" in d for d in cls.decorators)


class TestRailsCallbacks:
    """Tests for callback extraction."""

    @pytest.mark.asyncio
    async def test_extract_before_action(self, extractor, write_rb_file) -> None:
        """before_action stored as decorator on ClassEntity."""
        code = """class UsersController < ApplicationController
  before_action :authenticate_user
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        cls = result.classes[0]
        assert any("before_action" in d for d in cls.decorators)


class TestRailsScopes:
    """Tests for scope extraction."""

    @pytest.mark.asyncio
    async def test_extract_scope(self, extractor, write_rb_file) -> None:
        """scope :active produces MethodEntity with is_static=True."""
        code = """class User < ApplicationRecord
  scope :active, -> { where(active: true) }
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        scope_methods = [m for m in result.methods if "scope" in m.decorators]
        assert len(scope_methods) == 1
        assert scope_methods[0].name == "active"
        assert scope_methods[0].is_static is True


class TestRailsDelegates:
    """Tests for delegate extraction."""

    @pytest.mark.asyncio
    async def test_extract_delegate(self, extractor, write_rb_file) -> None:
        """delegate :name produces PendingReference with CALLS relation."""
        code = """class Profile < ApplicationRecord
  delegate :name, to: :user
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())
        call_refs = [r for r in result.pending_references if r.relation_type == "calls"]
        assert any(r.target_qualified_name == "name" for r in call_refs)


class TestRailsFullModel:
    """Integration test with a comprehensive Rails model."""

    @pytest.mark.asyncio
    async def test_extract_mixed_rails_model(self, extractor, write_rb_file) -> None:
        """Full Rails model extracts classes, associations, validations, scopes."""
        code = """class User < ApplicationRecord
  include Auditable
  include Searchable

  has_many :posts
  has_one :profile
  belongs_to :organization

  validates :email, presence: true, uniqueness: true
  validates :name, presence: true

  before_save :normalize_email
  after_create :send_welcome_email

  scope :active, -> { where(active: true) }
  scope :admin, -> { where(role: 'admin') }

  delegate :company_name, to: :organization

  def full_name
    "#{first_name} #{last_name}"
  end

  private

  def normalize_email
    self.email = email.downcase
  end
end
"""
        result = await extractor.extract(write_rb_file(code), uuid4(), uuid4())

        # Class
        assert len(result.classes) == 1
        cls = result.classes[0]
        assert cls.name == "User"
        assert "ApplicationRecord" in cls.base_classes

        # Mixins
        assert "Auditable" in cls.mixins
        assert "Searchable" in cls.mixins

        # Check association references
        ref_targets = {
            r.target_qualified_name
            for r in result.pending_references
            if r.relation_type == "references"
        }
        assert "Post" in ref_targets
        assert "Profile" in ref_targets
        assert "Organization" in ref_targets

        # Scopes
        scope_methods = [m for m in result.methods if "scope" in m.decorators]
        assert len(scope_methods) == 2
        scope_names = {s.name for s in scope_methods}
        assert "active" in scope_names
        assert "admin" in scope_names

        # Regular methods
        regular_methods = [
            m for m in result.methods if not m.decorators or "scope" not in m.decorators
        ]
        method_names = {m.name for m in regular_methods}
        assert "full_name" in method_names
        assert "normalize_email" in method_names

        # Visibility
        methods_by_name = {m.name: m for m in regular_methods}
        assert methods_by_name["full_name"].visibility == "public"
        assert methods_by_name["normalize_email"].visibility == "private"
