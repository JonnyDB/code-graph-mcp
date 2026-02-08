"""File event routing service.

Routes file system change events to appropriate indexing operations.
Extracted from server.py to follow Single Responsibility Principle.
"""

from typing import TYPE_CHECKING

from loguru import logger

from mrcis.config.models import RepositoryConfig
from mrcis.models.state import FileStatus, Repository
from mrcis.services.watcher import FileEvent

if TYPE_CHECKING:
    from mrcis.ports import RelationGraphPort, StatePort, VectorStorePort
    from mrcis.services.indexer import IndexingService


class FileEventRouter:
    """Routes file change events to indexing operations.

    Responsibilities:
    - Validate repository and configuration
    - Normalize file paths
    - Detect atomic saves vs real deletions
    - Dispatch to appropriate indexing operations
    """

    def __init__(
        self,
        state_db: "StatePort",
        indexer: "IndexingService",
        relation_graph: "RelationGraphPort",
        vector_store: "VectorStorePort",
        repo_configs: dict[str, RepositoryConfig],
    ) -> None:
        """Initialize router with dependencies.

        Args:
            state_db: State database port
            indexer: Indexing service
            relation_graph: Relation graph port
            vector_store: Vector store port
            repo_configs: Repository configurations by name
        """
        self.state_db = state_db
        self.indexer = indexer
        self.relation_graph = relation_graph
        self.vector_store = vector_store
        self.repo_configs = repo_configs

    async def handle(self, event: FileEvent) -> None:
        """Handle a file system change event.

        Args:
            event: File system event to handle
        """
        # Validate repository exists in DB
        repo = await self.state_db.get_repository_by_name(event.repository)
        if not repo:
            logger.warning("Event for unknown repository: {}", event.repository)
            return

        # Validate repository configuration exists
        repo_config = self.repo_configs.get(event.repository)
        if not repo_config:
            logger.warning("No config for repository: {}", event.repository)
            return

        # Compute relative path for DB lookups (DB stores relative paths)
        try:
            relative_path = str(event.path.relative_to(repo_config.path))
        except ValueError:
            relative_path = str(event.path)

        if event.type == "deleted":
            await self._handle_deletion(event, repo, repo_config, relative_path)
        else:
            # created/modified - queue for indexing
            await self.indexer.index_file(event.path, str(repo.id), repo_root=repo_config.path)
            logger.debug("File queued for indexing: {}", event.path)

    async def _handle_deletion(
        self,
        event: FileEvent,
        repo: Repository,
        repo_config: RepositoryConfig,
        relative_path: str,
    ) -> None:
        """Handle file deletion event.

        Atomic saves (delete + rename) appear as delete events.
        After debouncing, check whether the file still exists on disk.

        Args:
            event: File deletion event
            repo: Repository model
            repo_config: Repository configuration
            relative_path: File path relative to repository root
        """
        if event.path.exists():
            # File still exists — this was an atomic save, not a real deletion
            await self.indexer.index_file(event.path, str(repo.id), repo_root=repo_config.path)
            logger.info("File modified (atomic save), re-queued: {}", event.path)
        else:
            # Real deletion - remove from index
            file = await self.state_db.get_file_by_path(str(repo.id), relative_path)
            if file:
                await self.relation_graph.delete_entities_for_file(str(file.id))
                await self.vector_store.delete_by_file(str(file.id))
                await self.state_db.update_file_status(str(file.id), FileStatus.DELETED)
                logger.info("File deleted from index: {}", event.path)
