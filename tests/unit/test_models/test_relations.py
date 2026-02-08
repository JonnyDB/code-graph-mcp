"""Tests for CodeRelation and PendingReference models."""

from datetime import datetime
from uuid import UUID, uuid4

from mrcis.models.relations import CodeRelation, PendingReference, RelationType


class TestCodeRelation:
    """Tests for CodeRelation model."""

    def test_code_relation_required_fields(self) -> None:
        """Test CodeRelation required fields."""

        relation = CodeRelation(
            source_id=uuid4(),
            source_qualified_name="app.UserValidator",
            source_entity_type="class",
            source_repository_id=uuid4(),
            target_qualified_name="sdk.BaseValidator",
            relation_type=RelationType.EXTENDS,
        )

        assert relation.source_qualified_name == "app.UserValidator"
        assert relation.target_qualified_name == "sdk.BaseValidator"
        assert relation.relation_type == RelationType.EXTENDS

    def test_code_relation_auto_generates_id(self) -> None:
        """Test CodeRelation auto-generates UUID."""

        relation = CodeRelation(
            source_id=uuid4(),
            source_qualified_name="source",
            source_entity_type="class",
            source_repository_id=uuid4(),
            target_qualified_name="target",
            relation_type=RelationType.CALLS,
        )

        assert isinstance(relation.id, UUID)

    def test_code_relation_defaults(self) -> None:
        """Test CodeRelation has correct defaults."""

        relation = CodeRelation(
            source_id=uuid4(),
            source_qualified_name="source",
            source_entity_type="function",
            source_repository_id=uuid4(),
            target_qualified_name="target",
            relation_type=RelationType.CALLS,
        )

        assert relation.target_id is None
        assert relation.target_entity_type is None
        assert relation.target_repository_id is None
        assert relation.is_cross_repository is False
        assert relation.resolution_status == "resolved"
        assert relation.line_number is None
        assert relation.context_snippet is None
        assert relation.weight == 1.0
        assert relation.metadata == {}

    def test_code_relation_cross_repository(self) -> None:
        """Test CodeRelation with cross-repository flag."""

        source_repo = uuid4()
        target_repo = uuid4()

        relation = CodeRelation(
            source_id=uuid4(),
            source_qualified_name="app.UserValidator",
            source_entity_type="class",
            source_repository_id=source_repo,
            target_id=uuid4(),
            target_qualified_name="sdk.BaseValidator",
            target_entity_type="class",
            target_repository_id=target_repo,
            relation_type=RelationType.EXTENDS,
            is_cross_repository=True,
        )

        assert relation.is_cross_repository is True
        assert relation.source_repository_id != relation.target_repository_id

    def test_code_relation_with_context(self) -> None:
        """Test CodeRelation with context information."""

        relation = CodeRelation(
            source_id=uuid4(),
            source_qualified_name="source",
            source_entity_type="function",
            source_repository_id=uuid4(),
            target_qualified_name="target",
            relation_type=RelationType.CALLS,
            line_number=42,
            context_snippet="result = target()",
        )

        assert relation.line_number == 42
        assert relation.context_snippet == "result = target()"


class TestPendingReference:
    """Tests for PendingReference model."""

    def test_pending_reference_required_fields(self) -> None:
        """Test PendingReference required fields."""

        ref = PendingReference(
            source_entity_id=uuid4(),
            source_qualified_name="app.UserValidator",
            source_repository_id=uuid4(),
            target_qualified_name="sdk.BaseValidator",
            relation_type=RelationType.EXTENDS,
            line_number=10,
        )

        assert ref.source_qualified_name == "app.UserValidator"
        assert ref.target_qualified_name == "sdk.BaseValidator"
        assert ref.relation_type == RelationType.EXTENDS
        assert ref.line_number == 10

    def test_pending_reference_defaults(self) -> None:
        """Test PendingReference has correct defaults."""

        ref = PendingReference(
            source_entity_id=uuid4(),
            source_qualified_name="source",
            source_repository_id=uuid4(),
            target_qualified_name="target",
            relation_type=RelationType.IMPORTS,
            line_number=1,
        )

        assert ref.status == "pending"
        assert ref.attempts == 0
        assert ref.resolved_target_id is None
        assert ref.resolved_at is None
        assert ref.context_snippet is None

    def test_pending_reference_status_values(self) -> None:
        """Test PendingReference valid status values."""

        for status in ["pending", "resolved", "unresolved"]:
            ref = PendingReference(
                source_entity_id=uuid4(),
                source_qualified_name="source",
                source_repository_id=uuid4(),
                target_qualified_name="target",
                relation_type=RelationType.CALLS,
                line_number=1,
                status=status,
            )
            assert ref.status == status

    def test_pending_reference_with_resolution(self) -> None:
        """Test PendingReference when resolved."""

        target_id = uuid4()
        ref = PendingReference(
            source_entity_id=uuid4(),
            source_qualified_name="source",
            source_repository_id=uuid4(),
            target_qualified_name="target",
            relation_type=RelationType.EXTENDS,
            line_number=10,
            status="resolved",
            resolved_target_id=target_id,
            resolved_at=datetime.now(),
        )

        assert ref.status == "resolved"
        assert ref.resolved_target_id == target_id
        assert ref.resolved_at is not None

    def test_pending_reference_receiver_expr(self) -> None:
        """PendingReference should accept optional receiver_expr field."""
        ref = PendingReference(
            source_entity_id=uuid4(),
            source_qualified_name="module.MyClass.run",
            source_repository_id=uuid4(),
            target_qualified_name="helper",
            relation_type=RelationType.CALLS,
            line_number=10,
            receiver_expr="ctx.redis",
        )
        assert ref.receiver_expr == "ctx.redis"

    def test_pending_reference_receiver_expr_defaults_none(self) -> None:
        """PendingReference.receiver_expr should default to None."""
        ref = PendingReference(
            source_entity_id=uuid4(),
            source_qualified_name="module.func",
            source_repository_id=uuid4(),
            target_qualified_name="helper",
            relation_type=RelationType.CALLS,
            line_number=10,
        )
        assert ref.receiver_expr is None
