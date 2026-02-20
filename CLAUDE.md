# CLAUDE.md - Multi-Repository Code Intelligence System (MRCIS)

> **Last Updated**: 2026-02-08

---

## Project Overview

**MRCIS** (Multi-Repository Code Intelligence System) is an MCP (Model Context Protocol) server that provides semantic code search and cross-repository symbol resolution using vector embeddings and AST parsing.

### Core Capabilities

- **Semantic Code Search**: Natural language queries against indexed codebases using vector embeddings
- **Cross-Repository Symbol Resolution**: Understanding symbol relationships across multiple repositories
- **Structural Analysis**: AST-based parsing for 15+ languages (Python, TypeScript, Go, Rust, Java, etc.)
- **Real-time File Watching**: Automatic re-indexing on file changes
- **Pluggable Storage Backends**: SQLite+LanceDB or Neo4j graph database
- **MCP Prompt Workflows**: Interactive code exploration, impact analysis, and change planning

---

## Tech Stack

| Component        | Technology                                 |
| ---------------- | ------------------------------------------ |
| Language         | Python 3.11+                               |
| Package Manager  | uv                                         |
| Task Runner      | mise                                       |
| MCP Framework    | `mcp>=1.0.0` (FastMCP)                     |
| CLI Framework    | click                                      |
| Data Validation  | Pydantic v2 + Settings                     |
| Vector Storage   | LanceDB (default) or Neo4j native vectors  |
| Database         | aiosqlite (SQLite async) or Neo4j          |
| AST Parsing      | tree-sitter + tree-sitter-language-pack    |
| Embeddings       | OpenAI-compatible (Ollama)                 |
| File Watching    | watchdog                                   |
| Logging          | loguru                                     |
| Testing          | pytest, pytest-asyncio                     |
| Linting          | ruff, mypy (strict)                        |

---

## Project Structure

