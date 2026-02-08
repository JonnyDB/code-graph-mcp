"""Tests for search MCP tools."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mrcis.models.entities import EntityType
from mrcis.models.responses import SearchResponse, SymbolResponse
from mrcis.tools.search import find_symbol, search_code


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Create mock embedder."""
    embedder = AsyncMock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
    return embedder


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_state_db() -> AsyncMock:
    """Create mock state database."""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_relation_graph() -> AsyncMock:
    """Create mock relation graph for entity lookups."""
    graph = AsyncMock()
    graph.get_entity_by_qualified_name = AsyncMock(return_value=None)
    graph.get_entities_by_suffix = AsyncMock(return_value=[])
    return graph


class TestSearchCode:
    """Test search_code tool."""

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_no_results(
        self,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_state_db: AsyncMock,
    ) -> None:
        """Should return empty results when nothing matches."""
        result = await search_code(
            query="nonexistent",
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            state_db=mock_state_db,
        )

        assert isinstance(result, SearchResponse)
        assert len(result.results) == 0
        assert result.total_count == 0
        assert result.query == "nonexistent"

    @pytest.mark.asyncio
    async def test_search_embeds_query(
        self,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_state_db: AsyncMock,
    ) -> None:
        """Should embed the query text."""
        await search_code(
            query="find classes",
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            state_db=mock_state_db,
        )

        mock_embedder.embed_query.assert_called_once_with("find classes")

    @pytest.mark.asyncio
    async def test_search_applies_filters(
        self,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_state_db: AsyncMock,
    ) -> None:
        """Should apply repository and language filters."""
        # Setup mock to return repository with string ID
        mock_repo = MagicMock()
        mock_repo.id = "repo-123"
        mock_state_db.get_repository_by_name = AsyncMock(return_value=mock_repo)

        await search_code(
            query="test",
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            state_db=mock_state_db,
            repository="test-repo",
            language="python",
        )

        # Check that filters were passed to vector search
        call_args = mock_vector_store.search.call_args
        filters = call_args.kwargs.get("filters", {})
        assert "repository_id" in filters or "language" in filters

    @pytest.mark.asyncio
    async def test_search_returns_results(
        self,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_state_db: AsyncMock,
    ) -> None:
        """Should return search results."""
        # Setup mock to return results
        mock_vector_store.search.return_value = [
            {
                "id": str(uuid4()),
                "repository_id": "repo-1",
                "file_path": "src/main.py",
                "qualified_name": "my_module.MyClass",
                "simple_name": "MyClass",
                "entity_type": "class",
                "line_start": 10,
                "line_end": 50,
                "_distance": 0.1,
                "signature": "class MyClass:",
                "docstring": "A class",
            }
        ]

        # Mock repository lookup
        mock_repo = MagicMock()
        mock_repo.name = "test-repo"
        mock_state_db.get_repository.return_value = mock_repo

        result = await search_code(
            query="MyClass",
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            state_db=mock_state_db,
        )

        assert len(result.results) == 1
        assert result.results[0].simple_name == "MyClass"
        assert result.results[0].score > 0


