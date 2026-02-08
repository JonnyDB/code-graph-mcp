"""Tests for entity and relation type enums."""

from mrcis.models.entities import EntityType, Visibility
from mrcis.models.relations import RelationType


class TestEntityType:
    """Tests for EntityType enum."""

    def test_entity_type_has_required_values(self) -> None:
        """Test EntityType has all required code entity types."""
        # Core code constructs
        assert EntityType.MODULE == "module"
        assert EntityType.PACKAGE == "package"
        assert EntityType.CLASS == "class"
        assert EntityType.INTERFACE == "interface"
        assert EntityType.FUNCTION == "function"
        assert EntityType.METHOD == "method"
        assert EntityType.VARIABLE == "variable"
        assert EntityType.CONSTANT == "constant"
        assert EntityType.PARAMETER == "parameter"

    def test_entity_type_has_type_system_values(self) -> None:
        """Test EntityType has type system entities."""
        assert EntityType.TYPE_ALIAS == "type_alias"
        assert EntityType.ENUM == "enum"
        assert EntityType.ENUM_MEMBER == "enum_member"

    def test_entity_type_has_import_export_values(self) -> None:
        """Test EntityType has import/export entities."""
        assert EntityType.IMPORT == "import"
        assert EntityType.EXPORT == "export"

    def test_entity_type_is_string_enum(self) -> None:
        """Test EntityType values are strings."""
        for entity_type in EntityType:
            assert isinstance(entity_type.value, str)


class TestRelationType:
    """Tests for RelationType enum."""

    def test_relation_type_has_structural_values(self) -> None:
        """Test RelationType has structural containment relations."""
        assert RelationType.CONTAINS == "contains"
        assert RelationType.DEFINED_IN == "defined_in"

    def test_relation_type_has_inheritance_values(self) -> None:
        """Test RelationType has inheritance relations."""
        assert RelationType.EXTENDS == "extends"
        assert RelationType.IMPLEMENTS == "implements"
        assert RelationType.OVERRIDES == "overrides"

    def test_relation_type_has_dependency_values(self) -> None:
        """Test RelationType has dependency relations."""
        assert RelationType.IMPORTS == "imports"
        assert RelationType.EXPORTS == "exports"
        assert RelationType.DEPENDS_ON == "depends_on"

    def test_relation_type_has_usage_values(self) -> None:
        """Test RelationType has usage relations."""
        assert RelationType.CALLS == "calls"
        assert RelationType.INSTANTIATES == "instantiates"
        assert RelationType.USES_TYPE == "uses_type"
        assert RelationType.REFERENCES == "references"


class TestVisibility:
    """Tests for Visibility enum."""

    def test_visibility_values(self) -> None:
        """Test Visibility has standard visibility levels."""
        assert Visibility.PUBLIC == "public"
        assert Visibility.PRIVATE == "private"
        assert Visibility.PROTECTED == "protected"
        assert Visibility.INTERNAL == "internal"