```
rag-indexing/
├── CLAUDE.md                        # This file
├── SYSTEM_ARCHITECTURE.md           # System design & ADRs
├── TECHNICAL_DESIGN.md              # Technical specifications
├── docs/plans/                      # Phase implementation plans
├── pyproject.toml                   # Dependencies & tool config
├── mise.toml                        # Task runner config
├── src/mrcis/
│   ├── __init__.py                  # Package version
│   ├── __main__.py                  # CLI entry point (click)
│   ├── errors.py                    # Exception hierarchy (MRCISError base)
│   ├── server.py                    # FastMCP server with lifespan
│   ├── server_runtime.py            # ServerRuntime lifecycle manager
│   │
│   ├── config/
│   │   ├── models.py                # Pydantic config (incl. Neo4jConfig)
│   │   ├── loader.py                # YAML config loading
│   │   └── reconciler.py            # Config ↔ DB reconciliation
│   │
│   ├── models/
│   │   ├── entities.py              # CodeEntity, ClassEntity, FunctionEntity, etc.
│   │   ├── extraction.py            # ExtractionResult, EnumEntity, InterfaceEntity
│   │   ├── relations.py             # CodeRelation, PendingReference
│   │   ├── state.py                 # Repository, IndexedFile
│   │   └── responses.py             # MCP tool response DTOs
│   │
│   ├── ports/                       # ★ Port interfaces (DIP)
│   │   ├── db_session.py            # DbSessionPort
│   │   ├── embedder.py              # EmbedderPort
│   │   ├── extractors.py            # ExtractorPort, ExtractorRegistryPort
│   │   ├── relation_graph.py        # RelationGraphPort
│   │   ├── state.py                 # StatePort + segregated reader/writer ports (ISP)
│   │   └── vector_store.py          # VectorStorePort
│   │
│   ├── extractors/                  # ★ Language extractors (OCP)
│   │   ├── base.py                  # TreeSitterExtractor ABC + ExtractorProtocol
│   │   ├── context.py               # ExtractionContext (parameter object)
│   │   ├── registry.py              # ExtractorRegistry (factory)
│   │   ├── defaults.py              # Default extractor factory
│   │   ├── adapter.py               # LegacyExtractorAdapter (migration)
│   │   ├── python.py                # Python extractor
│   │   ├── typescript.py            # TypeScript extractor
│   │   ├── javascript.py            # JavaScript extractor
│   │   ├── go.py                    # Go extractor
│   │   ├── rust.py                  # Rust extractor
│   │   ├── java.py                  # Java extractor
│   │   ├── kotlin.py                # Kotlin extractor
│   │   ├── ruby.py                  # Ruby extractor
│   │   ├── markdown.py              # Markdown extractor
│   │   ├── dockerfile.py            # Dockerfile extractor
│   │   ├── html_extractor.py        # HTML extractor
│   │   ├── json_extractor.py        # JSON extractor
│   │   ├── toml_extractor.py        # TOML extractor
│   │   └── yaml_extractor.py        # YAML extractor
│   │
│   ├── services/
│   │   ├── indexer.py               # IndexingService (orchestrator)
│   │   ├── resolver.py              # ReferenceResolver (deferred resolution)
│   │   ├── embedder.py              # EmbeddingService (Ollama)
│   │   ├── watcher.py               # FileWatcher (watchdog)
│   │   ├── file_event_router.py     # Routes file events to handlers
│   │   ├── file_filter.py           # Include/exclude pattern matching
│   │   ├── pathing.py               # Path normalization
│   │   └── indexing/                # ★ Modular indexing pipeline (SRP)
│   │       ├── pipeline.py          # FileIndexingPipeline
│   │       ├── scanner.py           # RepositoryScanner
│   │       ├── language.py          # LanguageDetector
│   │       ├── text_builder.py      # EmbeddingTextBuilder
│   │       ├── stats_updater.py     # RepositoryStatsUpdater
│   │       └── failure_policy.py    # IndexFailurePolicy
│   │
│   ├── storage/
│   │   ├── factory.py               # ★ StorageBackendFactory
│   │   ├── state_db.py              # StateDB (SQLite — repos, files, queue)
│   │   ├── relation_graph.py        # RelationGraph (SQLite — entities, relations)
│   │   ├── vector_store.py          # VectorStore (LanceDB)
│   │   ├── neo4j_graph.py           # Neo4jRelationGraph (Neo4j backend)
│   │   ├── neo4j_vectors.py         # Neo4jVectorStore (Neo4j backend)
│   │   └── migrations/
│   │       └── v001_initial.py      # Initial schema migration
│   │
│   ├── tools/
│   │   ├── __init__.py              # register_all_tools()
│   │   ├── search.py                # search_code, find_symbol
│   │   ├── references.py            # get_symbol_references, find_usages
│   │   └── status.py                # get_index_status, reindex_repository
│   │
│   ├── prompts/                     # ★ MCP prompt workflows
│   │   ├── explore.py               # Code exploration prompt
│   │   ├── change_plan.py           # Change planning prompt
│   │   ├── impact.py                # Impact analysis prompt
│   │   └── safe_change.py           # Safe change validation prompt
│   │
│   └── utils/
│       ├── logging.py               # configure_logging()
│       ├── hashing.py               # File checksum utils
│       ├── paths.py                 # GitignoreFilter
│       └── retry.py                 # Retry utilities
│
└── tests/
    ├── unit/                        # 858 unit tests
    └── integration/                 # Full pipeline + Neo4j tests
```

---

## Architecture Overview

### SOLID Principles in Practice

This codebase applies SOLID principles throughout. Understanding these patterns is essential for making changes correctly.

#### Dependency Inversion (DIP) — Ports & Adapters

All services depend on **port interfaces** (`ports/`), never on concrete storage classes. This allows swapping backends without changing business logic.

