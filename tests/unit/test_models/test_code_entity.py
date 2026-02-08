"""Tests for CodeEntity base model."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from mrcis.models.entities import CodeEntity, Visibility


@pytest.fixture
def base_entity_data() -> dict:
    """Minimal data for creating a CodeEntity."""
    return {
        "name": "TestEntity",
        "qualified_name": "module.TestEntity",
        "entity_type": "class",
        "repository_id": uuid4(),
        "file_id": uuid4(),
        "file_path": "src/module.py",
        "line_start": 10,
        "line_end": 50,
        "language": "python",
    }


class TestCodeEntity:
    """Tests for CodeEntity base model."""

    def test_code_entity_required_fields(self, base_entity_data: dict) -> None:
        """Test CodeEntity requires essential fields."""

        entity = CodeEntity(**base_entity_data)

        assert entity.name == "TestEntity"
        assert entity.qualified_name == "module.TestEntity"
        assert entity.entity_type == "class"
        assert entity.file_path == "src/module.py"
        assert entity.line_start == 10
        assert entity.line_end == 50
        assert entity.language == "python"

    def test_code_entity_auto_generates_id(self, base_entity_data: dict) -> None:
        """Test CodeEntity auto-generates UUID if not provided."""

        entity = CodeEntity(**base_entity_data)
        assert isinstance(entity.id, UUID)

    def test_code_entity_accepts_explicit_id(self, base_entity_data: dict) -> None:
        """Test CodeEntity accepts explicit id."""

        explicit_id = uuid4()
        entity = CodeEntity(id=explicit_id, **base_entity_data)
        assert entity.id == explicit_id

    def test_code_entity_defaults(self, base_entity_data: dict) -> None:
        """Test CodeEntity has correct defaults."""

        entity = CodeEntity(**base_entity_data)

        assert entity.source_text is None
        assert entity.docstring is None
        assert entity.comments == []
        assert entity.is_exported is False
        assert entity.visibility == Visibility.PUBLIC
        assert entity.decorators == []
        assert entity.annotations == {}
        assert entity.embedding_text is None
        assert entity.vector_id is None

    def test_code_entity_optional_location_fields(self, base_entity_data: dict) -> None:
        """Test CodeEntity handles optional column fields."""

        entity = CodeEntity(
            **base_entity_data,
            col_start=5,
            col_end=25,
        )
        assert entity.col_start == 5
        assert entity.col_end == 25

    def test_code_entity_with_docstring(self, base_entity_data: dict) -> None:
        """Test CodeEntity with docstring."""

        entity = CodeEntity(
            **base_entity_data,
            docstring="This is a test entity.",
        )
        assert entity.docstring == "This is a test entity."

    def test_code_entity_with_decorators(self, base_entity_data: dict) -> None:
        """Test CodeEntity with decorators."""

        entity = CodeEntity(
            **base_entity_data,
            decorators=["@dataclass", "@frozen"],
        )
        assert entity.decorators == ["@dataclass", "@frozen"]

    def test_code_entity_timestamps(self, base_entity_data: dict) -> None:
        """Test CodeEntity has auto-generated timestamps."""

        entity = CodeEntity(**base_entity_data)

        assert isinstance(entity.created_at, datetime)
        assert isinstance(entity.updated_at, datetime)

    def test_code_entity_serializes_to_dict(self, base_entity_data: dict) -> None:
        """Test CodeEntity can be serialized to dict."""

        entity = CodeEntity(**base_entity_data)
        data = entity.model_dump()

        assert isinstance(data, dict)
        assert data["name"] == "TestEntity"
        assert data["entity_type"] == "class"
