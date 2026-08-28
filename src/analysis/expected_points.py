"""Expected-points model (see docs/analysis_methodology.md section 6.2).

A simplified, explainable proxy for a team's underlying performance level,
built from each team's own goals-for/against rates compared to the league
average via a standard football-analytics attack/defense-strength Poisson
model - not derived from shot-level Expected Goals (xG) data, which isn't
available from any source this project ingests.

For each team, attack/defense strength (relative to the league average,
split by home/away since home advantage affects scoring rates) implies an
expected goals rate against a league-average opponent; the expected-points
figure is the average, across a hypothetical home fixture and a
hypothetical away fixture (both vs an average opponent), of 3*P(win) +
1*P(draw) computed from the Poisson distribution over scorelines.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.analysis.standings import get_played_matches
from src.database.models import Match, Team

_MAX_GOALS = (
    10  # Poisson mass beyond this is negligible for realistic football scorelines
)


@dataclass(frozen=True)
class ExpectedPointsResult:
    team_id: int
    canonical_key: str
    display_name: str
    expected_points_per_game: float
    matches_considered: int


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def _match_outcome_expected_points(lam_team: float, lam_opponent: float) -> float:
    win_prob = 0.0
    draw_prob = 0.0
    for team_goals in range(_MAX_GOALS + 1):
        p_team = _poisson_pmf(team_goals, lam_team)
        for opp_goals in range(_MAX_GOALS + 1):
            joint = p_team * _poisson_pmf(opp_goals, lam_opponent)
            if team_goals > opp_goals:
                win_prob += joint
            elif team_goals == opp_goals:
                draw_prob += joint
    return 3.0 * win_prob + 1.0 * draw_prob


def compute_expected_points(
    session: Session, season_id: int, *, matches: list[Match] | None = None
) -> list[ExpectedPointsResult]:
    season_matches = (
        matches if matches is not None else get_played_matches(session, season_id)
    )
    if not season_matches:
        return []

    home_goals_for: dict[int, int] = {}
    home_goals_against: dict[int, int] = {}
    home_played: dict[int, int] = {}
    away_goals_for: dict[int, int] = {}
    away_goals_against: dict[int, int] = {}
    away_played: dict[int, int] = {}
    teams: dict[int, Team] = {}
    total_home_goals = 0
    total_away_goals = 0

    for m in season_matches:
        assert m.home_goals is not None and m.away_goals is not None
        teams[m.home_team_id] = m.home_team
        teams[m.away_team_id] = m.away_team

        home_goals_for[m.home_team_id] = (
            home_goals_for.get(m.home_team_id, 0) + m.home_goals
        )
        home_goals_against[m.home_team_id] = (
            home_goals_against.get(m.home_team_id, 0) + m.away_goals
        )
        home_played[m.home_team_id] = home_played.get(m.home_team_id, 0) + 1

        away_goals_for[m.away_team_id] = (
            away_goals_for.get(m.away_team_id, 0) + m.away_goals
        )
        away_goals_against[m.away_team_id] = (
            away_goals_against.get(m.away_team_id, 0) + m.home_goals
        )
        away_played[m.away_team_id] = away_played.get(m.away_team_id, 0) + 1

        total_home_goals += m.home_goals
        total_away_goals += m.away_goals

    total_matches = len(season_matches)
    league_avg_home_goals = total_home_goals / total_matches
    league_avg_away_goals = total_away_goals / total_matches

    results = []
    for team_id, team in teams.items():
        n_home = home_played.get(team_id, 0)
        n_away = away_played.get(team_id, 0)
        played = n_home + n_away
        if played == 0:
            continue

        attack_home = (
            (home_goals_for.get(team_id, 0) / n_home) / league_avg_home_goals
            if n_home
            else 1.0
        )
        defense_home = (
            (home_goals_against.get(team_id, 0) / n_home) / league_avg_away_goals
            if n_home
            else 1.0
        )
        attack_away = (
            (away_goals_for.get(team_id, 0) / n_away) / league_avg_away_goals
            if n_away
            else 1.0
        )
        defense_away = (
            (away_goals_against.get(team_id, 0) / n_away) / league_avg_home_goals
            if n_away
            else 1.0
        )

        home_fixture_xpts = _match_outcome_expected_points(
            league_avg_home_goals * attack_home, league_avg_away_goals * defense_home
        )
        away_fixture_xpts = _match_outcome_expected_points(
            league_avg_away_goals * attack_away, league_avg_home_goals * defense_away
        )

        results.append(
            ExpectedPointsResult(
                team_id=team_id,
                canonical_key=team.canonical_key,
                display_name=team.name,
                expected_points_per_game=(home_fixture_xpts + away_fixture_xpts) / 2.0,
                matches_considered=played,
            )
        )

    results.sort(key=lambda r: -r.expected_points_per_game)
    return results