```
                   ┌──────────────────────┐
                   │    MCP Tools/Server   │
                   └──────────┬───────────┘
                              │ depends on
                   ┌──────────▼───────────┐
                   │      Services        │
                   │  (IndexingService,   │
                   │   ReferenceResolver) │
                   └──────────┬───────────┘
                              │ depends on ports
              ┌───────────────┼───────────────┐
              │               │               │
   ┌──────────▼───┐  ┌───────▼────┐  ┌───────▼──────┐
   │ StatePort    │  │ Relation   │  │ VectorStore  │
   │ (Protocol)   │  │ GraphPort  │  │ Port         │
   └──────┬───────┘  └─────┬──────┘  └──────┬───────┘
          │                │                 │
   ┌──────▼───────┐  ┌─────▼──────┐  ┌──────▼───────┐
   │   StateDB    │  │ Relation   │  │ VectorStore  │  ← SQLite+LanceDB
   │  (SQLite)    │  │ Graph      │  │ (LanceDB)    │
   └──────────────┘  └────────────┘  └──────────────┘
                     ┌─────▼──────┐  ┌──────▼───────┐
                     │ Neo4j      │  │ Neo4j        │  ← Neo4j backend
                     │ Relation   │  │ VectorStore  │
                     │ Graph      │  │              │
                     └────────────┘  └──────────────┘
```

#### Interface Segregation (ISP) — State Ports

The `StatePort` is decomposed into focused protocols so consumers only depend on what they need:

| Port                    | Methods                                  | Used By                        |
| ----------------------- | ---------------------------------------- | ------------------------------ |
| `RepositoryReaderPort`  | `get_repository`, `list_repositories`    | MCP tools, status reporting    |
| `RepositoryWriterPort`  | `add_repository`, `update_stats`         | Reconciler, indexing           |
| `FileReaderPort`        | `get_file`, `list_files_by_repository`   | Tools, pipeline                |
| `FileWriterPort`        | `upsert_file`, `mark_files_pending`      | Indexing, reindex command      |
| `QueuePort`             | `enqueue_file`, `dequeue_next_file`      | Indexing pipeline              |
| `IndexingStatePort`     | All reader + writer + queue + transaction| IndexingService                |
| `StatePort`             | Everything + `initialize` / `close`      | Server lifecycle only          |

#### Open-Closed Principle (OCP) — Extractors

New languages are added by creating a new extractor class extending `TreeSitterExtractor`. No existing code is modified.

```python
# To add a new language:
# 1. Create extractors/my_language.py
# 2. Extend TreeSitterExtractor
# 3. Register in extractors/defaults.py
```

#### Single Responsibility (SRP) — Indexing Pipeline

The indexing pipeline is decomposed into focused modules:

| Module              | Responsibility                        |
| ------------------- | ------------------------------------- |
| `pipeline.py`       | Orchestrates file → entities flow     |
| `scanner.py`        | Discovers and queues changed files    |
| `language.py`       | Detects file language from extension  |
| `text_builder.py`   | Builds embedding text from entities   |
| `stats_updater.py`  | Updates repository statistics         |
| `failure_policy.py` | Decides retry/skip on extraction fail |

### Storage Backend Factory

`StorageBackendFactory` reads `config.storage.backend` and returns the correct implementations:

| Backend          | RelationGraph       | VectorStore        |
| ---------------- | ------------------- | -------------------|
| `sqlite_lancedb` | RelationGraph       | VectorStore        |
| `neo4j`          | Neo4jRelationGraph  | Neo4jVectorStore   |

### Server Lifecycle

`ServerRuntime` encapsulates the full lifecycle (replaces module-level globals). **The server starts automatically on application startup and begins indexing immediately**, without waiting for client connections:

1. `ServerRuntime.start()` → loads config, initializes services via `StorageBackendFactory`
2. `ConfigReconciler.reconcile()` → syncs config repos with DB
3. `startup_indexing()` → scans repos and queues changed files **automatically**
4. Background tasks start: `process_backlog()`, `retry_failed_files()`, `resolve_references()`, `watcher.start()`
5. Server runs continuously, processing files and watching for changes
6. `ServerRuntime.stop()` → gracefully cancels tasks and shuts down services on application exit

### Error Hierarchy

All custom exceptions inherit from `MRCISError`:

