"""Tests for MRCIS server module."""

from unittest.mock import MagicMock

from mrcis.server import create_server


def _make_mock_runtime():
    """Create a mock ServerRuntime for create_server()."""
    runtime = MagicMock()
    runtime.get_context.return_value = MagicMock()
    return runtime


class TestCreateServer:
    """Test create_server() function."""

    def test_create_server_returns_fastmcp_instance(self) -> None:
        """create_server() should return a FastMCP instance."""
        server = create_server(_make_mock_runtime())
        assert server is not None

    def test_create_server_with_custom_host_port(self) -> None:
        """create_server() should accept custom host and port."""
        server = create_server(_make_mock_runtime(), host="0.0.0.0", port=9000)
        assert server is not None
