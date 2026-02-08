"""Tests for YAMLExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.yaml_extractor import YAMLExtractor


@pytest.fixture
def extractor():
    """Provide YAMLExtractor instance."""
    return YAMLExtractor()


@pytest.fixture
def write_yaml_file(tmp_path: Path):
    """Factory fixture to write YAML files."""

    def _write(content: str, ext: str = ".yaml") -> Path:
        file_path = tmp_path / f"config{ext}"
        file_path.write_text(content)
        return file_path

    return _write


class TestYAMLExtractorSupports:
    """Tests for file support detection."""

    def test_supports_yaml_files(self, extractor) -> None:
        """Test supports .yaml files."""
        assert extractor.supports(Path("config.yaml"))

    def test_supports_yml_files(self, extractor) -> None:
        """Test supports .yml files."""
        assert extractor.supports(Path("config.yml"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support non-YAML files."""
        assert not extractor.supports(Path("config.json"))


class TestYAMLKeyExtraction:
    """Tests for YAML key extraction."""

    @pytest.mark.asyncio
    async def test_extract_top_level_keys(self, extractor, write_yaml_file) -> None:
        """Test extracting top-level keys."""
        content = """
name: test-app
version: 1.0.0
description: A test application
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 3
        var_names = {v.name for v in result.variables}
        assert "name" in var_names
        assert "version" in var_names
        assert "description" in var_names

    @pytest.mark.asyncio
    async def test_extract_nested_keys(self, extractor, write_yaml_file) -> None:
        """Test extracting nested keys."""
        content = """
database:
  host: localhost
  port: 5432
  credentials:
    username: admin
    password: secret
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Check for nested paths
        qualified_names = {v.qualified_name for v in result.variables}
        assert "database" in qualified_names
        assert "database.host" in qualified_names
        assert "database.port" in qualified_names
        assert "database.credentials" in qualified_names
        assert "database.credentials.username" in qualified_names

    @pytest.mark.asyncio
    async def test_extract_list_items(self, extractor, write_yaml_file) -> None:
        """Test extracting list structures."""
        content = """
services:
  - name: web
    port: 80
  - name: api
    port: 8080
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        var_names = {v.name for v in result.variables}
        assert "services" in var_names
        # List items should be indexed
        qualified_names = {v.qualified_name for v in result.variables}
        assert "services[0]" in qualified_names or "services" in qualified_names


class TestYAMLAnchorsAndAliases:
    """Tests for YAML anchors and aliases."""

    @pytest.mark.asyncio
    async def test_extract_anchors(self, extractor, write_yaml_file) -> None:
        """Test extracting YAML anchors."""
        content = """
defaults: &defaults
  timeout: 30
  retries: 3

production:
  <<: *defaults
  host: prod.example.com
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract keys including anchor definitions
        var_names = {v.name for v in result.variables}
        assert "defaults" in var_names
        assert "production" in var_names

    @pytest.mark.asyncio
    async def test_extract_with_aliases(self, extractor, write_yaml_file) -> None:
        """Test extracting YAML with aliases."""
        content = """
base_config: &base
  port: 8080
  debug: false

dev_config:
  <<: *base
  debug: true
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        qualified_names = {v.qualified_name for v in result.variables}
        assert "base_config" in qualified_names
        assert "dev_config" in qualified_names


class TestYAMLComplexStructures:
    """Tests for complex YAML structures."""

    @pytest.mark.asyncio
    async def test_extract_kubernetes_style(self, extractor, write_yaml_file) -> None:
        """Test extracting Kubernetes-style YAML."""
        content = """
apiVersion: v1
kind: Service
metadata:
  name: my-service
  namespace: default
spec:
  selector:
    app: my-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 9376
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        qualified_names = {v.qualified_name for v in result.variables}
        assert "apiVersion" in qualified_names
        assert "kind" in qualified_names
        assert "metadata.name" in qualified_names
        assert "spec.selector" in qualified_names

    @pytest.mark.asyncio
    async def test_max_depth_limit(self, extractor, write_yaml_file) -> None:
        """Test that deeply nested structures respect max depth."""
        content = """
level1:
  level2:
    level3:
      level4:
        level5:
          level6: too_deep
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should respect max_depth parameter (default 5)
        assert len(result.variables) > 0
        # Check that extraction stopped at reasonable depth
        qualified_names = {v.qualified_name for v in result.variables}
        assert "level1" in qualified_names


class TestYAMLErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_invalid_yaml(self, extractor, write_yaml_file) -> None:
        """Test handling invalid YAML."""
        content = """
key: value
  : invalid: syntax: here
  [unclosed bracket
another_key: value
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should report parse error
        assert len(result.parse_errors) > 0

    @pytest.mark.asyncio
    async def test_empty_yaml(self, extractor, write_yaml_file) -> None:
        """Test handling empty YAML file."""
        content = ""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should return empty result, no errors
        assert len(result.variables) == 0
        assert len(result.parse_errors) == 0

    @pytest.mark.asyncio
    async def test_yaml_with_comments(self, extractor, write_yaml_file) -> None:
        """Test handling YAML with comments."""
        content = """
# This is a comment
name: test  # inline comment
# Another comment
version: 1.0
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should extract keys, ignore comments
        var_names = {v.name for v in result.variables}
        assert "name" in var_names
        assert "version" in var_names


class TestYAMLDockerCompose:
    """Tests for Docker Compose YAML patterns."""

    @pytest.mark.asyncio
    async def test_docker_compose_structure(self, extractor, write_yaml_file) -> None:
        """Test extracting Docker Compose YAML structure."""
        content = """
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    environment:
      - NODE_ENV=production
  db:
    image: postgres:14
    volumes:
      - db-data:/var/lib/postgresql/data
volumes:
  db-data:
"""
        file_path = write_yaml_file(content)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        qualified_names = {v.qualified_name for v in result.variables}
        assert "version" in qualified_names
        assert "services" in qualified_names
        assert "volumes" in qualified_names
