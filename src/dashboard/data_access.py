"""Cached data-access helpers for the Streamlit dashboard (see
docs/visualisation_plan.md). Streamlit reruns the whole page script on
every interaction, so these wrap DB/analysis queries in st.cache_data to
keep pages responsive; each materializes results into plain
dicts/DataFrames before its session closes, so nothing ORM-attached
leaks past the `with` block into the (picklable, hashable) cache.

Phase 1 note: docs/visualisation_plan.md section 2 describes pages
reading precomputed summary tables (team_season_stats) rather than
recomputing live. At this data volume (a few hundred matches per season)
recomputing on every cache miss is simple and fast enough; a persisted
summary table is deferred until/unless it's actually needed (see
docs/roadmap.md).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import select

from src.analysis.form import compute_form_guides_for_season
from src.analysis.standings import compute_league_table, get_played_matches
from src.database.models import Season
from src.database.session import session_scope

_CACHE_TTL_SECONDS = 60


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def list_seasons() -> pd.DataFrame:
    with session_scope() as session:
        seasons = session.scalars(
            select(Season).order_by(Season.start_date.desc())
        ).all()
        return pd.DataFrame(
            [
                {
                    "season_id": s.season_id,
                    "label": s.label,
                    "start_date": s.start_date,
                    "end_date": s.end_date,
                    "is_current": s.is_current,
                }
                for s in seasons
            ]
        )


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_season_date_range(season_id: int) -> tuple[dt.date, dt.date] | None:
    with session_scope() as session:
        season = session.get(Season, season_id)
        if season is None or season.end_date is None:
            return None
        return season.start_date, season.end_date


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_standings_table(
    season_id: int, as_of_date: dt.date | None = None
) -> pd.DataFrame:
    with session_scope() as session:
        matches = get_played_matches(session, season_id)
        standings = compute_league_table(
            session, season_id, as_of_date=as_of_date, matches=matches
        )
        form_map = compute_form_guides_for_season(
            session, season_id, as_of_date=as_of_date, matches=matches
        )
        rows = [
            {
                "Pos": s.position,
                "Team": s.display_name,
                "team_id": s.team_id,
                "P": s.played,
                "W": s.wins,
                "D": s.draws,
                "L": s.losses,
                "GF": s.goals_for,
                "GA": s.goals_against,
                "GD": s.goal_difference,
                "Pts": s.points,
                "Form": (
                    "".join(form_map[s.team_id].results)
                    if s.team_id in form_map
                    else ""
                ),
            }
            for s in standings
        ]
    return pd.DataFrame(rows)


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def list_teams_for_season(season_id: int) -> pd.DataFrame:
    with session_scope() as session:
        matches = get_played_matches(session, season_id)
        teams: dict[int, str] = {}
        for m in matches:
            teams[m.home_team_id] = m.home_team.name
            teams[m.away_team_id] = m.away_team.name
    team_rows = sorted(teams.items(), key=lambda item: item[1])
    return pd.DataFrame([{"team_id": tid, "name": name} for tid, name in team_rows])


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_team_summary(season_id: int, team_id: int) -> dict[str, Any] | None:
    """This team's row from the full-season table (position, points, etc.)."""
    with session_scope() as session:
        standings = compute_league_table(session, season_id)
    for s in standings:
        if s.team_id == team_id:
            return {
                "display_name": s.display_name,
                "position": s.position,
                "played": s.played,
                "points": s.points,
                "goal_difference": s.goal_difference,
                "teams_in_table": len(standings),
            }
    return None


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_team_matches(season_id: int, team_id: int) -> pd.DataFrame:
    """One row per played match involving this team, date-ordered, with a
    running cumulative-points column for the season-progression chart."""
    with session_scope() as session:
        matches = get_played_matches(session, season_id)
        rows: list[dict[str, Any]] = []
        cumulative_points = 0
        for m in matches:
            if m.home_team_id != team_id and m.away_team_id != team_id:
                continue
            is_home = m.home_team_id == team_id
            assert m.home_goals is not None and m.away_goals is not None
            goals_for = m.home_goals if is_home else m.away_goals
            goals_against = m.away_goals if is_home else m.home_goals
            opponent = m.away_team.name if is_home else m.home_team.name
            if goals_for > goals_against:
                result, points = "W", 3
            elif goals_for < goals_against:
                result, points = "L", 0
            else:
                result, points = "D", 1
            cumulative_points += points
            rows.append(
                {
                    "Date": m.match_date,
                    "Venue": "Home" if is_home else "Away",
                    "Opponent": opponent,
                    "Score": f"{goals_for}-{goals_against}",
                    "Result": result,
                    "GF": goals_for,
                    "GA": goals_against,
                    "Points": points,
                    "CumulativePoints": cumulative_points,
                    "MatchNumber": len(rows) + 1,
                }
            )
    return pd.DataFrame(rows)
