---
name: mrcis-architecture-guide
description: >
  Use when making any code change to MRCIS to ensure SOLID/OOP compliance. Auto-activates
  with phrases like "architecture guide", "SOLID principles", "design patterns", "how should
  I structure", "where does this go", "which module", "refactor", "add feature to MRCIS".
  Provides architectural decision guidance and maps changes to the correct modules.
allowed-tools: Read, Grep, Glob
---

# MRCIS Architecture Guide

## Quick Decision: Where Does My Change Go?

### Change Type → Module Mapping

| I want to...                          | Module(s) to change                          | Principle |
| ------------------------------------- | -------------------------------------------- | --------- |
| Add a new language                    | `extractors/{lang}.py`, `extractors/defaults.py` | OCP   |
| Add a new storage backend             | `storage/{backend}.py`, `storage/factory.py` | DIP/LSP   |
| Add a new entity type                 | `models/entities.py`, `models/extraction.py` | OCP       |
| Add a new relation type               | `models/relations.py`                        | OCP       |
| Add a new MCP tool                    | `tools/{module}.py`, `tools/__init__.py`     | SRP       |
| Add a new MCP prompt                  | `prompts/{name}.py`, `prompts/__init__.py`   | SRP       |
| Change how files are discovered       | `services/indexing/scanner.py`               | SRP       |
| Change how extraction failures work   | `services/indexing/failure_policy.py`         | SRP       |
| Change how embeddings are built       | `services/indexing/text_builder.py`           | SRP       |
| Change language detection             | `services/indexing/language.py`               | SRP       |
| Change repo statistics updates        | `services/indexing/stats_updater.py`          | SRP       |
| Change file event handling            | `services/file_event_router.py`              | SRP       |
| Change the indexing pipeline flow     | `services/indexing/pipeline.py`              | SRP       |
| Add configuration options             | `config/models.py`                           | —         |
| Change server startup/shutdown        | `server_runtime.py`                          | SRP       |
| Add a new error type                  | `errors.py`                                  | OCP       |

### Red Flags — Signs You're Violating SOLID

| Symptom | Likely Violation | Fix |
| ------- | ---------------- | --- |
| Modifying an existing extractor to handle a new language | OCP violation | Create a new extractor class |
| Adding a method to `StatePort` that only one consumer needs | ISP violation | Create a focused sub-port |
| Service imports a concrete storage class | DIP violation | Use the port interface |
| One class does extraction AND embedding | SRP violation | Split into separate classes |
| Backend X works but backend Y doesn't with same service | LSP violation | Fix backend Y to match the contract |
| Adding `if backend == "foo"` inside a service | DIP violation | Use factory + port interfaces |

## SOLID Principles — MRCIS Examples

### S — Single Responsibility Principle

**Each module has one reason to change.**

The indexing pipeline demonstrates SRP decomposition:

```
IndexingService (orchestrator)
    │
    ├── RepositoryScanner        ← file discovery
    ├── LanguageDetector          ← extension → language mapping
    ├── FileIndexingPipeline      ← file → entities processing
    ├── EmbeddingTextBuilder      ← entities → embedding text
    ├── RepositoryStatsUpdater    ← statistics tracking
    └── IndexFailurePolicy        ← retry/skip decisions
```

**When to split**: If you're adding functionality that has a different "reason to change" than the existing module, create a new module.

### O — Open-Closed Principle

**Open for extension, closed for modification.**

The extractor system is the primary example:

```python
# GOOD: Adding a new language
class SwiftExtractor(TreeSitterExtractor):
    def get_language_name(self) -> str: return "swift"
    def get_supported_extensions(self) -> set[str]: return {".swift"}
    def _extract_from_tree(self, ...): ...

# BAD: Modifying PythonExtractor to also handle Swift
```

OCP also applies to:
- **Entity types**: Add new `EntityType` enum values, don't redefine existing ones
- **Error types**: Add new exception subclasses of `MRCISError`
- **Storage backends**: Add new implementations, don't modify existing ones

### L — Liskov Substitution Principle

**Every implementation of a port must be interchangeable.**

```python
# This code works with ANY RelationGraphPort implementation:
async def resolve_references(graph: RelationGraphPort):
    refs = await graph.get_pending_references(limit=100)
    for ref in refs:
        entity = await graph.get_entity_by_qualified_name(ref.target_qualified_name)
        if entity:
            await graph.resolve_reference(str(ref.id), str(entity.id))
```

