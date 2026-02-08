"""Initial database schema migration."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

SCHEMA = """
-- ============================================================================
-- REPOSITORIES (State only - configuration comes from config file)
-- ============================================================================
CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'indexing', 'watching', 'error', 'paused')),
    last_indexed_commit TEXT,
    last_indexed_at TEXT,
    file_count INTEGER NOT NULL DEFAULT 0,
    entity_count INTEGER NOT NULL DEFAULT 0,
    relation_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_repositories_status ON repositories(status);
CREATE INDEX IF NOT EXISTS idx_repositories_name ON repositories(name);

-- ============================================================================
-- INDEXED FILES
-- ============================================================================
CREATE TABLE IF NOT EXISTS indexed_files (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    language TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'processing', 'indexed', 'failed', 'permanent_failure', 'deleted'
        )),
    failure_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    entity_count INTEGER NOT NULL DEFAULT 0,
    last_modified_at TEXT NOT NULL,
    last_indexed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE (repository_id, path),
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_files_repo ON indexed_files(repository_id);
CREATE INDEX IF NOT EXISTS idx_files_status ON indexed_files(status);
CREATE INDEX IF NOT EXISTS idx_files_checksum ON indexed_files(checksum);
CREATE INDEX IF NOT EXISTS idx_files_path ON indexed_files(path);

-- ============================================================================
-- ENTITIES (Symbol Registry)
-- ============================================================================
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    file_id TEXT NOT NULL,

    qualified_name TEXT NOT NULL,
    simple_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    language TEXT NOT NULL,

    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    col_start INTEGER,
    col_end INTEGER,

    signature TEXT,
    docstring TEXT,
    source_text TEXT,

    visibility TEXT NOT NULL DEFAULT 'public',
    is_exported INTEGER NOT NULL DEFAULT 0,
    decorators_json TEXT,
    metadata_json TEXT,

    vector_id TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES indexed_files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_repo ON entities(repository_id);
CREATE INDEX IF NOT EXISTS idx_entities_file ON entities(file_id);
CREATE INDEX IF NOT EXISTS idx_entities_qualified ON entities(qualified_name);
CREATE INDEX IF NOT EXISTS idx_entities_simple ON entities(simple_name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);

-- Full-text search on qualified names
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    qualified_name,
    simple_name,
    docstring,
    content='entities',
    content_rowid='rowid'
);

-- Triggers to keep FTS table in sync with entities table
-- INSERT trigger: add new entities to FTS
CREATE TRIGGER IF NOT EXISTS entities_fts_insert AFTER INSERT ON entities BEGIN
    INSERT INTO entities_fts(rowid, qualified_name, simple_name, docstring)
    VALUES (NEW.rowid, NEW.qualified_name, NEW.simple_name, NEW.docstring);
END;

-- UPDATE trigger: update FTS when entities change
CREATE TRIGGER IF NOT EXISTS entities_fts_update AFTER UPDATE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, qualified_name, simple_name, docstring)
    VALUES ('delete', OLD.rowid, OLD.qualified_name, OLD.simple_name, OLD.docstring);
    INSERT INTO entities_fts(rowid, qualified_name, simple_name, docstring)
    VALUES (NEW.rowid, NEW.qualified_name, NEW.simple_name, NEW.docstring);
END;

-- DELETE trigger: remove entities from FTS
CREATE TRIGGER IF NOT EXISTS entities_fts_delete AFTER DELETE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, qualified_name, simple_name, docstring)
    VALUES ('delete', OLD.rowid, OLD.qualified_name, OLD.simple_name, OLD.docstring);
END;

-- ============================================================================
-- RELATIONS (Resolved Edges)
-- ============================================================================
CREATE TABLE IF NOT EXISTS relations (
    id TEXT PRIMARY KEY,

    source_id TEXT NOT NULL,
    source_qualified_name TEXT NOT NULL,
    source_entity_type TEXT NOT NULL,
    source_repository_id TEXT NOT NULL,

    target_id TEXT NOT NULL,
    target_qualified_name TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    target_repository_id TEXT NOT NULL,

    relation_type TEXT NOT NULL,
    is_cross_repository INTEGER NOT NULL DEFAULT 0,

    line_number INTEGER,
    context_snippet TEXT,
    weight REAL NOT NULL DEFAULT 1.0,
    metadata_json TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type);
CREATE INDEX IF NOT EXISTS idx_relations_cross_repo ON relations(is_cross_repository);

-- ============================================================================
-- PENDING REFERENCES (For Deferred Resolution)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pending_references (
    id TEXT PRIMARY KEY,

    source_entity_id TEXT NOT NULL,
    source_qualified_name TEXT NOT NULL,
    source_repository_id TEXT NOT NULL,

    target_qualified_name TEXT NOT NULL,
    relation_type TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'resolved', 'unresolved')),
    attempts INTEGER NOT NULL DEFAULT 0,
    resolved_target_id TEXT,
    resolved_at TEXT,

    line_number INTEGER,
    context_snippet TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (source_entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pending_source ON pending_references(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_references(status);
CREATE INDEX IF NOT EXISTS idx_pending_target ON pending_references(target_qualified_name);

-- ============================================================================
-- INDEXING QUEUE (FIFO Backlog)
-- ============================================================================
CREATE TABLE IF NOT EXISTS indexing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT UNIQUE NOT NULL,
    repository_id TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    queued_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (file_id) REFERENCES indexed_files(id) ON DELETE CASCADE,
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_queue_priority ON indexing_queue(priority DESC, id ASC);

-- ============================================================================
-- SYNC HISTORY (Audit Trail)
-- ============================================================================
CREATE TABLE IF NOT EXISTS sync_history (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    from_commit TEXT,
    to_commit TEXT,
    files_added INTEGER NOT NULL DEFAULT 0,
    files_modified INTEGER NOT NULL DEFAULT 0,
    files_deleted INTEGER NOT NULL DEFAULT 0,
    entities_added INTEGER NOT NULL DEFAULT 0,
    relations_added INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL,
    error_message TEXT,

    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sync_repo ON sync_history(repository_id);
CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_history(status);

-- ============================================================================
-- SCHEMA VERSION
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
"""


async def apply_migration(db: "aiosqlite.Connection") -> None:
    """Apply the initial schema migration."""
    await db.executescript(SCHEMA)
    await db.commit()

    # Verify FTS triggers were created successfully
    cursor = await db.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'trigger' AND name IN (
            'entities_fts_insert',
            'entities_fts_update',
            'entities_fts_delete'
        )
        """
    )
    triggers = await cursor.fetchall()
    trigger_names = {row[0] for row in triggers}

    expected_triggers = {"entities_fts_insert", "entities_fts_update", "entities_fts_delete"}
    missing_triggers = expected_triggers - trigger_names

    if missing_triggers:
        raise RuntimeError(
            f"FTS triggers not created: {', '.join(sorted(missing_triggers))}. "
            "Database schema may be corrupted."
        )
