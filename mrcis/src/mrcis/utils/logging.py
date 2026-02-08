"""Logging configuration using loguru.

Provides centralized logging setup with configurable
format, level, and file output. All console logging
goes to stderr to avoid corrupting MCP stdio transport.
"""

import logging
import sys
from typing import Any

from loguru import logger

from mrcis.config.models import LoggingConfig


class _InterceptHandler(logging.Handler):
    """Route standard library logging through loguru.

    Ensures third-party libraries (mcp, httpx, watchdog, etc.)
    that use the stdlib logging module have their output routed
    through loguru to stderr, preventing stdout pollution that
    would break MCP stdio transport.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Map stdlib level to loguru level
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find the caller frame (skip logging internals)
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(config: LoggingConfig) -> None:
    """
    Configure loguru logger based on configuration.

    All console output is directed to stderr. Standard library
    logging is intercepted so third-party libraries also log
    to stderr via loguru.

    Args:
        config: LoggingConfig with level, format, and file settings.
    """
    # Remove default handler
    logger.remove()

    # Determine format
    if config.format == "json":
        fmt = "{message}"
        serialize = True
    else:
        fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        serialize = False

    # Add console handler — always stderr to protect stdio transport
    logger.add(
        sys.stderr,
        format=fmt,
        level=config.level,
        serialize=serialize,
        colorize=config.format == "console",
    )

    # Add file handler if configured
    if config.file:
        logger.add(
            config.file,
            format=fmt,
            level=config.level,
            serialize=serialize,
            rotation=config.rotation,
            retention=config.retention,
            compression="gz",
        )

    # Intercept stdlib logging → loguru → stderr
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    logger.debug("Logging configured: level={} format={}", config.level, config.format)


def get_logger(name: str) -> Any:
    """
    Get a logger instance with context.

    Args:
        name: Logger name (typically module name).

    Returns:
        Configured logger instance.
    """
    return logger.bind(name=name)
