"""Centralized configuration loading.

Single source of truth for all reproducibility-relevant parameters. The values
live in ``configs/config.yaml``; this module only loads and exposes them so that
no configuration is duplicated or hard-coded across the codebase.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Repository root = parent of the ``src`` package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the project configuration from a YAML file.

    Parameters
    ----------
    path:
        Optional path to a config file. Defaults to ``configs/config.yaml`` at
        the repository root.

    Returns
    -------
    dict
        The parsed configuration mapping.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if not isinstance(config, dict):
        raise ValueError(
            f"Configuration root must be a mapping, got {type(config).__name__}."
        )
    return config


def resolve_path(relative: str | Path) -> Path:
    """Resolve a config-relative path against the repository root.

    Absolute paths are returned unchanged.
    """
    p = Path(relative)
    return p if p.is_absolute() else (PROJECT_ROOT / p)
