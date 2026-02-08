"""Tests for references MCP tools."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mrcis.models.responses import ReferencesResponse
from mrcis.tools.references import find_usages, get_symbol_references


@pytest.fixture
def mock_state_db() -> AsyncMock:
    """Create mock state database."""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_relation_graph() -> AsyncMock:
    """Create mock relation graph."""
    graph = AsyncMock()
    graph.get_entity_by_qualified_name = AsyncMock(return_value=None)
    graph.get_entity = AsyncMock(return_value=None)
    graph.get_entities_by_suffix = AsyncMock(return_value=[])
    graph.get_incoming_relations = AsyncMock(return_value=[])
    graph.get_outgoing_relations = AsyncMock(return_value=[])
    return graph


class TestGetSymbolReferences:
    """Test get_symbol_references tool."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_symbol(
        self,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
    ) -> None:
        """Should return empty when symbol not found."""
        result = await get_symbol_references(
            qualified_name="nonexistent.Symbol",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert isinstance(result, ReferencesResponse)
        assert len(result.references) == 0
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_returns_incoming_references(
        self,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
    ) -> None:
        """Should return incoming references."""
        # Setup mock entity via RelationGraph
        mock_entity = MagicMock()
        mock_entity.id = str(uuid4())
        mock_entity.qualified_name = "my_module.MyClass"
        mock_relation_graph.get_entity_by_qualified_name.return_value = mock_entity

        # Setup mock relations
        mock_relation = MagicMock()
        mock_relation.source_id = str(uuid4())
        mock_relation.source_qualified_name = "other_module.caller"
        mock_relation.relation_type = "calls"
        mock_relation.line_number = 25
        mock_relation.context_snippet = "my_class = MyClass()"
        mock_relation.source_repository_id = "repo-1"

        # Mock source entity lookup via RelationGraph
        mock_source_entity = MagicMock()
        mock_source_entity.file_id = "file-1"
        mock_relation_graph.get_entity.return_value = mock_source_entity

        # Mock file lookup via StateDB
        mock_file = MagicMock()
        mock_file.path = "src/other.py"
        mock_state_db.get_file.return_value = mock_file

        # Mock repository lookup
        mock_repo = MagicMock()
        mock_repo.name = "test-repo"
        mock_state_db.get_repository.return_value = mock_repo

        mock_relation_graph.get_incoming_relations.return_value = [mock_relation]

        result = await get_symbol_references(
            qualified_name="my_module.MyClass",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.total_count == 1
        assert result.references[0].source_entity == "other_module.caller"
        assert result.references[0].relation_type == "calls"

    @pytest.mark.asyncio
    async def test_get_symbol_references_suffix_fallback(
        self,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
    ) -> None:
        """Should fall back to suffix matching and return references."""
        # Exact match fails
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Suffix match finds one entity
        mock_entity = MagicMock()
        mock_entity.id = str(uuid4())
        mock_entity.qualified_name = "paths.GitignoreFilter"
        mock_relation_graph.get_entities_by_suffix.return_value = [mock_entity]

        # Entity has an incoming relation
        mock_relation = MagicMock()
        mock_relation.source_id = str(uuid4())
        mock_relation.source_qualified_name = "indexer.IndexingService"
        mock_relation.relation_type = "imports"
        mock_relation.line_number = 18
        mock_relation.context_snippet = None
        mock_relation.source_repository_id = "repo-1"
        mock_relation_graph.get_incoming_relations.return_value = [mock_relation]

        # Mock source entity
        mock_source = MagicMock()
        mock_source.file_id = "file-2"
        mock_relation_graph.get_entity.return_value = mock_source

        # Mock file and repo lookups
        mock_file = MagicMock()
        mock_file.path = "src/services/indexer.py"
        mock_state_db.get_file.return_value = mock_file
        mock_repo = MagicMock()
        mock_repo.name = "test-repo"
        mock_state_db.get_repository.return_value = mock_repo

        result = await get_symbol_references(
            qualified_name="mrcis.utils.paths.GitignoreFilter",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.total_count == 1
        assert result.references[0].relation_type == "imports"
        mock_relation_graph.get_entities_by_suffix.assert_called_once_with("GitignoreFilter")

    @pytest.mark.asyncio
    async def test_get_symbol_references_suffix_no_match(
        self,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
    ) -> None:
        """Should return empty when both exact and suffix match fail."""
        mock_relation_graph.get_entity_by_qualified_name.return_value = None
        mock_relation_graph.get_entities_by_suffix.return_value = []

        result = await get_symbol_references(
            qualified_name="mrcis.nonexistent.Symbol",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.total_count == 0


class TestFindUsages:
    """Test find_usages tool."""

    @pytest.mark.asyncio
    async def test_find_usages_returns_empty_for_unknown(
        self,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
    ) -> None:
        """find_usages should return empty for unknown symbols."""
        mock_relation_graph.get_entities_by_suffix.return_value = []

        result = await find_usages(
            symbol_name="MyClass",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert isinstance(result, ReferencesResponse)
        assert result.total_count == 0
        mock_relation_graph.get_entities_by_suffix.assert_called_once_with("MyClass")

    @pytest.mark.asyncio
    async def test_find_usages_delegates_qualified_name(
        self,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
    ) -> None:
        """find_usages with qualified name should use get_symbol_references."""
        result = await find_usages(
            symbol_name="my_module.MyClass",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert isinstance(result, ReferencesResponse)
        # Should have used get_entity_by_qualified_name, not get_entities_by_suffix
        mock_relation_graph.get_entity_by_qualified_name.assert_called_once_with(
            "my_module.MyClass"
        )
