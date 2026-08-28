"""League table computation (see docs/analysis_methodology.md section 2).

Implementation note on point-in-time reconstruction: the documented design
sketches "table as of matchweek N" (section 2.2), but football-data.co.uk -
the only ingested source so far - doesn't provide round/matchday numbers
(match.matchweek is NULL for every row it loads; see docs/roadmap.md's
Phase 1 processing notes). Point-in-time reconstruction here is therefore
date-based ("table as of a given date") rather than matchweek-based. Once a
source that supplies matchweek is ingested (Phase 2), an as_of_matchweek
variant can be added alongside this one.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analysis.results import ResultTotals
from src.database.models import Match, Team


@dataclass(frozen=True)
class TeamStanding:
    team_id: int
    canonical_key: str
    display_name: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    position: int


def get_played_matches(session: Session, season_id: int) -> list[Match]:
    return list(
        session.scalars(
            select(Match)
            .where(Match.season_id == season_id, Match.status == "played")
            .order_by(Match.match_date)
        )
    )


def compute_league_table(
    session: Session,
    season_id: int,
    *,
    as_of_date: dt.date | None = None,
    matches: list[Match] | None = None,
) -> list[TeamStanding]:
    """Compute the league table for a season.

    With as_of_date=None (the default), includes every played match - i.e.
    the current/full table. With as_of_date set, only matches on or before
    that date count, but every team that plays anywhere in the season still
    appears (at 0 played) if the cutoff is before their first fixture -
    matching how a real table looks before a team's season has started.

    `matches` lets a caller that has already fetched the season's played
    matches (e.g. to also compute form guides) pass them in and avoid a
    second query.
    """
    season_matches = (
        matches if matches is not None else get_played_matches(session, season_id)
    )

    teams_in_season: dict[int, Team] = {}
    for m in season_matches:
        teams_in_season[m.home_team_id] = m.home_team
        teams_in_season[m.away_team_id] = m.away_team

    cutoff_matches = (
        season_matches
        if as_of_date is None
        else [m for m in season_matches if m.match_date <= as_of_date]
    )

    totals: dict[int, ResultTotals] = dict.fromkeys(teams_in_season, ResultTotals())
    for m in cutoff_matches:
        # home_goals/away_goals are nullable at the schema level (for
        # scheduled matches), but status == "played" guarantees both are
        # set (see src/processing/normalize.py's infer_status).
        assert m.home_goals is not None and m.away_goals is not None
        totals[m.home_team_id] = totals[m.home_team_id].with_result(
            m.home_goals, m.away_goals
        )
        totals[m.away_team_id] = totals[m.away_team_id].with_result(
            m.away_goals, m.home_goals
        )

    # Tiebreakers per docs/analysis_methodology.md section 2.1: points, then
    # goal difference, then goals for, then alphabetical by name.
    ordered_team_ids = sorted(
        teams_in_season,
        key=lambda team_id: (
            -totals[team_id].points,
            -totals[team_id].goal_difference,
            -totals[team_id].goals_for,
            teams_in_season[team_id].name,
        ),
    )

    return [
        TeamStanding(
            team_id=team_id,
            canonical_key=teams_in_season[team_id].canonical_key,
            display_name=teams_in_season[team_id].name,
            played=totals[team_id].played,
            wins=totals[team_id].wins,
            draws=totals[team_id].draws,
            losses=totals[team_id].losses,
            goals_for=totals[team_id].goals_for,
            goals_against=totals[team_id].goals_against,
            goal_difference=totals[team_id].goal_difference,
            points=totals[team_id].points,
            position=position,
        )
        for position, team_id in enumerate(ordered_team_ids, start=1)
    ]