class TestFindSymbol:
    """Test find_symbol tool."""

    @pytest.mark.asyncio
    async def test_find_symbol_returns_none_on_no_match(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """Should return not found when symbol doesn't exist."""
        result = await find_symbol(
            qualified_name="nonexistent.Symbol",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert isinstance(result, SymbolResponse)
        assert result.found is False
        assert result.symbol is None

    @pytest.mark.asyncio
    async def test_find_symbol_suffix_fallback(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """Should fall back to suffix matching when exact match fails."""
        # Exact match returns None
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Suffix match returns one candidate
        mock_entity = MagicMock()
        mock_entity.id = str(uuid4())
        mock_entity.qualified_name = "paths.GitignoreFilter"
        mock_entity.simple_name = "GitignoreFilter"
        mock_entity.entity_type = MagicMock()
        mock_entity.entity_type.value = "class"
        mock_entity.language = "python"
        mock_entity.line_start = 10
        mock_entity.line_end = 50
        mock_entity.signature = None
        mock_entity.docstring = None
        mock_entity.visibility = "public"
        mock_entity.is_exported = False
        mock_entity.file_id = "file-1"
        mock_entity.repository_id = "repo-1"
        mock_entity.source_text = None
        mock_entity.decorators = None
        mock_entity.base_classes = None
        mock_entity.return_type = None
        mock_entity.parameters = None
        mock_relation_graph.get_entities_by_suffix.return_value = [mock_entity]

        mock_repo = MagicMock()
        mock_repo.name = "test-repo"
        mock_state_db.get_repository.return_value = mock_repo

        mock_file = MagicMock()
        mock_file.path = "src/utils/paths.py"
        mock_state_db.get_file.return_value = mock_file

        result = await find_symbol(
            qualified_name="mrcis.utils.paths.GitignoreFilter",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.found is True
        assert result.symbol is not None
        assert result.symbol.qualified_name == "paths.GitignoreFilter"
        mock_relation_graph.get_entities_by_suffix.assert_called_once_with("GitignoreFilter")

    @pytest.mark.asyncio
    async def test_find_symbol_suffix_fallback_no_match(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """Should return not found when both exact and suffix match fail."""
        mock_relation_graph.get_entity_by_qualified_name.return_value = None
        mock_relation_graph.get_entities_by_suffix.return_value = []

        result = await find_symbol(
            qualified_name="mrcis.nonexistent.Symbol",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.found is False

    @pytest.mark.asyncio
    async def test_find_symbol_by_qualified_name(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """Should find symbol by qualified name via RelationGraph."""
        # Setup mock entity (RelationGraph Entity dataclass)
        mock_entity = MagicMock()
        mock_entity.id = str(uuid4())
        mock_entity.qualified_name = "my_module.MyClass"
        mock_entity.simple_name = "MyClass"
        mock_entity.entity_type = MagicMock()
        mock_entity.entity_type.value = "class"
        mock_entity.language = "python"
        mock_entity.line_start = 10
        mock_entity.line_end = 50
        mock_entity.signature = "class MyClass:"
        mock_entity.docstring = "A class"
        mock_entity.visibility = "public"
        mock_entity.is_exported = True
        mock_entity.file_id = "file-1"
        mock_entity.repository_id = "repo-1"
        mock_entity.source_text = None
        mock_entity.decorators = None
        mock_entity.base_classes = None
        mock_entity.return_type = None
        mock_entity.parameters = None

        mock_relation_graph.get_entity_by_qualified_name.return_value = mock_entity

        mock_repo = MagicMock()
        mock_repo.name = "test-repo"
        mock_state_db.get_repository.return_value = mock_repo

        mock_file = MagicMock()
        mock_file.path = "src/main.py"
        mock_state_db.get_file.return_value = mock_file

        result = await find_symbol(
            qualified_name="my_module.MyClass",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.found is True
        assert result.symbol is not None
        assert result.symbol.qualified_name == "my_module.MyClass"
        mock_relation_graph.get_entity_by_qualified_name.assert_called_once_with(
            "my_module.MyClass"
        )


class TestSearchCodeSnippet:
    """Test that search_code populates snippet field."""

    @pytest.mark.asyncio
    async def test_search_populates_snippet_from_entity(
        self,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_state_db: AsyncMock,
        mock_relation_graph: AsyncMock,
    ) -> None:
        """Search results should include snippet from entity source_text."""
        repo_id = str(uuid4())

        mock_vector_store.search.return_value = [
            {
                "id": "vec-1",
                "repository_id": repo_id,
                "file_path": "test.py",
                "qualified_name": "module.my_func",
                "simple_name": "my_func",
                "entity_type": "function",
                "line_start": 1,
                "line_end": 5,
                "_distance": 0.2,
                "signature": "def my_func()",
                "docstring": None,
            }
        ]

        repo = MagicMock()
        repo.name = "test-repo"
        mock_state_db.get_repository.return_value = repo

        entity = MagicMock()
        entity.source_text = "def my_func():\n    return 42"
        mock_relation_graph.get_entity_by_qualified_name.return_value = entity

        result = await search_code(
            query="my function",
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.results[0].snippet == "def my_func():\n    return 42"

    @pytest.mark.asyncio
    async def test_search_snippet_null_without_relation_graph(
        self,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_state_db: AsyncMock,
    ) -> None:
        """Without relation_graph, snippet should be None."""
        repo_id = str(uuid4())
        mock_vector_store.search.return_value = [
            {
                "id": "vec-1",
                "repository_id": repo_id,
                "file_path": "test.py",
                "qualified_name": "module.my_func",
                "simple_name": "my_func",
                "entity_type": "function",
                "line_start": 1,
                "line_end": 5,
                "_distance": 0.2,
                "signature": None,
                "docstring": None,
            }
        ]
        repo = MagicMock()
        repo.name = "test-repo"
        mock_state_db.get_repository.return_value = repo

        result = await search_code(
            query="my function",
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            state_db=mock_state_db,
        )

        assert result.results[0].snippet is None


class TestFindSymbolDetails:
    """Test that find_symbol populates type-specific fields."""

    @pytest.mark.asyncio
    async def test_find_symbol_includes_decorators(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """find_symbol should include decorators from entity."""

        entity = MagicMock()
        entity.id = str(uuid4())
        entity.repository_id = str(uuid4())
        entity.file_id = str(uuid4())
        entity.qualified_name = "module.MyClass"
        entity.simple_name = "MyClass"
        entity.entity_type = EntityType.CLASS
        entity.language = "python"
        entity.line_start = 1
        entity.line_end = 10
        entity.signature = None
        entity.docstring = None
        entity.source_text = None
        entity.visibility = "public"
        entity.is_exported = False
        entity.decorators = ["@dataclass"]
        entity.base_classes = ["BaseModel"]
        entity.return_type = None
        entity.parameters = None
        mock_relation_graph.get_entity_by_qualified_name.return_value = entity

        repo = MagicMock()
        repo.name = "test-repo"
        mock_state_db.get_repository.return_value = repo

        file_info = MagicMock()
        file_info.path = "test.py"
        mock_state_db.get_file.return_value = file_info

        result = await find_symbol(
            qualified_name="module.MyClass",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.found is True
        assert result.symbol.decorators == ["@dataclass"]
        assert result.symbol.base_classes == ["BaseModel"]

    @pytest.mark.asyncio
    async def test_find_symbol_parses_return_type_from_signature(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """find_symbol should parse return_type from signature."""

        entity = MagicMock()
        entity.id = str(uuid4())
        entity.repository_id = str(uuid4())
        entity.file_id = str(uuid4())
        entity.qualified_name = "module.my_func"
        entity.simple_name = "my_func"
        entity.entity_type = EntityType.FUNCTION
        entity.language = "python"
        entity.line_start = 1
        entity.line_end = 3
        entity.signature = "def my_func(x: int) -> str"
        entity.docstring = None
        entity.source_text = None
        entity.visibility = "public"
        entity.is_exported = False
        entity.decorators = None
        entity.base_classes = None
        entity.return_type = None
        entity.parameters = None
        mock_relation_graph.get_entity_by_qualified_name.return_value = entity

        repo = MagicMock()
        repo.name = "test-repo"
        mock_state_db.get_repository.return_value = repo

        file_info = MagicMock()
        file_info.path = "test.py"
        mock_state_db.get_file.return_value = file_info

        result = await find_symbol(
            qualified_name="module.my_func",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.symbol.return_type == "str"

    @pytest.mark.asyncio
    async def test_find_symbol_no_return_type_without_arrow(
        self, mock_state_db: AsyncMock, mock_relation_graph: AsyncMock
    ) -> None:
        """find_symbol should not set return_type if no arrow in signature."""

        entity = MagicMock()
        entity.id = str(uuid4())
        entity.repository_id = str(uuid4())
        entity.file_id = str(uuid4())
        entity.qualified_name = "module.my_func"
        entity.simple_name = "my_func"
        entity.entity_type = EntityType.FUNCTION
        entity.language = "python"
        entity.line_start = 1
        entity.line_end = 3
        entity.signature = "def my_func(x: int)"
        entity.docstring = None
        entity.source_text = None
        entity.visibility = "public"
        entity.is_exported = False
        entity.decorators = None
        entity.base_classes = None
        entity.return_type = None
        entity.parameters = None
        mock_relation_graph.get_entity_by_qualified_name.return_value = entity

        repo = MagicMock()
        repo.name = "test-repo"
        mock_state_db.get_repository.return_value = repo

        file_info = MagicMock()
        file_info.path = "test.py"
        mock_state_db.get_file.return_value = file_info

        result = await find_symbol(
            qualified_name="module.my_func",
            state_db=mock_state_db,
            relation_graph=mock_relation_graph,
        )

        assert result.symbol.return_type is None
