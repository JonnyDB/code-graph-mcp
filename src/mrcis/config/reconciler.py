"""Configuration reconciler.

Reconciles the configuration file with database state on startup.
Configuration is authoritative - database only stores state.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from mrcis.config.models import Config


@dataclass
class ReconciliationResult:
    """Result of config/database reconciliation."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


class ConfigReconciler:
    """
    Reconciles config file with database state on startup.

    Configuration is authoritative - database only stores state.
    """

    def __init__(self, state_db: Any, config: "Config") -> None:
        self.db = state_db
        self.config = config

    async def reconcile(self) -> ReconciliationResult:
        """
        Sync config file repositories with database state.

        - New repos in config: create DB records with status='pending'
        - Removed repos from config: mark for cleanup (optional)
        - Existing repos: validate, keep state intact
        """
        result = ReconciliationResult()

        config_repos = {r.name: r for r in self.config.repositories}
        db_repos_list = await self.db.get_all_repositories()
        db_repos = {r.name: r for r in db_repos_list}

        # Add new repositories from config
        for name, _repo_config in config_repos.items():
            if name not in db_repos:
                await self.db.create_repository(
                    name=name,
                    status="pending",
                )
                result.added.append(name)
                logger.info("Repository added from config: {}", name)

        # Handle removed repositories (repos in DB but not in config)
        for name in db_repos:
            if name not in config_repos:
                result.removed.append(name)
                logger.warning(
                    "Repository '{}' in database but not in config. "
                    "Use CLI to remove if no longer needed.",
                    name,
                )

        # Validate existing repositories
        for name, _repo_config in config_repos.items():
            if name in db_repos:
                # Config is authoritative - no validation needed
                # State (status, counts, etc.) is preserved
                result.unchanged.append(name)

        return result
