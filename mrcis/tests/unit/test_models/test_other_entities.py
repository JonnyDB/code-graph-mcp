"""Tests for ImportEntity, VariableEntity, ModuleEntity, TypeAliasEntity."""

from uuid import uuid4

import pytest

from mrcis.models.entities import (
    EntityType,
    ImportEntity,
    ModuleEntity,
    TypeAliasEntity,
    VariableEntity,
)


@pytest.fixture
def base_entity_data() -> dict:
    """Minimal data for creating entities."""
    return {
        "name": "test",
        "qualified_name": "module.test",
        "repository_id": uuid4(),
        "file_id": uuid4(),
        "file_path": "src/module.py",
        "line_start": 1,
        "line_end": 1,
        "language": "python",
    }


class TestImportEntity:
    """Tests for ImportEntity model."""

    def test_import_entity_required_fields(self, base_entity_data: dict) -> None:
        """Test ImportEntity requires source_module."""

        entity = ImportEntity(**base_entity_data, source_module="typing")

        assert entity.entity_type == EntityType.IMPORT
        assert entity.source_module == "typing"

    def test_import_entity_defaults(self, base_entity_data: dict) -> None:
        """Test ImportEntity has correct defaults."""

        entity = ImportEntity(**base_entity_data, source_module="typing")

        assert entity.imported_symbols == []
        assert entity.is_wildcard is False
        assert entity.is_default is False
        assert entity.is_namespace is False
        assert entity.alias is None
        assert entity.is_relative is False
        assert entity.relative_level == 0

    def test_import_entity_with_symbols(self, base_entity_data: dict) -> None:
        """Test ImportEntity with imported symbols."""

        entity = ImportEntity(
            **base_entity_data,
            source_module="typing",
            imported_symbols=["Optional", "List", "Dict"],
        )
        assert entity.imported_symbols == ["Optional", "List", "Dict"]

    def test_import_entity_wildcard(self, base_entity_data: dict) -> None:
        """Test ImportEntity wildcard import."""

        entity = ImportEntity(
            **base_entity_data,
            source_module="module",
            is_wildcard=True,
        )
        assert entity.is_wildcard is True

    def test_import_entity_relative(self, base_entity_data: dict) -> None:
        """Test ImportEntity relative import."""

        entity = ImportEntity(
            **base_entity_data,
            source_module=".utils",
            is_relative=True,
            relative_level=1,
        )
        assert entity.is_relative is True
        assert entity.relative_level == 1

    def test_import_entity_with_alias(self, base_entity_data: dict) -> None:
        """Test ImportEntity with alias."""

        entity = ImportEntity(
            **base_entity_data,
            source_module="numpy",
            alias="np",
        )
        assert entity.alias == "np"


class TestVariableEntity:
    """Tests for VariableEntity model."""

    def test_variable_entity_defaults(self, base_entity_data: dict) -> None:
        """Test VariableEntity has correct defaults."""

        entity = VariableEntity(**base_entity_data)

        assert entity.entity_type == EntityType.VARIABLE
        assert entity.type_annotation is None
        assert entity.initial_value is None
        assert entity.is_constant is False
        assert entity.is_class_variable is False
        assert entity.is_instance_variable is False
        assert entity.parent_class is None
        assert entity.parent_function is None

    def test_variable_entity_with_type(self, base_entity_data: dict) -> None:
        """Test VariableEntity with type annotation."""

        entity = VariableEntity(
            **base_entity_data,
            type_annotation="int",
            initial_value="42",
        )
        assert entity.type_annotation == "int"
        assert entity.initial_value == "42"

    def test_variable_entity_constant(self, base_entity_data: dict) -> None:
        """Test VariableEntity as constant."""

        data = {**base_entity_data, "name": "MAX_SIZE"}
        entity = VariableEntity(
            **data,
            entity_type=EntityType.CONSTANT,
            is_constant=True,
        )
        assert entity.is_constant is True
        assert entity.entity_type == EntityType.CONSTANT


class TestModuleEntity:
    """Tests for ModuleEntity model."""

    def test_module_entity_defaults(self, base_entity_data: dict) -> None:
        """Test ModuleEntity has correct defaults."""

        entity = ModuleEntity(**base_entity_data)

        assert entity.entity_type == EntityType.MODULE
        assert entity.package_name is None
        assert entity.is_package is False
        assert entity.exports == []

    def test_module_entity_package(self, base_entity_data: dict) -> None:
        """Test ModuleEntity as package."""

        entity = ModuleEntity(
            **base_entity_data,
            is_package=True,
            package_name="myapp",
            exports=["MyClass", "helper_func"],
        )
        assert entity.is_package is True
        assert entity.package_name == "myapp"
        assert entity.exports == ["MyClass", "helper_func"]


class TestTypeAliasEntity:
    """Tests for TypeAliasEntity model."""

    def test_type_alias_entity_required_fields(self, base_entity_data: dict) -> None:
        """Test TypeAliasEntity requires aliased_type."""

        entity = TypeAliasEntity(**base_entity_data, aliased_type="str")

        assert entity.entity_type == EntityType.TYPE_ALIAS
        assert entity.aliased_type == "str"

    def test_type_alias_entity_defaults(self, base_entity_data: dict) -> None:
        """Test TypeAliasEntity has correct defaults."""

        entity = TypeAliasEntity(**base_entity_data, aliased_type="str")

        assert entity.type_parameters == []
        assert entity.is_union is False
        assert entity.is_intersection is False

    def test_type_alias_entity_union(self, base_entity_data: dict) -> None:
        """Test TypeAliasEntity as union type."""

        entity = TypeAliasEntity(
            **base_entity_data,
            aliased_type="str | int",
            is_union=True,
        )
        assert entity.is_union is True

    def test_type_alias_entity_with_params(self, base_entity_data: dict) -> None:
        """Test TypeAliasEntity with type parameters."""

        entity = TypeAliasEntity(
            **base_entity_data,
            aliased_type="list[T]",
            type_parameters=["T"],
        )
        assert entity.type_parameters == ["T"]
