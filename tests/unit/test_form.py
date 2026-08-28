"""Unit tests for the rolling form guide (src/analysis/form.py). See
docs/analysis_methodology.md section 3 and docs/testing_strategy.md
section 3.1 ("verify rolling-window form output for teams with fewer
matches than the window size").
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from src.analysis.form import DEFAULT_FORM_WINDOW, compute_form_guides_for_season
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


def test_form_guide_keeps_only_the_most_recent_window(db_session: Session) -> None:
    season = _make_season(db_session)
    team_a = _make_team(db_session, "team_a")
    team_b = _make_team(db_session, "team_b")

    # team_a's chronological results, always as the away side against b:
    # W, D, W, W, W, L (6 matches) - the oldest (W) should drop once the
    # window (5) is exceeded.
    away_goals_for_a = [3, 1, 2, 1, 4, 0]
    home_goals_for_b = [1, 1, 0, 0, 1, 2]
    for i, (ga, gb) in enumerate(zip(away_goals_for_a, home_goals_for_b, strict=True)):
        _add_match(
            db_session,
            season,
            team_b,
            team_a,
            gb,
            ga,
            _SEASON_START + dt.timedelta(days=i * 7),
        )

    forms = compute_form_guides_for_season(db_session, season.season_id)
    form_a = forms[team_a.team_id]

    assert form_a.matches_considered == DEFAULT_FORM_WINDOW
    assert form_a.results == ["D", "W", "W", "W", "L"]
    assert form_a.points == 10
    assert form_a.points_per_game == 2.0


def test_form_guide_with_fewer_matches_than_window(db_session: Session) -> None:
    """Season-start edge case: a team with fewer played matches than the
    window size should report exactly what it has, not pad or error."""
    season = _make_season(db_session)
    team_a = _make_team(db_session, "team_a")
    team_b = _make_team(db_session, "team_b")

    _add_match(
        db_session, season, team_a, team_b, 1, 0, _SEASON_START + dt.timedelta(days=1)
    )
    _add_match(
        db_session, season, team_b, team_a, 2, 2, _SEASON_START + dt.timedelta(days=8)
    )

    forms = compute_form_guides_for_season(db_session, season.season_id)
    form_a = forms[team_a.team_id]

    assert form_a.matches_considered == 2
    assert form_a.results == ["W", "D"]
    assert form_a.points == 4
    assert form_a.points_per_game == 2.0


def test_form_guide_as_of_date_excludes_later_matches(db_session: Session) -> None:
    season = _make_season(db_session)
    team_a = _make_team(db_session, "team_a")
    team_b = _make_team(db_session, "team_b")

    first_match = _SEASON_START + dt.timedelta(days=1)
    second_match = _SEASON_START + dt.timedelta(days=8)
    _add_match(db_session, season, team_a, team_b, 1, 0, first_match)
    _add_match(db_session, season, team_b, team_a, 5, 0, second_match)

    forms = compute_form_guides_for_season(
        db_session, season.season_id, as_of_date=first_match
    )
    form_a = forms[team_a.team_id]

    assert form_a.matches_considered == 1
    assert form_a.results == ["W"]
