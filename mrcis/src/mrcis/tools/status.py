"""Status MCP tools.

Provides index status and management functionality.
"""

from typing import TYPE_CHECKING, Any

from mrcis.models.responses import (
    IndexStatus,
    IndexStatusResponse,
    ReindexResponse,
)

if TYPE_CHECKING:
    from mrcis.ports import RepositoryReaderPort, StatePort


async def get_index_status(
    state_db: "RepositoryReaderPort",
    repository: str | None = None,
    relation_graph: Any = None,  # noqa: ARG001
    is_writer: bool = True,
) -> IndexStatusResponse:
    """
    Get index status for repositories.

    Args:
        state_db: StateDB instance.
        repository: Optional repository name to filter.
        relation_graph: Optional RelationGraph instance (reserved for future use).

    Returns:
        IndexStatusResponse with status information.
    """
    if repository:
        # Get single repository status
        repo = await state_db.get_repository_by_name(repository)
        if repo is None:
            return IndexStatusResponse(
                repositories=[],
                total_files=0,
                total_entities=0,
                total_relations=0,
            )
        repos = [repo]
    else:
        # Get all repositories
        repos = await state_db.get_all_repositories()

    statuses: list[IndexStatus] = []
    total_files = 0
    total_entities = 0
    total_relations = 0

    for repo in repos:
        repo_id = str(repo.id)
        pending = await state_db.count_pending_files(repo_id)
        failed = await state_db.count_failed_files(repo_id)
        file_count = await state_db.count_indexed_files(repo_id)
        entity_count = await state_db.count_entities(repo_id)
        relation_count = await state_db.count_relations(repo_id)

        statuses.append(
            IndexStatus(
                repository=repo.name,
                status=repo.status,
                file_count=file_count,
                entity_count=entity_count,
                relation_count=relation_count,
                pending_files=pending,
                failed_files=failed,
                last_indexed_at=(
                    repo.last_indexed_at.isoformat()
                    if repo.last_indexed_at and hasattr(repo.last_indexed_at, "isoformat")
                    else str(repo.last_indexed_at)
                    if repo.last_indexed_at
                    else None
                ),
                last_indexed_commit=repo.last_indexed_commit,
            )
        )

        total_files += file_count
        total_entities += entity_count
        total_relations += relation_count

    return IndexStatusResponse(
        repositories=statuses,
        total_files=total_files,
        total_entities=total_entities,
        total_relations=total_relations,
        is_writer=is_writer,
    )


async def reindex_repository(
    repository: str,
    state_db: "StatePort",
    indexer: Any,  # Keep Any for now, IndexingService
    force: bool = False,
) -> ReindexResponse:
    """
    Queue a repository for reindexing.

    Args:
        repository: Repository name to reindex.
        state_db: StateDB instance.
        indexer: IndexingService instance.
        force: Force reindex even if files haven't changed.

    Returns:
        ReindexResponse with queue status.
    """
    # Look up repository
    repo = await state_db.get_repository_by_name(repository)

    if repo is None:
        return ReindexResponse(
            repository=repository,
            status="error",
            files_queued=0,
            message=f"Repository not found: {repository}",
        )

    # Queue repository for reindexing
    try:
        files_queued = await indexer.queue_repository(str(repo.id), force=force)

        return ReindexResponse(
            repository=repository,
            status="queued",
            files_queued=files_queued,
            message=f"Queued {files_queued} files for reindexing",
        )
    except Exception as e:
        return ReindexResponse(
            repository=repository,
            status="error",
            files_queued=0,
            message=str(e),
        )
