"""Test package initialization."""

import mrcis


def test_version_exists() -> None:
    """Test that version is defined."""
    assert hasattr(mrcis, "__version__")
    assert isinstance(mrcis.__version__, str)


def test_version_format() -> None:
    """Test that version follows semver format."""
    version = mrcis.__version__
    parts = version.split(".")
    assert len(parts) == 3, f"Version should have 3 parts: {version}"
    for part in parts:
        assert part.isdigit(), f"Version part should be numeric: {part}"
