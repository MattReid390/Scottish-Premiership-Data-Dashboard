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
from sqlalchemy import or_, select

from src.analysis.elo import EloConfig, compute_elo_history
from src.analysis.form import compute_form_guides_for_season
from src.analysis.standings import compute_league_table, get_played_matches
from src.database.models import Match, Season, Team
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


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def list_all_teams() -> pd.DataFrame:
    """Every team that has ever appeared in a loaded match, for selectors
    (Head-to-Head, cross-season comparison) that aren't scoped to one
    season's roster."""
    with session_scope() as session:
        teams = session.scalars(select(Team).order_by(Team.name)).all()
        return pd.DataFrame([{"team_id": t.team_id, "name": t.name} for t in teams])


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_season_matches_table(season_id: int) -> pd.DataFrame:
    """Every played match in a season, for the Match Explorer page."""
    with session_scope() as session:
        matches = get_played_matches(session, season_id)
        rows: list[dict[str, Any]] = []
        for m in matches:
            assert m.home_goals is not None and m.away_goals is not None
            if m.home_goals > m.away_goals:
                result = "Home win"
            elif m.home_goals < m.away_goals:
                result = "Away win"
            else:
                result = "Draw"
            rows.append(
                {
                    "Date": m.match_date,
                    "Home": m.home_team.name,
                    "Away": m.away_team.name,
                    "Score": f"{m.home_goals}-{m.away_goals}",
                    "Result": result,
                    "TotalGoals": m.home_goals + m.away_goals,
                }
            )
    return pd.DataFrame(rows)


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_league_goals_trend(season_id: int, *, rolling_window: int = 10) -> pd.DataFrame:
    """League-wide goals scored per match in date order, with a rolling
    average - the "goals-per-matchweek" trend adapted to match index since
    this data source doesn't provide matchweek numbers (see
    docs/analysis_methodology.md section 2.2)."""
    with session_scope() as session:
        matches = get_played_matches(session, season_id)
        rows = []
        for i, m in enumerate(matches, start=1):
            assert m.home_goals is not None and m.away_goals is not None
            rows.append(
                {
                    "MatchIndex": i,
                    "Date": m.match_date,
                    "Goals": m.home_goals + m.away_goals,
                }
            )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["RollingAvgGoals"] = (
            df["Goals"].rolling(window=rolling_window, min_periods=1).mean()
        )
    return df


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_points_progression_all_teams(season_id: int) -> pd.DataFrame:
    """Long-format cumulative points per team by that team's own match
    number, for a multi-line season-progression chart."""
    with session_scope() as session:
        matches = get_played_matches(session, season_id)
        team_names: dict[int, str] = {}
        cumulative: dict[int, int] = {}
        match_count: dict[int, int] = {}
        rows: list[dict[str, Any]] = []
        for m in matches:
            assert m.home_goals is not None and m.away_goals is not None
            team_names[m.home_team_id] = m.home_team.name
            team_names[m.away_team_id] = m.away_team.name
            if m.home_goals > m.away_goals:
                home_points, away_points = 3, 0
            elif m.home_goals < m.away_goals:
                home_points, away_points = 0, 3
            else:
                home_points = away_points = 1
            for team_id, points in (
                (m.home_team_id, home_points),
                (m.away_team_id, away_points),
            ):
                cumulative[team_id] = cumulative.get(team_id, 0) + points
                match_count[team_id] = match_count.get(team_id, 0) + 1
                rows.append(
                    {
                        "Team": team_names[team_id],
                        "MatchNumber": match_count[team_id],
                        "Date": m.match_date,
                        "CumulativePoints": cumulative[team_id],
                    }
                )
    return pd.DataFrame(rows)


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_position_over_time(season_id: int) -> pd.DataFrame:
    """Long-format league position per team as of each distinct matchday
    (date) in the season, for a position-over-time chart. Date-based
    rather than matchweek-based - see docs/analysis_methodology.md
    section 2.2."""
    with session_scope() as session:
        matches = get_played_matches(session, season_id)
        distinct_dates = sorted({m.match_date for m in matches})
        rows: list[dict[str, Any]] = []
        for as_of_date in distinct_dates:
            standings = compute_league_table(
                session, season_id, as_of_date=as_of_date, matches=matches
            )
            for s in standings:
                if s.played == 0:
                    continue
                rows.append(
                    {"Team": s.display_name, "Date": as_of_date, "Position": s.position}
                )
    return pd.DataFrame(rows)


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_elo_trend_for_season(
    season_id: int, team_ids: tuple[int, ...] | None = None
) -> pd.DataFrame:
    """Long-format Elo rating over time, restricted to one season's date
    range (ratings still carry continuity from earlier seasons - see
    src/analysis/elo.py) and optionally to a subset of teams."""
    with session_scope() as session:
        season = session.get(Season, season_id)
        if season is None:
            return pd.DataFrame()
        history = compute_elo_history(session, config=EloConfig())
        team_names = {t.team_id: t.name for t in session.scalars(select(Team))}

    rows = [
        {
            "Team": team_names.get(point.team_id, str(point.team_id)),
            "Date": point.match_date,
            "Rating": point.rating_after,
        }
        for point in history
        if point.season_label == season.label
        and (team_ids is None or point.team_id in team_ids)
    ]
    return pd.DataFrame(rows)


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_cross_season_ppg(team_id: int) -> pd.DataFrame:
    """A team's points-per-game in every season it has played in."""
    with session_scope() as session:
        seasons = session.scalars(select(Season).order_by(Season.start_date)).all()
        rows = []
        for season in seasons:
            standings = compute_league_table(session, season.season_id)
            entry = next((s for s in standings if s.team_id == team_id), None)
            if entry is not None and entry.played > 0:
                rows.append(
                    {
                        "Season": season.label,
                        "PointsPerGame": round(entry.points / entry.played, 2),
                        "Played": entry.played,
                    }
                )
    return pd.DataFrame(rows)


