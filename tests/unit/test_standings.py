"""Unit tests for the league table engine (src/analysis/standings.py).
See docs/analysis_methodology.md section 2 and
docs/testing_strategy.md section 3.1.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from src.analysis.standings import compute_league_table
from src.database.models import Match, Season, Team

_SEASON_START = dt.date(2099, 8, 1)


def _make_team(session: Session, canonical_key: str, name: str | None = None) -> Team:
    team = Team(name=name or canonical_key.title(), canonical_key=canonical_key)
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


def test_basic_table_computation(db_session: Session) -> None:
    season = _make_season(db_session)
    a = _make_team(db_session, "team_a")
    b = _make_team(db_session, "team_b")

    _add_match(db_session, season, a, b, 3, 1, _SEASON_START + dt.timedelta(days=1))
    _add_match(db_session, season, b, a, 0, 0, _SEASON_START + dt.timedelta(days=8))

    standings = {
        s.canonical_key: s for s in compute_league_table(db_session, season.season_id)
    }

    assert standings["team_a"].played == 2
    assert standings["team_a"].wins == 1
    assert standings["team_a"].draws == 1
    assert standings["team_a"].losses == 0
    assert standings["team_a"].goals_for == 3
    assert standings["team_a"].goals_against == 1
    assert standings["team_a"].goal_difference == 2
    assert standings["team_a"].points == 4
    assert standings["team_a"].position == 1

    assert standings["team_b"].points == 1
    assert standings["team_b"].position == 2


def test_three_way_tiebreaker_by_goal_difference_then_goals_for(
    db_session: Session,
) -> None:
    """docs/testing_strategy.md section 3.1 calls for "a specific test case
    for a 3-way points/GD tie" - three teams finish on identical points (one
    win each) but distinct goal difference / goals-for, exercising every
    tiebreaker level in docs/analysis_methodology.md section 2.1."""
    season = _make_season(db_session)
    alpha = _make_team(db_session, "alpha")
    bravo = _make_team(db_session, "bravo")
    charlie = _make_team(db_session, "charlie")
    fodder = _make_team(db_session, "fodder")

    _add_match(
        db_session, season, alpha, fodder, 4, 0, _SEASON_START + dt.timedelta(days=1)
    )
    _add_match(
        db_session, season, bravo, fodder, 2, 0, _SEASON_START + dt.timedelta(days=2)
    )
    _add_match(
        db_session, season, charlie, fodder, 1, 0, _SEASON_START + dt.timedelta(days=3)
    )

    table = compute_league_table(db_session, season.season_id)
    ordered = [s.canonical_key for s in table if s.canonical_key != "fodder"]

    assert ordered == ["alpha", "bravo", "charlie"]


def test_alphabetical_final_tiebreaker(db_session: Session) -> None:
    """Identical points, GD, and GF for both teams - only name should
    break the tie (docs/analysis_methodology.md section 2.1)."""
    season = _make_season(db_session)
    zeta = _make_team(db_session, "zeta", name="Zeta FC")
    alpha = _make_team(db_session, "alpha_team", name="Alpha FC")
    fodder = _make_team(db_session, "fodder")

    _add_match(
        db_session, season, zeta, fodder, 2, 0, _SEASON_START + dt.timedelta(days=1)
    )
    _add_match(
        db_session, season, alpha, fodder, 2, 0, _SEASON_START + dt.timedelta(days=2)
    )

    table = compute_league_table(db_session, season.season_id)
    ordered = [s.display_name for s in table if s.canonical_key != "fodder"]

    assert ordered == ["Alpha FC", "Zeta FC"]


def test_point_in_time_reconstruction(db_session: Session) -> None:
    """docs/analysis_methodology.md section 2.2: a cutoff before any match
    still lists every team in the season, at 0 played."""
    season = _make_season(db_session)
    a = _make_team(db_session, "team_a")
    b = _make_team(db_session, "team_b")

    match_date = _SEASON_START + dt.timedelta(days=9)
    _add_match(db_session, season, a, b, 2, 0, match_date)

    before = compute_league_table(
        db_session, season.season_id, as_of_date=_SEASON_START
    )
    assert {s.canonical_key for s in before} == {"team_a", "team_b"}
    assert all(s.played == 0 and s.points == 0 for s in before)

    after = compute_league_table(db_session, season.season_id, as_of_date=match_date)
    winner = next(s for s in after if s.canonical_key == "team_a")
    assert winner.played == 1
    assert winner.points == 3
    assert winner.goal_difference == 2
