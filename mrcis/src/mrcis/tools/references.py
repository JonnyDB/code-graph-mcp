"""Reference MCP tools.

Provides symbol reference lookup functionality.
"""

from typing import TYPE_CHECKING

from mrcis.models.responses import ReferenceInfo, ReferencesResponse

if TYPE_CHECKING:
    from mrcis.ports import RelationGraphPort, StatePort


async def get_symbol_references(
    qualified_name: str,
    state_db: "StatePort",
    relation_graph: "RelationGraphPort",
    include_outgoing: bool = False,
) -> ReferencesResponse:
    """
    Get all references to a symbol.

    Args:
        qualified_name: Fully qualified name of the symbol.
        state_db: StateDB instance.
        relation_graph: RelationGraph instance.
        include_outgoing: Also include references FROM this symbol.

    Returns:
        ReferencesResponse with all references.
    """
    # Look up the entity in RelationGraph
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
        return ReferencesResponse(
            symbol=qualified_name,
            references=[],
            total_count=0,
        )

    references: list[ReferenceInfo] = []

    # Get incoming references (other symbols referencing this one)
    incoming = await relation_graph.get_incoming_relations(entity.id)
    for rel in incoming:
        # Get source entity's file info from RelationGraph + StateDB
        source_entity = await relation_graph.get_entity(rel.source_id)
        if source_entity:
            file_info = await state_db.get_file(source_entity.file_id)
            repo = await state_db.get_repository(rel.source_repository_id)

            references.append(
                ReferenceInfo(
                    file_path=file_info.path if file_info else "unknown",
                    repository=repo.name if repo else "unknown",
                    line_number=rel.line_number or 0,
                    relation_type=rel.relation_type,
                    context_snippet=rel.context_snippet,
                    source_entity=rel.source_qualified_name,
                )
            )

    outgoing_count = 0
    if include_outgoing:
        # Get outgoing references (symbols this one references)
        outgoing = await relation_graph.get_outgoing_relations(entity.id)
        outgoing_count = len(outgoing)

        for rel in outgoing:
            target_entity = await relation_graph.get_entity(rel.target_id)
            if target_entity:
                file_info = await state_db.get_file(target_entity.file_id)
                repo = await state_db.get_repository(rel.target_repository_id)

                references.append(
                    ReferenceInfo(
                        file_path=file_info.path if file_info else "unknown",
                        repository=repo.name if repo else "unknown",
                        line_number=rel.line_number or 0,
                        relation_type=rel.relation_type,
                        context_snippet=rel.context_snippet,
                        source_entity=rel.target_qualified_name,
                    )
                )

    return ReferencesResponse(
        symbol=qualified_name,
        references=references,
        total_count=len(references),
        incoming=len(incoming),
        outgoing=outgoing_count,
    )


async def find_usages(
    symbol_name: str,
    state_db: "StatePort",
    relation_graph: "RelationGraphPort",
    repository: str | None = None,
) -> ReferencesResponse:
    """
    Find all usages of a symbol by name.

    This is a convenience wrapper that searches by simple name
    and then gets references.

    Args:
        symbol_name: Simple or qualified name of the symbol.
        state_db: StateDB instance.
        relation_graph: RelationGraph instance.
        repository: Optional repository to search in.

    Returns:
        ReferencesResponse with all usages.
    """
    # If it looks like a qualified name, use it directly
    if "." in symbol_name:
        return await get_symbol_references(
            qualified_name=symbol_name,
            state_db=state_db,
            relation_graph=relation_graph,
            include_outgoing=False,
        )

    # Search for entities by simple name via RelationGraph
    entities = await relation_graph.get_entities_by_suffix(symbol_name)

    # Filter by repository if specified
    if repository and entities:
        repo = await state_db.get_repository_by_name(repository)
        if repo:
            entities = [e for e in entities if e.repository_id == repo.id]

    if not entities:
        return ReferencesResponse(
            symbol=symbol_name,
            references=[],
            total_count=0,
        )

    # If multiple matches, use the first one (shortest qualified name)
    entity = entities[0]
    return await get_symbol_references(
        qualified_name=entity.qualified_name,
        state_db=state_db,
        relation_graph=relation_graph,
        include_outgoing=False,
    )
