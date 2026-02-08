"""Pydantic configuration models for MRCIS."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class ServerConfig(BaseModel):
    """MCP server configuration."""

    transport: Literal["sse", "stdio"] = "sse"
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    shutdown_timeout_seconds: int = Field(default=30, ge=5, le=300)


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""

    provider: Literal["openai_compatible"] = "openai_compatible"
    api_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    model: str = "mxbai-embed-large"
    dimensions: int = Field(default=1024, ge=64, le=4096)
    batch_size: int = Field(default=100, ge=1, le=1000)
    timeout_seconds: float = Field(default=30.0, ge=5.0, le=300.0)

    @field_validator("api_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format and strip trailing slash."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("api_url must start with http:// or https://")
        return v.rstrip("/")


class Neo4jConfig(BaseModel):
    """Neo4j connection and vector index configuration."""

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "mrcis1234!"
    database: str = "neo4j"
    max_connection_pool_size: int = Field(default=50, ge=1, le=500)
    connection_timeout_seconds: float = Field(default=30.0, ge=5.0, le=300.0)
    vector_dimensions: int = Field(default=1024, ge=64, le=4096)
    vector_index_name: str = "code_vectors"
    vector_similarity_function: Literal["cosine", "euclidean"] = "cosine"

    @field_validator("uri")
    @classmethod
    def validate_neo4j_uri(cls, v: str) -> str:
        """Validate Neo4j URI scheme."""
        valid_schemes = (
            "bolt://",
            "bolt+s://",
            "bolt+ssc://",
            "neo4j://",
            "neo4j+s://",
            "neo4j+ssc://",
        )
        if not v.startswith(valid_schemes):
            raise ValueError(f"uri must start with one of: {', '.join(valid_schemes)}")
        return v


class StorageConfig(BaseModel):
    """Storage configuration."""

    backend: Literal["sqlite_lancedb", "neo4j"] = "sqlite_lancedb"
    data_directory: Path = Field(default_factory=lambda: Path("~/.mrcis").expanduser())
    vector_table_name: str = "code_vectors"
    state_db_name: str = "state.db"

    @field_validator("data_directory", mode="before")
    @classmethod
    def expand_path(cls, v: Path | str) -> Path:
        """Expand user path and resolve to absolute."""
        if isinstance(v, str):
            v = Path(v)
        return v.expanduser().resolve()


class RepositoryConfig(BaseModel):
    """Single repository configuration."""

    name: str = Field(min_length=1, max_length=100)
    path: Path
    branch: str = "main"
    depends_on: list[str] = Field(default_factory=list)
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, v: Path | str) -> Path:
        """Validate path exists and expand to absolute."""
        if isinstance(v, str):
            v = Path(v)
        expanded = v.expanduser().resolve()
        if not expanded.exists():
            raise ValueError(f"Repository path does not exist: {expanded}")
        if not expanded.is_dir():
            raise ValueError(f"Repository path must be a directory: {expanded}")
        return expanded


class FilesConfig(BaseModel):
    """File filtering configuration."""

    include_patterns: list[str] = Field(
        default_factory=lambda: [
            # Programming languages
            "**/*.py",
            "**/*.ts",
            "**/*.tsx",
            "**/*.js",
            "**/*.jsx",
            "**/*.go",
            "**/*.rs",
            "**/*.rb",
            "**/*.java",
            "**/*.kt",
            # Configuration files
            "**/*.json",
            "**/*.yaml",
            "**/*.yml",
            "**/*.toml",
            # Markup and documentation
            "**/*.html",
            "**/*.htm",
            "**/*.xml",
            "**/*.md",
            "**/*.markdown",
            # Templating
            "**/*.erb",
            # Docker
            "**/Dockerfile",
            "**/Dockerfile.*",
            "**/docker-compose.yml",
            "**/docker-compose.yaml",
            "**/docker-compose.*.yml",
            "**/docker-compose.*.yaml",
        ]
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/node_modules/**",
            "**/.git/**",
            "**/dist/**",
            "**/build/**",
            "**/__pycache__/**",
            "**/.venv/**",
            "**/vendor/**",
        ]
    )
    respect_gitignore: bool = True
    max_file_size_kb: int = Field(default=1024, ge=1, le=10240)


class ParserConfig(BaseModel):
    """Parser configuration."""

    max_chunk_chars: int = Field(default=4000, ge=500, le=32000)
    chunk_overlap_chars: int = Field(default=200, ge=0, le=1000)
    extract_docstrings: bool = True
    extract_comments: bool = False

    @field_validator("chunk_overlap_chars")
    @classmethod
    def validate_overlap(cls, v: int, info: Any) -> int:
        """Validate chunk overlap is less than max chunk size."""
        if "max_chunk_chars" in info.data and v >= info.data["max_chunk_chars"]:
            raise ValueError("chunk_overlap_chars must be less than max_chunk_chars")
        return v


class IndexingConfig(BaseModel):
    """Indexing behavior configuration."""

    batch_size: int = Field(default=50, ge=1, le=500)
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    resolution_interval_seconds: int = Field(default=60, ge=10, le=600)
    watch_debounce_ms: int = Field(default=500, ge=100, le=5000)


class LoggingConfig(BaseModel):
    """Logging configuration for loguru."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["console", "json"] = "console"
    file: Path | None = None
    rotation: str = "10 MB"
    retention: str = "7 days"


class Config(BaseSettings):
    """Root configuration for MRCIS."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    repositories: list[RepositoryConfig] = Field(default_factory=list)
    files: FilesConfig = Field(default_factory=FilesConfig)
    parser: ParserConfig = Field(default_factory=ParserConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = {
        "env_prefix": "MRCIS_",
        "env_nested_delimiter": "__",
    }