| Exception           | Purpose                       | Extra Fields                    |
| ------------------- | ----------------------------- | ------------------------------- |
| `ConfigurationError`| Invalid config                | —                               |
| `StorageError`      | DB/storage failures           | —                               |
| `ExtractionError`   | Code parsing failures         | `file_path`, `recoverable`      |
| `EmbeddingError`    | Embedding generation failures | `retryable`                     |
| `ResolutionError`   | Symbol resolution failures    | —                               |

---

## How to Make Changes

### Adding a New Language Extractor

This is the most common change. Follow the Open-Closed Principle — extend, don't modify.

1. **Create** `src/mrcis/extractors/my_language.py`:
   - Extend `TreeSitterExtractor`
   - Implement `get_language_name()`, `get_supported_extensions()`, `_extract_from_tree()`
   - Use utility methods from the base class: `_node_text()`, `_find_child()`, `_find_descendants()`, `_get_docstring()`
2. **Register** in `src/mrcis/extractors/defaults.py`
3. **Add tests** in `tests/unit/extractors/test_my_language.py`
4. **Verify**: `uv run pytest tests/unit/extractors/ -v`

Reference: Look at `extractors/go.py` or `extractors/rust.py` as clean examples.

### Adding a New Storage Backend

Follow the Dependency Inversion Principle — implement the port interfaces.

1. **Implement** `RelationGraphPort` (see `ports/relation_graph.py` for the contract)
2. **Implement** `VectorStorePort` (see `ports/vector_store.py` for the contract)
3. **Register** in `storage/factory.py` — add a new branch in `create_relation_graph()` and `create_vector_store()`
4. **Add config** model in `config/models.py` if backend needs configuration
5. **Add tests** against the port contract
6. **Verify**: `uv run pytest tests/ -v`

Reference: `storage/neo4j_graph.py` and `storage/neo4j_vectors.py` show the full pattern.

### Adding a New MCP Tool

1. **Create** or extend a file in `src/mrcis/tools/`
2. **Register** the tool in `tools/__init__.py` via `register_all_tools()`
3. Tools receive `ServerContext` — use `ctx.relation_graph` for entities, `ctx.state_db` for repos/files
4. **Add tests** and verify

### Adding a New MCP Prompt

1. **Create** `src/mrcis/prompts/my_prompt.py`
2. **Register** in `prompts/__init__.py`
3. Prompts return structured messages with tool call instructions

### Modifying the Indexing Pipeline

The pipeline is decomposed into SRP modules under `services/indexing/`. Identify which module owns the responsibility you need to change:

- File discovery → `scanner.py`
- Language detection → `language.py`
- Processing orchestration → `pipeline.py`
- Error handling → `failure_policy.py`
- Stats tracking → `stats_updater.py`
- Embedding text generation → `text_builder.py`

### Modifying State/Entity Models

- **Entities** (`models/entities.py`): Add new `EntityType` enum values, create new entity subclasses
- **Extraction** (`models/extraction.py`): Add new entity lists to `ExtractionResult`, update `all_entities()`
- **Relations** (`models/relations.py`): Add new `RelationType` values
- **State** (`models/state.py`): Modify `Repository`/`IndexedFile` fields (requires migration)
- **Responses** (`models/responses.py`): MCP tool response DTOs (separate from domain models per SRP)

---

