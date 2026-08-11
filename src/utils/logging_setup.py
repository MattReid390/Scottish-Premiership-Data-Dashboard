"""Centralised logging configuration (see docs/environment_configuration.md
section 7). Named logging_setup rather than logging to avoid shadowing the
standard library module."""

from __future__ import annotations

import logging
import logging.handlers

from src.utils.config import PROJECT_ROOT, get_env, load_app_config

_configured = False


def configure_logging() -> None:
    """Attach console + rotating file handlers to the root logger. Safe to
    call multiple times; only the first call has an effect."""
    global _configured
    if _configured:
        return

    level_name = get_env("LOG_LEVEL", "INFO") or "INFO"
    level = getattr(logging, level_name.upper(), logging.INFO)

    max_bytes = 1_048_576
    backup_count = 5
    try:
        logging_config = load_app_config().get("logging", {})
        max_bytes = logging_config.get("rotate_max_bytes", max_bytes)
        backup_count = logging_config.get("rotate_backup_count", backup_count)
    except FileNotFoundError:
        pass  # config/config.yaml not present locally; fall back to defaults

    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    _configured = True
