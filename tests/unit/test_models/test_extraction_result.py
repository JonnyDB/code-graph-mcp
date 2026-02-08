"""Tests for ExtractionResult model."""

from uuid import uuid4

import pytest

from mrcis.models.entities import ClassEntity, FunctionEntity, MethodEntity
from mrcis.models.extraction import ExtractionResult


@pytest.fixture
def extraction_result_data() -> dict:
    """Minimal data for creating ExtractionResult."""
    return {
        "file_id": uuid4(),
        "file_path": "src/module.py",
        "repository_id": uuid4(),
        "language": "python",
    }


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_extraction_result_required_fields(self, extraction_result_data: dict) -> None:
        """Test ExtractionResult requires file info."""

        result = ExtractionResult(**extraction_result_data)

        assert result.file_path == "src/module.py"
        assert result.language == "python"

    def test_extraction_result_defaults(self, extraction_result_data: dict) -> None:
        """Test ExtractionResult has empty default lists."""

        result = ExtractionResult(**extraction_result_data)

        assert result.modules == []
        assert result.classes == []
        assert result.interfaces == []
        assert result.functions == []
        assert result.methods == []
        assert result.variables == []
        assert result.imports == []
        assert result.type_aliases == []
        assert result.enums == []
        assert result.relations == []
        assert result.pending_references == []
        assert result.parse_errors == []
        assert result.extraction_time_ms == 0.0

    def test_extraction_result_all_entities(self, extraction_result_data: dict) -> None:
        """Test ExtractionResult.all_entities() returns flat list."""

        base_data = {
            "qualified_name": "test",
            "repository_id": extraction_result_data["repository_id"],
            "file_id": extraction_result_data["file_id"],
            "file_path": extraction_result_data["file_path"],
            "line_start": 1,
            "line_end": 10,
            "language": "python",
        }

        cls = ClassEntity(name="MyClass", **base_data)
        func = FunctionEntity(name="my_func", **base_data)

        result = ExtractionResult(
            **extraction_result_data,
            classes=[cls],
            functions=[func],
        )

        all_entities = result.all_entities()
        assert len(all_entities) == 2
        assert cls in all_entities
        assert func in all_entities

    def test_extraction_result_entity_count(self, extraction_result_data: dict) -> None:
        """Test ExtractionResult.entity_count() returns total."""

        base_data = {
            "qualified_name": "test",
            "repository_id": extraction_result_data["repository_id"],
            "file_id": extraction_result_data["file_id"],
            "file_path": extraction_result_data["file_path"],
            "line_start": 1,
            "line_end": 10,
            "language": "python",
        }

        result = ExtractionResult(
            **extraction_result_data,
            classes=[ClassEntity(name="A", **base_data)],
            functions=[
                FunctionEntity(name="f1", **base_data),
                FunctionEntity(name="f2", **base_data),
            ],
            methods=[MethodEntity(name="m1", parent_class="A", **base_data)],
        )

        assert result.entity_count() == 4

    def test_extraction_result_with_parse_errors(self, extraction_result_data: dict) -> None:
        """Test ExtractionResult tracks parse errors."""

        result = ExtractionResult(
            **extraction_result_data,
            parse_errors=["Syntax error at line 10", "Unexpected token"],
        )

        assert len(result.parse_errors) == 2
        assert "Syntax error at line 10" in result.parse_errors
