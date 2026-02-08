"""Tests for Neo4j configuration models."""

import os

import pytest

from mrcis.config.models import Config, Neo4jConfig, StorageConfig


class TestNeo4jConfig:
    """Tests for Neo4j configuration model."""

    def test_neo4j_config_defaults(self) -> None:
        cfg = Neo4jConfig()
        assert cfg.uri == "bolt://localhost:7687"
        assert cfg.username == "neo4j"
        assert cfg.password == "mrcis1234!"
        assert cfg.database == "neo4j"
        assert cfg.max_connection_pool_size == 50
        assert cfg.connection_timeout_seconds == 30.0
        assert cfg.vector_dimensions == 1024
        assert cfg.vector_index_name == "code_vectors"
        assert cfg.vector_similarity_function == "cosine"

    def test_neo4j_config_custom_values(self) -> None:
        cfg = Neo4jConfig(
            uri="bolt://db.example.com:7687",
            username="admin",
            password="secret123",
            database="mrcis_prod",
            max_connection_pool_size=100,
            vector_dimensions=768,
        )
        assert cfg.uri == "bolt://db.example.com:7687"
        assert cfg.username == "admin"
        assert cfg.password == "secret123"
        assert cfg.database == "mrcis_prod"
        assert cfg.max_connection_pool_size == 100
        assert cfg.vector_dimensions == 768

    def test_neo4j_uri_validation_bolt(self) -> None:
        cfg = Neo4jConfig(uri="bolt://localhost:7687")
        assert cfg.uri == "bolt://localhost:7687"

    def test_neo4j_uri_validation_neo4j_scheme(self) -> None:
        cfg = Neo4jConfig(uri="neo4j://cluster.example.com:7687")
        assert cfg.uri == "neo4j://cluster.example.com:7687"

    def test_neo4j_uri_validation_bolt_s(self) -> None:
        cfg = Neo4jConfig(uri="bolt+s://secure.example.com:7687")
        assert cfg.uri == "bolt+s://secure.example.com:7687"

    def test_neo4j_uri_rejects_http(self) -> None:
        with pytest.raises(ValueError, match="uri must start with"):
            Neo4jConfig(uri="http://localhost:7474")


class TestStorageBackendConfig:
    """Tests for storage backend selection."""

    def test_default_backend_is_sqlite_lancedb(self) -> None:
        cfg = StorageConfig()
        assert cfg.backend == "sqlite_lancedb"

    def test_neo4j_backend(self) -> None:
        cfg = StorageConfig(backend="neo4j")
        assert cfg.backend == "neo4j"

    def test_invalid_backend_rejected(self) -> None:
        with pytest.raises(ValueError):
            StorageConfig(backend="postgres")  # type: ignore[arg-type]

    def test_root_config_includes_neo4j(self) -> None:
        cfg = Config()
        assert cfg.neo4j is not None
        assert cfg.neo4j.uri == "bolt://localhost:7687"

    def test_neo4j_env_vars(self) -> None:
        """Neo4j config should be configurable via MRCIS_ env vars."""
        env = {
            "MRCIS_NEO4J__URI": "bolt://prod:7687",
            "MRCIS_NEO4J__USERNAME": "produser",
            "MRCIS_NEO4J__PASSWORD": "prodpass",
        }
        for k, v in env.items():
            os.environ[k] = v
        try:
            cfg = Config()
            assert cfg.neo4j.uri == "bolt://prod:7687"
            assert cfg.neo4j.username == "produser"
            assert cfg.neo4j.password == "prodpass"
        finally:
            for k in env:
                os.environ.pop(k, None)
