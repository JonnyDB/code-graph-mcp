"""Server runtime lifecycle management.

Encapsulates server initialization, lifecycle, and context management.
Replaces module-level globals with a proper runtime object.
"""

import asyncio
from pathlib import Path

from loguru import logger

from mrcis.config.loader import load_config
from mrcis.config.models import Config
from mrcis.config.reconciler import ConfigReconciler
from mrcis.extractors.registry import ExtractorRegistry
from mrcis.server import ServerContext, shutdown_services
from mrcis.services.embedder import EmbeddingService
from mrcis.services.file_event_router import FileEventRouter
from mrcis.services.indexer import IndexingService
from mrcis.services.instance_lock import InstanceLock
from mrcis.services.resolver import ReferenceResolver
from mrcis.services.watcher import FileWatcher
from mrcis.storage.factory import StorageBackendFactory
from mrcis.storage.state_db import StateDB
from mrcis.utils.logging import configure_logging


async def initialize_services(config: Config, *, is_writer: bool = True) -> ServerContext:
    """
    Initialize all services.

    Args:
        config: Loaded configuration.
        is_writer: Whether this instance holds the writer lock.
            When False, skip write operations (crash recovery, reconciliation).

    Returns:
        ServerContext with all initialized services.
    """
    # Initialize storage
    state_db = StateDB(config.storage.data_directory / config.storage.state_db_name)
    await state_db.initialize()

    if is_writer:
        recovered = await state_db.recover_from_crash()
        if recovered > 0:
            logger.info("Recovered {} files from interrupted indexing", recovered)

        # Reconcile config file with database state
        reconciler = ConfigReconciler(state_db, config)
        reconcile_result = await reconciler.reconcile()
        logger.info(
            "Config reconciled: added={} removed={} unchanged={}",
            len(reconcile_result.added),
            len(reconcile_result.removed),
            len(reconcile_result.unchanged),
        )
    else:
        logger.info("Read-only instance — skipping crash recovery and reconciliation")

    # Create storage backends via factory
    factory = StorageBackendFactory(config)
    logger.info("Storage backend: {}", factory.backend)

    logger.info("Creating vector store...")
    vector_store = factory.create_vector_store()
    logger.info("Initializing vector store...")
    await vector_store.initialize()
    logger.info("Vector store ready")

    logger.info("Creating relation graph...")
    relation_graph = factory.create_relation_graph(state_db)
    logger.info("Initializing relation graph...")
    await relation_graph.initialize()
    logger.info("Relation graph ready")

    # Initialize services
    logger.info("Initializing embedder...")
    embedder = EmbeddingService(config.embedding)
    await embedder.initialize()
    logger.info("Embedder ready")

    extractor_registry = ExtractorRegistry.create_default()

    # Build repo config lookup
    repo_configs = {r.name: r for r in config.repositories}

    indexer = IndexingService(
        state_db=state_db,  # type: ignore[arg-type]
        vector_store=vector_store,
        relation_graph=relation_graph,  # type: ignore[arg-type]
        extractor_registry=extractor_registry,
        embedder=embedder,
        repo_configs=repo_configs,
        indexing_config=config.indexing,
        files_config=config.files,
    )

    resolver = ReferenceResolver(
        relation_graph=relation_graph,  # type: ignore[arg-type]
        interval_seconds=config.indexing.resolution_interval_seconds,
        max_attempts=config.indexing.max_retries,
    )

    # Wire resolver into indexer for post-index resolution
    indexer.resolver = resolver

    # Create file event router
    file_event_router = FileEventRouter(
        state_db=state_db,  # type: ignore[arg-type]
        indexer=indexer,
        relation_graph=relation_graph,  # type: ignore[arg-type]
        vector_store=vector_store,
        repo_configs=repo_configs,
    )

    watcher = FileWatcher(
        repo_configs=repo_configs,
        debounce_ms=config.indexing.watch_debounce_ms,
    )

    return ServerContext(
        config=config,
        state_db=state_db,  # type: ignore[arg-type]
        vector_store=vector_store,
        relation_graph=relation_graph,  # type: ignore[arg-type]
        embedder=embedder,
        extractor_registry=extractor_registry,
        indexer=indexer,
        resolver=resolver,
        file_event_router=file_event_router,
        watcher=watcher,
    )


async def startup_indexing(context: ServerContext) -> None:
    """Scan repositories and queue files on startup."""
    logger.info("Scanning {} repositories...", len(context.config.repositories))
    for repo_config in context.config.repositories:
        repo = await context.state_db.get_repository_by_name(repo_config.name)
        if repo:
            count = await context.indexer.scan_repository(str(repo.id), repo_config)
            logger.info("Queued {} files from '{}'", count, repo_config.name)
        else:
            logger.info("Repository '{}' not found in DB, skipping scan", repo_config.name)


