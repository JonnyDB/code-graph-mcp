---
name: mrcis-add-extractor
description: >
  Use when adding a new language extractor to MRCIS. Auto-activates with phrases like
  "add extractor", "new language support", "extract [language]", "support [language] files",
  "new extractor for", "add [language] parsing". Guides through the OCP-compliant extractor
  creation process with TreeSitterExtractor base class.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Add Language Extractor to MRCIS

## Overview

MRCIS extractors follow the **Open-Closed Principle (OCP)**: add new languages by creating new classes, never by modifying existing extractors.

All extractors extend `TreeSitterExtractor` (an abstract base class) and implement the `ExtractorProtocol`.

## Architecture

```
ExtractorProtocol (Protocol)     TreeSitterExtractor (ABC)
         │                               │
         └──────────┬────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   PythonExtractor GoExtractor RustExtractor ...
```

Key files:
- `src/mrcis/extractors/base.py` — `TreeSitterExtractor` ABC + `ExtractorProtocol`
- `src/mrcis/extractors/context.py` — `ExtractionContext` (parameter object)
- `src/mrcis/models/extraction.py` — `ExtractionResult` (return type)
- `src/mrcis/extractors/defaults.py` — Registration of all extractors
- `src/mrcis/extractors/registry.py` — `ExtractorRegistry` (factory/lookup)

## Step-by-Step Process

### Step 1: Identify the tree-sitter language name

Check if the language is available in `tree-sitter-language-pack`. The language name must match what `get_language()` and `get_parser()` accept.

### Step 2: Create the extractor file

Create `src/mrcis/extractors/{language}.py`. Use this template:

```python
"""[Language] code extractor using tree-sitter."""

from pathlib import Path
from uuid import UUID

from tree_sitter import Tree

from mrcis.extractors.base import TreeSitterExtractor
from mrcis.models.entities import EntityType, FunctionEntity, ClassEntity  # as needed
from mrcis.models.extraction import ExtractionResult
from mrcis.models.relations import PendingReference


class [Language]Extractor(TreeSitterExtractor):
    """Extracts code entities from [Language] source files."""

    def get_language_name(self) -> str:
        return "[tree-sitter-name]"

    def get_supported_extensions(self) -> set[str]:
        return {".ext1", ".ext2"}

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="[language]",
        )

        root = tree.root_node
        module_name = file_path.stem

        # Extract functions, classes, etc. from AST nodes
        # Use self._node_text(), self._find_child(), self._find_descendants()

        return result
```

### Step 3: Implement entity extraction

For each AST node type you want to extract:
1. Find the node using `self._find_descendants(root, "node_type")`
2. Extract name, signature, docstring using base class utilities
3. Build qualified names using `self._build_qualified_name()`
4. Create entity objects (FunctionEntity, ClassEntity, etc.)
5. Append to the appropriate list in ExtractionResult

### Step 4: Register the extractor

Edit `src/mrcis/extractors/defaults.py` and add the import + registration:

```python
from mrcis.extractors.my_language import MyLanguageExtractor

def create_default_extractors() -> list:
    return [
        # ... existing extractors ...
        MyLanguageExtractor(),
    ]
```

### Step 5: Add tests

Create `tests/unit/extractors/test_{language}.py`:

```python
"""Tests for [Language] extractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.[language] import [Language]Extractor
from mrcis.extractors.context import ExtractionContext


@pytest.fixture
def extractor():
    return [Language]Extractor()


class TestSupports:
    def test_supported_extension(self, extractor):
        assert extractor.supports(Path("test.ext"))

    def test_unsupported_extension(self, extractor):
        assert not extractor.supports(Path("test.txt"))


class TestExtraction:
    async def test_extracts_functions(self, extractor, tmp_path):
        source = '''
        // [Language] code with a function
        '''
        file_path = tmp_path / "test.ext"
        file_path.write_text(source)

        ctx = ExtractionContext(
            file_path=file_path,
            file_id=uuid4(),
            repository_id=uuid4(),
        )
        result = await extractor.extract_with_context(ctx)

        assert result.entity_count() > 0
        assert len(result.functions) > 0
```

### Step 6: Verify

```bash
cd mrcis
uv run pytest tests/unit/extractors/test_{language}.py -v
uv run ruff check src/mrcis/extractors/{language}.py
uv run mypy src/mrcis/extractors/{language}.py
```

## Reference Extractors

Good examples to study, ordered by complexity:
1. **`go.py`** — Clean, simple structure
2. **`rust.py`** — Traits, impls, good pattern matching
3. **`python.py`** — Most complete (decorators, nested classes, imports)
4. **`typescript.py`** — Interfaces, type aliases, enums

## Entity Types Available

From `models/entities.py` — EntityType enum:
- MODULE, CLASS, FUNCTION, METHOD, VARIABLE, IMPORT
- ENUM, ENUM_MEMBER, TYPE_ALIAS, INTERFACE
- CONFIG_SECTION, CONFIG_KEY, TABLE, COLUMN, INDEX
- COMPONENT, ELEMENT, STAGE, TASK

## Base Class Utilities

From `TreeSitterExtractor`:
- `_node_text(node, source)` — Get text content of an AST node
- `_find_child(node, type_name)` — First child of type
- `_find_children(node, type_name)` — All direct children of type
- `_find_descendants(node, type_name)` — Recursive search for descendants
- `_get_docstring(body_node, source)` — Extract docstring from body
- `_get_source_line(node, source)` — Get trimmed source line
- `_build_qualified_name(name, parent, module)` — Build fully qualified name

## Common Mistakes

- Forgetting to register in `defaults.py` (extractor won't be used)
- Using wrong tree-sitter node type names (check tree-sitter playground)
- Not handling optional AST children (nodes can be None)
- Hardcoding module names instead of using `file_path.stem`
- Missing `entity_type` on entity constructors
