"""Tests for MCP response models."""

from uuid import uuid4

from mrcis.models.responses import (
    IndexStatus,
    ReferenceInfo,
    SearchResponse,
    SearchResult,
    SymbolInfo,
)
from mrcis.models.responses import (
    MCPRepositoryStatus as RepositoryStatus,
)


class TestSearchResult:
    """Test SearchResult model."""

    def test_creates_search_result(self) -> None:
        """Should create SearchResult with all fields."""
        result = SearchResult(
            id=str(uuid4()),
            repository="test-repo",
            file_path="src/main.py",
            qualified_name="my_module.MyClass",
            simple_name="MyClass",
            entity_type="class",
            line_start=10,
            line_end=50,
            score=0.95,
            signature="class MyClass(BaseClass):",
            docstring="A sample class.",
            snippet="class MyClass(BaseClass):\n    pass",
        )

        assert result.repository == "test-repo"
        assert result.score == 0.95

    def test_optional_fields_default_to_none(self) -> None:
        """Optional fields should default to None."""
        result = SearchResult(
            id=str(uuid4()),
            repository="test-repo",
            file_path="src/main.py",
            qualified_name="my_module.my_func",
            simple_name="my_func",
            entity_type="function",
            line_start=5,
            line_end=10,
            score=0.8,
        )

        assert result.signature is None
        assert result.docstring is None
        assert result.snippet is None


class TestSearchResponse:
    """Test SearchResponse model."""

    def test_creates_empty_response(self) -> None:
        """Should create empty search response."""
        response = SearchResponse(
            results=[],
            total_count=0,
            query="test query",
        )

        assert len(response.results) == 0
        assert response.total_count == 0

    def test_creates_response_with_results(self) -> None:
        """Should create response with results."""
        result = SearchResult(
            id=str(uuid4()),
            repository="test-repo",
            file_path="src/main.py",
            qualified_name="my_module.MyClass",
            simple_name="MyClass",
            entity_type="class",
            line_start=10,
            line_end=50,
            score=0.95,
        )

        response = SearchResponse(
            results=[result],
            total_count=1,
            query="MyClass",
        )

        assert len(response.results) == 1
        assert response.total_count == 1


class TestSymbolInfo:
    """Test SymbolInfo model."""

    def test_creates_symbol_info(self) -> None:
        """Should create SymbolInfo with all fields."""
        info = SymbolInfo(
            id=str(uuid4()),
            repository="test-repo",
            file_path="src/main.py",
            qualified_name="my_module.MyClass",
            simple_name="MyClass",
            entity_type="class",
            language="python",
            line_start=10,
            line_end=50,
            signature="class MyClass(BaseClass):",
            docstring="A sample class.",
            source_text="class MyClass(BaseClass):\n    pass",
            visibility="public",
            is_exported=True,
            decorators=["@dataclass"],
            base_classes=["BaseClass"],
        )

        assert info.qualified_name == "my_module.MyClass"
        assert info.base_classes == ["BaseClass"]


class TestReferenceInfo:
    """Test ReferenceInfo model."""

    def test_creates_reference_info(self) -> None:
        """Should create ReferenceInfo with all fields."""
        info = ReferenceInfo(
            file_path="src/other.py",
            repository="test-repo",
            line_number=25,
            relation_type="calls",
            context_snippet="    result = my_func()",
            source_entity="other_module.caller",
        )

        assert info.line_number == 25
        assert info.relation_type == "calls"


class TestIndexStatus:
    """Test IndexStatus model."""

    def test_creates_index_status(self) -> None:
        """Should create IndexStatus with all fields."""
        status = IndexStatus(
            repository="test-repo",
            status="watching",
            file_count=100,
            entity_count=500,
            relation_count=200,
            pending_files=5,
            failed_files=2,
            last_indexed_at="2026-02-02T12:00:00Z",
            last_indexed_commit="abc123",
        )

        assert status.status == "watching"
        assert status.file_count == 100


class TestRepositoryStatus:
    """Test RepositoryStatus model."""

    def test_creates_repository_status(self) -> None:
        """Should create RepositoryStatus."""
        status = RepositoryStatus(
            name="test-repo",
            path="/path/to/repo",
            status="watching",
            file_count=100,
            entity_count=500,
        )

        assert status.name == "test-repo"
