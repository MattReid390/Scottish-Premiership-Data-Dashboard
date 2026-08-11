"""Normalization of validated raw rows into canonical, source-agnostic
match records (see docs/data_ingestion.md section 4.3, "Normalize").

Expects the dataframe to have already passed
src.processing.schemas.FOOTBALL_DATA_CO_UK_SCHEMA validation (so FTHG/FTAG
are coerced to float and nullable there).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

from src.processing.team_aliases import TeamAliasEntry, resolve_team_alias

# football-data.co.uk uses a 4-digit year in recent seasons and a 2-digit
# year in older archives (verified against real fetched data - see
# docs/data_ingestion.md's note on source quirks).
_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y")


class DateParseError(ValueError):
    """Raised when a raw date string doesn't match any known
    football-data.co.uk date format."""


@dataclass(frozen=True)
class NormalizedMatch:
    season_label: str
    match_date: dt.date
    home_team: TeamAliasEntry
    away_team: TeamAliasEntry
    home_goals: int | None
    away_goals: int | None
    status: str
    source: str


def parse_match_date(raw_date: str) -> dt.date:
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(  # noqa: DTZ007 (calendar date only; no time/tz to attach)
                raw_date.strip(), fmt
            ).date()
        except ValueError:
            continue
    raise DateParseError(
        f"Could not parse date {raw_date!r} against any known format {_DATE_FORMATS}."
    )


def infer_status(home_goals: float | None, away_goals: float | None) -> str:
    """A played match has both full-time scores recorded; this historical
    results source doesn't carry postponement/abandonment flags, so
    anything without both scores is treated as not yet played."""
    if pd.notna(home_goals) and pd.notna(away_goals):
        return "played"
    return "scheduled"


def normalize_football_data_co_uk(
    df: pd.DataFrame,
    *,
    season_label: str,
    source: str,
    alias_map: dict[str, TeamAliasEntry],
) -> list[NormalizedMatch]:
    """Convert a validated football-data.co.uk dataframe into canonical
    NormalizedMatch records.

    Raises on any row with an unresolvable team name (UnknownTeamAliasError)
    or unparseable date (DateParseError) rather than skipping it silently -
    both indicate the alias map or date-format assumptions need updating,
    not a match to quietly drop.
    """
    normalized: list[NormalizedMatch] = []
    # to_dict("records") gives plain `Any` values per field; itertuples()'s
    # pandas-stubs typing synthesizes an overly narrow per-row type that
    # doesn't hold up under mypy for heterogeneous columns like these.
    for fields in df.to_dict(orient="records"):
        home_team = resolve_team_alias(str(fields["HomeTeam"]), alias_map)
        away_team = resolve_team_alias(str(fields["AwayTeam"]), alias_map)
        match_date = parse_match_date(str(fields["Date"]))
        fthg, ftag = fields["FTHG"], fields["FTAG"]
        home_goals = int(fthg) if pd.notna(fthg) else None
        away_goals = int(ftag) if pd.notna(ftag) else None
        normalized.append(
            NormalizedMatch(
                season_label=season_label,
                match_date=match_date,
                home_team=home_team,
                away_team=away_team,
                home_goals=home_goals,
                away_goals=away_goals,
                status=infer_status(fthg, ftag),
                source=source,
            )
        )
    return normalized
