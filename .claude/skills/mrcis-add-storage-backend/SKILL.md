---
name: mrcis-add-storage-backend
description: >
  Use when adding a new storage backend to MRCIS. Auto-activates with phrases like
  "add storage backend", "new database backend", "implement storage", "add [db] support",
  "new backend for", "implement [db] storage". Guides through DIP/LSP-compliant backend
  implementation using port interfaces and the StorageBackendFactory.
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

# Add Storage Backend to MRCIS

## Overview

MRCIS storage follows the **Dependency Inversion Principle (DIP)**: all services depend on port interfaces (protocols), never on concrete storage classes. Adding a backend means implementing those ports — no service code changes.

The **Liskov Substitution Principle (LSP)** is critical: every implementation must be fully interchangeable with the existing SQLite+LanceDB backend. If `RelationGraph` works with the indexing service, your new backend must also work without any calling-code changes.

## Architecture

```
Services (depend on ports only)
         │
         ▼
┌──────────────────────┐
│   Port Interfaces    │  ← contracts in ports/
│  RelationGraphPort   │
│  VectorStorePort     │
│  StatePort           │
└──────────┬───────────┘
           │ implemented by
    ┌──────┴──────┐
    │             │
    ▼             ▼
SQLite+LanceDB   Neo4j        ← your new backend here
```

Key files:
- `src/mrcis/ports/relation_graph.py` — `RelationGraphPort` protocol
- `src/mrcis/ports/vector_store.py` — `VectorStorePort` protocol
- `src/mrcis/ports/state.py` — `StatePort` + segregated ports (ISP)
- `src/mrcis/storage/factory.py` — `StorageBackendFactory`
- `src/mrcis/config/models.py` — Configuration models

## Port Contracts

### RelationGraphPort (mandatory)

Every backend must implement all methods:

```python
class RelationGraphPort(Protocol):
    async def add_entity(...) -> str
    async def get_entity(entity_id) -> CodeEntity | None
    async def get_entity_by_qualified_name(qualified_name) -> CodeEntity | None
    async def get_entities_by_suffix(suffix, limit) -> list[CodeEntity]
    async def get_entities_for_file(file_id) -> list[CodeEntity]
    async def delete_entities_for_file(file_id) -> int
    async def update_entity_vector_id(entity_id, vector_id) -> None
    async def add_relation(...) -> str
    async def get_incoming_relations(entity_id) -> list[CodeRelation]
    async def get_outgoing_relations(entity_id) -> list[CodeRelation]
    async def add_pending_reference(...) -> str
    async def get_pending_references(*, limit) -> list[PendingReference]
    async def resolve_reference(reference_id, target_entity_id) -> None
    async def mark_reference_unresolved(ref_id, max_attempts) -> None
```

### VectorStorePort (mandatory)

```python
class VectorStorePort(Protocol):
    async def initialize() -> None
    async def add_embedding(entity_id, embedding, metadata) -> str
    async def search(query_vector, limit, filters) -> list[SearchResult]
    async def delete_embeddings_for_file(file_id) -> int
    async def get_stats() -> dict
```

### StatePort (optional — only if replacing SQLite for state)

Most backends only replace RelationGraph + VectorStore. The StateDB (SQLite) handles repos/files/queue and usually stays unchanged.

## Step-by-Step Process

### Step 1: Add configuration model

Edit `src/mrcis/config/models.py`:

```python
class MyBackendConfig(BaseModel):
    """Configuration for MyBackend storage."""
    host: str = "localhost"
    port: int = 12345
    # ... backend-specific settings
```

Add to the main `Config` model:

```python
class Config(BaseModel):
    # ... existing fields
    my_backend: MyBackendConfig = MyBackendConfig()
```

Update `StorageConfig` to accept the new backend name:

```python
class StorageConfig(BaseModel):
    backend: Literal["sqlite_lancedb", "neo4j", "my_backend"] = "sqlite_lancedb"
```

### Step 2: Implement RelationGraphPort

Create `src/mrcis/storage/my_backend_graph.py`:

```python
"""MyBackend relation graph implementation."""

from typing import Any
from uuid import UUID

from mrcis.config.models import MyBackendConfig
from mrcis.models.entities import CodeEntity, EntityType
from mrcis.models.relations import CodeRelation, PendingReference


class MyBackendRelationGraph:
    """RelationGraphPort implementation using MyBackend."""

    def __init__(self, config: MyBackendConfig) -> None:
        self._config = config
        self._client = None  # lazy init

    async def initialize(self) -> None:
        """Connect and set up schema/indexes."""
        # Create connection, ensure schema exists
        pass

    async def close(self) -> None:
        """Close connection."""
        pass

    # Implement every method from RelationGraphPort
    async def add_entity(self, ...) -> str:
        ...

    async def get_entity(self, entity_id: str | UUID | None) -> CodeEntity | None:
        ...

    # ... all other methods
```

