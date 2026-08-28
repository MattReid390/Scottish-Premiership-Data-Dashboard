"""Parsing and normalization of spfl.co.uk's per-club results HTML (see
docs/data_ingestion.md sections 4.2-4.3).

The markup was verified directly against the live site while building this
module (2026-08-28): each `div.fixtures-list__group` is either a played
result (has a `.fixtures-list__results` child with two
`.fixtures-list__results__team` spans and one `.fixtures-list__results__score`
span) or an upcoming fixture (a `<dl class="fixtures-list__group__fixtures">`
instead, with no score) - only the former is parsed here. A club plays
multiple competitions concurrently (league, cups), so groups are filtered
to ones whose `.fixtures-list__group__title` contains "premiership"
(case-insensitive, robust to the title's sponsor-name prefix changing
season to season, e.g. "William Hill Premiership").
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from src.processing.normalize import NormalizedMatch
from src.processing.team_aliases import TeamAliasEntry, resolve_team_alias
from src.utils.season_dates import infer_season_label

SOURCE_NAME = "spfl.co.uk"

_DATE_RE = re.compile(r"^\w+\s+(\d{1,2})(?:st|nd|rd|th)\s+(\w+)\s+(\d{4})$")
_SCORE_RE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


class SpflParseError(ValueError):
    """Raised when a club's results page doesn't match the expected markup
    shape, or a date/score within it can't be parsed."""


@dataclass(frozen=True)
class RawSpflResult:
    match_date: dt.date
    home_team_name: str
    away_team_name: str
    home_goals: int
    away_goals: int


def parse_spfl_date(raw: str) -> dt.date:
    """Parse spfl.co.uk's "Saturday 22nd August 2026" style date text."""
    match = _DATE_RE.match(raw.strip())
    if not match:
        raise SpflParseError(f"Could not parse SPFL date {raw!r}.")
    day, month_name, year = match.groups()
    try:
        return dt.datetime.strptime(  # noqa: DTZ007 (calendar date only; no time/tz to attach)
            f"{day} {month_name} {year}", "%d %B %Y"
        ).date()
    except ValueError as exc:
        raise SpflParseError(f"Could not parse SPFL date {raw!r}: {exc}") from exc


def _parse_score(raw: str) -> tuple[int, int]:
    match = _SCORE_RE.match(raw.strip())
    if not match:
        raise SpflParseError(f"Could not parse SPFL score {raw!r}.")
    home_goals, away_goals = match.groups()
    return int(home_goals), int(away_goals)


def parse_club_results_html(html: str, club_canonical_key: str) -> list[RawSpflResult]:
    """Extract played Premiership results from one club's raw results page."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[RawSpflResult] = []

    for group in soup.select("div.fixtures-list__group"):
        title_el = group.select_one(".fixtures-list__group__title")
        day_el = group.select_one(".fixtures-list__group__day")
        results_el = group.select_one(".fixtures-list__results")
        if title_el is None or day_el is None or results_el is None:
            continue  # an upcoming-fixture group, or an unrecognised layout
        if "premiership" not in title_el.get_text(strip=True).lower():
            continue

        team_spans = results_el.select(".fixtures-list__results__team")
        score_span = results_el.select_one(".fixtures-list__results__score")
        if len(team_spans) != 2 or score_span is None:
            raise SpflParseError(
                f"Unexpected results markup for {club_canonical_key} on "
                f"{day_el.get_text(strip=True)!r}: expected 2 teams and a score."
            )

        match_date = parse_spfl_date(day_el.get_text(strip=True))
        home_goals, away_goals = _parse_score(score_span.get_text(strip=True))
        results.append(
            RawSpflResult(
                match_date=match_date,
                home_team_name=team_spans[0].get_text(strip=True),
                away_team_name=team_spans[1].get_text(strip=True),
                home_goals=home_goals,
                away_goals=away_goals,
            )
        )
    return results


def normalize_spfl_results(
    raw_results: list[RawSpflResult], *, alias_map: dict[str, TeamAliasEntry]
) -> list[NormalizedMatch]:
    """Resolve team names and infer each result's season, producing the
    same NormalizedMatch shape src/processing/loader.py already loads from
    football-data.co.uk (see src/processing/normalize.py)."""
    normalized = []
    for r in raw_results:
        normalized.append(
            NormalizedMatch(
                season_label=infer_season_label(r.match_date),
                match_date=r.match_date,
                home_team=resolve_team_alias(r.home_team_name, alias_map),
                away_team=resolve_team_alias(r.away_team_name, alias_map),
                home_goals=r.home_goals,
                away_goals=r.away_goals,
                status="played",
                source=SOURCE_NAME,
            )
        )
    return normalized
