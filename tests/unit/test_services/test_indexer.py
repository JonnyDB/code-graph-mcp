"""Tests for IndexingService."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from mrcis.config.models import IndexingConfig, RepositoryConfig
from mrcis.models.state import FileStatus, IndexedFile
from mrcis.services.indexer import IndexingService
from mrcis.services.resolver import ReferenceResolver, ResolutionResult


@pytest.fixture
def indexing_config() -> IndexingConfig:
    """Create test indexing config."""
    return IndexingConfig(
        batch_size=50,
        max_retries=3,
        retry_delay_seconds=5.0,
    )


@pytest.fixture
def repo_config(tmp_path: Path) -> RepositoryConfig:
    """Create test repository config."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    return RepositoryConfig(
        name="test-repo",
        path=repo_path,
        branch="main",
    )


@pytest.fixture
def mock_state_db() -> AsyncMock:
    """Create mock state database."""
    db = AsyncMock()
    db.dequeue_next_file = AsyncMock(return_value=None)
    db.upsert_file = AsyncMock()
    db.enqueue_file = AsyncMock()
    db.update_file_status = AsyncMock()
    db.update_file_indexed = AsyncMock()
    db.update_file_failure = AsyncMock()
    db.get_file_by_path = AsyncMock(return_value=None)
    db.get_repository = AsyncMock()
    db.transaction = MagicMock()
    db.transaction.return_value.__aenter__ = AsyncMock()
    db.transaction.return_value.__aexit__ = AsyncMock()
    return db


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    store.upsert_vectors = AsyncMock(return_value=0)
    store.delete_by_file = AsyncMock()
    return store


@pytest.fixture
def mock_relation_graph() -> AsyncMock:
    """Create mock relation graph."""
    graph = AsyncMock()
    graph.add_entity = AsyncMock(return_value="entity-id")
    graph.add_relation = AsyncMock(return_value="relation-id")
    graph.add_pending_reference = AsyncMock(return_value="ref-id")
    graph.delete_entities_for_file = AsyncMock(return_value=0)
    return graph


