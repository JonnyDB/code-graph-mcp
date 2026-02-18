# MRCIS: Multi-Repository Code Intelligence System

A semantic code search and cross-repository symbol resolution engine, built as an [MCP](https://modelcontextprotocol.io/) server. MRCIS indexes your codebases using Tree-sitter AST parsing and vector embeddings, then lets AI assistants query code structure and relationships using natural language.

## Key Capabilities

- **Semantic Code Search**: Natural language queries against indexed codebases using vector embeddings
- **Cross-Repository Symbol Resolution**: Understand how symbols relate across multiple repositories
- **15+ Language Support**: AST-based parsing via Tree-sitter for Python, TypeScript, Go, Rust, Java, Kotlin, Ruby, and more
- **Real-Time File Watching**: Automatic re-indexing when files change
- **Pluggable Storage Backends**: SQLite + LanceDB for simplicity, or Neo4j for large-scale graph queries
- **MCP Prompt Workflows**: Interactive code exploration, impact analysis, and change planning

## Supported Languages

| Language   | Extensions  | Functions | Classes | Modules | Relations |
| ---------- | ----------- | --------- | ------- | ------- | --------- |
| Python     | .py         | Y         | Y       | Y       | Y         |
| TypeScript | .ts, .tsx   | Y         | Y       | Y       | Y         |
| JavaScript | .js, .jsx   | Y         | Y       | Y       | Y         |
| Go         | .go         | Y         | Y       | Y       | Y         |
| Rust       | .rs         | Y         | Y       | Y       | Y         |
| Java       | .java       | Y         | Y       | Y       | Y         |
| Kotlin     | .kt         | Y         | Y       | Y       | Y         |
| Ruby       | .rb         | Y         | Y       | Y       | Y         |
| Markdown   | .md         | -         | -       | Y       | -         |
| Dockerfile | Dockerfile  | -         | -       | Y       | -         |
| HTML       | .html       | -         | -       | Y       | -         |
| JSON       | .json       | -         | -       | Y       | -         |
| TOML       | .toml       | -         | -       | Y       | -         |
| YAML       | .yaml, .yml | -         | -       | Y       | -         |

## Architecture

MRCIS follows a **Ports & Adapters** architecture with strict SOLID principles. Services depend on port interfaces, never on concrete storage classes, allowing backends to be swapped without changing business logic.

```
MCP Tools / Server
        |
    Services (IndexingService, ReferenceResolver, EmbeddingService)
        |
    Port Interfaces (StatePort, RelationGraphPort, VectorStorePort)
       / \
      /   \
SQLite+LanceDB   Neo4j
```

| Component             | Responsibility                                     |
| --------------------- | -------------------------------------------------- |
| **StateDB**           | Repositories, files, indexing queue                |
| **RelationGraph**     | Entities, relations, pending cross-repo references |
| **VectorStore**       | Embedding vectors for semantic search              |
| **Extractors**        | AST parsing per language (Tree-sitter)             |
| **IndexingService**   | Orchestrates file discovery, extraction, embedding |
| **ReferenceResolver** | Deferred cross-repo symbol resolution              |

### Storage Backends

| Backend              | Best For                                      | Components                            |
| -------------------- | --------------------------------------------- | ------------------------------------- |
| **SQLite + LanceDB** | Small to medium projects, zero infrastructure | SQLite for state, LanceDB for vectors |
| **Neo4j**            | Large codebases, complex cross-repo analysis  | Neo4j for graph + vectors             |

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- **[Ollama](https://ollama.com/)** for local embeddings
- **Docker** (only if using Neo4j backend)

## Quick Start

### 1. Install Ollama and pull the embedding model

```bash
brew install ollama       # macOS
ollama serve              # Start the server
ollama pull mxbai-embed-large
```

### 2. Create a config file

Create `config.yaml`:

```yaml
repositories:
  - name: my-project
    path: /path/to/your/project
    branch: main

embedding:
  api_url: http://localhost:11434/v1
  api_key: ollama
  model: mxbai-embed-large
  dimensions: 1024

storage:
  backend: sqlite_lancedb
  data_directory: ~/.mrcis

logging:
  level: INFO
```

### 3. Run with uvx (no install required)

```bash
uvx --from 'git+https://github.com/JonnyDB/code-graph-mcp@main' mrcis init --config config.yaml
uvx --from 'git+https://github.com/JonnyDB/code-graph-mcp@main' mrcis serve --config config.yaml
```

Or install and run with uv:

```bash
uv sync --dev
uv run mrcis init --config config.yaml
uv run mrcis serve --config config.yaml
```

The server starts indexing your repositories immediately on startup.

### Using Neo4j Instead

For large codebases or complex cross-repository analysis, switch to the Neo4j backend:

```bash
docker compose up -d   # Start Neo4j (bolt://localhost:7687, UI at http://localhost:7474)
```

Add to your `config.yaml`:

```yaml
storage:
  backend: neo4j
  data_directory: ~/.mrcis

neo4j:
  uri: bolt://localhost:7687
  username: neo4j
  password: mrcis1234!
  database: neo4j
  vector_dimensions: 1024
```

## MCP Tools

When running as an MCP server, these tools are exposed to AI assistants:

| Tool                       | Description                            |
| -------------------------- | -------------------------------------- |
| `mrcis_search_code`        | Semantic search across indexed code    |
| `mrcis_find_symbol`        | Find a symbol by qualified name        |
| `mrcis_get_references`     | Get all references to a symbol         |
| `mrcis_find_usages`        | Find usages of a symbol by simple name |
| `mrcis_get_index_status`   | Get indexing progress and statistics   |
| `mrcis_reindex_repository` | Queue a repository for reindexing      |

### MCP Prompt Workflows

| Prompt                     | Purpose                                           |
| -------------------------- | ------------------------------------------------- |
| **Code Exploration**       | Interactive guided exploration of unfamiliar code |
| **Change Planning**        | Plan multi-file changes with dependency awareness |
| **Impact Analysis**        | Understand blast radius of proposed changes       |
| **Safe Change Validation** | Validate changes won't break dependents           |

## Using with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mrcis": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/JonnyDB/code-graph-mcp@main", "mrcis", "serve", "--config", "/path/to/config.yaml"],
      "env": {}
    }
  }
}
```

Or if running from a local clone:

```json
{
  "mcpServers": {
    "mrcis": {
      "command": "uv",
      "args": ["--directory", "/path/to/code-graph-mcp", "run", "mrcis", "serve", "--config", "/path/to/config.yaml"],
      "env": {}
    }
  }
}
```

## CLI Reference

```bash
# Via uvx (no install required)
uvx --from 'git+https://github.com/JonnyDB/code-graph-mcp@main' mrcis serve [--config FILE] [--transport stdio|sse]
uvx --from 'git+https://github.com/JonnyDB/code-graph-mcp@main' mrcis init  [--config FILE]

