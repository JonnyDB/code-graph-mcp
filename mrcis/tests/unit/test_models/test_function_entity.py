"""Tests for FunctionEntity and MethodEntity models."""

from uuid import uuid4

import pytest

from mrcis.models.entities import EntityType, FunctionEntity, MethodEntity, ParameterEntity


@pytest.fixture
def base_entity_data() -> dict:
    """Minimal data for creating entities."""
    return {
        "name": "process_data",
        "qualified_name": "module.process_data",
        "repository_id": uuid4(),
        "file_id": uuid4(),
        "file_path": "src/utils.py",
        "line_start": 10,
        "line_end": 25,
        "language": "python",
    }


class TestParameterEntity:
    """Tests for ParameterEntity model."""

    def test_parameter_entity_minimal(self) -> None:
        """Test ParameterEntity with just name."""

        param = ParameterEntity(name="value")
        assert param.name == "value"
        assert param.type_annotation is None
        assert param.default_value is None

    def test_parameter_entity_with_type(self) -> None:
        """Test ParameterEntity with type annotation."""

        param = ParameterEntity(name="value", type_annotation="int")
        assert param.type_annotation == "int"

    def test_parameter_entity_with_default(self) -> None:
        """Test ParameterEntity with default value."""

        param = ParameterEntity(name="value", default_value="42")
        assert param.default_value == "42"
        assert param.is_optional is False

    def test_parameter_entity_flags(self) -> None:
        """Test ParameterEntity flag fields."""

        param = ParameterEntity(
            name="args",
            is_rest=True,
            is_keyword_only=True,
        )
        assert param.is_rest is True
        assert param.is_keyword_only is True
        assert param.is_positional_only is False
        assert param.is_optional is False


class TestFunctionEntity:
    """Tests for FunctionEntity model."""

    def test_function_entity_defaults(self, base_entity_data: dict) -> None:
        """Test FunctionEntity has correct defaults."""

        entity = FunctionEntity(**base_entity_data)

        assert entity.entity_type == EntityType.FUNCTION
        assert entity.parameters == []
        assert entity.return_type is None
        assert entity.is_async is False
        assert entity.is_generator is False
        assert entity.is_lambda is False
        assert entity.type_parameters == []
        assert entity.calls == []
        assert entity.type_references == []

    def test_function_entity_with_parameters(self, base_entity_data: dict) -> None:
        """Test FunctionEntity with parameters."""

        params = [
            ParameterEntity(name="x", type_annotation="int"),
            ParameterEntity(name="y", type_annotation="int"),
        ]
        entity = FunctionEntity(**base_entity_data, parameters=params)

        assert len(entity.parameters) == 2
        assert entity.parameters[0].name == "x"

    def test_function_entity_with_return_type(self, base_entity_data: dict) -> None:
        """Test FunctionEntity with return type."""

        entity = FunctionEntity(**base_entity_data, return_type="str")
        assert entity.return_type == "str"

    def test_function_entity_async(self, base_entity_data: dict) -> None:
        """Test FunctionEntity async flag."""

        entity = FunctionEntity(**base_entity_data, is_async=True)
        assert entity.is_async is True

    def test_function_entity_with_calls(self, base_entity_data: dict) -> None:
        """Test FunctionEntity tracks calls."""

        entity = FunctionEntity(
            **base_entity_data,
            calls=["helper.format", "utils.validate"],
        )
        assert entity.calls == ["helper.format", "utils.validate"]


class TestMethodEntity:
    """Tests for MethodEntity model."""

    def test_method_entity_requires_parent_class(self, base_entity_data: dict) -> None:
        """Test MethodEntity requires parent_class."""

        entity = MethodEntity(
            **base_entity_data,
            parent_class="MyClass",
        )
        assert entity.entity_type == EntityType.METHOD
        assert entity.parent_class == "MyClass"

    def test_method_entity_defaults(self, base_entity_data: dict) -> None:
        """Test MethodEntity has correct defaults."""

        entity = MethodEntity(**base_entity_data, parent_class="MyClass")

        assert entity.is_static is False
        assert entity.is_classmethod is False
        assert entity.is_property is False
        assert entity.is_abstract is False
        assert entity.is_constructor is False
        assert entity.is_destructor is False
        assert entity.overrides is None

    def test_method_entity_static(self, base_entity_data: dict) -> None:
        """Test MethodEntity static flag."""

        entity = MethodEntity(
            **base_entity_data,
            parent_class="MyClass",
            is_static=True,
        )
        assert entity.is_static is True

    def test_method_entity_constructor(self, base_entity_data: dict) -> None:
        """Test MethodEntity constructor flag."""

        data = {**base_entity_data, "name": "__init__"}
        entity = MethodEntity(
            **data,
            parent_class="MyClass",
            is_constructor=True,
        )
        assert entity.is_constructor is True

    def test_method_entity_with_overrides(self, base_entity_data: dict) -> None:
        """Test MethodEntity tracking overrides."""

        entity = MethodEntity(
            **base_entity_data,
            parent_class="ChildClass",
            overrides="BaseClass.process_data",
        )
        assert entity.overrides == "BaseClass.process_data"
