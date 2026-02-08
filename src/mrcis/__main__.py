"""CLI entry point for MRCIS.

Provides commands for starting the server, initializing
the database, and managing repositories.
"""

import asyncio
from pathlib import Path
from typing import Literal

import click

from mrcis import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Multi-Repository Code Intelligence System.

    A semantic code search and intelligence system that indexes
    code across multiple repositories for AI-powered search
    and navigation.
    """
    pass


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="MCP transport type",
)
def serve(config: Path | None, transport: Literal["stdio", "sse"] = "stdio") -> None:
    """Start the MCP server.

    Starts the MRCIS runtime immediately (indexing, background tasks,
    file watching), then serves MCP tools over the chosen transport.
    Runtime lifecycle is decoupled from MCP client connections.
    """
    from mrcis.config.loader import load_config
    from mrcis.server import create_server
    from mrcis.server_runtime import ServerRuntime
    from mrcis.utils.logging import configure_logging

    cfg = load_config(config)

    # Configure logging early — stderr only, before any log output
    # can corrupt MCP stdio transport on stdout.
    configure_logging(cfg.logging)

    async def main() -> None:
        runtime = ServerRuntime()
        await runtime.start(config_path=config)
        mcp = create_server(runtime, host=cfg.server.host, port=cfg.server.port)
        try:
            if transport == "sse":
                await mcp.run_sse_async()
            else:
                await mcp.run_stdio_async()
        finally:
            await runtime.stop()

    asyncio.run(main())


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
def init(config: Path | None) -> None:
    """Initialize the database and verify configuration.

    Creates the database schema and validates that all
    configured repositories exist.
    """
    from mrcis.config.loader import load_config
    from mrcis.storage.state_db import StateDB

    cfg = load_config(config)

    async def main() -> None:
        db_path = cfg.storage.data_directory / cfg.storage.state_db_name

        # Ensure data directory exists
        cfg.storage.data_directory.mkdir(parents=True, exist_ok=True)

        db = StateDB(db_path)
        await db.initialize()
        await db.close()

        click.echo(f"Database initialized at {db_path}")

        # Validate repositories
        for repo in cfg.repositories:
            if repo.path.exists():
                click.echo(f"  [OK] Repository '{repo.name}' at {repo.path}")
            else:
                click.echo(f"  [WARN] Repository '{repo.name}' path not found: {repo.path}")

    asyncio.run(main())


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--repository",
    "-r",
    help="Filter by repository name",
)
def status(config: Path | None, repository: str | None) -> None:
    """Show index status for repositories.

    Displays file counts, entity counts, and indexing status
    for all configured repositories.
    """
    from mrcis.config.loader import load_config
    from mrcis.storage.state_db import StateDB

    cfg = load_config(config)

    async def main() -> None:
        db_path = cfg.storage.data_directory / cfg.storage.state_db_name

        if not db_path.exists():
            click.echo("Database not initialized. Run 'mrcis init' first.")
            return

        db = StateDB(db_path)
        await db.initialize()

        repos = await db.get_all_repositories()

        if repository:
            repos = [r for r in repos if r.name == repository]

        if not repos:
            click.echo("No repositories found.")
            await db.close()
            return

        click.echo("\nRepository Status:")
        click.echo("-" * 60)

        for repo in repos:
            queue_len = await db.get_queue_length()

            click.echo(f"\n{repo.name}:")
            click.echo(f"  Status: {repo.status.value}")
            click.echo(f"  Files: {repo.file_count}")
            click.echo(f"  Entities: {repo.entity_count}")
            click.echo(f"  Relations: {repo.relation_count}")
            click.echo(f"  Queue depth: {queue_len}")

            if repo.last_indexed_at:
                click.echo(f"  Last indexed: {repo.last_indexed_at}")

            if repo.error_message:
                click.echo(f"  Error: {repo.error_message}")

        await db.close()

    asyncio.run(main())


@cli.command()
@click.argument("repository")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force reindex even if files haven't changed",
)
def reindex(repository: str, config: Path | None, force: bool) -> None:
    """Queue a repository for reindexing.

    Queues all files in the repository for reindexing.
    Use --force to reindex even unchanged files.
    """
    from mrcis.config.loader import load_config
    from mrcis.storage.state_db import StateDB

    cfg = load_config(config)

    async def main() -> None:
        db_path = cfg.storage.data_directory / cfg.storage.state_db_name

        if not db_path.exists():
            click.echo("Database not initialized. Run 'mrcis init' first.")
            return

        db = StateDB(db_path)
        await db.initialize()

        repo = await db.get_repository_by_name(repository)
        if not repo:
            click.echo(f"Repository not found: {repository}")
            await db.close()
            return

        # Mark all files as pending for reindexing using public API
        count = await db.mark_repository_files_pending(str(repo.id), reset_failures=force)
        enqueued = await db.enqueue_pending_files(str(repo.id))

        click.echo(f"Marked {count} files as pending")
        click.echo(f"Enqueued {enqueued} files for reindexing")
        if force:
            click.echo("Failure counts reset")

        await db.close()

    asyncio.run(main())


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
