"""Tests for RelationGraph."""

from datetime import datetime
from uuid import uuid4

import pytest

from mrcis.models.entities import EntityType
from mrcis.models.state import FileStatus, IndexedFile
from mrcis.storage.relation_graph import RelationGraph
from mrcis.storage.state_db import StateDB


@pytest.fixture
async def state_db(tmp_path):
    """Create initialized StateDB."""
    db = StateDB(tmp_path / "test.db")
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
async def relation_graph(state_db):
    """Create RelationGraph with StateDB."""
    rg = RelationGraph(state_db)
    await rg.initialize()
    return rg


@pytest.fixture
async def sample_repo(state_db):
    """Create sample repository."""
    repo_id = await state_db.create_repository("test-repo")
    return repo_id


@pytest.fixture
async def sample_file(state_db, sample_repo):
    """Create sample indexed file."""
    file = IndexedFile(
        id=str(uuid4()),
        repository_id=sample_repo,
        path="/test/file.py",
        checksum="abc123",
        file_size=100,
        language="python",
        status=FileStatus.INDEXED,
        last_modified_at=datetime.now(),
    )
    file_id = await state_db.upsert_file(file)
    return file_id


class TestRelationGraphInitialize:
    """Test initialization."""

    @pytest.mark.asyncio
    async def test_initializes_with_state_db(self, state_db):
        """Should initialize without error."""
        rg = RelationGraph(state_db)
        await rg.initialize()
        # No error means success


class TestEntityOperations:
    """Test entity CRUD."""

    @pytest.mark.asyncio
    async def test_add_entity(self, relation_graph, sample_repo, sample_file):
        """Should add entity to database."""
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="test_module.TestClass",
            simple_name="TestClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        assert entity_id is not None

    @pytest.mark.asyncio
    async def test_get_entity_by_qualified_name(self, relation_graph, sample_repo, sample_file):
        """Should find entity by qualified name."""
        await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="test_module.TestClass",
            simple_name="TestClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        entity = await relation_graph.get_entity_by_qualified_name("test_module.TestClass")

        assert entity is not None
        assert entity.simple_name == "TestClass"

    @pytest.mark.asyncio
    async def test_get_entity_by_suffix(self, relation_graph, sample_repo, sample_file):
        """Should find entity by name suffix."""
        await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="test_module.TestClass",
            simple_name="TestClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        entities = await relation_graph.get_entities_by_suffix("TestClass")

        assert len(entities) == 1
        assert entities[0].qualified_name == "test_module.TestClass"

    @pytest.mark.asyncio
    async def test_delete_entities_for_file(self, relation_graph, sample_repo, sample_file):
        """Should delete all entities for a file."""
        await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="test_module.TestClass",
            simple_name="TestClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        deleted = await relation_graph.delete_entities_for_file(sample_file)

        assert deleted == 1
        entity = await relation_graph.get_entity_by_qualified_name("test_module.TestClass")
        assert entity is None

    @pytest.mark.asyncio
    async def test_add_entity_with_caller_provided_id(
        self, relation_graph, sample_repo, sample_file
    ):
        """Should use caller-provided entity ID instead of generating one."""
        provided_id = str(uuid4())
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="test_module.ProvidedIdClass",
            simple_name="ProvidedIdClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
            entity_id=provided_id,
        )

        assert entity_id == provided_id

        # Verify entity can be fetched by the provided ID
        entity = await relation_graph.get_entity(provided_id)
        assert entity is not None
        assert entity.id == provided_id
        assert entity.simple_name == "ProvidedIdClass"

    @pytest.mark.asyncio
    async def test_add_entity_generates_id_when_not_provided(
        self, relation_graph, sample_repo, sample_file
    ):
        """Should generate UUID when entity_id is not provided."""
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="test_module.AutoIdClass",
            simple_name="AutoIdClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        assert entity_id is not None
        entity = await relation_graph.get_entity(entity_id)
        assert entity is not None

    @pytest.mark.asyncio
    async def test_add_entity_with_vector_id(self, relation_graph, sample_repo, sample_file):
        """Should persist vector_id when provided."""
        vector_id = "vec-" + str(uuid4())
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="test_module.VectorClass",
            simple_name="VectorClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
            vector_id=vector_id,
        )

        entity = await relation_graph.get_entity(entity_id)
        assert entity is not None
        assert entity.vector_id == vector_id

    @pytest.mark.asyncio
    async def test_add_entity_vector_id_null_when_not_provided(
        self, relation_graph, sample_repo, sample_file
    ):
        """Should have NULL vector_id when not provided."""
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="test_module.NoVectorClass",
            simple_name="NoVectorClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        entity = await relation_graph.get_entity(entity_id)
        assert entity is not None
        assert entity.vector_id is None


