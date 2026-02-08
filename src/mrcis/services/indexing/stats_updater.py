"""Repository statistics updater for indexing operations.

Handles updating repository statistics after file indexing and reference resolution.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mrcis.ports import IndexingStatePort


class RepositoryStatsUpdater:
    """Updates repository statistics during indexing operations.

    Encapsulates the logic for querying counts and updating repository
    statistics after file indexing and reference resolution events.
    """

    def __init__(self, state_db: "IndexingStatePort") -> None:
        """Initialize stats updater.

        Args:
            state_db: State database port for querying counts and updating stats.
        """
        self.state_db = state_db

    async def update_after_file_indexed(self, repo_id: str) -> None:
        """Update repository statistics after a file has been indexed.

        Queries all relevant counts (files, entities, relations, pending)
        and updates the repository record with fresh statistics and timestamp.
        Automatically transitions status to "watching" when no pending files remain.

        Args:
            repo_id: Repository ID to update.
        """
        # Query all current counts
        file_count = await self.state_db.count_indexed_files(repo_id)
        entity_count = await self.state_db.count_entities(repo_id)
        relation_count = await self.state_db.count_relations(repo_id)
        pending_count = await self.state_db.count_pending_files(repo_id)

        # Transition to "watching" when no more pending files
        new_status = "watching" if pending_count == 0 else "indexing"

        # Update repository with fresh stats
        await self.state_db.update_repository_stats(
            repo_id,
            file_count=file_count,
            entity_count=entity_count,
            relation_count=relation_count,
            last_indexed_at=datetime.now(UTC).isoformat(),
            status=new_status,
        )

    async def update_after_resolution(self, repo_id: str) -> None:
        """Update relation count after reference resolution.

        After resolving pending references, the relation count may have
        increased. This method updates only the relation count without
        re-querying all other statistics.

        Args:
            repo_id: Repository ID to update.
        """
        # Re-query relation count after resolution
        relation_count = await self.state_db.count_relations(repo_id)

        # Update only relation count
        await self.state_db.update_repository_stats(
            repo_id,
            relation_count=relation_count,
        )
