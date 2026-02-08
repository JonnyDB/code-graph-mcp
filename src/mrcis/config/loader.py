"""Configuration loading utilities."""

from pathlib import Path

import yaml

from mrcis.config.models import Config


def load_config(config_path: Path | None) -> Config:
    """
    Load configuration from YAML file or return defaults.

    Args:
        config_path: Path to YAML config file, or None for defaults.

    Returns:
        Validated Config object.

    Raises:
        FileNotFoundError: If config_path doesn't exist.
        ValueError: If YAML is invalid.
    """
    if config_path is None:
        return Config()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with config_path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}") from e

    if data is None:
        data = {}

    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping, not {type(data).__name__}")

    return Config(**data)
