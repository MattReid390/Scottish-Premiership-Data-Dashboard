"""Elo rating model (see docs/analysis_methodology.md section 6.1).

Processes every played match across every loaded season in chronological
order, carrying ratings across season boundaries with partial regression
toward the baseline rating. Ratings are a relative-strength signal
independent of raw league position, not something stored as an
authoritative Match/Team field - callers recompute the full history from
the database whenever they need current or historical values (see
src/dashboard/data_access.py's caching for how this stays fast enough for
the dashboard).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.database.models import Match
from src.utils.config import load_app_config

DEFAULT_INITIAL_RATING = 1500.0
DEFAULT_K_FACTOR = 20.0
DEFAULT_HOME_ADVANTAGE = 60.0
DEFAULT_CARRY_OVER_FACTOR = 0.75


@dataclass(frozen=True)
class EloConfig:
    initial_rating: float = DEFAULT_INITIAL_RATING
    k_factor: float = DEFAULT_K_FACTOR
    home_advantage: float = DEFAULT_HOME_ADVANTAGE
    carry_over_factor: float = DEFAULT_CARRY_OVER_FACTOR

    @classmethod
    def from_app_config(cls, app_config: dict[str, Any] | None = None) -> EloConfig:
        app_config = app_config if app_config is not None else load_app_config()
        elo_config = app_config.get("ratings", {}).get("elo", {})
        return cls(
            initial_rating=elo_config.get("initial_rating", DEFAULT_INITIAL_RATING),
            k_factor=elo_config.get("k_factor", DEFAULT_K_FACTOR),
            home_advantage=elo_config.get(
                "home_advantage_offset", DEFAULT_HOME_ADVANTAGE
            ),
            carry_over_factor=elo_config.get(
                "season_carry_over_factor", DEFAULT_CARRY_OVER_FACTOR
            ),
        )


@dataclass(frozen=True)
class EloRatingPoint:
    team_id: int
    season_label: str
    match_date: dt.date
    rating_before: float
    rating_after: float


def _expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def compute_elo_history(
    session: Session, *, config: EloConfig | None = None
) -> list[EloRatingPoint]:
    """Compute an Elo rating point for every team after every played match,
    across every loaded season in chronological order."""
    config = config or EloConfig()
    matches = list(
        session.scalars(
            select(Match)
            .options(joinedload(Match.season))
            .where(Match.status == "played")
            .order_by(Match.match_date)
        )
    )

    ratings: dict[int, float] = {}
    current_season_label: str | None = None
    history: list[EloRatingPoint] = []

    for match in matches:
        if match.season.label != current_season_label:
            # New season: regress every team already seen toward the
            # baseline. A team appearing for the first time (e.g. newly
            # promoted, or the very first ingested season) has no prior
            # rating to regress and simply starts at the baseline via
            # dict.setdefault below.
            for team_id in list(ratings):
                ratings[team_id] = config.initial_rating + config.carry_over_factor * (
                    ratings[team_id] - config.initial_rating
                )
            current_season_label = match.season.label

        home_rating = ratings.setdefault(match.home_team_id, config.initial_rating)
        away_rating = ratings.setdefault(match.away_team_id, config.initial_rating)

        assert match.home_goals is not None and match.away_goals is not None
        if match.home_goals > match.away_goals:
            home_actual, away_actual = 1.0, 0.0
        elif match.home_goals < match.away_goals:
            home_actual, away_actual = 0.0, 1.0
        else:
            home_actual = away_actual = 0.5

        home_expected = _expected_score(
            home_rating + config.home_advantage, away_rating
        )
        away_expected = 1.0 - home_expected

        new_home_rating = home_rating + config.k_factor * (home_actual - home_expected)
        new_away_rating = away_rating + config.k_factor * (away_actual - away_expected)

        history.append(
            EloRatingPoint(
                match.home_team_id,
                match.season.label,
                match.match_date,
                home_rating,
                new_home_rating,
            )
        )
        history.append(
            EloRatingPoint(
                match.away_team_id,
                match.season.label,
                match.match_date,
                away_rating,
                new_away_rating,
            )
        )

        ratings[match.home_team_id] = new_home_rating
        ratings[match.away_team_id] = new_away_rating

    return history


def latest_ratings(history: list[EloRatingPoint]) -> dict[int, float]:
    """The most recent rating_after per team from a chronological history."""
    latest: dict[int, float] = {}
    for point in history:
        latest[point.team_id] = point.rating_after
    return latest


def ratings_as_of(history: list[EloRatingPoint], season_label: str) -> dict[int, float]:
    """The most recent rating_after per team within a single season, i.e.
    end-of-season ratings for back-testing (see section 6.3)."""
    latest: dict[int, float] = {}
    for point in history:
        if point.season_label == season_label:
            latest[point.team_id] = point.rating_after
    return latest
