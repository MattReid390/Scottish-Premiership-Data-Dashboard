"""Unit tests for the expected-points model
(src/analysis/expected_points.py). See docs/analysis_methodology.md
section 6.2.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from src.analysis.expected_points import compute_expected_points
from src.database.models import Match, Season, Team

_SEASON_START = dt.date(2099, 8, 1)


def _make_team(session: Session, canonical_key: str) -> Team:
    team = Team(name=canonical_key.title(), canonical_key=canonical_key)
    session.add(team)
    session.flush()
    return team


def _make_season(session: Session) -> Season:
    season = Season(
        label="2099-00", start_date=_SEASON_START, end_date=dt.date(2100, 5, 1)
    )
    session.add(season)
    session.flush()
    return season


def _add_match(
    session: Session,
    season: Season,
    home: Team,
    away: Team,
    home_goals: int,
    away_goals: int,
    match_date: dt.date,
) -> None:
    session.add(
        Match(
            season=season,
            match_date=match_date,
            home_team=home,
            away_team=away,
            home_goals=home_goals,
            away_goals=away_goals,
            status="played",
            source="test",
        )
    )
    session.flush()


def test_stronger_team_gets_higher_expected_points(db_session: Session) -> None:
    """A team that consistently scores more and concedes less than the
    league average should rank above a team with the opposite record."""
    season = _make_season(db_session)
    strong = _make_team(db_session, "strong")
    weak = _make_team(db_session, "weak")
    filler_a = _make_team(db_session, "filler_a")
    filler_b = _make_team(db_session, "filler_b")

    # strong: wins big both home and away.
    _add_match(
        db_session, season, strong, filler_a, 4, 0, _SEASON_START + dt.timedelta(days=1)
    )
    _add_match(
        db_session, season, filler_b, strong, 0, 3, _SEASON_START + dt.timedelta(days=8)
    )
    # weak: loses big both home and away.
    _add_match(
        db_session, season, weak, filler_a, 0, 4, _SEASON_START + dt.timedelta(days=1)
    )
    _add_match(
        db_session, season, filler_b, weak, 3, 0, _SEASON_START + dt.timedelta(days=8)
    )
    # filler_a and filler_b play each other too, so every team has a
    # comparable number of matches for a well-defined league average.
    _add_match(
        db_session,
        season,
        filler_a,
        filler_b,
        1,
        1,
        _SEASON_START + dt.timedelta(days=15),
    )
    _add_match(
        db_session,
        season,
        filler_b,
        filler_a,
        1,
        1,
        _SEASON_START + dt.timedelta(days=22),
    )

    results = {
        r.canonical_key: r
        for r in compute_expected_points(db_session, season.season_id)
    }

    assert (
        results["strong"].expected_points_per_game
        > results["filler_a"].expected_points_per_game
    )
    assert (
        results["filler_a"].expected_points_per_game
        > results["weak"].expected_points_per_game
    )


def test_expected_points_per_game_is_bounded(db_session: Session) -> None:
    """3*P(win) + 1*P(draw) can never exceed 3 (a certain win) or go
    negative, regardless of how lopsided the input goals are."""
    season = _make_season(db_session)
    a = _make_team(db_session, "team_a")
    b = _make_team(db_session, "team_b")
    _add_match(db_session, season, a, b, 9, 0, _SEASON_START + dt.timedelta(days=1))
    _add_match(db_session, season, b, a, 0, 9, _SEASON_START + dt.timedelta(days=8))

    for result in compute_expected_points(db_session, season.season_id):
        assert 0.0 <= result.expected_points_per_game <= 3.0


def test_no_played_matches_returns_empty(db_session: Session) -> None:
    season = _make_season(db_session)
    assert compute_expected_points(db_session, season.season_id) == []
