"""Upsert-based loading of normalized match records into the database (see
docs/data_ingestion.md section 4.4, "Deduplicate & Upsert").

Matches are upserted on their natural key (season, home team, away team,
date) so re-running the pipeline against the same or corrected raw data
never creates duplicate fixtures - it inserts new matches, updates changed
ones, and leaves unchanged ones alone.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.database.models import Match, Season, Team
from src.processing.normalize import NormalizedMatch

# Lower number = higher priority. See docs/data_ingestion.md section 2,
# "Source priority for conflict resolution": SPFL official is authoritative
# for current-season results; football-data.co.uk is used for historical
# backfill and as a fallback. An unlisted source is treated as lowest
# priority, so a newly added source without an explicit ranking can never
# silently clobber an already-trusted row.
SOURCE_PRIORITY: dict[str, int] = {
    "spfl.co.uk": 0,
    "football-data.co.uk": 1,
}
_UNKNOWN_SOURCE_PRIORITY = 99


def _source_priority(source: str) -> int:
    return SOURCE_PRIORITY.get(source, _UNKNOWN_SOURCE_PRIORITY)


@dataclass
class LoadSummary:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_lower_priority: int = 0


def get_or_create_season(
    session: Session, season_label: str, first_match_date: dt.date
) -> Season:
    season = session.scalar(select(Season).where(Season.label == season_label))
    if season is None:
        season = Season(
            label=season_label, start_date=first_match_date, end_date=first_match_date
        )
        session.add(season)
        session.flush()
    return season


def get_or_create_team(session: Session, canonical_key: str, display_name: str) -> Team:
    team = session.scalar(select(Team).where(Team.canonical_key == canonical_key))
    if team is None:
        team = Team(name=display_name, canonical_key=canonical_key)
        session.add(team)
        session.flush()
    return team


def _widen_season_date_range(season: Season, match_date: dt.date) -> None:
    season.start_date = min(season.start_date, match_date)
    if season.end_date is None or match_date > season.end_date:
        season.end_date = match_date


def _set_current_season(session: Session, season: Season) -> None:
    """Ensure at most one season is flagged current. Enforced here rather
    than by a database constraint, per docs/database_schema.md section 3.1
    ("Exactly one row should be TRUE at a time (enforced at the
    application/processing level)")."""
    if season.is_current:
        return
    session.execute(
        update(Season)
        .where(Season.season_id != season.season_id)
        .values(is_current=False)
    )
    season.is_current = True


def upsert_match(
    session: Session,
    normalized: NormalizedMatch,
    season: Season,
    home_team: Team,
    away_team: Team,
    summary: LoadSummary,
) -> None:
    existing = session.scalar(
        select(Match).where(
            Match.season_id == season.season_id,
            Match.home_team_id == home_team.team_id,
            Match.away_team_id == away_team.team_id,
            Match.match_date == normalized.match_date,
        )
    )
    if existing is None:
        session.add(
            Match(
                season=season,
                match_date=normalized.match_date,
                home_team=home_team,
                away_team=away_team,
                home_goals=normalized.home_goals,
                away_goals=normalized.away_goals,
                status=normalized.status,
                source=normalized.source,
            )
        )
        summary.inserted += 1
        return

    if normalized.source != existing.source and _source_priority(
        normalized.source
    ) > _source_priority(existing.source):
        # Incoming data is from a strictly lower-priority source than
        # what's already recorded for this match; don't let it overwrite a
        # higher-priority source's data (docs/data_ingestion.md section 2).
        summary.skipped_lower_priority += 1
        return

    changed = (
        existing.home_goals != normalized.home_goals
        or existing.away_goals != normalized.away_goals
        or existing.status != normalized.status
    )
    if changed:
        existing.home_goals = normalized.home_goals
        existing.away_goals = normalized.away_goals
        existing.status = normalized.status
        existing.source = normalized.source
        summary.updated += 1
    else:
        summary.unchanged += 1


def load_normalized_matches(
    session: Session,
    matches: list[NormalizedMatch],
    *,
    current_season_label: str | None = None,
) -> LoadSummary:
    summary = LoadSummary()
    seasons: dict[str, Season] = {}
    teams: dict[str, Team] = {}

    for normalized in matches:
        season = seasons.get(normalized.season_label)
        if season is None:
            season = get_or_create_season(
                session, normalized.season_label, normalized.match_date
            )
            seasons[normalized.season_label] = season
            if (
                current_season_label is not None
                and normalized.season_label == current_season_label
            ):
                _set_current_season(session, season)
        _widen_season_date_range(season, normalized.match_date)

        home_team = teams.get(normalized.home_team.canonical_key)
        if home_team is None:
            home_team = get_or_create_team(
                session,
                normalized.home_team.canonical_key,
                normalized.home_team.display_name,
            )
            teams[normalized.home_team.canonical_key] = home_team

        away_team = teams.get(normalized.away_team.canonical_key)
        if away_team is None:
            away_team = get_or_create_team(
                session,
                normalized.away_team.canonical_key,
                normalized.away_team.display_name,
            )
            teams[normalized.away_team.canonical_key] = away_team

        upsert_match(session, normalized, season, home_team, away_team, summary)

    session.flush()
    return summary
