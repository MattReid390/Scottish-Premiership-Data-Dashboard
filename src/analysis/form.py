"""Rolling form guide calculation (see docs/analysis_methodology.md
section 3). Same date-based point-in-time caveat as standings.py applies:
this source doesn't provide matchweek, so "as of" means "as of a date".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analysis.results import RESULT_POINTS, result_letter
from src.database.models import Match

DEFAULT_FORM_WINDOW = 5


@dataclass(frozen=True)
class FormGuide:
    team_id: int
    results: list[str]  # e.g. ["L", "D", "W", "W", "W"], most recent last
    matches_considered: int

    @property
    def points(self) -> int:
        return sum(RESULT_POINTS[r] for r in self.results)

    @property
    def points_per_game(self) -> float:
        if self.matches_considered == 0:
            return 0.0
        return self.points / self.matches_considered


def _result_for_team(match: Match, team_id: int) -> str:
    # home_goals/away_goals are nullable at the schema level (for scheduled
    # matches); callers only pass played matches here, which guarantees
    # both are set (see src/processing/normalize.py's infer_status).
    assert match.home_goals is not None and match.away_goals is not None
    if match.home_team_id == team_id:
        return result_letter(match.home_goals, match.away_goals)
    return result_letter(match.away_goals, match.home_goals)


def compute_form_guide(
    team_matches: list[Match], team_id: int, *, window: int = DEFAULT_FORM_WINDOW
) -> FormGuide:
    """Compute form from an already date-ordered list of one team's played
    matches (ascending by date). Only the most recent `window` are used."""
    recent = team_matches[-window:] if window > 0 else team_matches
    results = [_result_for_team(m, team_id) for m in recent]
    return FormGuide(team_id=team_id, results=results, matches_considered=len(results))


def compute_form_guides_for_season(
    session: Session,
    season_id: int,
    *,
    as_of_date: dt.date | None = None,
    window: int = DEFAULT_FORM_WINDOW,
    matches: list[Match] | None = None,
) -> dict[int, FormGuide]:
    """Compute a form guide for every team that has played in the season,
    as of a given date (defaults to the season's most recent played match).

    `matches` lets a caller that has already fetched the season's played
    matches pass them in and avoid a second query.
    """
    if matches is None:
        query = select(Match).where(
            Match.season_id == season_id, Match.status == "played"
        )
        if as_of_date is not None:
            query = query.where(Match.match_date <= as_of_date)
        season_matches = list(session.scalars(query.order_by(Match.match_date)))
    else:
        season_matches = (
            matches
            if as_of_date is None
            else [m for m in matches if m.match_date <= as_of_date]
        )

    matches_by_team: dict[int, list[Match]] = {}
    for m in season_matches:
        matches_by_team.setdefault(m.home_team_id, []).append(m)
        matches_by_team.setdefault(m.away_team_id, []).append(m)

    return {
        team_id: compute_form_guide(team_matches, team_id, window=window)
        for team_id, team_matches in matches_by_team.items()
    }