# Via uv (from local clone)
uv run mrcis serve    [--config FILE] [--transport stdio|sse]
uv run mrcis init     [--config FILE]
```

## Configuration

All settings can be overridden with environment variables using the `MRCIS_` prefix and `__` as a nested delimiter:

```bash
MRCIS_EMBEDDING__API_URL="http://localhost:11434/v1"
MRCIS_EMBEDDING__MODEL="mxbai-embed-large"
MRCIS_STORAGE__BACKEND="neo4j"
MRCIS_NEO4J__URI="bolt://localhost:7687"
MRCIS_LOGGING__LEVEL="DEBUG"
```

Any OpenAI-compatible embedding API works. For alternative Ollama models:

```bash
ollama pull nomic-embed-text    # Smaller/faster — dimensions: 768
ollama pull mxbai-embed-large   # Default/recommended — dimensions: 1024
```

### Using LM Studio

Point MRCIS at LM Studio's local server and set `append_eos_token: true` to silence the tokenizer warning that llama.cpp emits when the GGUF model lacks `tokenizer.ggml.add_eos_token` in its header:

```yaml
embedding:
  api_url: http://localhost:1234/v1
  api_key: lm-studio
  model: your-model-name          # as shown in LM Studio
  dimensions: 1024                # match your model's output dimensions
  append_eos_token: true          # appends </s> to each text before embedding
  # eos_token: "[SEP]"            # override for BERT-style models
```

## Development

```bash
uv sync --dev                             # Install dependencies
uv run pytest tests/unit/ -v              # Run unit tests
uv run pytest tests/ -v                   # Run all tests
uv run ruff check src/ tests/             # Lint
uv run ruff format src/ tests/            # Format
uv run mypy src/                          # Type check (strict)
```

Or with [mise](https://mise.jdx.dev/):

```bash
mise run test          # All tests
mise run check         # Lint + format + typecheck
mise run fix           # Auto-fix lint + format
```

See [CLAUDE.md](./CLAUDE.md) for full architecture docs and development guidelines.

## License

MIT