@pytest.fixture
def mock_extractor_registry() -> MagicMock:
    """Create mock extractor registry."""
    registry = MagicMock()
    return registry


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Create mock embedder service."""
    embedder = AsyncMock()
    embedder.embed_texts = AsyncMock(return_value=[])
    return embedder


@pytest.fixture
def indexing_service(
    mock_state_db: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_relation_graph: AsyncMock,
    mock_extractor_registry: MagicMock,
    mock_embedder: AsyncMock,
    repo_config: RepositoryConfig,
    indexing_config: IndexingConfig,
) -> IndexingService:
    """Create indexing service with mocks."""
    return IndexingService(
        state_db=mock_state_db,
        vector_store=mock_vector_store,
        relation_graph=mock_relation_graph,
        extractor_registry=mock_extractor_registry,
        embedder=mock_embedder,
        repo_configs={repo_config.name: repo_config},
        indexing_config=indexing_config,
    )


class TestIndexingServiceInit:
    """Test IndexingService initialization."""

    def test_creates_with_dependencies(self, indexing_service: IndexingService) -> None:
        """Should create service with all dependencies."""
        assert indexing_service.state_db is not None
        assert indexing_service.vector_store is not None
        assert indexing_service.relation_graph is not None
        assert indexing_service.extractors is not None
        assert indexing_service.embedder is not None

    def test_stores_batch_size_from_config(self, indexing_service: IndexingService) -> None:
        """Should store batch size from config."""
        assert indexing_service.batch_size == 50

    def test_stores_max_retries_from_config(self, indexing_service: IndexingService) -> None:
        """Should create failure policy with max retries from config."""
        assert indexing_service.failure_policy is not None
        assert indexing_service.failure_policy.max_retries == 3


class TestStop:
    """Test stop method."""

    @pytest.mark.asyncio
    async def test_stop_sets_shutdown_event(self, indexing_service: IndexingService) -> None:
        """stop should set shutdown event."""
        await indexing_service.stop()
        assert indexing_service._shutdown_event.is_set()


class TestRepoStatsUpdate:
    """Test that _process_file updates repository stats after indexing."""

    @pytest.mark.asyncio
    async def test_process_file_updates_repo_stats(
        self,
        indexing_service: IndexingService,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
        mock_extractor_registry: MagicMock,
        repo_config: RepositoryConfig,
    ) -> None:
        """_process_file should update repository stats after successful indexing."""
        # Create a real file so the extractor path check passes
        test_file = repo_config.path / "test.py"
        test_file.write_text("def hello(): pass")

        repo_id = str(uuid4())
        file_id = str(uuid4())

        file = IndexedFile(
            id=file_id,
            repository_id=repo_id,
            path="test.py",
            checksum="abc123",
            file_size=100,
            language="python",
            status=FileStatus.PENDING,
            last_modified_at=datetime.now(UTC),
        )

        # Mock repo lookup
        mock_repo = MagicMock()
        mock_repo.name = repo_config.name
        mock_state_db.get_repository.return_value = mock_repo

        # Mock extraction result with no entities (simplest case)
        mock_result = MagicMock()
        mock_result.parse_errors = []
        mock_result.all_entities.return_value = []
        mock_result.relations = []
        mock_result.pending_references = []

        mock_extractor = AsyncMock()
        mock_extractor.extract_with_context.return_value = mock_result
        mock_extractor_registry.get_extractor.return_value = mock_extractor

        # Set up count methods on state_db (file/pending counts)
        mock_state_db.count_indexed_files = AsyncMock(return_value=10)
        mock_state_db.count_pending_files = AsyncMock(return_value=0)
        mock_state_db.update_repository_stats = AsyncMock()

        # Set up count methods on relation_graph (entity/relation counts)
        mock_relation_graph.count_entities = AsyncMock(return_value=50)
        mock_relation_graph.count_relations = AsyncMock(return_value=20)

        await indexing_service._process_file(file)

        # Verify file/pending counts were queried from state_db
        mock_state_db.count_indexed_files.assert_called_once_with(repo_id)
        mock_state_db.count_pending_files.assert_called_once_with(repo_id)

        # Verify entity/relation counts were queried from relation_graph
        mock_relation_graph.count_entities.assert_called_once_with(repo_id)
        mock_relation_graph.count_relations.assert_called_once_with(repo_id)

        # Verify update_repository_stats was called with live counts,
        # last_indexed_at, and status transition to "watching" (no pending files)
        call_args = mock_state_db.update_repository_stats.call_args
        assert call_args.args[0] == repo_id
        assert call_args.kwargs["file_count"] == 10
        assert call_args.kwargs["entity_count"] == 50
        assert call_args.kwargs["relation_count"] == 20
        assert call_args.kwargs["last_indexed_at"] is not None
        assert call_args.kwargs["status"] == "watching"

    @pytest.mark.asyncio
    async def test_process_file_stats_called_after_file_indexed(
        self,
        indexing_service: IndexingService,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
        mock_extractor_registry: MagicMock,
        repo_config: RepositoryConfig,
    ) -> None:
        """update_repository_stats should be called after update_file_indexed."""
        # Create a real file
        test_file = repo_config.path / "test.py"
        test_file.write_text("x = 1")

        repo_id = str(uuid4())
        file_id = str(uuid4())

        file = IndexedFile(
            id=file_id,
            repository_id=repo_id,
            path="test.py",
            checksum="abc123",
            file_size=100,
            language="python",
            status=FileStatus.PENDING,
            last_modified_at=datetime.now(UTC),
        )

        mock_repo = MagicMock()
        mock_repo.name = repo_config.name
        mock_state_db.get_repository.return_value = mock_repo

        mock_result = MagicMock()
        mock_result.parse_errors = []
        mock_result.all_entities.return_value = []
        mock_result.relations = []
        mock_result.pending_references = []

        mock_extractor = AsyncMock()
        mock_extractor.extract_with_context.return_value = mock_result
        mock_extractor_registry.get_extractor.return_value = mock_extractor

        mock_state_db.count_indexed_files = AsyncMock(return_value=5)
        mock_state_db.count_pending_files = AsyncMock(return_value=0)
        mock_state_db.update_repository_stats = AsyncMock()
        mock_relation_graph.count_entities = AsyncMock(return_value=25)
        mock_relation_graph.count_relations = AsyncMock(return_value=10)

        # Track call order
        call_order: list[str] = []
        original_update_file_indexed = mock_state_db.update_file_indexed

        async def track_file_indexed(*args: object, **kwargs: object) -> None:
            call_order.append("update_file_indexed")
            return await original_update_file_indexed(*args, **kwargs)

        async def track_repo_stats(*_args: object, **_kwargs: object) -> None:
            call_order.append("update_repository_stats")

        mock_state_db.update_file_indexed = AsyncMock(side_effect=track_file_indexed)
        mock_state_db.update_repository_stats = AsyncMock(side_effect=track_repo_stats)

        await indexing_service._process_file(file)

        assert call_order == ["update_file_indexed", "update_repository_stats"]


class TestPostIndexResolution:
    """Test that resolver is triggered after each file is indexed."""

    @pytest.mark.asyncio
    async def test_process_file_triggers_resolver(
        self,
        mock_state_db: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_relation_graph: AsyncMock,
        mock_extractor_registry: MagicMock,
        mock_embedder: AsyncMock,
        repo_config: RepositoryConfig,
        indexing_config: IndexingConfig,
    ) -> None:
        """After indexing a file, should run a resolver batch."""
        mock_resolver = AsyncMock(spec=ReferenceResolver)
        mock_resolver.resolve_batch = AsyncMock(return_value=ResolutionResult())

        service = IndexingService(
            state_db=mock_state_db,
            vector_store=mock_vector_store,
            relation_graph=mock_relation_graph,
            extractor_registry=mock_extractor_registry,
            embedder=mock_embedder,
            repo_configs={repo_config.name: repo_config},
            indexing_config=indexing_config,
            resolver=mock_resolver,
        )

        # Setup mocks for _process_file
        file = IndexedFile(
            id=str(uuid4()),
            repository_id=str(uuid4()),
            path="test.py",
            checksum="abc123",
            file_size=100,
            language="python",
            status=FileStatus.PENDING,
            last_modified_at=datetime.now(UTC),
        )

        repo_state = MagicMock()
        repo_state.name = repo_config.name
        mock_state_db.get_repository.return_value = repo_state

        mock_result = MagicMock()
        mock_result.all_entities.return_value = []
        mock_result.relations = []
        mock_result.pending_references = []
        mock_result.parse_errors = []

        extractor = AsyncMock()
        extractor.extract_with_context.return_value = mock_result
        mock_extractor_registry.get_extractor.return_value = extractor

        test_file = repo_config.path / "test.py"
        test_file.write_text("# test")

        await service._process_file(file)

        mock_resolver.resolve_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_file_works_without_resolver(
        self,
        indexing_service: IndexingService,
        mock_state_db: AsyncMock,
        mock_extractor_registry: MagicMock,
        repo_config: RepositoryConfig,
    ) -> None:
        """Should work fine when no resolver is set (backwards compatible)."""
        file = IndexedFile(
            id=str(uuid4()),
            repository_id=str(uuid4()),
            path="test.py",
            checksum="abc123",
            file_size=100,
            language="python",
            status=FileStatus.PENDING,
            last_modified_at=datetime.now(UTC),
        )

        repo_state = MagicMock()
        repo_state.name = repo_config.name
        mock_state_db.get_repository.return_value = repo_state

        mock_result = MagicMock()
        mock_result.all_entities.return_value = []
        mock_result.relations = []
        mock_result.pending_references = []
        mock_result.parse_errors = []

        extractor = AsyncMock()
        extractor.extract_with_context.return_value = mock_result
        mock_extractor_registry.get_extractor.return_value = extractor

        test_file = repo_config.path / "test.py"
        test_file.write_text("# test")

        # Should not raise
        await indexing_service._process_file(file)

    @pytest.mark.asyncio
    async def test_resolver_updates_relation_count_on_resolve(
        self,
        mock_state_db: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_relation_graph: AsyncMock,
        mock_extractor_registry: MagicMock,
        mock_embedder: AsyncMock,
        repo_config: RepositoryConfig,
        indexing_config: IndexingConfig,
    ) -> None:
        """After resolver resolves references, relation_count should be re-queried and updated."""
        mock_resolver = AsyncMock(spec=ReferenceResolver)
        mock_resolver.resolve_batch = AsyncMock(
            return_value=ResolutionResult(resolved=3, still_pending=1)
        )

        service = IndexingService(
            state_db=mock_state_db,
            vector_store=mock_vector_store,
            relation_graph=mock_relation_graph,
            extractor_registry=mock_extractor_registry,
            embedder=mock_embedder,
            repo_configs={repo_config.name: repo_config},
            indexing_config=indexing_config,
            resolver=mock_resolver,
        )

        file = IndexedFile(
            id=str(uuid4()),
            repository_id=str(uuid4()),
            path="test.py",
            checksum="abc123",
            file_size=100,
            language="python",
            status=FileStatus.PENDING,
            last_modified_at=datetime.now(UTC),
        )

        repo_state = MagicMock()
        repo_state.name = repo_config.name
        mock_state_db.get_repository.return_value = repo_state

        mock_result = MagicMock()
        mock_result.all_entities.return_value = []
        mock_result.relations = []
        mock_result.pending_references = []
        mock_result.parse_errors = []

        extractor = AsyncMock()
        extractor.extract_with_context.return_value = mock_result
        mock_extractor_registry.get_extractor.return_value = extractor

        test_file = repo_config.path / "test.py"
        test_file.write_text("# test")

        # Set count_relations to return 5 after resolution
        mock_relation_graph.count_relations.return_value = 5

        await service._process_file(file)

        # update_repository_stats should be called twice:
        # 1st: after indexing (with file_count, entity_count, relation_count)
        # 2nd: after resolver resolves (with only relation_count)
        calls = mock_state_db.update_repository_stats.call_args_list
        assert len(calls) == 2
        # Second call should only update relation_count
        assert calls[1].kwargs.get("relation_count") == 5


class TestRetryFailedFiles:
    """Test retry_failed_files background loop."""

    @pytest.mark.asyncio
    async def test_enqueues_failed_files(
        self,
        indexing_service: IndexingService,
        mock_state_db: AsyncMock,
    ) -> None:
        """Should re-enqueue files returned by get_retryable_failed_files."""
        repo_id = str(uuid4())
        file1 = IndexedFile(
            id=str(uuid4()),
            repository_id=repo_id,
            path="a.py",
            checksum="abc",
            file_size=100,
            language="python",
            status=FileStatus.FAILED,
            failure_count=1,
            error_message="transient",
            last_modified_at=datetime.now(UTC),
        )
        file2 = IndexedFile(
            id=str(uuid4()),
            repository_id=repo_id,
            path="b.py",
            checksum="def",
            file_size=200,
            language="python",
            status=FileStatus.FAILED,
            failure_count=2,
            error_message="also transient",
            last_modified_at=datetime.now(UTC),
        )
        mock_state_db.get_retryable_failed_files = AsyncMock(return_value=[file1, file2])

        # Run a single iteration: let the first sleep pass (work happens),
        # then set shutdown on the second sleep so the loop exits.
        call_count = 0

        async def fake_sleep(_seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                indexing_service._shutdown_event.set()

        with patch("mrcis.services.indexer.asyncio.sleep", side_effect=fake_sleep):
            await indexing_service.retry_failed_files()

        assert mock_state_db.enqueue_file.call_count == 2
        mock_state_db.enqueue_file.assert_any_call(str(file1.id), repo_id)
        mock_state_db.enqueue_file.assert_any_call(str(file2.id), repo_id)

    @pytest.mark.asyncio
    async def test_skips_when_no_failed_files(
        self,
        indexing_service: IndexingService,
        mock_state_db: AsyncMock,
    ) -> None:
        """Should not call enqueue_file when there are no failed files."""
        mock_state_db.get_retryable_failed_files = AsyncMock(return_value=[])

        call_count = 0

        async def fake_sleep(_seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                indexing_service._shutdown_event.set()

        with patch("mrcis.services.indexer.asyncio.sleep", side_effect=fake_sleep):
            await indexing_service.retry_failed_files()

        mock_state_db.enqueue_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_db_error_gracefully(
        self,
        indexing_service: IndexingService,
        mock_state_db: AsyncMock,
    ) -> None:
        """Should log and continue when get_retryable_failed_files raises."""
        mock_state_db.get_retryable_failed_files = AsyncMock(side_effect=RuntimeError("db gone"))

        call_count = 0

        async def fake_sleep(_seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                indexing_service._shutdown_event.set()

        with patch("mrcis.services.indexer.asyncio.sleep", side_effect=fake_sleep):
            await indexing_service.retry_failed_files()

        # Should not raise — error is caught and logged
        mock_state_db.enqueue_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_stops_on_shutdown_event(
        self,
        indexing_service: IndexingService,
    ) -> None:
        """Should exit loop when shutdown event is set."""
        indexing_service._shutdown_event.set()

        # Should return immediately without doing anything
        await indexing_service.retry_failed_files()