class TestRelationOperations:
    """Test relation CRUD."""

    @pytest.mark.asyncio
    async def test_add_relation(self, relation_graph, sample_repo, sample_file):
        """Should add relation between entities."""
        source_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="module.ClassA",
            simple_name="ClassA",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        target_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="module.ClassB",
            simple_name="ClassB",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=20,
            line_end=30,
        )

        relation_id = await relation_graph.add_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type="inherits",
        )

        assert relation_id is not None

    @pytest.mark.asyncio
    async def test_get_incoming_relations(self, relation_graph, sample_repo, sample_file):
        """Should get relations pointing to entity."""
        source_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="module.ClassA",
            simple_name="ClassA",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        target_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="module.ClassB",
            simple_name="ClassB",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=20,
            line_end=30,
        )

        await relation_graph.add_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type="inherits",
        )

        incoming = await relation_graph.get_incoming_relations(target_id)

        assert len(incoming) == 1
        assert incoming[0].source_id == source_id


class TestPendingReferenceOperations:
    """Test pending reference management."""

    @pytest.mark.asyncio
    async def test_add_pending_reference(self, relation_graph, sample_repo, sample_file):
        """Should add pending reference."""
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="module.ClassA",
            simple_name="ClassA",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        ref_id = await relation_graph.add_pending_reference(
            source_entity_id=entity_id,
            source_qualified_name="module.ClassA",
            source_repository_id=sample_repo,
            target_qualified_name="other_module.ClassB",
            relation_type="imports",
        )

        assert ref_id is not None

    @pytest.mark.asyncio
    async def test_get_pending_references(self, relation_graph, sample_repo, sample_file):
        """Should get pending references."""
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="module.ClassA",
            simple_name="ClassA",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        await relation_graph.add_pending_reference(
            source_entity_id=entity_id,
            source_qualified_name="module.ClassA",
            source_repository_id=sample_repo,
            target_qualified_name="other_module.ClassB",
            relation_type="imports",
        )

        pending = await relation_graph.get_pending_references(limit=10)

        assert len(pending) == 1
        assert pending[0].target_qualified_name == "other_module.ClassB"

    @pytest.mark.asyncio
    async def test_resolve_reference(self, relation_graph, sample_repo, sample_file):
        """Should resolve pending reference."""
        source_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="module.ClassA",
            simple_name="ClassA",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )

        target_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="other_module.ClassB",
            simple_name="ClassB",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=20,
            line_end=30,
        )

        ref_id = await relation_graph.add_pending_reference(
            source_entity_id=source_id,
            source_qualified_name="module.ClassA",
            source_repository_id=sample_repo,
            target_qualified_name="other_module.ClassB",
            relation_type="imports",
        )

        await relation_graph.resolve_reference(ref_id, target_id)

        # Should create relation
        incoming = await relation_graph.get_incoming_relations(target_id)
        assert len(incoming) == 1

        # Pending should be marked resolved
        pending = await relation_graph.get_pending_references(limit=10)
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_add_pending_reference_with_receiver_expr(
        self, relation_graph, sample_repo, sample_file
    ):
        """add_pending_reference should store receiver_expr."""
        # Setup: create an entity first
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="mod.MyClass.run",
            simple_name="run",
            entity_type=EntityType.METHOD,
            language="python",
            line_start=1,
            line_end=5,
        )

        ref_id = await relation_graph.add_pending_reference(
            source_entity_id=entity_id,
            source_qualified_name="mod.MyClass.run",
            source_repository_id=sample_repo,
            target_qualified_name="get",
            relation_type="calls",
            line_number=3,
            receiver_expr="ctx.redis",
        )

        refs = await relation_graph.get_pending_references(limit=10)
        ref = next(r for r in refs if r.id == ref_id)
        assert ref.receiver_expr == "ctx.redis"

    @pytest.mark.asyncio
    async def test_add_pending_reference_without_receiver_expr(
        self, relation_graph, sample_repo, sample_file
    ):
        """add_pending_reference without receiver_expr should store None."""
        entity_id = await relation_graph.add_entity(
            repository_id=sample_repo,
            file_id=sample_file,
            qualified_name="mod.func",
            simple_name="func",
            entity_type=EntityType.FUNCTION,
            language="python",
            line_start=1,
            line_end=5,
        )

        ref_id = await relation_graph.add_pending_reference(
            source_entity_id=entity_id,
            source_qualified_name="mod.func",
            source_repository_id=sample_repo,
            target_qualified_name="helper",
            relation_type="calls",
            line_number=2,
        )

        refs = await relation_graph.get_pending_references(limit=10)
        ref = next(r for r in refs if r.id == ref_id)
        assert ref.receiver_expr is None
