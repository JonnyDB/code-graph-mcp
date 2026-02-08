"""Tests for ClassEntity model."""

from uuid import uuid4

import pytest

from mrcis.models.entities import ClassEntity, EntityType


@pytest.fixture
def base_entity_data() -> dict:
    """Minimal data for creating entities."""
    return {
        "name": "UserValidator",
        "qualified_name": "app.validators.UserValidator",
        "repository_id": uuid4(),
        "file_id": uuid4(),
        "file_path": "src/validators.py",
        "line_start": 10,
        "line_end": 50,
        "language": "python",
    }


class TestClassEntity:
    """Tests for ClassEntity model."""

    def test_class_entity_defaults(self, base_entity_data: dict) -> None:
        """Test ClassEntity has correct defaults."""
        entity = ClassEntity(**base_entity_data)

        assert entity.entity_type == EntityType.CLASS
        assert entity.base_classes == []
        assert entity.interfaces == []
        assert entity.mixins == []
        assert entity.is_abstract is False
        assert entity.is_dataclass is False
        assert entity.is_frozen is False
        assert entity.type_parameters == []
        assert entity.method_names == []
        assert entity.property_names == []
        assert entity.class_variable_names == []

    def test_class_entity_with_inheritance(self, base_entity_data: dict) -> None:
        """Test ClassEntity with base classes."""
        entity = ClassEntity(
            **base_entity_data,
            base_classes=["BaseValidator", "Serializable"],
        )
        assert entity.base_classes == ["BaseValidator", "Serializable"]

    def test_class_entity_with_interfaces(self, base_entity_data: dict) -> None:
        """Test ClassEntity with interfaces."""
        entity = ClassEntity(
            **base_entity_data,
            interfaces=["Comparable", "Hashable"],
        )
        assert entity.interfaces == ["Comparable", "Hashable"]

    def test_class_entity_abstract(self, base_entity_data: dict) -> None:
        """Test ClassEntity abstract flag."""
        entity = ClassEntity(**base_entity_data, is_abstract=True)
        assert entity.is_abstract is True

    def test_class_entity_dataclass(self, base_entity_data: dict) -> None:
        """Test ClassEntity dataclass flag."""
        entity = ClassEntity(**base_entity_data, is_dataclass=True)
        assert entity.is_dataclass is True

    def test_class_entity_with_type_parameters(self, base_entity_data: dict) -> None:
        """Test ClassEntity with generic type parameters."""
        entity = ClassEntity(
            **base_entity_data,
            type_parameters=["T", "K"],
        )
        assert entity.type_parameters == ["T", "K"]

    def test_class_entity_with_members(self, base_entity_data: dict) -> None:
        """Test ClassEntity with member names."""
        entity = ClassEntity(
            **base_entity_data,
            method_names=["validate", "process"],
            property_names=["is_valid"],
            class_variable_names=["DEFAULT_VALUE"],
        )
        assert entity.method_names == ["validate", "process"]
        assert entity.property_names == ["is_valid"]
        assert entity.class_variable_names == ["DEFAULT_VALUE"]
