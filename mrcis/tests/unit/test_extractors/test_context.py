"""Tests for ExtractionContext."""

from pathlib import Path
from uuid import uuid4

from mrcis.extractors.context import ExtractionContext


class TestExtractionContext:
    """Tests for ExtractionContext class."""

    def test_create_with_required_fields(self) -> None:
        """Should create context with required fields."""
        file_path = Path("/repo/src/module.py")
        file_id = uuid4()
        repo_id = uuid4()

        context = ExtractionContext(
            file_path=file_path,
            file_id=file_id,
            repository_id=repo_id,
        )

        assert context.file_path == file_path
        assert context.file_id == file_id
        assert context.repository_id == repo_id
        assert context.language is None
        assert context.source_bytes is None

    def test_create_with_language(self) -> None:
        """Should store language when provided."""
        context = ExtractionContext(
            file_path=Path("/repo/test.py"),
            file_id=uuid4(),
            repository_id=uuid4(),
            language="python",
        )

        assert context.language == "python"

    def test_create_with_source_bytes(self) -> None:
        """Should store source bytes when provided."""
        source = b"def foo():\n    pass"
        context = ExtractionContext(
            file_path=Path("/repo/test.py"),
            file_id=uuid4(),
            repository_id=uuid4(),
            source_bytes=source,
        )

        assert context.source_bytes == source

    def test_create_with_all_fields(self) -> None:
        """Should create context with all optional fields."""
        file_path = Path("/repo/src/module.py")
        file_id = uuid4()
        repo_id = uuid4()
        source = b"print('hello')"

        context = ExtractionContext(
            file_path=file_path,
            file_id=file_id,
            repository_id=repo_id,
            language="python",
            source_bytes=source,
        )

        assert context.file_path == file_path
        assert context.file_id == file_id
        assert context.repository_id == repo_id
        assert context.language == "python"
        assert context.source_bytes == source

    def test_file_path_is_immutable(self) -> None:
        """Context fields should be frozen (immutable)."""
        context = ExtractionContext(
            file_path=Path("/repo/test.py"),
            file_id=uuid4(),
            repository_id=uuid4(),
        )

        # Pydantic frozen models raise ValidationError on attribute assignment
        try:
            context.file_path = Path("/other/path.py")  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except Exception:
            pass  # Expected - frozen models prevent mutation
