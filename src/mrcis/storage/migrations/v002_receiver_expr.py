"""Add receiver_expr column to pending_references table."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

MIGRATION_SQL = """
ALTER TABLE pending_references ADD COLUMN receiver_expr TEXT;

UPDATE schema_version SET version = 2 WHERE version = 1;
"""


async def apply_migration(db: "aiosqlite.Connection") -> None:
    """Apply v002 migration: add receiver_expr to pending_references."""
    await db.executescript(MIGRATION_SQL)
    await db.commit()
