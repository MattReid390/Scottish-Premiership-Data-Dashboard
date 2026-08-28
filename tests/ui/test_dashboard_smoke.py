"""UI smoke tests for the Streamlit dashboard pages (see
docs/testing_strategy.md section 3.3). These assert each page renders
without raising, for both a populated and an empty database - not a
visual/pixel regression check.

Each AppTest.from_file(...) run re-executes the target page's module
top-to-bottom in-process; st.cache_data is a process-wide cache with no
awareness of which DATABASE_URL was active when a cached result was
computed, so every test here goes through the isolated_database fixture
(tests/conftest.py), which clears it - confirmed necessary: without the
clear, a page tested against an empty database first would show stale
"empty" results when re-tested against a populated one.
"""

from __future__ import annotations

import datetime as dt

import pytest
from streamlit.testing.v1 import AppTest

from src.database.models import Match, Season, Team
from src.database.session import session_scope
from src.utils.config import PROJECT_ROOT

# AppTest.from_file resolves relative paths against the file that calls it
# (this test file's directory), not the working directory - absolute paths
# rooted at the project sidestep that entirely.
_DASHBOARD_DIR = PROJECT_ROOT / "src" / "dashboard"
_PAGES = [
    str(_DASHBOARD_DIR / "app.py"),
    str(_DASHBOARD_DIR / "pages" / "1_Team_Profile.py"),
    str(_DASHBOARD_DIR / "pages" / "2_Match_Explorer.py"),
    str(_DASHBOARD_DIR / "pages" / "3_Trends_Analytics.py"),
    str(_DASHBOARD_DIR / "pages" / "4_Head_to_Head.py"),
    str(_DASHBOARD_DIR / "pages" / "5_Data_Quality_Admin.py"),
]

_SEASON_START = dt.date(2099, 8, 1)
# (home_idx, away_idx, home_goals, away_goals, days_after_season_start)
_FIXTURES = [
    (0, 1, 2, 0, 1),
    (2, 3, 1, 1, 1),
    (1, 2, 0, 3, 8),
    (3, 0, 2, 2, 8),
    (0, 2, 1, 1, 15),
    (1, 3, 4, 0, 15),
]


@pytest.fixture
def seeded_database(isolated_database: None) -> None:
    """A small, self-contained dataset sufficient to exercise every page's
    happy path: standings, form, home/away splits, Elo, expected points,
    and head-to-head all need at least a couple of teams with a few played
    matches each."""
    with session_scope() as session:
        season = Season(
            label="2099-00",
            start_date=_SEASON_START,
            end_date=_SEASON_START + dt.timedelta(days=280),
            is_current=True,
        )
        teams = [
            Team(
                name=f"Smoke Team {letter}",
                canonical_key=f"smoke_team_{letter.lower()}",
            )
            for letter in "ABCD"
        ]
        session.add(season)
        session.add_all(teams)
        session.flush()

        for home_idx, away_idx, home_goals, away_goals, days in _FIXTURES:
            session.add(
                Match(
                    season=season,
                    match_date=_SEASON_START + dt.timedelta(days=days),
                    home_team=teams[home_idx],
                    away_team=teams[away_idx],
                    home_goals=home_goals,
                    away_goals=away_goals,
                    status="played",
                    source="test",
                )
            )


@pytest.mark.parametrize("page_path", _PAGES)
def test_page_loads_without_exception_with_data(
    seeded_database: None, page_path: str
) -> None:
    at = AppTest.from_file(page_path, default_timeout=30)
    at.run()
    assert not at.exception


@pytest.mark.parametrize("page_path", _PAGES)
def test_page_loads_without_exception_when_empty(
    isolated_database: None, page_path: str
) -> None:
    at = AppTest.from_file(page_path, default_timeout=30)
    at.run()
    assert not at.exception
