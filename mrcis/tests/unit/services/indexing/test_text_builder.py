"""Tests for EmbeddingTextBuilder."""

from uuid import uuid4

from mrcis.models.entities import ClassEntity, EntityType, FunctionEntity
from mrcis.services.indexing.text_builder import EmbeddingTextBuilder


class TestEmbeddingTextBuilder:
    """Tests for EmbeddingTextBuilder class."""

    def test_build_text_for_function_with_all_fields(self):
        """Builder should include all available fields for function."""
        entity = FunctionEntity(
            name="calculate_sum",
            qualified_name="math.utils.calculate_sum",
            entity_type=EntityType.FUNCTION,
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="math/utils.py",
            language="python",
            line_start=10,
            line_end=15,
            signature="def calculate_sum(a: int, b: int) -> int",
            docstring="Calculate the sum of two numbers.",
            source_text="def calculate_sum(a: int, b: int) -> int:\n    return a + b",
        )

        builder = EmbeddingTextBuilder()
        text = builder.build(entity)

        assert "function: math.utils.calculate_sum" in text
        assert "Signature: def calculate_sum(a: int, b: int) -> int" in text
        assert "Description: Calculate the sum of two numbers." in text
        assert "Code:\ndef calculate_sum(a: int, b: int) -> int:\n    return a + b" in text

    def test_build_text_for_class_minimal_fields(self):
        """Builder should handle entity with only required fields."""
        entity = ClassEntity(
            name="MyClass",
            qualified_name="mymodule.MyClass",
            entity_type=EntityType.CLASS,
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="mymodule.py",
            language="python",
            line_start=5,
            line_end=10,
        )

        builder = EmbeddingTextBuilder()
        text = builder.build(entity)

        assert text == "class: mymodule.MyClass"

    def test_build_text_with_signature_no_docstring(self):
        """Builder should include signature even without docstring."""
        entity = FunctionEntity(
            name="helper",
            qualified_name="utils.helper",
            entity_type=EntityType.FUNCTION,
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="utils.py",
            language="python",
            line_start=1,
            line_end=2,
            signature="def helper() -> None",
        )

        builder = EmbeddingTextBuilder()
        text = builder.build(entity)

        assert "function: utils.helper" in text
        assert "Signature: def helper() -> None" in text
        assert "Description:" not in text

    def test_build_text_with_docstring_no_signature(self):
        """Builder should include docstring even without signature."""
        entity = ClassEntity(
            name="DataClass",
            qualified_name="models.DataClass",
            entity_type=EntityType.CLASS,
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="models.py",
            language="python",
            line_start=1,
            line_end=5,
            docstring="A simple data class.",
        )

        builder = EmbeddingTextBuilder()
        text = builder.build(entity)

        assert "class: models.DataClass" in text
        assert "Description: A simple data class." in text
        assert "Signature:" not in text

    def test_build_text_truncates_long_source(self):
        """Builder should truncate source text that exceeds 2000 characters."""
        long_source = "x = 1\n" * 500  # ~3000 characters
        entity = FunctionEntity(
            name="long_func",
            qualified_name="module.long_func",
            entity_type=EntityType.FUNCTION,
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="module.py",
            language="python",
            line_start=1,
            line_end=500,
            source_text=long_source,
        )

        builder = EmbeddingTextBuilder()
        text = builder.build(entity)

        # Source should be truncated
        assert "Code:\n" in text
        assert len(text) < len(long_source) + 100  # Account for other fields

    def test_build_text_with_entity_type_enum(self):
        """Builder should handle EntityType enum values."""
        entity = FunctionEntity(
            name="test",
            qualified_name="test",
            entity_type=EntityType.FUNCTION,  # Enum, not string
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="test.py",
            language="python",
            line_start=1,
            line_end=1,
        )

        builder = EmbeddingTextBuilder()
        text = builder.build(entity)

        assert "function: test" in text

    def test_build_text_with_entity_type_string(self):
        """Builder should handle entity_type as string."""
        entity = FunctionEntity(
            name="test",
            qualified_name="test",
            entity_type="function",  # String, not enum
            repository_id=uuid4(),
            file_id=uuid4(),
            file_path="test.py",
            language="python",
            line_start=1,
            line_end=1,
        )

        builder = EmbeddingTextBuilder()
        text = builder.build(entity)

        assert "function: test" in text
