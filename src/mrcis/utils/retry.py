"""Retry utilities with exponential backoff.

Uses the backoff library for retry logic with configurable
backoff strategies for different error types.
"""

from collections.abc import Mapping
from typing import Any

import backoff
from loguru import logger

from mrcis.errors import EmbeddingError, StorageError


def on_backoff(details: Mapping[str, Any]) -> None:
    """Log retry attempts."""
    logger.warning(
        "Retrying {}: attempt={} wait={}s error={}",
        details["target"].__name__,
        details["tries"],
        details["wait"],
        details["exception"],
    )


def on_giveup(details: Mapping[str, Any]) -> None:
    """Log when retries are exhausted."""
    logger.error(
        "Gave up on {}: attempts={} error={}",
        details["target"].__name__,
        details["tries"],
        details["exception"],
    )


# Reusable decorators for common retry scenarios

retry_embedding = backoff.on_exception(
    backoff.expo,
    EmbeddingError,
    max_tries=3,
    on_backoff=on_backoff,
    on_giveup=on_giveup,
)

retry_storage = backoff.on_exception(
    backoff.expo,
    StorageError,
    max_tries=5,
    on_backoff=on_backoff,
    on_giveup=on_giveup,
)

retry_network = backoff.on_exception(
    backoff.expo,
    (ConnectionError, TimeoutError),
    max_tries=3,
    max_time=30,  # Total max time in seconds
    on_backoff=on_backoff,
    on_giveup=on_giveup,
)