If this works with `RelationGraph` (SQLite), it MUST also work with `Neo4jRelationGraph`. The contract is defined by `RelationGraphPort` in `ports/relation_graph.py`.

**LSP test**: Can you swap backend implementations in `StorageBackendFactory` without changing any service code? If yes, LSP holds.

### I — Interface Segregation Principle

**Depend on the narrowest interface you need.**

The state ports demonstrate ISP:

```python
# GOOD: This function only reads repositories
async def list_repos(state: RepositoryReaderPort) -> list[Repository]:
    return await state.list_repositories()

# BAD: This function accepts StatePort but only uses one method
async def list_repos(state: StatePort) -> list[Repository]:
    return await state.list_repositories()
```

Port hierarchy (narrowest → broadest):
```
RepositoryReaderPort  ← read repos only
RepositoryWriterPort  ← write repos only
FileReaderPort        ← read files only
FileWriterPort        ← write files only
QueuePort             ← queue operations only
IndexingStatePort     ← all above + transactions (for IndexingService)
StatePort             ← everything + initialize/close (for server lifecycle)
```

### D — Dependency Inversion Principle

**High-level modules depend on abstractions, not details.**

```python
# GOOD: IndexingService depends on ports
class IndexingService:
    def __init__(
        self,
        state_db: IndexingStatePort,        # port, not StateDB
        vector_store: VectorStorePort,       # port, not VectorStore
        relation_graph: RelationGraphPort,   # port, not RelationGraph
        ...
    ): ...

# BAD: Direct dependency on concrete class
class IndexingService:
    def __init__(self, state_db: StateDB): ...  # Never do this
```

The `StorageBackendFactory` handles instantiation. Services never know which concrete class they're using.

## Design Patterns in Use

| Pattern | Where | Purpose |
| ------- | ----- | ------- |
| **Factory** | `StorageBackendFactory`, `ExtractorRegistry.create_default()` | Create correct implementations based on config |
| **Protocol (Structural typing)** | All ports in `ports/` | Define contracts without inheritance coupling |
| **Template Method** | `TreeSitterExtractor._extract_from_tree()` | Base class handles parsing, subclass handles extraction |
| **Parameter Object** | `ExtractionContext` | Bundle extraction parameters into a single object |
| **Adapter** | `LegacyExtractorAdapter` | Bridge old extractor interface to new one |
| **Strategy** | `IndexFailurePolicy` | Pluggable failure handling logic |
| **Observer** | `FileWatcher.on_change()` → `FileEventRouter.handle()` | Decouple file watching from event processing |
| **Composition Root** | `ServerRuntime.start()` / `initialize_services()` | Wire all dependencies in one place |

## Composition Root

All dependency wiring happens in `server_runtime.py:initialize_services()`. This is the only place where concrete classes are instantiated and connected. Services receive their dependencies via constructor injection.

```python
# In initialize_services():
state_db = StateDB(...)                              # concrete
factory = StorageBackendFactory(config)               # chooses backend
vector_store = factory.create_vector_store()           # returns port impl
relation_graph = factory.create_relation_graph(state_db)  # returns port impl

indexer = IndexingService(
    state_db=state_db,           # injected as IndexingStatePort
    vector_store=vector_store,   # injected as VectorStorePort
    relation_graph=relation_graph,  # injected as RelationGraphPort
    ...
)
```

**Rule**: If you're instantiating a storage class anywhere other than `server_runtime.py` or `storage/factory.py`, you're likely violating DIP.

## Adding New Capabilities Checklist

Before making any change, verify:

- [ ] **SRP**: Does this change belong in the module I'm editing? Or should it be a new module?
- [ ] **OCP**: Am I extending the system (new class/module) or modifying existing behavior?
- [ ] **LSP**: If I'm implementing a port, does my implementation pass all existing tests?
- [ ] **ISP**: Am I depending on the narrowest port that covers my needs?
- [ ] **DIP**: Am I depending on a port interface, not a concrete class?
- [ ] **Tests**: Did I add tests for the new behavior?
- [ ] **Types**: Does `mypy --strict` pass?
- [ ] **Lint**: Does `ruff check` pass?
