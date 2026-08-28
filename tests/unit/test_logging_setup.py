"""Unit test for src/utils/logging_setup.py."""

from __future__ import annotations

import logging

from src.utils import logging_setup


def test_configure_logging_attaches_handlers_once(tmp_path, monkeypatch) -> None:
    # configure_logging() writes to PROJECT_ROOT / "logs", a fixed absolute
    # path - not the working directory - so redirecting it for the test
    # means patching that name, not chdir'ing.
    monkeypatch.setattr(logging_setup, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(logging_setup, "_configured", False)
    root_logger = logging.getLogger()
    handlers_before = list(root_logger.handlers)

    try:
        logging_setup.configure_logging()
        handlers_after_first_call = list(root_logger.handlers)
        logging_setup.configure_logging()  # second call should be a no-op
        handlers_after_second_call = list(root_logger.handlers)

        assert len(handlers_after_first_call) == len(handlers_before) + 2
        assert handlers_after_second_call == handlers_after_first_call
        assert (tmp_path / "logs" / "app.log").exists()
    finally:
        for handler in root_logger.handlers[len(handlers_before) :]:
            root_logger.removeHandler(handler)
            handler.close()
