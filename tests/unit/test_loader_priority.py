"""Unit tests for source-priority conflict resolution
(src/processing/loader.py). See docs/data_ingestion.md section 2, "Source
priority for conflict resolution".
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from src.database.models import Match, Team
from src.processing.loader import load_normalized_matches
from src.processing.normalize import NormalizedMatch
from src.processing.team_aliases import TeamAliasEntry

_MATCH_DATE = dt.date(2099, 8, 1)


def _make_team(session: Session, canonical_key: str) -> Team:
    team = Team(name=canonical_key.title(), canonical_key=canonical_key)
    session.add(team)
    session.flush()
    return team


def _normalized(
    home: Team, away: Team, home_goals: int, away_goals: int, source: str
) -> NormalizedMatch:
    return NormalizedMatch(
        season_label="2099-00",
        match_date=_MATCH_DATE,
        home_team=TeamAliasEntry(home.canonical_key, home.name),
        away_team=TeamAliasEntry(away.canonical_key, away.name),
        home_goals=home_goals,
        away_goals=away_goals,
        status="played",
        source=source,
    )


def test_higher_priority_source_overwrites_lower_priority(db_session: Session) -> None:
    home = _make_team(db_session, "home_team")
    away = _make_team(db_session, "away_team")

    load_normalized_matches(
        db_session, [_normalized(home, away, 1, 0, "football-data.co.uk")]
    )
    summary = load_normalized_matches(
        db_session, [_normalized(home, away, 3, 3, "spfl.co.uk")]
    )

    match = db_session.query(Match).one()
    assert summary.updated == 1
    assert summary.skipped_lower_priority == 0
    assert (match.home_goals, match.away_goals, match.source) == (3, 3, "spfl.co.uk")


def test_lower_priority_source_cannot_overwrite_higher_priority(
    db_session: Session,
) -> None:
    home = _make_team(db_session, "home_team")
    away = _make_team(db_session, "away_team")

    load_normalized_matches(db_session, [_normalized(home, away, 2, 1, "spfl.co.uk")])
    summary = load_normalized_matches(
        db_session, [_normalized(home, away, 9, 9, "football-data.co.uk")]
    )

    match = db_session.query(Match).one()
    assert summary.updated == 0
    assert summary.skipped_lower_priority == 1
    assert (match.home_goals, match.away_goals, match.source) == (2, 1, "spfl.co.uk")


def test_same_source_updates_normally(db_session: Session) -> None:
    home = _make_team(db_session, "home_team")
    away = _make_team(db_session, "away_team")

    load_normalized_matches(
        db_session, [_normalized(home, away, 1, 1, "football-data.co.uk")]
    )
    summary = load_normalized_matches(
        db_session, [_normalized(home, away, 2, 1, "football-data.co.uk")]
    )

    match = db_session.query(Match).one()
    assert summary.updated == 1
    assert summary.skipped_lower_priority == 0
    assert (match.home_goals, match.away_goals) == (2, 1)
