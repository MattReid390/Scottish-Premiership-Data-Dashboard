"""Engine and session construction.

Engines are created lazily and cached per connection URL, rather than at
import time, so tests can point at an isolated SQLite database (e.g.
"sqlite:///:memory:") without touching the default local database file or
environment variables (see docs/testing_strategy.md section 3.2).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.utils.config import get_database_url

_engines: dict[str, Engine] = {}


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_database_url()
    if url not in _engines:
        engine = create_engine(url, future=True)
        if engine.dialect.name == "sqlite":
            _enable_sqlite_foreign_keys(engine)
        _engines[url] = engine
    return _engines[url]


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ignores FOREIGN KEY constraints unless explicitly enabled per
    connection; without this, the schema's referential integrity checks
    (e.g. match.home_team_id -> team.team_id) would be silently unenforced."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection: object, _connection_record: object) -> None:
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(database_url), expire_on_commit=False, future=True
    )


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    """Yield a Session, committing on success and rolling back on error."""
    session = get_session_factory(database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
