"""Port interface for database session operations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol


class DbSessionPort(Protocol):
    """Protocol for database session operations.

    Provides low-level SQL execution and transaction management
    without exposing the underlying connection implementation.
    """

    async def execute(self, sql: str, params: list[Any] | None = None) -> Any:
        """Execute a SQL statement.

        Args:
            sql: SQL statement to execute
            params: Optional parameter list

        Returns:
            Cursor or result object
        """
        ...

    async def fetchone(self, sql: str, params: list[Any] | None = None) -> Any | None:
        """Execute query and fetch one row.

        Args:
            sql: SQL query
            params: Optional parameter list

        Returns:
            Single row or None
        """
        ...

    async def fetchall(self, sql: str, params: list[Any] | None = None) -> list[Any]:
        """Execute query and fetch all rows.

        Args:
            sql: SQL query
            params: Optional parameter list

        Returns:
            List of rows
        """
        ...

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Start a transaction context.

        Commits on success, rolls back on exception.

        Yields:
            None (context manager)
        """
        yield
