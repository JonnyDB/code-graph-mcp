"""Tests for DockerfileExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.dockerfile import DockerfileExtractor


@pytest.fixture
def extractor():
    """Provide DockerfileExtractor instance."""
    return DockerfileExtractor()


@pytest.fixture
def write_dockerfile(tmp_path: Path):
    """Factory fixture to write Dockerfile files."""

    def _write(content: str, name: str = "Dockerfile") -> Path:
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path

    return _write


class TestDockerfileExtractorSupports:
    """Tests for file support detection."""

    def test_supports_dockerfile(self, extractor) -> None:
        """Test supports Dockerfile."""
        assert extractor.supports(Path("Dockerfile"))

    def test_supports_dockerfile_with_extension(self, extractor) -> None:
        """Test supports Dockerfile with extensions."""
        assert extractor.supports(Path("Dockerfile.dev"))
        assert extractor.supports(Path("Dockerfile.prod"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support non-Dockerfile files."""
        assert not extractor.supports(Path("README.md"))
        assert not extractor.supports(Path("docker-compose.yml"))


class TestDockerfileBaseImageExtraction:
    """Tests for FROM instruction extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_from(self, extractor, write_dockerfile) -> None:
        """Test extracting simple FROM instruction."""
        code = "FROM python:3.11"
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "python:3.11"
        assert result.imports[0].name == "python:3.11"

    @pytest.mark.asyncio
    async def test_extract_from_with_alias(self, extractor, write_dockerfile) -> None:
        """Test extracting FROM instruction with AS alias."""
        code = "FROM node:20-alpine AS builder"
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 1
        assert result.imports[0].source_module == "node:20-alpine"
        assert "builder" in result.imports[0].imported_symbols

    @pytest.mark.asyncio
    async def test_extract_multiple_from_stages(self, extractor, write_dockerfile) -> None:
        """Test extracting multi-stage build."""
        code = """FROM golang:1.21 AS builder
FROM alpine:latest AS runtime"""
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.imports) == 2
        assert result.imports[0].source_module == "golang:1.21"
        assert result.imports[1].source_module == "alpine:latest"


class TestDockerfileEnvExtraction:
    """Tests for ENV/ARG extraction."""

    @pytest.mark.asyncio
    async def test_extract_env_variable(self, extractor, write_dockerfile) -> None:
        """Test extracting ENV variable."""
        code = "ENV APP_HOME=/app"
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 1
        var = next(v for v in result.variables if v.name == "APP_HOME")
        assert var is not None

    @pytest.mark.asyncio
    async def test_extract_multiple_env_variables(self, extractor, write_dockerfile) -> None:
        """Test extracting multiple ENV variables."""
        code = """ENV NODE_ENV=production
ENV PORT=3000"""
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        var_names = {v.name for v in result.variables}
        assert "NODE_ENV" in var_names
        assert "PORT" in var_names

    @pytest.mark.asyncio
    async def test_extract_arg_variable(self, extractor, write_dockerfile) -> None:
        """Test extracting ARG variable."""
        code = "ARG BUILD_VERSION=1.0.0"
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 1
        var = next(v for v in result.variables if v.name == "BUILD_VERSION")
        assert var is not None


class TestDockerfileExposeExtraction:
    """Tests for EXPOSE instruction extraction."""

    @pytest.mark.asyncio
    async def test_extract_expose_port(self, extractor, write_dockerfile) -> None:
        """Test extracting EXPOSE instruction."""
        code = "EXPOSE 8080"
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 1
        port_var = next((v for v in result.variables if v.name.startswith("port_")), None)
        assert port_var is not None

    @pytest.mark.asyncio
    async def test_extract_multiple_expose_ports(self, extractor, write_dockerfile) -> None:
        """Test extracting multiple EXPOSE instructions."""
        code = """EXPOSE 80
EXPOSE 443"""
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        port_vars = [v for v in result.variables if v.name.startswith("port_")]
        assert len(port_vars) >= 2


class TestDockerfileEntrypointAndCmd:
    """Tests for ENTRYPOINT and CMD extraction."""

    @pytest.mark.asyncio
    async def test_extract_entrypoint(self, extractor, write_dockerfile) -> None:
        """Test extracting ENTRYPOINT instruction."""
        code = 'ENTRYPOINT ["python", "app.py"]'
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # ENTRYPOINT creates a function-like entity
        assert len(result.functions) >= 1
        entrypoint_func = next((f for f in result.functions if f.name == "entrypoint"), None)
        assert entrypoint_func is not None

    @pytest.mark.asyncio
    async def test_extract_cmd(self, extractor, write_dockerfile) -> None:
        """Test extracting CMD instruction."""
        code = 'CMD ["npm", "start"]'
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # CMD creates a function-like entity
        assert len(result.functions) >= 1
        cmd_func = next((f for f in result.functions if f.name == "cmd"), None)
        assert cmd_func is not None


class TestDockerfileCompleteExample:
    """Tests for complete Dockerfile extraction."""

    @pytest.mark.asyncio
    async def test_extract_complete_dockerfile(self, extractor, write_dockerfile) -> None:
        """Test extracting a complete Dockerfile with multiple instructions."""
        code = """FROM python:3.11-slim AS base

ARG APP_VERSION=1.0.0
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

EXPOSE 8000

ENTRYPOINT ["python", "manage.py"]
CMD ["runserver", "0.0.0.0:8000"]
"""
        file_path = write_dockerfile(code)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should have FROM as import
        assert len(result.imports) >= 1
        assert result.imports[0].source_module == "python:3.11-slim"

        # Should have ENV and ARG as variables
        var_names = {v.name for v in result.variables}
        assert "APP_VERSION" in var_names
        assert "PYTHONUNBUFFERED" in var_names
        assert "APP_HOME" in var_names

        # Should have EXPOSE port
        port_vars = [v for v in result.variables if v.name.startswith("port_")]
        assert len(port_vars) >= 1

        # Should have ENTRYPOINT and CMD as functions
        func_names = {f.name for f in result.functions}
        assert "entrypoint" in func_names or "cmd" in func_names
