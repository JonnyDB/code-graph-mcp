"""Tests for DbSessionPort protocol."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from mrcis.ports.db_session import DbSessionPort


@pytest.mark.asyncio
async def test_db_session_port_protocol():
    """Test that DbSessionPort protocol can be implemented."""

    class MockSession:
        """Mock implementation of DbSessionPort."""

        async def execute(self, sql: str, params: list | None = None):  # noqa: ARG002
            return MagicMock()

        async def fetchone(self, sql: str, params: list | None = None):  # noqa: ARG002
            return None

        async def fetchall(self, sql: str, params: list | None = None):  # noqa: ARG002
            return []

        def transaction(self):
            """Async context manager for transactions."""

            class TransactionContext:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *args):
                    return None

            return TransactionContext()

    # Verify protocol compliance
    session: DbSessionPort = MockSession()

    # Test methods exist and are callable
    await session.execute("SELECT 1")
    await session.fetchone("SELECT 1")
    await session.fetchall("SELECT 1")

    async with session.transaction():
        pass
