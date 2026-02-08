"""Tests for PythonExtractor import extraction."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.python import PythonExtractor


@pytest.fixture
def extractor():
    """Provide PythonExtractor instance."""
    return PythonExtractor()


@pytest.fixture
def write_py_file(tmp_path: Path):
    """Factory fixture to write Python files."""

    def _write(content: str) -> Path:
        file_path = tmp_path / "test_module.py"
        file_path.write_text(content)
        return file_path

    return _write


class TestPythonImportExtraction:
    """Tests for import statement extraction."""

    @pytest.mark.asyncio
    async def test_extract_simple_import(self, extractor, write_py_file) -> None:
        """Test extracting 'import x' statement."""
        code = "import os"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.source_module == "os"
        assert imp.is_relative is False

    @pytest.mark.asyncio
    async def test_extract_import_from(self, extractor, write_py_file) -> None:
        """Test extracting 'from x import y' statement."""
        code = "from typing import Optional, List"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.source_module == "typing"
        assert "Optional" in imp.imported_symbols
        assert "List" in imp.imported_symbols

    @pytest.mark.asyncio
    async def test_extract_relative_import(self, extractor, write_py_file) -> None:
        """Test extracting relative import."""
        code = "from . import utils"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.is_relative is True
        assert imp.relative_level == 1

    @pytest.mark.asyncio
    async def test_extract_wildcard_import(self, extractor, write_py_file) -> None:
        """Test extracting wildcard import."""
        code = "from module import *"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp.is_wildcard is True


class TestPythonImportPendingReferences:
    """Tests for import pending reference creation."""

    @pytest.mark.asyncio
    async def test_simple_import_creates_pending_reference(self, extractor, write_py_file) -> None:
        """'import os' should create a pending reference with target 'os'."""
        code = "import os"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.pending_references) == 1
        ref = result.pending_references[0]
        assert ref.target_qualified_name == "os"
        assert ref.relation_type == "imports"

    @pytest.mark.asyncio
    async def test_from_import_creates_pending_references(self, extractor, write_py_file) -> None:
        """'from typing import Optional, List' should create 2 pending references."""
        code = "from typing import Optional, List"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        targets = {ref.target_qualified_name for ref in result.pending_references}
        assert "typing.Optional" in targets
        assert "typing.List" in targets

    @pytest.mark.asyncio
    async def test_from_import_single_symbol(self, extractor, write_py_file) -> None:
        """'from os.path import join' should create 1 pending reference."""
        code = "from os.path import join"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        import_refs = [r for r in result.pending_references if r.relation_type == "imports"]
        assert len(import_refs) == 1
        assert import_refs[0].target_qualified_name == "os.path.join"

    @pytest.mark.asyncio
    async def test_wildcard_import_no_pending_reference(self, extractor, write_py_file) -> None:
        """'from module import *' should not create pending references."""
        code = "from module import *"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        import_refs = [r for r in result.pending_references if r.relation_type == "imports"]
        assert len(import_refs) == 0

    @pytest.mark.asyncio
    async def test_relative_import_creates_pending_reference(
        self, extractor, write_py_file
    ) -> None:
        """'from . import utils' should create pending reference with target 'utils'."""
        code = "from . import utils"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        import_refs = [r for r in result.pending_references if r.relation_type == "imports"]
        assert len(import_refs) == 1
        assert import_refs[0].target_qualified_name == "utils"

    @pytest.mark.asyncio
    async def test_pending_reference_source_matches_import_entity(
        self, extractor, write_py_file
    ) -> None:
        """Pending reference source_entity_id should match the import entity id."""
        code = "from os.path import join"
        file_path = write_py_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.imports) == 1
        import_refs = [r for r in result.pending_references if r.relation_type == "imports"]
        assert len(import_refs) == 1
        assert import_refs[0].source_entity_id == result.imports[0].id


class TestPythonExtractorSupports:
    """Tests for file support detection."""

    def test_supports_py_files(self, extractor) -> None:
        """Test supports .py files."""
        assert extractor.supports(Path("module.py"))
        assert extractor.supports(Path("module.PY"))

    def test_supports_pyi_files(self, extractor) -> None:
        """Test supports .pyi stub files."""
        assert extractor.supports(Path("module.pyi"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support non-Python files."""
        assert not extractor.supports(Path("module.js"))
        assert not extractor.supports(Path("module.ts"))
        assert not extractor.supports(Path("module.txt"))
