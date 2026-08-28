"""Unit tests for the Elo rating model (src/analysis/elo.py). See
docs/analysis_methodology.md section 6.1.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from src.analysis.elo import (
    EloConfig,
    compute_elo_history,
    latest_ratings,
    ratings_as_of,
)
from src.database.models import Match, Season, Team


def _make_team(session: Session, canonical_key: str) -> Team:
    team = Team(name=canonical_key.title(), canonical_key=canonical_key)
    session.add(team)
    session.flush()
    return team


def _make_season(session: Session, label: str, start_date: dt.date) -> Season:
    season = Season(
        label=label, start_date=start_date, end_date=start_date + dt.timedelta(days=280)
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


def test_winner_gains_rating_and_loser_loses_rating(db_session: Session) -> None:
    season = _make_season(db_session, "2099-00", dt.date(2099, 8, 1))
    a = _make_team(db_session, "team_a")
    b = _make_team(db_session, "team_b")
    _add_match(db_session, season, a, b, 3, 0, dt.date(2099, 8, 2))

    history = compute_elo_history(db_session, config=EloConfig())
    ratings = latest_ratings(history)

    assert ratings[a.team_id] > EloConfig().initial_rating
    assert ratings[b.team_id] < EloConfig().initial_rating
    # Zero-sum aside from the home-advantage asymmetry: both started equal.
    assert ratings[a.team_id] - EloConfig().initial_rating == -(
        ratings[b.team_id] - EloConfig().initial_rating
    )


def test_draw_between_equal_teams_leaves_ratings_unchanged_aside_from_home_advantage(
    db_session: Session,
) -> None:
    """A draw is exactly the expected outcome when both teams are rated
    equal and home advantage is zero, so ratings shouldn't move at all."""
    season = _make_season(db_session, "2099-00", dt.date(2099, 8, 1))
    a = _make_team(db_session, "team_a")
    b = _make_team(db_session, "team_b")
    _add_match(db_session, season, a, b, 1, 1, dt.date(2099, 8, 2))

    config = EloConfig(home_advantage=0.0)
    history = compute_elo_history(db_session, config=config)
    ratings = latest_ratings(history)

    assert ratings[a.team_id] == config.initial_rating
    assert ratings[b.team_id] == config.initial_rating


def test_season_boundary_regresses_ratings_toward_baseline(db_session: Session) -> None:
    season1 = _make_season(db_session, "2099-00", dt.date(2099, 8, 1))
    season2 = _make_season(db_session, "2100-01", dt.date(2100, 8, 1))
    a = _make_team(db_session, "team_a")
    b = _make_team(db_session, "team_b")

    # A big win pushes team_a well above baseline in season 1.
    _add_match(db_session, season1, a, b, 5, 0, dt.date(2099, 8, 2))
    # A single season-2 match forces the season-boundary regression to run
    # and gives us a rating_before to inspect.
    _add_match(db_session, season2, a, b, 1, 1, dt.date(2100, 8, 2))

    config = EloConfig(carry_over_factor=0.75)
    history = compute_elo_history(db_session, config=config)

    end_of_season1 = ratings_as_of(history, "2099-00")[a.team_id]
    season2_point = next(
        p for p in history if p.season_label == "2100-01" and p.team_id == a.team_id
    )
    expected_regressed = config.initial_rating + config.carry_over_factor * (
        end_of_season1 - config.initial_rating
    )

    assert end_of_season1 > config.initial_rating
    assert season2_point.rating_before == expected_regressed
    # Regression pulls it back toward baseline but not all the way.
    assert config.initial_rating < season2_point.rating_before < end_of_season1


def test_newly_appearing_team_starts_at_baseline(db_session: Session) -> None:
    season = _make_season(db_session, "2099-00", dt.date(2099, 8, 1))
    a = _make_team(db_session, "team_a")
    b = _make_team(db_session, "team_b")
    _add_match(db_session, season, a, b, 2, 1, dt.date(2099, 8, 2))

    config = EloConfig()
    history = compute_elo_history(db_session, config=config)
    first_point_for_a = next(p for p in history if p.team_id == a.team_id)

    assert first_point_for_a.rating_before == config.initial_rating