@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def get_head_to_head(team_a_id: int, team_b_id: int) -> dict[str, Any]:
    """Aggregate historical record and recent meetings between two teams,
    across every loaded season (see docs/analysis_methodology.md section 7)."""
    with session_scope() as session:
        matches = list(
            session.scalars(
                select(Match)
                .where(
                    Match.status == "played",
                    or_(
                        (Match.home_team_id == team_a_id)
                        & (Match.away_team_id == team_b_id),
                        (Match.home_team_id == team_b_id)
                        & (Match.away_team_id == team_a_id),
                    ),
                )
                .order_by(Match.match_date)
            )
        )
        team_a = session.get(Team, team_a_id)
        team_b = session.get(Team, team_b_id)
        if team_a is None or team_b is None:
            return {"total_meetings": 0}

        team_a_wins = team_b_wins = draws = 0
        team_a_goals = team_b_goals = 0
        recent_rows: list[dict[str, Any]] = []
        for m in matches:
            assert m.home_goals is not None and m.away_goals is not None
            a_is_home = m.home_team_id == team_a_id
            a_goals = m.home_goals if a_is_home else m.away_goals
            b_goals = m.away_goals if a_is_home else m.home_goals
            team_a_goals += a_goals
            team_b_goals += b_goals
            if a_goals > b_goals:
                team_a_wins += 1
            elif a_goals < b_goals:
                team_b_wins += 1
            else:
                draws += 1
            recent_rows.append(
                {
                    "Date": m.match_date,
                    "Home": m.home_team.name,
                    "Away": m.away_team.name,
                    "Score": f"{m.home_goals}-{m.away_goals}",
                }
            )

        return {
            "team_a_name": team_a.name,
            "team_b_name": team_b.name,
            "total_meetings": len(matches),
            "team_a_wins": team_a_wins,
            "team_b_wins": team_b_wins,
            "draws": draws,
            "team_a_goals": team_a_goals,
            "team_b_goals": team_b_goals,
            "recent_meetings": pd.DataFrame(list(reversed(recent_rows))[:10]),
        }
