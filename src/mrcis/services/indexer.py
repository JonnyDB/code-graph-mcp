"""Indexing service for processing files through the pipeline.

Processes files from the queue, extracts entities,
generates embeddings, and stores results.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from loguru import logger

from mrcis.config.models import FilesConfig, IndexingConfig, RepositoryConfig
from mrcis.models.state import FileStatus, IndexedFile
from mrcis.services.indexing import (
    FileIndexingPipeline,
    IndexFailurePolicy,
    LanguageDetector,
    RepositoryScanner,
    RepositoryStatsUpdater,
)
from mrcis.services.pathing import PathNormalizer
from mrcis.utils.hashing import compute_file_checksum

if TYPE_CHECKING:
    from mrcis.ports import (
        EmbedderPort,
        ExtractorRegistryPort,
        IndexingStatePort,
        RelationGraphPort,
        VectorStorePort,
    )


class IndexingService:
    """
    Core indexing pipeline.

    Processes files from the queue, extracts entities,
    generates embeddings, and stores results.

    Configuration is injected, not read from database.
    """

    def __init__(
        self,
        state_db: "IndexingStatePort",
        vector_store: "VectorStorePort",
        relation_graph: "RelationGraphPort",
        extractor_registry: "ExtractorRegistryPort",
        embedder: "EmbedderPort",
        repo_configs: dict[str, RepositoryConfig],
        indexing_config: IndexingConfig,
        files_config: FilesConfig | None = None,
        resolver: Any | None = None,  # ReferenceResolver, keep Any for now
    ) -> None:
        """Initialize indexing service with dependency ports."""
        self.state_db = state_db
        self.vector_store = vector_store
        self.relation_graph = relation_graph
        self.extractors = extractor_registry
        self.embedder = embedder
        self.repo_configs = repo_configs  # Config is authoritative
        self.batch_size = indexing_config.batch_size
        self.files_config = files_config or FilesConfig()
        self.resolver = resolver

        # Create pipeline for file processing
        self.pipeline = FileIndexingPipeline(
            vector_store=vector_store,
            relation_graph=relation_graph,
            extractor_registry=extractor_registry,
            embedder=embedder,
        )
        self.language_detector = LanguageDetector()
        self.failure_policy = IndexFailurePolicy(max_retries=indexing_config.max_retries)
        self.stats_updater = RepositoryStatsUpdater(state_db, relation_graph)

        self._shutdown_event = asyncio.Event()
        self._current_file: str | None = None

    async def process_backlog(self) -> None:
        """
        Main processing loop. Runs until shutdown.

        Processes files in FIFO order from the queue.
        """
        logger.info("Indexing backlog processing started")

        while not self._shutdown_event.is_set():
            # Get next file from queue (FIFO)
            try:
                file = await self.state_db.dequeue_next_file()
            except Exception as e:
                logger.warning("Dequeue failed (will retry): {}", e)
                await asyncio.sleep(1.0)
                continue

            if file is None:
                # No pending files, wait before checking again
                await asyncio.sleep(1.0)
                continue

            self._current_file = str(file.id)
            try:
                await self._process_file(file)
            except Exception as e:
                await self._handle_failure(file, e)
            finally:
                self._current_file = None

    async def retry_failed_files(self) -> None:
        """Periodically re-enqueue files stuck in 'failed' status.

        Runs every 60 seconds as a safety net. Files that failed but
        weren't re-enqueued (e.g. due to a crash during _handle_failure)
        are picked up and placed back in the indexing queue.
        """
        logger.info("Failed file retry loop started")

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(60.0)
            except asyncio.CancelledError:
                break

            if self._shutdown_event.is_set():
                break

            try:
                files = await self.state_db.get_retryable_failed_files()
                if files:
                    for file in files:
                        await self.state_db.enqueue_file(str(file.id), str(file.repository_id))
                    logger.info("Re-enqueued {} failed file(s) for retry", len(files))
            except Exception as e:
                logger.warning("Failed file retry check error: {}", e)

    async def stop(self) -> None:
        """Signal shutdown and wait for current file to complete."""
        self._shutdown_event.set()
        # If processing a file, it will complete before loop exits

    async def index_file(
        self,
        file_path: Path,
        repo_id: str,
        repo_root: Path | None = None,
        force: bool = False,
    ) -> str:
        """
        Queue a single file for indexing.

        Uses an atomic transaction to ensure the file record and queue
        entry are created together. On crash recovery, files with
        status='pending' not in the queue are automatically re-queued.

        Args:
            file_path: Path to the file (absolute or relative).
            repo_id: Repository ID.
            repo_root: Repository root path for computing relative paths.
            force: If True, queue even if checksum is unchanged.

        Returns:
            File ID
        """
        checksum = await compute_file_checksum(file_path)

        # Store path relative to repository root using PathNormalizer
        if repo_root:
            normalizer = PathNormalizer(repo_root)
            stored_path = normalizer.to_repo_relative(file_path)
        else:
            stored_path = str(file_path)

        # Check if already indexed with same checksum (skip when forcing)
        existing = await self.state_db.get_file_by_path(repo_id, stored_path)
        if not force and existing and existing.checksum == checksum:
            logger.debug("File unchanged: {}", file_path)
            return str(existing.id)

        file_id = existing.id if existing else uuid4()

        # Create or update file record
        file = IndexedFile(
            id=file_id,
            repository_id=UUID(repo_id),
            path=stored_path,
            checksum=checksum,
            file_size=file_path.stat().st_size,
            language=self.language_detector.detect(file_path),
            status=FileStatus.PENDING,
            last_modified_at=datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC),
        )

        # Atomic: both succeed or both fail
        async with self.state_db.transaction():
            actual_id = await self.state_db.upsert_file(file)
            await self.state_db.enqueue_file(actual_id, repo_id)

        return actual_id

    async def scan_repository(
        self, repo_id: str, repo_config: "RepositoryConfig", force: bool = False
    ) -> int:
        """
        Scan repository and queue changed/new files for indexing.

        Args:
            repo_id: Repository ID in database.
            repo_config: Repository configuration.
            force: If True, queue files even if unchanged.

        Returns:
            Number of files queued.
        """
        queued = 0
        scanner = RepositoryScanner(repo_config.path, self.files_config)

        for file_path in scanner.iter_files():
            # Check if file changed (unless forcing)
            if not force:
                checksum = await compute_file_checksum(file_path)
                # Use relative path for lookup (DB stores relative paths)
                normalizer = PathNormalizer(repo_config.path)
                lookup_path = normalizer.to_repo_relative(file_path)
                existing = await self.state_db.get_file_by_path(repo_id, lookup_path)
                if existing and existing.checksum == checksum:
                    continue  # Unchanged

            # Queue for indexing
            await self.index_file(file_path, repo_id, repo_root=repo_config.path, force=force)
            queued += 1

        if queued > 0:
            await self.state_db.update_repository_stats(repo_id, status="indexing")

        logger.info(
            "Repository scan complete: repo={} queued={}",
            repo_config.name,
            queued,
        )
        return queued

    async def queue_repository(self, repo_id: str, force: bool = False) -> int:
        """
        Queue all files in repository for reindexing.

        Args:
            repo_id: Repository ID.
            force: If True, reindex even unchanged files.

        Returns:
            Number of files queued.
        """
        repo = await self.state_db.get_repository(repo_id)
        if not repo:
            raise ValueError(f"Repository not found: {repo_id}")

        repo_config = self.repo_configs.get(repo.name)
        if not repo_config:
            raise ValueError(f"Repository not in config: {repo.name}")

        if force:
            # Clear existing index for fresh start
            await self._clear_repository_index(repo_id)

        return await self.scan_repository(repo_id, repo_config, force=force)

    async def _clear_repository_index(self, repo_id: str) -> None:
        """Clear all indexed data for a repository."""
        # Get all files for this repository using public API
        files = await self.state_db.list_files_by_repository(repo_id)

        for file in files:
            # Delete entities and vectors
            await self.relation_graph.delete_entities_for_file(str(file.id))
            await self.vector_store.delete_by_file(str(file.id))

        # Reset file statuses using public API
        await self.state_db.mark_repository_files_pending(repo_id, reset_failures=True)
        await self.state_db.enqueue_pending_files(repo_id)

        logger.info("Cleared index for repository: {}", repo_id)

    async def _process_file(self, file: IndexedFile) -> None:
        """Process a single file through the indexing pipeline.

        Orchestrates file processing by:
        1. Managing file status transitions
        2. Resolving repository paths
        3. Delegating to pipeline for actual processing
        4. Updating repository statistics
        5. Triggering reference resolution
        """
        # Mark as processing
        await self.state_db.update_file_status(str(file.id), FileStatus.PROCESSING)

        # Get repository config (config file is authoritative for paths)
        repo_state = await self.state_db.get_repository(str(file.repository_id))
        if not repo_state:
            logger.error("Repository not found: {}", file.repository_id)
            return
        repo_config = self.repo_configs[repo_state.name]
        full_path = repo_config.path / file.path

        if not full_path.exists():
            # File was deleted
            await self._handle_deleted_file(file)
            return

        # Detect language for this file
        language = self.language_detector.detect(full_path)

        # Process file through pipeline
        result = await self.pipeline.process(file, full_path, language)

        # Update file status
        await self.state_db.update_file_indexed(
            str(file.id),
            entity_count=result.entity_count,
        )

        # Update repository stats with live counts and last_indexed_at
        repo_id_str = str(file.repository_id)
        await self.stats_updater.update_after_file_indexed(repo_id_str)

        logger.info(
            "File indexed: id={} path={} entities={}",
            file.id,
            file.path,
            result.entity_count,
        )

        # Trigger resolver pass to immediately resolve pending references
        # that may now have matching target entities
        if self.resolver:
            try:
                resolve_result = await self.resolver.resolve_batch()
                if resolve_result.resolved > 0:
                    logger.info(
                        "Post-index resolution: resolved={} pending={}",
                        resolve_result.resolved,
                        resolve_result.still_pending,
                    )
                    # Update relation count after resolution
                    await self.stats_updater.update_after_resolution(repo_id_str)
            except Exception as e:
                logger.warning("Post-index resolution failed: {}", e)

    async def _handle_failure(self, file: IndexedFile, error: Exception) -> None:
        """Handle indexing failure with retry logic."""
        logger.error("Indexing failed: file_id={} error={}", file.id, error)

        new_count = file.failure_count + 1
        should_retry, status = self.failure_policy.determine_action(new_count)

        if should_retry:
            # Re-queue for retry
            await self.state_db.enqueue_file(str(file.id), str(file.repository_id))

        await self.state_db.update_file_failure(
            str(file.id),
            status=status,
            failure_count=new_count,
            error_message=str(error),
        )

    async def _handle_deleted_file(self, file: IndexedFile) -> None:
        """Clean up a deleted file."""
        logger.info("File deleted: id={} path={}", file.id, file.path)

        # Remove from vector store
        await self.vector_store.delete_by_file(str(file.id))

        # Remove entities and relations
        await self.relation_graph.delete_entities_for_file(str(file.id))

        # Mark file as deleted
        await self.state_db.update_file_status(str(file.id), FileStatus.DELETED)
