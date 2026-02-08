"""Tests for Rake DSL and Gemfile extraction in RubyExtractor."""

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
    """Factory fixture to write Ruby files with custom names."""

    def _write(content: str, name: str = "test.rake") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestRakeTaskExtraction:
    """Tests for Rake task extraction."""

    @pytest.mark.asyncio
    async def test_extract_rake_task(self, extractor, write_rb_file) -> None:
        """task :migrate produces FunctionEntity with entity_type=task."""
        code = """task :migrate do
  puts "Running migrations"
end
"""
        result = await extractor.extract(write_rb_file(code, "deploy.rake"), uuid4(), uuid4())
        tasks = [f for f in result.functions if f.entity_type == "task"]
        assert len(tasks) == 1
        assert tasks[0].name == "migrate"

    @pytest.mark.asyncio
    async def test_extract_rake_namespace(self, extractor, write_rb_file) -> None:
        """namespace :db produces ModuleEntity."""
        code = """namespace :db do
  task :migrate do
  end
end
"""
        result = await extractor.extract(write_rb_file(code, "tasks.rake"), uuid4(), uuid4())
        assert len(result.modules) >= 1
        ns = result.modules[0]
        assert ns.name == "db"

    @pytest.mark.asyncio
    async def test_nested_namespace_task_qualified_name(self, extractor, write_rb_file) -> None:
        """Nested namespace:task produces qualified name like 'db:migrate'."""
        code = """namespace :db do
  task :migrate do
  end
end
"""
        result = await extractor.extract(write_rb_file(code, "database.rake"), uuid4(), uuid4())
        tasks = [f for f in result.functions if f.entity_type == "task"]
        assert len(tasks) == 1
        assert tasks[0].qualified_name == "db:migrate"

    @pytest.mark.asyncio
    async def test_extract_rake_desc(self, extractor, write_rb_file) -> None:
        """desc 'Run migrations' applied as docstring on next task."""
        code = """desc 'Run database migrations'
task :migrate do
end
"""
        result = await extractor.extract(write_rb_file(code, "db.rake"), uuid4(), uuid4())
        tasks = [f for f in result.functions if f.entity_type == "task"]
        assert len(tasks) == 1
        assert tasks[0].docstring == "Run database migrations"

    @pytest.mark.asyncio
    async def test_extract_deeply_nested_rake(self, extractor, write_rb_file) -> None:
        """Multiple levels of namespace nesting produce correct qualified names."""
        code = """namespace :deploy do
  namespace :assets do
    task :precompile do
    end
  end
end
"""
        result = await extractor.extract(write_rb_file(code, "deploy.rake"), uuid4(), uuid4())
        tasks = [f for f in result.functions if f.entity_type == "task"]
        assert len(tasks) == 1
        assert tasks[0].qualified_name == "deploy:assets:precompile"


class TestRakefileSupport:
    """Tests for Rakefile (extensionless) support."""

    @pytest.mark.asyncio
    async def test_rakefile_extracts_tasks(self, extractor, write_rb_file) -> None:
        """Rakefile is treated as a Rake file and extracts tasks."""
        code = """task :default do
  puts "Hello"
end
"""
        result = await extractor.extract(write_rb_file(code, "Rakefile"), uuid4(), uuid4())
        tasks = [f for f in result.functions if f.entity_type == "task"]
        assert len(tasks) == 1
        assert tasks[0].name == "default"


class TestGemfileExtraction:
    """Tests for Gemfile gem dependency extraction."""

    @pytest.mark.asyncio
    async def test_extract_gemfile_deps(self, extractor, write_rb_file) -> None:
        """gem 'rails' produces ImportEntity."""
        code = """source 'https://rubygems.org'

gem 'rails', '~> 7.0'
gem 'pg'
gem 'puma'
"""
        result = await extractor.extract(write_rb_file(code, "Gemfile"), uuid4(), uuid4())
        assert len(result.imports) >= 3
        gem_names = {i.name for i in result.imports}
        assert "rails" in gem_names
        assert "pg" in gem_names
        assert "puma" in gem_names

    @pytest.mark.asyncio
    async def test_gemfile_imports_are_not_relative(self, extractor, write_rb_file) -> None:
        """Gemfile imports have is_relative=False."""
        code = """gem 'sidekiq'
"""
        result = await extractor.extract(write_rb_file(code, "Gemfile"), uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].is_relative is False
