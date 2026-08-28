"""Shared pytest fixtures (see docs/testing_strategy.md section 3).

Both fixtures use a real file-based SQLite database under pytest's
per-test tmp_path rather than a bare ":memory:" URL: src.database.session
caches engines by URL string, so a shared literal ":memory:" URL would
have every test reuse the same engine/connection and leak state between
tests. A unique tmp_path per test sidesteps that entirely.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import streamlit as st
from sqlalchemy.orm import Session

from src.database.models import Base
from src.database.session import get_engine, get_session_factory


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    """An isolated, schema-initialised session for tests that talk to the
    ORM directly (e.g. the analysis layer, which accepts a Session)."""
    url = f"sqlite:///{tmp_path / 'unit_test.db'}"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    session = get_session_factory(url)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def isolated_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Points the application's default DATABASE_URL - what session_scope()
    resolves to when called with no explicit URL, i.e. what application
    code under test actually uses - at an isolated, schema-initialised
    temp SQLite file. For integration tests exercising code (like
    src.processing.pipeline) that opens its own sessions internally.

    Also clears st.cache_data: it's a process-wide cache keyed only on
    function name/args, with no awareness that DATABASE_URL changed
    between tests - confirmed to leak a previous test's (or the developer's
    local) query results into this one otherwise (see
    docs/testing_strategy.md section 3.3)."""
    url = f"sqlite:///{tmp_path / 'integration_test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    st.cache_data.clear()
    try:
        yield
    finally:
        engine.dispose()
        st.cache_data.clear()