## Development Workflow

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [mise](https://mise.jdx.dev/) task runner (optional, convenience wrappers)
- [Ollama](https://ollama.com/) for local embeddings

### Initial Setup

```bash
uv sync --dev                    # Install all dependencies
```

### Starting Ollama (required for server)

```bash
ollama serve                     # Start Ollama daemon
ollama pull mxbai-embed-large    # Pull default embedding model
```

### Running Tests

```bash
# Direct pytest commands
uv run pytest tests/unit/ -v              # Unit tests only
uv run pytest tests/ -v                   # All tests
uv run pytest tests/ -x                   # Stop on first failure
uv run pytest tests/ -m "not slow"        # Skip slow tests
uv run pytest tests/ -m "not integration" # Skip integration tests

# Via mise task runner
mise run test                    # All tests
mise run test-fast               # Skip slow tests
mise run test-cov                # With coverage report
```

### Code Quality

```bash
# Individual checks
uv run ruff check src/ tests/   # Lint
uv run ruff format src/ tests/  # Format
uv run mypy src/                 # Type check (strict)

# Via mise
mise run lint                    # Lint only
mise run check                   # Lint + format + typecheck
mise run fix                     # Auto-fix lint + format
mise run pre-commit              # Full check + test suite
```

### Running the Server

```bash
# Initialize database first
uv run mrcis init --config config.yaml

# Start server (stdio for MCP clients)
uv run mrcis serve --config config.yaml

# Check index status
uv run mrcis status --config config.yaml

# Reindex a repository
uv run mrcis reindex my-repo --config config.yaml
uv run mrcis reindex my-repo --config config.yaml --force  # Reset failures too
```

---

## Development Guidelines

### Commit Message Style

Use Conventional Commits format with **sentence case** after the colon (capitalize the first word):

```
fix(extractors): Use tsx grammar for .tsx files to support JSX syntax
feat(tools): Add receiver-aware call resolution
```

- Format: `type(scope): Subject line` — subject is sentence case (first word capitalized)
- Body paragraphs are also sentence case

### Code Style

- **Line Length**: 100 characters
- **Python Version**: 3.11+ features allowed
- **Type Hints**: Required on all public functions (strict mypy)
- **Async**: Use `async/await` for all I/O operations

### SOLID/OOP Requirements

These are mandatory for all changes:

1. **SRP**: Each class/module has one reason to change. Don't add unrelated responsibilities.
2. **OCP**: Add new behavior via new classes (new extractor, new backend), not by modifying existing ones.
3. **LSP**: All implementations of a port must be interchangeable. If `RelationGraph` works, `Neo4jRelationGraph` must also work with the same calling code.
4. **ISP**: Depend on the narrowest port that covers your needs. Don't accept `StatePort` when `RepositoryReaderPort` suffices.
5. **DIP**: Services depend on port protocols, never on concrete storage classes. Use `StorageBackendFactory` for instantiation.

### Python Style Requirements

#### Imports

- **All imports must be at module level** — no imports inside functions, methods, or conditionals
- Use absolute imports, organized by isort
- Import order: standard library, third-party, local
- `from module import *` is forbidden

```python
# Correct
from pathlib import Path
from pydantic import BaseModel
from mrcis.models import Repository

# Wrong — import inside function
def process_repo(repo):
    from pathlib import Path  # Never do this!
```

#### Exceptions to Module-Level Imports

1. **`TYPE_CHECKING` blocks** — for type hints that would cause circular imports
2. **CLI command bodies** — lazy imports in click command functions to keep startup fast
3. **Storage factory** — lazy imports for optional backends (e.g., Neo4j) to avoid mandatory dependencies

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mrcis.services import IndexerService
```

### Testing Patterns

- All new features require tests
- Use `pytest-asyncio` for async tests (mode: auto)
- Mark slow tests with `@pytest.mark.slow`
- Mark integration tests with `@pytest.mark.integration`
- `_get_conn()` is sync → mock with `MagicMock`
- `.commit()` is async → mock with `AsyncMock`
- Test against port interfaces when possible, not concrete implementations

### Common Pitfalls

| Pitfall | Fix |
| ------- | --- |
| Calling `state_db.get_entity_*()` | Entities are in RelationGraph, not StateDB |
| Calling `.value` on relation types in tools | Relation types are already strings from DB |
| `_get_conn()` returns a coroutine | It's sync — returns the connection directly |
| Storing absolute file paths | Use `repo_root` param in `index_file()` for relative paths |
| Entity ID mismatch with pending refs | Pass `entity_id=str(entity.id)` to `add_entity()` |
| Accepting `StatePort` when only reading repos | Use `RepositoryReaderPort` (ISP) |
| Importing Neo4j at module level | Use lazy import in factory — it's an optional dependency |
| Modifying existing extractors for new languages | Create a new extractor class (OCP) |

### Error Handling

- Use the exception hierarchy from `errors.py` (`MRCISError` → specific types)
- `ExtractionError` includes `recoverable` flag for retry decisions
- `EmbeddingError` includes `retryable` flag for transient failures
- Log errors with `loguru`
- Provide actionable error messages
- Handle file system edge cases (permissions, missing files)

---

## Configuration

### YAML Config File

```yaml
repositories:
  - name: my-project
    path: /path/to/project
    branch: main

embedding:
  api_url: http://localhost:11434/v1
  api_key: ollama
  model: mxbai-embed-large
  dimensions: 1024

storage:
  backend: sqlite_lancedb           # or "neo4j"
  data_directory: ~/.mrcis

# Only needed when backend: neo4j
neo4j:
  uri: bolt://localhost:7687
  username: neo4j
  password: mrcis1234!
  database: neo4j
  vector_dimensions: 1024

logging:
  level: INFO
```

### Environment Variables

All settings use `MRCIS_` prefix with `__` nested delimiter:

```bash
MRCIS_EMBEDDING__API_URL="http://localhost:11434/v1"
MRCIS_EMBEDDING__MODEL="mxbai-embed-large"
MRCIS_EMBEDDING__DIMENSIONS="1024"
MRCIS_STORAGE__BACKEND="sqlite_lancedb"
MRCIS_STORAGE__DATA_DIRECTORY="~/.mrcis"
MRCIS_LOGGING__LEVEL="DEBUG"
MRCIS_SERVER__HOST="127.0.0.1"
MRCIS_SERVER__PORT="8765"
MRCIS_NEO4J__URI="bolt://localhost:7687"
```

---

## Implementation Phases

| Phase     | Status      | Description                             |
| --------- | ----------- | --------------------------------------- |
| Phase 0   | Complete    | Bootstrap — project structure           |
| Phase 1   | Complete    | Configuration & Models                  |
| Phase 2   | Complete    | Domain Models                           |
| Phase 3   | Complete    | Storage Layer                           |
| Phase 4   | Complete    | AST Extractors                          |
| Phase 5   | Complete    | Core Services                           |
| Phase 6   | Complete    | MCP Tools                               |
| Phase 7   | Complete    | Integration & Server                    |
| Phase 7.1 | Complete    | Critical Fixes (storage migration)      |
| Phase 8   | Complete    | Multi-language extractors (15 languages)|
| Phase 9   | Complete    | Ports & adapters refactor (SOLID)       |
| Phase 10  | Complete    | ServerRuntime + MCP prompts             |
| Phase 11  | Complete    | Neo4j storage backend                   |
| Phase 12  | Planned     | Operational Hardening                   |

---

## Troubleshooting

| Issue                        | Solution                                              |
| ---------------------------- | ----------------------------------------------------- |
| `uv sync` fails              | Ensure Python 3.11+ is installed                      |
| Import errors                | Run `uv sync --dev` to install dependencies           |
| Type errors                  | Run `uv run mypy src/` and fix reported issues        |
| Test failures                | Check for missing fixtures in `conftest.py`           |
| Ollama connection refused     | Run `ollama serve` and verify with `curl localhost:11434` |
| Embedding dimension mismatch | Ensure `dimensions` in config matches model output    |
| Entity not found in tools    | Entities are in RelationGraph, not StateDB            |
| Neo4j connection refused      | Ensure Neo4j is running: `neo4j start`                |
| Optional dep missing          | `uv sync --extra neo4j` for Neo4j support             |

---

## Related Documentation

- [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md) — Full system design
- [`TECHNICAL_DESIGN.md`](./TECHNICAL_DESIGN.md) — Technical specifications
- [`RECONCILIATION_PLAN.md`](./RECONCILIATION_PLAN.md) — Design evolution tracking
- [`docs/plans/`](./docs/plans/) — Phase-by-phase implementation guides
- [`README.md`](./README.md) — Quick start and user-facing docs