### Step 3: Implement VectorStorePort

Create `src/mrcis/storage/my_backend_vectors.py`:

```python
"""MyBackend vector storage implementation."""

from mrcis.config.models import MyBackendConfig


class MyBackendVectorStore:
    """VectorStorePort implementation using MyBackend."""

    def __init__(self, config: MyBackendConfig) -> None:
        self._config = config

    async def initialize(self) -> None:
        ...

    async def add_embedding(self, entity_id, embedding, metadata) -> str:
        ...

    async def search(self, query_vector, limit, filters) -> list:
        ...

    async def delete_embeddings_for_file(self, file_id) -> int:
        ...

    async def get_stats(self) -> dict:
        ...
```

### Step 4: Register in StorageBackendFactory

Edit `src/mrcis/storage/factory.py`:

```python
def create_relation_graph(self, state_db: Any = None) -> Any:
    if self.backend == "neo4j":
        from mrcis.storage.neo4j_graph import Neo4jRelationGraph
        return Neo4jRelationGraph(self._config.neo4j)
    elif self.backend == "my_backend":
        from mrcis.storage.my_backend_graph import MyBackendRelationGraph  # noqa: PLC0415
        return MyBackendRelationGraph(self._config.my_backend)
    else:
        if state_db is None:
            raise ValueError("state_db is required for sqlite_lancedb backend")
        return RelationGraph(state_db)

def create_vector_store(self) -> Any:
    if self.backend == "neo4j":
        from mrcis.storage.neo4j_vectors import Neo4jVectorStore
        return Neo4jVectorStore(self._config.neo4j)
    elif self.backend == "my_backend":
        from mrcis.storage.my_backend_vectors import MyBackendVectorStore  # noqa: PLC0415
        return MyBackendVectorStore(self._config.my_backend)
    else:
        return VectorStore(...)
```

**Important**: Use lazy imports (`from ... import` inside the method) for optional backend dependencies. This prevents import errors when the backend's library is not installed.

### Step 5: Add tests

Test against the port contracts. Create `tests/unit/storage/test_my_backend_graph.py`:

```python
"""Tests for MyBackend relation graph."""

import pytest

from mrcis.models.entities import EntityType


class TestMyBackendRelationGraph:
    """Test RelationGraphPort contract compliance."""

    async def test_add_and_get_entity(self, backend):
        entity_id = await backend.add_entity(
            repository_id="repo-1",
            file_id="file-1",
            qualified_name="module.MyClass",
            simple_name="MyClass",
            entity_type=EntityType.CLASS,
            language="python",
            line_start=1,
            line_end=10,
        )
        entity = await backend.get_entity(entity_id)
        assert entity is not None
        assert entity.simple_name == "MyClass"

    async def test_delete_entities_for_file(self, backend):
        # Add entities, then delete, verify count
        ...

    async def test_add_and_resolve_pending_reference(self, backend):
        # Add reference, resolve it, verify relation created
        ...
```

### Step 6: Verify

```bash
cd mrcis
uv run pytest tests/unit/storage/test_my_backend*.py -v
uv run ruff check src/mrcis/storage/my_backend*.py
uv run mypy src/mrcis/storage/my_backend*.py
```

## LSP Compliance Checklist

Your backend MUST pass all of these to be interchangeable:

- [ ] `add_entity()` returns a string entity ID
- [ ] `get_entity()` returns `CodeEntity | None` (never raises for missing)
- [ ] `get_entity_by_qualified_name()` returns exact match or None
- [ ] `get_entities_by_suffix()` returns entities whose qualified_name ends with suffix
- [ ] `delete_entities_for_file()` returns count of deleted entities
- [ ] `add_relation()` returns a string relation ID
- [ ] `get_incoming_relations()` and `get_outgoing_relations()` return `list[CodeRelation]`
- [ ] `add_pending_reference()` returns a string reference ID
- [ ] `resolve_reference()` creates a relation AND removes/marks the pending reference
- [ ] `mark_reference_unresolved()` increments attempt count, marks failed at max
- [ ] `add_embedding()` returns a string vector ID
- [ ] `search()` returns results sorted by similarity (descending)
- [ ] `delete_embeddings_for_file()` returns count deleted
- [ ] All async methods are truly async (no blocking I/O)

## Reference Implementation

Study the Neo4j backend for a complete example:
- `storage/neo4j_graph.py` — Full `RelationGraphPort` implementation
- `storage/neo4j_vectors.py` — Full `VectorStorePort` implementation
- `tests/integration/test_neo4j_backend.py` — Integration tests

## Common Mistakes

- Returning wrong types (e.g., int instead of str for IDs)
- Not handling `None` entity_id in `get_entity()`
- Blocking I/O in async methods (use async drivers)
- Forgetting to implement `initialize()` and `close()`
- Not using lazy imports in factory (breaks when dep not installed)
- Modifying service code to accommodate your backend (violates DIP)
