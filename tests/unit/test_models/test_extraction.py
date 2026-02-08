"""Tests for extraction models."""

from uuid import uuid4

from mrcis.models.entities import ClassEntity, EntityType, FunctionEntity, MethodEntity
from mrcis.models.extraction import EnumEntity, ExtractionResult, InterfaceEntity


class TestEnumEntity:
    """Tests for EnumEntity model."""

    def test_enum_entity_has_correct_type(self) -> None:
        """EnumEntity should have ENUM entity type."""
        entity = EnumEntity(
            name="Color",
            qualified_name="enums.Color",
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="enums.py",
            language="python",
            line_start=1,
            line_end=5,
        )

        assert entity.entity_type == EntityType.ENUM


class TestInterfaceEntity:
    """Tests for InterfaceEntity model."""

    def test_interface_entity_has_correct_type(self) -> None:
        """InterfaceEntity should have INTERFACE entity type."""
        entity = InterfaceEntity(
            name="ILogger",
            qualified_name="interfaces.ILogger",
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="interfaces.ts",
            language="typescript",
            line_start=1,
            line_end=10,
        )

        assert entity.entity_type == EntityType.INTERFACE


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_extraction_result_with_minimal_fields(self) -> None:
        """ExtractionResult should work with only required fields."""
        result = ExtractionResult(
            file_id=uuid4(),
            file_path="test.py",
            repository_id=uuid4(),
            language="python",
        )

        assert result.modules == []
        assert result.classes == []
        assert result.parse_errors == []
        assert result.entity_count() == 0

    def test_all_entities_aggregates_all_entity_types(self) -> None:
        """all_entities() should return all entities from all lists."""
        file_id = uuid4()
        repo_id = uuid4()

        func = FunctionEntity(
            name="func",
            qualified_name="func",
            repository_id=repo_id,
            file_id=file_id,
            file_path="test.py",
            language="python",
            line_start=1,
            line_end=2,
        )

        cls = ClassEntity(
            name="TestClass",
            qualified_name="TestClass",
            repository_id=repo_id,
            file_id=file_id,
            file_path="test.py",
            language="python",
            line_start=5,
            line_end=10,
        )

        result = ExtractionResult(
            file_id=file_id,
            file_path="test.py",
            repository_id=repo_id,
            language="python",
            functions=[func],
            classes=[cls],
        )

        entities = result.all_entities()
        assert len(entities) == 2
        assert func in entities
        assert cls in entities

    def test_entity_count_returns_total(self) -> None:
        """entity_count() should return total number of entities."""
        file_id = uuid4()
        repo_id = uuid4()

        result = ExtractionResult(
            file_id=file_id,
            file_path="test.py",
            repository_id=repo_id,
            language="python",
            functions=[
                FunctionEntity(
                    name=f"func{i}",
                    qualified_name=f"func{i}",
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path="test.py",
                    language="python",
                    line_start=i,
                    line_end=i + 1,
                )
                for i in range(3)
            ],
            classes=[
                ClassEntity(
                    name="TestClass",
                    qualified_name="TestClass",
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path="test.py",
                    language="python",
                    line_start=10,
                    line_end=20,
                )
            ],
            methods=[
                MethodEntity(
                    name="method",
                    qualified_name="TestClass.method",
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path="test.py",
                    language="python",
                    line_start=15,
                    line_end=17,
                    parent_class="TestClass",
                )
            ],
        )

        assert result.entity_count() == 5  # 3 functions + 1 class + 1 method
