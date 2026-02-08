"""Tests for ServerConfig model."""

import pytest
from pydantic import ValidationError

from mrcis.config.models import ServerConfig


def test_server_config_defaults() -> None:
    """Test ServerConfig has correct defaults."""
    config = ServerConfig()
    assert config.transport == "sse"
    assert config.host == "127.0.0.1"
    assert config.port == 8765
    assert config.shutdown_timeout_seconds == 30


def test_server_config_custom_values() -> None:
    """Test ServerConfig accepts custom values."""
    config = ServerConfig(
        transport="stdio",
        host="0.0.0.0",
        port=9000,
        shutdown_timeout_seconds=60,
    )
    assert config.transport == "stdio"
    assert config.host == "0.0.0.0"
    assert config.port == 9000
    assert config.shutdown_timeout_seconds == 60


def test_server_config_invalid_transport() -> None:
    """Test ServerConfig rejects invalid transport."""
    with pytest.raises(ValidationError) as exc_info:
        ServerConfig(transport="invalid")
    assert "transport" in str(exc_info.value)


def test_server_config_port_range() -> None:
    """Test ServerConfig validates port range."""
    # Valid ports
    ServerConfig(port=1024)
    ServerConfig(port=65535)

    # Invalid ports
    with pytest.raises(ValidationError):
        ServerConfig(port=1023)  # Too low
    with pytest.raises(ValidationError):
        ServerConfig(port=65536)  # Too high


def test_server_config_shutdown_timeout_range() -> None:
    """Test ServerConfig validates shutdown timeout range."""
    # Valid timeouts
    ServerConfig(shutdown_timeout_seconds=5)
    ServerConfig(shutdown_timeout_seconds=300)

    # Invalid timeouts
    with pytest.raises(ValidationError):
        ServerConfig(shutdown_timeout_seconds=4)  # Too low
    with pytest.raises(ValidationError):
        ServerConfig(shutdown_timeout_seconds=301)  # Too high
