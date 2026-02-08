"""Tests for FileIndexingPipeline."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mrcis.models.entities import EntityType, FunctionEntity
from mrcis.models.extraction import ExtractionResult
from mrcis.models.state import FileStatus, IndexedFile
from mrcis.services.indexing.pipeline import FileIndexingPipeline


@pytest.fixture
def mock_vector_store():
    """Create mock vector store."""
    store = AsyncMock()
    store.delete_by_file = AsyncMock()
    store.upsert_vectors = AsyncMock()
    # Create a simple mock model
    store.model = type(
        "CodeVectorModel",
        (),
        {"__init__": lambda self, **kwargs: setattr(self, "__dict__", kwargs)},
    )
    return store


@pytest.fixture
def mock_relation_graph():
    """Create mock relation graph."""
    graph = AsyncMock()
    graph.delete_entities_for_file = AsyncMock()
    graph.add_entity = AsyncMock()
    graph.add_relation = AsyncMock()
    graph.add_pending_reference = AsyncMock()
    return graph


@pytest.fixture
def mock_extractor_registry():
    """Create mock extractor registry."""
    registry = MagicMock()
    return registry


@pytest.fixture
def mock_embedder():
    """Create mock embedder."""
    embedder = AsyncMock()
    embedder.embed_texts = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return embedder


@pytest.fixture
def pipeline(mock_vector_store, mock_relation_graph, mock_extractor_registry, mock_embedder):
    """Create pipeline with mocked dependencies."""
    return FileIndexingPipeline(
        vector_store=mock_vector_store,
        relation_graph=mock_relation_graph,
        extractor_registry=mock_extractor_registry,
        embedder=mock_embedder,
    )


@pytest.mark.asyncio
async def test_process_cleans_existing_data(pipeline, mock_vector_store, mock_relation_graph):
    """Pipeline should clean up existing data before processing."""
    file = IndexedFile(
        id=uuid4(),
        repository_id=uuid4(),
        path="test.py",
        checksum="abc123",
        file_size=100,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.PENDING,
    )
    full_path = Path("/repo/test.py")

    # Mock extractor to return no results
    pipeline.extractors.get_extractor = MagicMock(return_value=None)

    await pipeline.process(file, full_path, "python")

    # Should clean up existing data
    mock_vector_store.delete_by_file.assert_called_once_with(str(file.id))
    mock_relation_graph.delete_entities_for_file.assert_called_once_with(str(file.id))


@pytest.mark.asyncio
async def test_process_skips_when_no_extractor(pipeline):
    """Pipeline should return early when no extractor available."""
    file = IndexedFile(
        id=uuid4(),
        repository_id=uuid4(),
        path="unknown.xyz",
        checksum="abc123",
        file_size=100,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.PENDING,
    )
    full_path = Path("/repo/unknown.xyz")

    pipeline.extractors.get_extractor = MagicMock(return_value=None)

    result = await pipeline.process(file, full_path, None)

    assert result.entity_count == 0
    # Should not attempt embedding
    pipeline.embedder.embed_texts.assert_not_called()


@pytest.mark.asyncio
async def test_process_extracts_and_stores_entities(
    pipeline, mock_embedder, mock_vector_store, mock_relation_graph
):
    """Pipeline should extract entities and store them."""
    file = IndexedFile(
        id=uuid4(),
        repository_id=uuid4(),
        path="test.py",
        checksum="abc123",
        file_size=100,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.PENDING,
    )
    full_path = Path("/repo/test.py")

    # Create test entity
    entity = FunctionEntity(
        name="test_func",
        qualified_name="module.test_func",
        entity_type=EntityType.FUNCTION,
        repository_id=file.repository_id,
        file_id=file.id,
        file_path="test.py",
        language="python",
        line_start=1,
        line_end=5,
        signature="def test_func(): pass",
        docstring="Test function",
    )

    extraction_result = ExtractionResult(
        file_id=file.id,
        file_path=str(full_path),
        repository_id=file.repository_id,
        language="python",
        functions=[entity],
    )

    # Mock extractor
    mock_extractor = AsyncMock()
    mock_extractor.extract_with_context = AsyncMock(return_value=extraction_result)
    pipeline.extractors.get_extractor = MagicMock(return_value=mock_extractor)

    result = await pipeline.process(file, full_path, "python")

    # Should extract with context
    mock_extractor.extract_with_context.assert_called_once()
    # Verify context had correct fields
    call_args = mock_extractor.extract_with_context.call_args[0][0]
    assert call_args.file_path == full_path
    assert call_args.file_id == file.id
    assert call_args.repository_id == file.repository_id
    assert call_args.language == "python"

    # Should embed
    mock_embedder.embed_texts.assert_called_once()

    # Should store vectors
    mock_vector_store.upsert_vectors.assert_called_once()

    # Should store entity
    mock_relation_graph.add_entity.assert_called_once()

    # Result should have count
    assert result.entity_count == 1


@pytest.mark.asyncio
async def test_process_handles_multiple_entities(
    pipeline, mock_embedder, mock_vector_store, mock_relation_graph
):
    """Pipeline should handle multiple entities."""
    file = IndexedFile(
        id=uuid4(),
        repository_id=uuid4(),
        path="test.py",
        checksum="abc123",
        file_size=100,
        last_modified_at=datetime.now(UTC),
        status=FileStatus.PENDING,
    )
    full_path = Path("/repo/test.py")

    # Create multiple entities
    entities = [
        FunctionEntity(
            name=f"func_{i}",
            qualified_name=f"module.func_{i}",
            entity_type=EntityType.FUNCTION,
            repository_id=file.repository_id,
            file_id=file.id,
            file_path="test.py",
            language="python",
            line_start=i,
            line_end=i + 1,
        )
        for i in range(3)
    ]

    extraction_result = ExtractionResult(
        file_id=file.id,
        file_path=str(full_path),
        repository_id=file.repository_id,
        language="python",
        functions=entities,
    )

    mock_extractor = AsyncMock()
    mock_extractor.extract_with_context = AsyncMock(return_value=extraction_result)
    pipeline.extractors.get_extractor = MagicMock(return_value=mock_extractor)

    # Mock embedder to return 3 vectors
    mock_embedder.embed_texts = AsyncMock(return_value=[[0.1] * 3 for _ in range(3)])

    result = await pipeline.process(file, full_path, "python")

    assert result.entity_count == 3

    # Should generate 3 embeddings
    call_args = mock_embedder.embed_texts.call_args[0][0]
    assert len(call_args) == 3

    # Should store 3 vectors
    call_args = mock_vector_store.upsert_vectors.call_args[0][0]
    assert len(call_args) == 3

    # Should store 3 entities
    assert mock_relation_graph.add_entity.call_count == 3
