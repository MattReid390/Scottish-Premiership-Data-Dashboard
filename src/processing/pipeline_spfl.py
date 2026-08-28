"""Orchestrates spfl.co.uk raw HTML (already fetched per club) through
parse -> normalize -> dedupe -> load -> ingestion_log. Mirrors
src/processing/pipeline.py's pattern (see docs/data_ingestion.md section 3).

Unlike the football-data.co.uk pipeline (one raw file -> one run), this
combines the latest raw HTML file for every configured club into a single
run, since spfl.co.uk's per-club pages together form one logical snapshot
of current-season results - and since the same match appears on both
participating clubs' pages, results are deduplicated by natural key before
loading (the natural-key upsert in src/processing/loader.py would handle
the duplication correctly either way, but deduplicating first keeps the
run's insert/update counts meaningful rather than double-counted).
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.database.models import IngestionLog
from src.database.session import session_scope
from src.processing.loader import load_normalized_matches
from src.processing.normalize import NormalizedMatch
from src.processing.spfl_parser import (
    SOURCE_NAME,
    SpflParseError,
    normalize_spfl_results,
    parse_club_results_html,
)
from src.processing.team_aliases import UnknownTeamAliasError, load_alias_map
from src.utils.config import load_app_config

logger = logging.getLogger(__name__)

_NOTES_MAX_LENGTH = 500  # ingestion_log.notes is String(512); leave headroom


@dataclass
class SpflProcessingResult:
    clubs_processed: int
    records_parsed: int
    records_deduped: int
    inserted: int
    updated: int
    unchanged: int
    skipped_lower_priority: int
    parse_errors: list[str]


def _deduplicate(matches: list[NormalizedMatch]) -> list[NormalizedMatch]:
    by_natural_key = {
        (
            m.season_label,
            m.home_team.canonical_key,
            m.away_team.canonical_key,
            m.match_date,
        ): m
        for m in matches
    }
    return list(by_natural_key.values())


def _truncate_notes(notes: str) -> str:
    if len(notes) <= _NOTES_MAX_LENGTH:
        return notes
    return notes[: _NOTES_MAX_LENGTH - 3] + "..."


def process_club_raw_files(
    raw_files: dict[str, Path],
    *,
    app_config: dict[str, Any] | None = None,
) -> SpflProcessingResult:
    """raw_files maps team.canonical_key to the path of that club's latest
    fetched results HTML. Parse failures for individual clubs don't abort
    the run - a run still loads and logs whatever parsed successfully,
    marked "partial" rather than "success" (see
    docs/data_ingestion.md section 4.5)."""
    app_config = app_config if app_config is not None else load_app_config()
    run_started_at = dt.datetime.now(dt.UTC)
    alias_map = load_alias_map()

    all_normalized: list[NormalizedMatch] = []
    parse_errors: list[str] = []
    for canonical_key, raw_path in raw_files.items():
        html = raw_path.read_text(encoding="utf-8")
        try:
            raw_results = parse_club_results_html(html, canonical_key)
            all_normalized.extend(
                normalize_spfl_results(raw_results, alias_map=alias_map)
            )
        except (SpflParseError, UnknownTeamAliasError) as exc:
            logger.error(
                "Failed to parse %s results (%s): %s", canonical_key, raw_path, exc
            )
            parse_errors.append(f"{canonical_key}: {exc}")

    deduped = _deduplicate(all_normalized)
    current_season_label = app_config.get("season", {}).get("current_label")

    with session_scope() as session:
        summary = load_normalized_matches(
            session, deduped, current_season_label=current_season_label
        )
        status = "success" if not parse_errors else "partial"
        notes = (
            f"clubs={len(raw_files)} parsed={len(all_normalized)} "
            f"deduped={len(deduped)} inserted={summary.inserted} "
            f"updated={summary.updated} unchanged={summary.unchanged} "
            f"skipped_lower_priority={summary.skipped_lower_priority}"
        )
        if parse_errors:
            notes += " errors=" + "; ".join(parse_errors)
        session.add(
            IngestionLog(
                source=SOURCE_NAME,
                run_started_at=run_started_at,
                run_finished_at=dt.datetime.now(dt.UTC),
                status=status,
                records_fetched=len(all_normalized),
                records_loaded=summary.inserted + summary.updated,
                notes=_truncate_notes(notes),
            )
        )

    logger.info(
        "SPFL processing complete: %d clubs, %d parsed, %d deduped -> "
        "%d inserted, %d updated, %d unchanged, %d skipped (lower priority).",
        len(raw_files),
        len(all_normalized),
        len(deduped),
        summary.inserted,
        summary.updated,
        summary.unchanged,
        summary.skipped_lower_priority,
    )
    return SpflProcessingResult(
        clubs_processed=len(raw_files),
        records_parsed=len(all_normalized),
        records_deduped=len(deduped),
        inserted=summary.inserted,
        updated=summary.updated,
        unchanged=summary.unchanged,
        skipped_lower_priority=summary.skipped_lower_priority,
        parse_errors=parse_errors,
    )
