"""Search MCP tools.

Provides semantic code search and symbol lookup functionality.
"""

from typing import TYPE_CHECKING

from mrcis.models.responses import (
    SearchResponse,
    SearchResult,
    SymbolInfo,
    SymbolResponse,
)

if TYPE_CHECKING:
    from mrcis.ports import EmbedderPort, RelationGraphPort, StatePort, VectorStorePort


async def search_code(
    query: str,
    embedder: "EmbedderPort",
    vector_store: "VectorStorePort",
    state_db: "StatePort",
    relation_graph: "RelationGraphPort | None" = None,
    limit: int = 10,
    repository: str | None = None,
    language: str | None = None,
    entity_type: str | None = None,
    min_score: float = 0.0,
) -> SearchResponse:
    """
    Search for code using semantic similarity.

    Args:
        query: Natural language search query.
        embedder: EmbeddingService instance.
        vector_store: VectorStore instance.
        state_db: StateDB instance.
        relation_graph: RelationGraph instance (for snippet lookup).
        limit: Maximum number of results.
        repository: Filter by repository name.
        language: Filter by programming language.
        entity_type: Filter by entity type (class, function, etc.).
        min_score: Minimum similarity score (0-1).

    Returns:
        SearchResponse with matching results.
    """
    # Generate query embedding
    query_vector = await embedder.embed_query(query)

    # Build filters
    filters: dict[str, str] = {}
    if repository:
        # Look up repository ID
        repo = await state_db.get_repository_by_name(repository)
        if repo:
            filters["repository_id"] = str(repo.id)
    if language:
        filters["language"] = language
    if entity_type:
        filters["entity_type"] = entity_type

    # Search vector store
    raw_results = await vector_store.search(
        query_vector=query_vector,
        limit=limit,
        filters=filters if filters else None,
        min_score=min_score,
    )

    # Convert to response format
    results: list[SearchResult] = []
    for r in raw_results:
        # Get repository name
        repo = await state_db.get_repository(r["repository_id"])
        repo_name = repo.name if repo else "unknown"

        # Calculate score from distance, clamping to [0, 1]
        score = max(0.0, min(1.0, 1.0 - r.get("_distance", 0.0)))

        # Look up source_text for snippet
        snippet = None
        if relation_graph:
            entity = await relation_graph.get_entity_by_qualified_name(r["qualified_name"])
            if entity and entity.source_text:
                snippet = entity.source_text[:2000]

        # Fallback: use embedding_text from vector store
        if snippet is None and r.get("embedding_text"):
            snippet = r["embedding_text"][:2000]

        results.append(
            SearchResult(
                id=r["id"],
                repository=repo_name,
                file_path=r["file_path"],
                qualified_name=r["qualified_name"],
                simple_name=r["simple_name"],
                entity_type=r["entity_type"],
                line_start=r["line_start"],
                line_end=r["line_end"],
                score=score,
                signature=r.get("signature"),
                docstring=r.get("docstring"),
                snippet=snippet,
            )
        )

    return SearchResponse(
        results=results,
        total_count=len(results),
        query=query,
        filters_applied=filters if filters else None,
    )


async def find_symbol(
    qualified_name: str,
    state_db: "StatePort",
    relation_graph: "RelationGraphPort",
    include_source: bool = False,
) -> SymbolResponse:
    """
    Find a symbol by its qualified name.

    Args:
        qualified_name: Fully qualified name (e.g., "my_module.MyClass").
        state_db: StateDB instance (for repository lookup).
        relation_graph: RelationGraph instance (for entity lookup).
        include_source: Whether to include source code in response.

    Returns:
        SymbolResponse with symbol details if found.
    """
    # Look up entity in RelationGraph
    entity = await relation_graph.get_entity_by_qualified_name(qualified_name)

    # Fallback: try suffix matching when exact match fails for dotted names
    if entity is None and "." in qualified_name:
        suffix = qualified_name.rsplit(".", 1)[-1]
        candidates = await relation_graph.get_entities_by_suffix(suffix)
        if len(candidates) == 1:
            entity = candidates[0]
        elif candidates:
            for c in candidates:
                if c.qualified_name.endswith(qualified_name):
                    entity = c
                    break
            if entity is None:
                entity = candidates[0]

    if entity is None:
        return SymbolResponse(
            found=False,
            message=f"Symbol not found: {qualified_name}",
        )

    # Get repository name
    repo = await state_db.get_repository(entity.repository_id)
    repo_name = repo.name if repo else "unknown"

    # Get file path from StateDB
    file_info = await state_db.get_file(entity.file_id)
    file_path = file_info.path if file_info else "unknown"

    # Extract type-specific fields from entity attributes
    decorators = getattr(entity, "decorators", None)
    base_classes = getattr(entity, "base_classes", None)
    return_type = getattr(entity, "return_type", None)
    parameters = getattr(entity, "parameters", None)
    signature = getattr(entity, "signature", None)
    simple_name = getattr(entity, "simple_name", entity.name)

    # Parse return_type from signature if not set directly
    if return_type is None and signature and " -> " in signature:
        return_type = signature.split(" -> ", 1)[1].strip()

    # Build symbol info
    symbol = SymbolInfo(
        id=str(entity.id),
        repository=repo_name,
        file_path=file_path,
        qualified_name=entity.qualified_name,
        simple_name=simple_name,
        entity_type=entity.entity_type.value,
        language=entity.language,
        line_start=entity.line_start,
        line_end=entity.line_end,
        signature=signature,
        docstring=entity.docstring,
        source_text=entity.source_text if include_source else None,
        visibility=getattr(entity, "visibility", "public"),
        is_exported=getattr(entity, "is_exported", False),
        decorators=decorators,
        base_classes=base_classes,
        return_type=return_type,
        parameters=parameters,
    )

    return SymbolResponse(found=True, symbol=symbol)
