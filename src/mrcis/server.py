"""MCP server entry point.

Creates and configures the FastMCP server with all services
and tools for code intelligence.

Note: Tool implementations use lazy imports to avoid circular dependencies
and keep the server startup lightweight.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any

from loguru import logger
from mcp.server.fastmcp import FastMCP
from pydantic import Field

if TYPE_CHECKING:
    from mrcis.config.models import Config
    from mrcis.ports import (
        EmbedderPort,
        ExtractorRegistryPort,
        RelationGraphPort,
        StatePort,
        VectorStorePort,
    )
    from mrcis.server_runtime import ServerRuntime
    from mrcis.services.file_event_router import FileEventRouter
    from mrcis.services.indexer import IndexingService
    from mrcis.services.resolver import ReferenceResolver
    from mrcis.services.watcher import FileWatcher


@dataclass
class ServerContext:
    """Server runtime context with typed dependencies."""

    config: "Config"
    state_db: "StatePort"
    vector_store: "VectorStorePort"
    relation_graph: "RelationGraphPort"
    embedder: "EmbedderPort"
    extractor_registry: "ExtractorRegistryPort"
    indexer: "IndexingService"
    resolver: "ReferenceResolver"
    file_event_router: "FileEventRouter"
    watcher: "FileWatcher"
    background_tasks: list[Any] = field(default_factory=list)
    is_writer: bool = True


async def shutdown_services(context: ServerContext) -> None:
    """Gracefully shutdown all services."""
    await context.watcher.stop()
    await context.resolver.stop()
    await context.indexer.stop()
    await context.embedder.close()
    await context.state_db.close()
    # Close Neo4j connections if using neo4j backend
    if hasattr(context.relation_graph, "close"):
        await context.relation_graph.close()
    if hasattr(context.vector_store, "close"):
        await context.vector_store.close()
    logger.info("All services stopped")


def create_server(
    runtime: "ServerRuntime",
    host: str = "127.0.0.1",
    port: int = 8000,
) -> FastMCP:
    """
    Create the MCP server.

    The runtime must already be started before calling this function.
    Lifecycle (start/stop) is managed externally by the caller,
    decoupled from MCP client connections.

    Args:
        runtime: An already-started ServerRuntime instance.
        host: Host to bind to for SSE transport.
        port: Port to bind to for SSE transport.

    Returns:
        Configured FastMCP server instance.
    """
    mcp = FastMCP(
        "Multi-Repository Code Intelligence",
        host=host,
        port=port,
    )

    # Closure to get context from runtime
    def get_context() -> ServerContext:
        return runtime.get_context()

    # Lazy imports for response models (used in return type annotations)
    from mrcis.models.responses import (
        IndexStatusResponse,
        ReferencesResponse,
        ReindexResponse,
        SearchResponse,
        SymbolResponse,
    )

    # Register tools - they access context via get_context()
    @mcp.tool()
    async def mrcis_search_code(
        query: Annotated[
            str,
            Field(
                description="Natural language search query describing the code you're looking for"
            ),
        ],
        limit: Annotated[
            int, Field(description="Maximum number of results to return (1-100)")
        ] = 10,
        repository: Annotated[
            str | None,
            Field(
                description=(
                    "Filter results to a specific repository by name (as configured in config.yaml)"
                )
            ),
        ] = None,
        language: Annotated[
            str | None,
            Field(
                description=(
                    "Filter by programming language, e.g. 'python', 'javascript',"
                    " 'typescript', 'go', 'rust'"
                )
            ),
        ] = None,
        entity_type: Annotated[
            str | None,
            Field(
                description=(
                    "Filter by entity type. Valid values: 'module', 'package', 'class',"
                    " 'interface', 'function', 'method', 'variable', 'constant',"
                    " 'type_alias', 'enum', 'import', 'component', 'table'"
                )
            ),
        ] = None,
    ) -> SearchResponse:
        """Search for code using semantic similarity.

        Returns matching code entities ranked by relevance, including file
        locations, signatures, and docstrings.
        """
        from mrcis.tools.search import search_code

        ctx = get_context()
        return await search_code(
            query=query,
            embedder=ctx.embedder,
            vector_store=ctx.vector_store,
            state_db=ctx.state_db,
            relation_graph=ctx.relation_graph,
            limit=limit,
            repository=repository,
            language=language,
            entity_type=entity_type,
        )

    @mcp.tool()
    async def mrcis_find_symbol(
        qualified_name: Annotated[
            str,
            Field(
                description=(
                    "Fully qualified symbol name using dot notation,"
                    " e.g. 'my_module.MyClass', 'package.module.function_name'"
                )
            ),
        ],
        include_source: Annotated[
            bool,
            Field(description="When true, includes the full source code text of the symbol"),
        ] = False,
    ) -> SymbolResponse:
        """Find a symbol by its fully qualified name.

        Returns symbol details including location, type, signature,
        docstring, visibility, and optionally full source code.
        """
        from mrcis.tools.search import find_symbol

        ctx = get_context()
        return await find_symbol(
            qualified_name=qualified_name,
            state_db=ctx.state_db,
            relation_graph=ctx.relation_graph,
            include_source=include_source,
        )

    @mcp.tool()
    async def mrcis_get_references(
        qualified_name: Annotated[
            str,
            Field(
                description=(
                    "Fully qualified symbol name using dot notation,"
                    " e.g. 'my_module.MyClass', 'package.module.function_name'"
                )
            ),
        ],
        include_outgoing: Annotated[
            bool,
            Field(
                description=(
                    "When true, also includes references FROM this symbol to other symbols"
                    " (calls, imports, type usage). Default only shows incoming references."
                )
            ),
        ] = False,
    ) -> ReferencesResponse:
        """Get all references to a symbol.

        Returns incoming references (other symbols that reference this one),
        and optionally outgoing references, with file locations and context snippets.
        """
        from mrcis.tools.references import get_symbol_references

        ctx = get_context()
        return await get_symbol_references(
            qualified_name=qualified_name,
            state_db=ctx.state_db,
            relation_graph=ctx.relation_graph,
            include_outgoing=include_outgoing,
        )

    @mcp.tool()
    async def mrcis_find_usages(
        symbol_name: Annotated[
            str,
            Field(
                description=(
                    "Symbol name to search for. Can be a simple name (e.g. 'MyClass') or"
                    " fully qualified (e.g. 'my_module.MyClass')."
                    " Simple names search by suffix match."
                )
            ),
        ],
        repository: Annotated[
            str | None,
            Field(
                description=(
                    "Filter results to a specific repository by name (as configured in config.yaml)"
                )
            ),
        ] = None,
    ) -> ReferencesResponse:
        """Find all usages of a symbol by name.

        Locates the symbol definition and returns all references to it,
        including file locations, relation types, and context snippets.
        """
        from mrcis.tools.references import find_usages

        ctx = get_context()
        return await find_usages(
            symbol_name=symbol_name,
            state_db=ctx.state_db,
            relation_graph=ctx.relation_graph,
            repository=repository,
        )

    @mcp.tool()
    async def mrcis_get_index_status(
        repository: Annotated[
            str | None,
            Field(
                description=(
                    "Filter to a specific repository by name."
                    " When omitted, returns status for all configured repositories."
                )
            ),
        ] = None,
    ) -> IndexStatusResponse:
        """Get indexing status for repositories.

        Returns per-repository stats: file counts, entity counts, relation counts,
        pending/failed files, last indexed timestamp, and last indexed commit.
        """
        from mrcis.tools.status import get_index_status

        ctx = get_context()
        return await get_index_status(
            state_db=ctx.state_db,
            repository=repository,
            relation_graph=ctx.relation_graph,
            is_writer=ctx.is_writer,
        )

    @mcp.tool()
    async def mrcis_reindex_repository(
        repository: Annotated[
            str,
            Field(description="Name of the repository to reindex (as configured in config.yaml)"),
        ],
        force: Annotated[
            bool,
            Field(
                description=(
                    "When true, reindexes all files regardless of change detection"
                    " and resets failure counts. When false, only reindexes changed files."
                )
            ),
        ] = False,
    ) -> ReindexResponse:
        """Queue a repository for reindexing.

        Marks files as pending for re-processing by the indexing pipeline.
        Returns the number of files queued.
        """
        from mrcis.tools.status import reindex_repository

        ctx = get_context()
        if not ctx.is_writer:
            return ReindexResponse(
                repository=repository,
                status="error",
                files_queued=0,
                message=(
                    "This server instance is read-only. "
                    "Reindex is only available on the writer instance."
                ),
            )
        return await reindex_repository(
            repository=repository,
            state_db=ctx.state_db,
            indexer=ctx.indexer,
            force=force,
        )

    # Register prompts - cross-repository change safety workflows
    from mrcis.prompts.change_plan import mrcis_change_plan as _change_plan_impl
    from mrcis.prompts.explore import mrcis_explore as _explore_impl
    from mrcis.prompts.impact import mrcis_impact_analysis as _impact_impl
    from mrcis.prompts.safe_change import mrcis_safe_change as _safe_change_impl

    mcp.prompt(
        name="mrcis_explore",
        description=(
            "Explore a symbol: find its definition, map usage patterns across repositories,"
            " and trace cross-repo relationships."
        ),
    )(_explore_impl)

    mcp.prompt(
        name="mrcis_impact_analysis",
        description=(
            "Analyze the cross-repository impact of changing a symbol."
            " Identifies all direct and transitive dependents."
        ),
    )(_impact_impl)

    mcp.prompt(
        name="mrcis_change_plan",
        description=(
            "Create an ordered, file-by-file change plan for modifying a symbol."
            " Classifies dependents by required change type."
        ),
    )(_change_plan_impl)

    mcp.prompt(
        name="mrcis_safe_change",
        description=(
            "Full safe change workflow: explore the symbol, analyze impact,"
            " build a change plan, and define verification steps."
        ),
    )(_safe_change_impl)

    return mcp