class ServerRuntime:
    """Encapsulates server lifecycle and context management.

    Replaces module-level globals with proper instance state.
    Starts automatically on application startup and runs until shutdown.

    Supports multiple instances sharing the same storage directory.
    One instance acquires the writer lock (indexing, watching, resolving)
    while others run in read-only mode (search/reference queries only).
    """

    def __init__(self) -> None:
        """Initialize runtime in uninitialized state."""
        self._context: ServerContext | None = None
        self._config_path: Path | None = None
        self._lock: InstanceLock | None = None
        self._is_writer: bool = False

    def is_initialized(self) -> bool:
        """Check if runtime is initialized."""
        return self._context is not None

    @property
    def is_writer(self) -> bool:
        """Check if this instance holds the writer lock."""
        return self._is_writer

    def get_context(self) -> ServerContext:
        """Get current server context.

        Returns:
            ServerContext with all services.

        Raises:
            RuntimeError: If server not initialized.
        """
        if self._context is None:
            raise RuntimeError("Server not initialized")
        return self._context

    async def start(self, config: Config | None = None, config_path: Path | None = None) -> None:
        """Start the server runtime.

        Attempts to acquire the writer lock. If successful, starts all
        indexing and background services. Otherwise starts in read-only
        mode with a periodic lock check for promotion.

        Args:
            config: Optional pre-loaded configuration. If not provided, loads from config_path.
            config_path: Path to configuration file.

        Raises:
            RuntimeError: If already initialized.
        """
        if self._context is not None:
            raise RuntimeError("Server runtime already initialized")

        self._config_path = config_path

        # Load config if not provided
        if config is None:
            config = load_config(config_path)

        configure_logging(config.logging)
        logger.info("MRCIS server starting...")

        # Try to acquire writer lock
        config.storage.data_directory.mkdir(parents=True, exist_ok=True)
        self._lock = InstanceLock(config.storage.data_directory)
        self._is_writer = self._lock.try_acquire()

        if self._is_writer:
            logger.info("Acquired writer lock — starting as writer")
        else:
            logger.info("Writer lock held by another instance — starting as read-only")

        # Initialize all services
        logger.info("Initializing services...")
        self._context = await initialize_services(config, is_writer=self._is_writer)
        self._context.is_writer = self._is_writer
        logger.info("All services initialized")

        if self._is_writer:
            await self._start_writer_tasks()
        else:
            # Read-only: only run lock check loop
            logger.info("Starting lock check loop...")
            self._context.background_tasks = [
                asyncio.create_task(self._lock_check_loop()),
            ]

        logger.info("MRCIS server ready (mode={})", "writer" if self._is_writer else "read-only")

    async def _start_writer_tasks(self) -> None:
        """Start all writer-mode background tasks."""
        assert self._context is not None

        # Wire watcher to file event router
        self._context.watcher.on_change(self._context.file_event_router.handle)

        # Scan repositories on startup
        logger.info("Starting repository scan...")
        await startup_indexing(self._context)
        logger.info("Repository scan complete")

        # Start background tasks
        logger.info("Starting background tasks...")
        self._context.background_tasks.extend(
            [
                asyncio.create_task(self._context.indexer.process_backlog()),
                asyncio.create_task(self._context.indexer.retry_failed_files()),
                asyncio.create_task(self._context.resolver.run_forever()),
                asyncio.create_task(self._context.watcher.start()),
                asyncio.create_task(self._heartbeat_loop()),
            ]
        )

    async def _heartbeat_loop(self) -> None:
        """Periodically update the lock file timestamp while holding the lock."""
        assert self._lock is not None
        while True:
            try:
                await asyncio.sleep(self._lock.heartbeat_seconds)
            except asyncio.CancelledError:
                break
            self._lock.heartbeat()

    async def _lock_check_loop(self) -> None:
        """Periodically check if the writer lock is stale and promote if possible."""
        assert self._lock is not None
        while True:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break

            if self._lock.check_and_promote():
                logger.info("Writer lock is stale — promoting to writer")
                await self._promote_to_writer()
                break  # Promotion complete, exit check loop

    async def _promote_to_writer(self) -> None:
        """Promote this read-only instance to writer mode."""
        assert self._context is not None
        self._is_writer = True
        self._context.is_writer = True
        await self._start_writer_tasks()
        logger.info("Promotion complete — now running as writer")

    async def stop(self) -> None:
        """Stop the server runtime gracefully."""
        if self._context is None:
            return

        logger.info("MRCIS server shutting down...")

        # Cancel background tasks
        for task in self._context.background_tasks:
            task.cancel()
        await asyncio.gather(*self._context.background_tasks, return_exceptions=True)

        # Release writer lock
        if self._lock is not None:
            self._lock.release()
            self._lock = None

        # Shutdown services
        await shutdown_services(self._context)
        self._context = None
        self._is_writer = False

        logger.info("MRCIS server shutdown complete")
