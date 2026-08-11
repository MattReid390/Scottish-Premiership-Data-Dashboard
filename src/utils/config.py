"""Configuration loading helpers.

Reads secrets from `.env` (via python-dotenv) and non-secret settings from
`config/config.yaml`, per docs/environment_configuration.md. Both files are
gitignored; `.env.example` and `config/config.example.yaml` are the committed
templates.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_dotenv_loaded = False


def _ensure_dotenv_loaded() -> None:
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv(PROJECT_ROOT / ".env")
        _dotenv_loaded = True


def get_database_url() -> str:
    """Return the SQLAlchemy connection string from DATABASE_URL, defaulting
    to a local SQLite file if unset (see .env.example)."""
    _ensure_dotenv_loaded()
    return os.environ.get("DATABASE_URL", "sqlite:///data/premiership.db")


def get_env(name: str, default: str | None = None) -> str | None:
    """Read a single environment variable, ensuring .env has been loaded first."""
    _ensure_dotenv_loaded()
    return os.environ.get(name, default)


def load_app_config(path: Path | None = None) -> dict[str, Any]:
    """Load non-secret application settings from config/config.yaml."""
    config_path = path or PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found at {config_path}. "
            "Copy config/config.example.yaml to config/config.yaml and adjust as needed."
        )
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
