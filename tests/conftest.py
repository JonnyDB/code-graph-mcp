"""Shared pytest fixtures for MRCIS tests."""

from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test data."""
    return tmp_path


@pytest.fixture
def unique_id() -> str:
    """Generate a unique identifier for tests."""
    return str(uuid4())


@pytest.fixture
def sample_python_code() -> str:
    """Sample Python code for testing extractors."""
    return '''
"""Sample module docstring."""
from typing import Optional
from base_module import BaseClass


class MyClass(BaseClass):
    """A sample class."""

    def __init__(self, value: int) -> None:
        self.value = value

    def process(self, data: str) -> Optional[str]:
        """Process the data."""
        return data.upper()


def helper_function(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


CONSTANT_VALUE = 42
'''
