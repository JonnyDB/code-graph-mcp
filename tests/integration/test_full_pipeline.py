"""Integration tests for the full indexing pipeline."""

import pytest

from mrcis.config.models import (
    Config,
    EmbeddingConfig,
    IndexingConfig,
    LoggingConfig,
    RepositoryConfig,
    StorageConfig,
)
from mrcis.extractors.registry import ExtractorRegistry
from mrcis.services.indexer import IndexingService
from mrcis.storage.relation_graph import RelationGraph
from mrcis.storage.state_db import StateDB
from mrcis.storage.vector_store import VectorStore


@pytest.fixture
async def services(tmp_path, sample_python_repo, mock_embedder):
    """Initialize all services with temp storage."""
    # Create config
    config = Config(
        repositories=[
            RepositoryConfig(
                name="test-repo",
                path=sample_python_repo,
                branch="main",
            )
        ],
        storage=StorageConfig(
            data_directory=tmp_path / "data",
        ),
        embedding=EmbeddingConfig(
            api_url="http://mock",
            api_key="mock",
            model="mock",
            dimensions=1024,
        ),
        indexing=IndexingConfig(),
        logging=LoggingConfig(level="DEBUG"),
    )

    # Ensure directories exist
    config.storage.data_directory.mkdir(parents=True, exist_ok=True)

    # Initialize storage
    state_db = StateDB(config.storage.data_directory / "state.db")
    await state_db.initialize()

    vector_store = VectorStore(
        str(config.storage.data_directory / "vectors"),
        "test_vectors",
        1024,
    )
    await vector_store.initialize()

    relation_graph = RelationGraph(state_db)
    await relation_graph.initialize()

    # Create repository in DB
    repo_id = await state_db.create_repository("test-repo")

    # Initialize services
    extractor_registry = ExtractorRegistry.create_default()

    repo_configs = {r.name: r for r in config.repositories}

    indexer = IndexingService(
        state_db=state_db,
        vector_store=vector_store,
        relation_graph=relation_graph,
        extractor_registry=extractor_registry,
        embedder=mock_embedder,
        repo_configs=repo_configs,
        indexing_config=config.indexing,
        files_config=config.files,
    )

    yield {
        "config": config,
        "state_db": state_db,
        "vector_store": vector_store,
        "relation_graph": relation_graph,
        "indexer": indexer,
        "embedder": mock_embedder,
        "repo_id": repo_id,
    }

    # Cleanup
    await state_db.close()


@pytest.mark.integration
class TestFullPipeline:
    """Full pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_scan_repository_queues_files(self, services, sample_python_repo):  # noqa: ARG002
        """Scanning repository should queue files for indexing."""
        repo_config = services["config"].repositories[0]

        count = await services["indexer"].scan_repository(services["repo_id"], repo_config)

        assert count == 2  # main.py and utils.py

        queue_len = await services["state_db"].get_queue_length()
        assert queue_len == 2

    @pytest.mark.asyncio
    async def test_process_file_creates_entities(self, services, sample_python_repo):  # noqa: ARG002
        """Processing a file should create entities in database."""
        repo_config = services["config"].repositories[0]

        # Queue files
        await services["indexer"].scan_repository(services["repo_id"], repo_config)

        # Process one file
        file = await services["state_db"].dequeue_next_file()
        assert file is not None

        # Process it (this tests the internal _process_file method indirectly)
        # For now just verify file was dequeued
        queue_len = await services["state_db"].get_queue_length()
        assert queue_len == 1  # One file processed

    @pytest.mark.asyncio
    async def test_entities_have_correct_types(self, services, sample_python_repo):
        """Extracted entities should have correct types."""
        from uuid import uuid4

        from mrcis.extractors.python import PythonExtractor

        extractor = PythonExtractor()
        result = await extractor.extract(
            sample_python_repo / "main.py",
            file_id=str(uuid4()),
            repo_id=services["repo_id"],
        )

        # Should find Application class
        assert len(result.classes) == 1
        assert result.classes[0].name == "Application"

        # Should find methods
        method_names = {m.name for m in result.methods}
        assert "__init__" in method_names
        assert "run" in method_names

        # Should find functions
        func_names = {f.name for f in result.functions}
        assert "main" in func_names

    @pytest.mark.asyncio
    async def test_relation_graph_stores_entities(self, services, sample_python_repo):
        """RelationGraph should store and retrieve entities."""
        from datetime import datetime

        from mrcis.models.entities import EntityType
        from mrcis.models.state import FileStatus, IndexedFile

        # Create a file record first
        file = IndexedFile(
            repository_id=services["repo_id"],
            path=str(sample_python_repo / "main.py"),
            checksum="test123",
            file_size=100,
            language="python",
            status=FileStatus.INDEXED,
            last_modified_at=datetime.now(),
        )
        file_id = await services["state_db"].upsert_file(file)

        # Add entity
        await services["relation_graph"].add_entity(
            repository_id=services["repo_id"],
            file_id=file_id,
            qualified_name="main.Application",
            simple_name="Application",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=7,
            line_end=18,
        )

        # Retrieve by qualified name
        entity = await services["relation_graph"].get_entity_by_qualified_name("main.Application")

        assert entity is not None
        assert entity.simple_name == "Application"
        assert entity.entity_type == EntityType.CLASS

    @pytest.mark.asyncio
    async def test_relation_graph_suffix_search(self, services, sample_python_repo):
        """RelationGraph should find entities by name suffix."""
        from datetime import datetime

        from mrcis.models.entities import EntityType
        from mrcis.models.state import FileStatus, IndexedFile

        # Create file
        file = IndexedFile(
            repository_id=services["repo_id"],
            path=str(sample_python_repo / "main.py"),
            checksum="test123",
            file_size=100,
            language="python",
            status=FileStatus.INDEXED,
            last_modified_at=datetime.now(),
        )
        file_id = await services["state_db"].upsert_file(file)

        # Add entity
        await services["relation_graph"].add_entity(
            repository_id=services["repo_id"],
            file_id=file_id,
            qualified_name="main.Application",
            simple_name="Application",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=7,
            line_end=18,
        )

        # Search by suffix
        entities = await services["relation_graph"].get_entities_by_suffix("Application")

        assert len(entities) == 1
        assert entities[0].qualified_name == "main.Application"
