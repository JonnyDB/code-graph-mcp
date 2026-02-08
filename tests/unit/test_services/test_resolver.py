"""Tests for ReferenceResolver service."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mrcis.models.entities import EntityType
from mrcis.models.relations import PendingReference, RelationType
from mrcis.services.resolver import ReferenceResolver, ResolutionResult


@pytest.fixture
def mock_relation_graph() -> AsyncMock:
    """Create mock relation graph."""
    graph = AsyncMock()
    graph.get_pending_references = AsyncMock(return_value=[])
    graph.get_entity_by_qualified_name = AsyncMock(return_value=None)
    graph.get_entities_by_suffix = AsyncMock(return_value=[])
    graph.resolve_reference = AsyncMock()
    graph.mark_reference_unresolved = AsyncMock()
    return graph


class TestResolutionResult:
    """Test ResolutionResult dataclass."""

    def test_default_values(self) -> None:
        """Should have zero default counts."""
        result = ResolutionResult()
        assert result.resolved == 0
        assert result.unresolved == 0
        assert result.still_pending == 0


class TestReferenceResolver:
    """Test ReferenceResolver service."""

    def test_creates_with_config(self, mock_relation_graph: AsyncMock) -> None:
        """Should create resolver with config."""
        resolver = ReferenceResolver(
            relation_graph=mock_relation_graph,
            interval_seconds=60,
            max_attempts=3,
        )

        assert resolver.graph == mock_relation_graph
        assert resolver.interval == 60
        assert resolver.max_attempts == 3

    @pytest.mark.asyncio
    async def test_stop_sets_shutdown_event(self, mock_relation_graph: AsyncMock) -> None:
        """stop should set shutdown event."""
        resolver = ReferenceResolver(mock_relation_graph)

        await resolver.stop()

        assert resolver._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_resolve_batch_no_pending(self, mock_relation_graph: AsyncMock) -> None:
        """resolve_batch with no pending refs should return zeros."""
        resolver = ReferenceResolver(mock_relation_graph)

        result = await resolver.resolve_batch()

        assert result.resolved == 0
        assert result.unresolved == 0
        assert result.still_pending == 0

    @pytest.mark.asyncio
    async def test_resolve_batch_resolves_exact_match(self, mock_relation_graph: AsyncMock) -> None:
        """Should resolve references with exact match."""
        # Setup pending reference
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="my_module.MyClass",
            source_repository_id=uuid4(),
            target_qualified_name="base_module.BaseClass",
            relation_type=RelationType.EXTENDS,
            line_number=10,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]

        # Setup target entity
        target = MagicMock()
        target.id = str(uuid4())
        target.qualified_name = "base_module.BaseClass"
        target.repository_id = str(uuid4())
        mock_relation_graph.get_entity_by_qualified_name.return_value = target

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(pending.id, target.id)

    @pytest.mark.asyncio
    async def test_resolve_batch_increments_attempts_on_no_match(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """Should increment attempts when no match found."""
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="my_module.MyClass",
            source_repository_id=uuid4(),
            target_qualified_name="unknown.UnknownClass",
            relation_type=RelationType.EXTENDS,
            attempts=0,
            line_number=10,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None
        mock_relation_graph.get_entities_by_suffix.return_value = []

        resolver = ReferenceResolver(mock_relation_graph, max_attempts=3)
        result = await resolver.resolve_batch()

        assert result.still_pending == 1
        mock_relation_graph.mark_reference_unresolved.assert_called_once_with(
            pending.id, max_attempts=3
        )

    @pytest.mark.asyncio
    async def test_resolve_batch_marks_unresolved_after_max_attempts(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """Should mark unresolved after max attempts."""
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="my_module.MyClass",
            source_repository_id=uuid4(),
            target_qualified_name="unknown.UnknownClass",
            relation_type=RelationType.EXTENDS,
            attempts=2,  # Already at max - 1
            line_number=10,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None
        mock_relation_graph.get_entities_by_suffix.return_value = []

        resolver = ReferenceResolver(mock_relation_graph, max_attempts=3)
        result = await resolver.resolve_batch()

        assert result.unresolved == 1
        mock_relation_graph.mark_reference_unresolved.assert_called_once_with(
            pending.id, max_attempts=3
        )

    @pytest.mark.asyncio
    async def test_resolve_batch_resolves_dotted_name_via_suffix(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """Should resolve dotted target names via suffix matching."""
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="indexer.IndexingService",
            source_repository_id=uuid4(),
            target_qualified_name="mrcis.utils.paths.GitignoreFilter",
            relation_type=RelationType.IMPORTS,
            line_number=18,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]

        # Exact match fails
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Suffix match finds one candidate
        target = MagicMock()
        target.id = str(uuid4())
        target.qualified_name = "paths.GitignoreFilter"
        target.repository_id = str(uuid4())
        mock_relation_graph.get_entities_by_suffix.return_value = [target]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        assert result.resolved == 1
        mock_relation_graph.get_entities_by_suffix.assert_called_once_with("GitignoreFilter")
        mock_relation_graph.resolve_reference.assert_called_once_with(pending.id, target.id)

    @pytest.mark.asyncio
    async def test_resolve_batch_disambiguates_dotted_name(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """Should disambiguate when dotted name suffix matches multiple entities."""
        repo_id = uuid4()
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="my_module.MyClass",
            source_repository_id=repo_id,
            target_qualified_name="pkg.utils.Helper",
            relation_type=RelationType.IMPORTS,
            line_number=5,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Suffix match returns multiple candidates - disambiguation picks shorter qualified name
        candidate1 = MagicMock()
        candidate1.id = str(uuid4())
        candidate1.qualified_name = "other.Helper"
        candidate1.repository_id = str(uuid4())
        candidate1.entity_type = EntityType.CLASS
        candidate2 = MagicMock()
        candidate2.id = str(uuid4())
        candidate2.qualified_name = "some.other.pkg.Helper"
        candidate2.repository_id = str(uuid4())
        candidate2.entity_type = EntityType.CLASS
        mock_relation_graph.get_entities_by_suffix.return_value = [candidate1, candidate2]

        resolver = ReferenceResolver(mock_relation_graph, max_attempts=3)
        result = await resolver.resolve_batch()

        # Disambiguation should resolve to candidate1 (shorter qualified name)
        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(pending.id, candidate1.id)

    @pytest.mark.asyncio
    async def test_resolve_batch_simple_name_still_uses_suffix(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """Should still resolve simple names (no dots) via suffix matching."""
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="my_module.MyClass",
            source_repository_id=uuid4(),
            target_qualified_name="BaseClass",
            relation_type=RelationType.EXTENDS,
            line_number=10,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        target = MagicMock()
        target.id = str(uuid4())
        target.qualified_name = "base.BaseClass"
        target.repository_id = str(uuid4())
        mock_relation_graph.get_entities_by_suffix.return_value = [target]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        assert result.resolved == 1
        mock_relation_graph.get_entities_by_suffix.assert_called_once_with("BaseClass")
        mock_relation_graph.resolve_reference.assert_called_once_with(pending.id, target.id)


class TestDisambiguation:
    """Tests for the _disambiguate method."""

    @pytest.mark.asyncio
    async def test_disambiguate_same_repository(self, mock_relation_graph: AsyncMock) -> None:
        """When multiple candidates, prefer same-repo candidate."""
        repo_id = uuid4()
        other_repo_id = str(uuid4())

        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="my_module.MyClass",
            source_repository_id=repo_id,
            target_qualified_name="pkg.Helper",
            relation_type=RelationType.IMPORTS,
            line_number=5,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Two candidates: one in same repo, one in different repo
        # Use pending.source_repository_id to match the UUID object from Pydantic
        same_repo_candidate = MagicMock()
        same_repo_candidate.id = str(uuid4())
        same_repo_candidate.qualified_name = "utils.Helper"
        same_repo_candidate.repository_id = pending.source_repository_id
        same_repo_candidate.entity_type = EntityType.CLASS

        other_repo_candidate = MagicMock()
        other_repo_candidate.id = str(uuid4())
        other_repo_candidate.qualified_name = "other.Helper"
        other_repo_candidate.repository_id = other_repo_id
        other_repo_candidate.entity_type = EntityType.CLASS

        mock_relation_graph.get_entities_by_suffix.return_value = [
            other_repo_candidate,
            same_repo_candidate,
        ]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(
            pending.id, same_repo_candidate.id
        )

    @pytest.mark.asyncio
    async def test_disambiguate_longest_suffix_match(self, mock_relation_graph: AsyncMock) -> None:
        """When multiple candidates, prefer the one matching more of the pattern."""
        repo_id = uuid4()

        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="app.Service",
            source_repository_id=repo_id,
            target_qualified_name="module.ClassName",
            relation_type=RelationType.IMPORTS,
            line_number=3,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Both candidates are in different repos so same-repo filter doesn't narrow
        other_repo1 = str(uuid4())
        other_repo2 = str(uuid4())

        # This candidate's qualified_name ends with the full pattern "module.ClassName"
        better_match = MagicMock()
        better_match.id = str(uuid4())
        better_match.qualified_name = "pkg.module.ClassName"
        better_match.repository_id = other_repo1
        better_match.entity_type = EntityType.CLASS

        # This candidate only matches the suffix "ClassName"
        weaker_match = MagicMock()
        weaker_match.id = str(uuid4())
        weaker_match.qualified_name = "other.ClassName"
        weaker_match.repository_id = other_repo2
        weaker_match.entity_type = EntityType.CLASS

        mock_relation_graph.get_entities_by_suffix.return_value = [
            weaker_match,
            better_match,
        ]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(pending.id, better_match.id)

    @pytest.mark.asyncio
    async def test_disambiguate_entity_type_for_extends(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """For EXTENDS relation, prefer class entities over function entities."""
        repo_id = uuid4()
        other_repo = str(uuid4())

        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="my_module.Child",
            source_repository_id=repo_id,
            target_qualified_name="Base",
            relation_type=RelationType.EXTENDS,
            line_number=10,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Two candidates with same name length, both in different repos
        class_candidate = MagicMock()
        class_candidate.id = str(uuid4())
        class_candidate.qualified_name = "mod_a.Base"
        class_candidate.repository_id = other_repo
        class_candidate.entity_type = EntityType.CLASS

        func_candidate = MagicMock()
        func_candidate.id = str(uuid4())
        func_candidate.qualified_name = "mod_b.Base"
        func_candidate.repository_id = str(uuid4())
        func_candidate.entity_type = EntityType.FUNCTION

        mock_relation_graph.get_entities_by_suffix.return_value = [
            func_candidate,
            class_candidate,
        ]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(
            pending.id, class_candidate.id
        )

    @pytest.mark.asyncio
    async def test_disambiguate_shortest_qualified_name_fallback(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """When all filters produce a tie, pick the shortest qualified name."""
        repo_id = uuid4()

        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="my_module.MyClass",
            source_repository_id=repo_id,
            target_qualified_name="Helper",
            relation_type=RelationType.IMPORTS,
            line_number=5,
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Both in same repo, same entity type, neither matches full pattern suffix
        # Use pending.source_repository_id to match the UUID object from Pydantic
        shorter = MagicMock()
        shorter.id = str(uuid4())
        shorter.qualified_name = "utils.Helper"
        shorter.repository_id = pending.source_repository_id
        shorter.entity_type = EntityType.CLASS

        longer = MagicMock()
        longer.id = str(uuid4())
        longer.qualified_name = "deep.nested.utils.Helper"
        longer.repository_id = pending.source_repository_id
        longer.entity_type = EntityType.CLASS

        mock_relation_graph.get_entities_by_suffix.return_value = [longer, shorter]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(pending.id, shorter.id)


class TestReceiverDisambiguation:
    """Test receiver-aware disambiguation."""

    @pytest.mark.asyncio
    async def test_prefers_matching_receiver_type(self, mock_relation_graph: AsyncMock) -> None:
        """When receiver name matches type, prefer that entity."""
        # Setup: Two entities with method "get", receiver suggests ChartWriter
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="app.main.process",
            source_repository_id=uuid4(),
            target_qualified_name="get",
            relation_type=RelationType.CALLS,
            line_number=42,
            receiver_expr="chart_writer",  # Suggests ChartWriter type
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Two candidates: ChartWriter.get() and CacheManager.get()
        chart_writer_get = MagicMock()
        chart_writer_get.id = str(uuid4())
        chart_writer_get.qualified_name = "charts.ChartWriter.get"
        chart_writer_get.repository_id = str(uuid4())
        chart_writer_get.entity_type = EntityType.METHOD

        cache_manager_get = MagicMock()
        cache_manager_get.id = str(uuid4())
        cache_manager_get.qualified_name = "cache.CacheManager.get"
        cache_manager_get.repository_id = str(uuid4())
        cache_manager_get.entity_type = EntityType.METHOD

        mock_relation_graph.get_entities_by_suffix.return_value = [
            cache_manager_get,
            chart_writer_get,
        ]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        # Should resolve to ChartWriter.get because receiver_expr matches
        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(
            pending.id, chart_writer_get.id
        )

    @pytest.mark.asyncio
    async def test_no_receiver_uses_existing_logic(self, mock_relation_graph: AsyncMock) -> None:
        """Without receiver, fall back to existing resolution."""
        # Pending ref with receiver_expr=None should work as before
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="app.main.process",
            source_repository_id=uuid4(),
            target_qualified_name="get",
            relation_type=RelationType.CALLS,
            line_number=42,
            receiver_expr=None,  # No receiver context
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Two candidates with different lengths - should pick shorter
        shorter_candidate = MagicMock()
        shorter_candidate.id = str(uuid4())
        shorter_candidate.qualified_name = "utils.get"
        shorter_candidate.repository_id = str(uuid4())
        shorter_candidate.entity_type = EntityType.FUNCTION

        longer_candidate = MagicMock()
        longer_candidate.id = str(uuid4())
        longer_candidate.qualified_name = "deep.nested.utils.get"
        longer_candidate.repository_id = str(uuid4())
        longer_candidate.entity_type = EntityType.FUNCTION

        mock_relation_graph.get_entities_by_suffix.return_value = [
            longer_candidate,
            shorter_candidate,
        ]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        # Should use existing logic (shortest qualified name)
        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(
            pending.id, shorter_candidate.id
        )

    @pytest.mark.asyncio
    async def test_receiver_mismatch_with_multiple_candidates(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """When receiver doesn't match any candidate, filter them all out."""
        # Two entities: ChartWriter.get() and FileWriter.get()
        # Pending ref: "get()" with receiver_expr="database"
        # Expected: No match, remains unresolved (better than false positive)
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="app.main.process",
            source_repository_id=uuid4(),
            target_qualified_name="get",
            relation_type=RelationType.CALLS,
            line_number=42,
            attempts=0,
            receiver_expr="database",  # Doesn't match any Writer classes
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Two candidates, neither matches "database"
        chart_writer_get = MagicMock()
        chart_writer_get.id = str(uuid4())
        chart_writer_get.qualified_name = "charts.ChartWriter.get"
        chart_writer_get.repository_id = str(uuid4())
        chart_writer_get.entity_type = EntityType.METHOD

        file_writer_get = MagicMock()
        file_writer_get.id = str(uuid4())
        file_writer_get.qualified_name = "files.FileWriter.get"
        file_writer_get.repository_id = str(uuid4())
        file_writer_get.entity_type = EntityType.METHOD

        mock_relation_graph.get_entities_by_suffix.return_value = [
            chart_writer_get,
            file_writer_get,
        ]

        resolver = ReferenceResolver(mock_relation_graph, max_attempts=3)
        result = await resolver.resolve_batch()

        # Should remain unresolved (no candidates match receiver)
        assert result.resolved == 0
        assert result.still_pending == 1
        mock_relation_graph.mark_reference_unresolved.assert_called_once_with(
            pending.id, max_attempts=3
        )

    @pytest.mark.asyncio
    async def test_receiver_dotted_expression(self, mock_relation_graph: AsyncMock) -> None:
        """Handle dotted receiver expressions like ctx.redis."""
        # receiver_expr="ctx.redis" should match Redis-related entities
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="app.main.process",
            source_repository_id=uuid4(),
            target_qualified_name="get",
            relation_type=RelationType.CALLS,
            line_number=42,
            receiver_expr="ctx.redis",  # Should extract "redis" → "Redis"
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Two candidates: RedisCache.get() and FileCache.get()
        redis_get = MagicMock()
        redis_get.id = str(uuid4())
        redis_get.qualified_name = "cache.RedisCache.get"
        redis_get.repository_id = str(uuid4())
        redis_get.entity_type = EntityType.METHOD

        file_get = MagicMock()
        file_get.id = str(uuid4())
        file_get.qualified_name = "cache.FileCache.get"
        file_get.repository_id = str(uuid4())
        file_get.entity_type = EntityType.METHOD

        mock_relation_graph.get_entities_by_suffix.return_value = [file_get, redis_get]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        # Should prefer RedisCache.get because "redis" matches
        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(pending.id, redis_get.id)

    @pytest.mark.asyncio
    async def test_receiver_only_filters_when_multiple_candidates(
        self, mock_relation_graph: AsyncMock
    ) -> None:
        """Receiver filtering only applies when there are multiple candidates."""
        # When only one candidate exists, resolve it regardless of receiver match
        pending = PendingReference(
            id=uuid4(),
            source_entity_id=uuid4(),
            source_qualified_name="app.main.process",
            source_repository_id=uuid4(),
            target_qualified_name="get",
            relation_type=RelationType.CALLS,
            line_number=42,
            receiver_expr="writer",  # Doesn't match ChartHelper
        )
        mock_relation_graph.get_pending_references.return_value = [pending]
        mock_relation_graph.get_entity_by_qualified_name.return_value = None

        # Only one candidate
        only_candidate = MagicMock()
        only_candidate.id = str(uuid4())
        only_candidate.qualified_name = "charts.ChartHelper.get"
        only_candidate.repository_id = str(uuid4())
        only_candidate.entity_type = EntityType.METHOD

        mock_relation_graph.get_entities_by_suffix.return_value = [only_candidate]

        resolver = ReferenceResolver(mock_relation_graph)
        result = await resolver.resolve_batch()

        # Should resolve despite mismatch (only one option)
        assert result.resolved == 1
        mock_relation_graph.resolve_reference.assert_called_once_with(pending.id, only_candidate.id)
