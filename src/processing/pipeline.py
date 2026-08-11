"""Orchestrates one raw file through validate -> normalize -> load ->
ingestion_log (see docs/data_ingestion.md section 3, pipeline architecture).

Every call records exactly one ingestion_log row, whichever stage it fails
at (or "success" if it completes) - per docs/data_ingestion.md section 4.5,
so the dashboard's Data Quality / Admin page never has a silent gap for a
run that raised partway through.
"""

from __future__ import annotations

import datetime as dt
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pandera.errors import SchemaError, SchemaErrors

from src.database.models import IngestionLog
from src.database.session import session_scope
from src.processing.loader import load_normalized_matches
from src.processing.normalize import DateParseError, normalize_football_data_co_uk
from src.processing.schemas import FOOTBALL_DATA_CO_UK_SCHEMA
from src.processing.team_aliases import UnknownTeamAliasError, load_alias_map
from src.utils.config import PROJECT_ROOT, load_app_config

logger = logging.getLogger(__name__)

SOURCE_NAME = "football-data.co.uk"
DEFAULT_QUARANTINE_DIR = PROJECT_ROOT / "data" / "raw" / "_quarantine"
_NOTES_MAX_LENGTH = 500  # ingestion_log.notes is String(512); leave headroom


class QuarantinedFileError(RuntimeError):
    """Raised when a raw file fails schema validation and has been
    quarantined rather than processed further."""


@dataclass
class ProcessingResult:
    season_label: str
    raw_path: Path
    records_fetched: int
    inserted: int
    updated: int
    unchanged: int


def process_raw_file(
    raw_path: Path,
    *,
    season_label: str,
    app_config: dict[str, Any] | None = None,
) -> ProcessingResult:
    """Validate, normalize, and load a single raw football-data.co.uk CSV.

    On validation failure the file is moved to the quarantine directory and
    QuarantinedFileError is raised (see docs/data_ingestion.md section
    4.2). On a normalization failure (unresolvable team name, unparseable
    date), the underlying error is raised unchanged so it's specific and
    actionable. Both cases still record a "failed" ingestion_log row before
    raising.
    """
    app_config = app_config if app_config is not None else load_app_config()
    run_started_at = dt.datetime.now(dt.UTC)
    df = pd.read_csv(raw_path)

    try:
        validated = FOOTBALL_DATA_CO_UK_SCHEMA.validate(df, lazy=True)
    except (SchemaError, SchemaErrors) as exc:
        quarantine_path = _quarantine_file(raw_path, app_config)
        logger.error(
            "Validation failed for %s; moved to %s. Errors: %s",
            raw_path,
            quarantine_path,
            exc,
        )
        _record_ingestion_log(
            status="failed",
            run_started_at=run_started_at,
            records_fetched=len(df),
            records_loaded=0,
            notes=f"season={season_label} validation failed, quarantined to "
            f"{quarantine_path}: {exc}",
        )
        raise QuarantinedFileError(
            f"{raw_path} failed schema validation and was quarantined to {quarantine_path}."
        ) from exc

    try:
        alias_map = load_alias_map()
        normalized = normalize_football_data_co_uk(
            validated,
            season_label=season_label,
            source=SOURCE_NAME,
            alias_map=alias_map,
        )
    except (UnknownTeamAliasError, DateParseError) as exc:
        logger.error("Normalization failed for %s: %s", raw_path, exc)
        _record_ingestion_log(
            status="failed",
            run_started_at=run_started_at,
            records_fetched=len(validated),
            records_loaded=0,
            notes=f"season={season_label} normalization failed: {exc}",
        )
        raise

    current_season_label = app_config.get("season", {}).get("current_label")
    with session_scope() as session:
        summary = load_normalized_matches(
            session, normalized, current_season_label=current_season_label
        )
        session.add(
            IngestionLog(
                source=SOURCE_NAME,
                run_started_at=run_started_at,
                run_finished_at=dt.datetime.now(dt.UTC),
                status="success",
                records_fetched=len(validated),
                records_loaded=summary.inserted + summary.updated,
                notes=_truncate_notes(
                    f"season={season_label} inserted={summary.inserted} "
                    f"updated={summary.updated} unchanged={summary.unchanged} "
                    f"raw_file={raw_path.name}"
                ),
            )
        )

    logger.info(
        "Processed %s (season %s): %d inserted, %d updated, %d unchanged.",
        raw_path,
        season_label,
        summary.inserted,
        summary.updated,
        summary.unchanged,
    )
    return ProcessingResult(
        season_label=season_label,
        raw_path=raw_path,
        records_fetched=len(validated),
        inserted=summary.inserted,
        updated=summary.updated,
        unchanged=summary.unchanged,
    )


def _truncate_notes(notes: str) -> str:
    if len(notes) <= _NOTES_MAX_LENGTH:
        return notes
    return notes[: _NOTES_MAX_LENGTH - 3] + "..."


def _record_ingestion_log(
    *,
    status: str,
    run_started_at: dt.datetime,
    records_fetched: int | None,
    records_loaded: int | None,
    notes: str,
) -> None:
    with session_scope() as session:
        session.add(
            IngestionLog(
                source=SOURCE_NAME,
                run_started_at=run_started_at,
                run_finished_at=dt.datetime.now(dt.UTC),
                status=status,
                records_fetched=records_fetched,
                records_loaded=records_loaded,
                notes=_truncate_notes(notes),
            )
        )


def _quarantine_file(raw_path: Path, app_config: dict[str, Any]) -> Path:
    configured = app_config.get("ingestion", {}).get("quarantine_dir")
    quarantine_dir = Path(configured) if configured else DEFAULT_QUARANTINE_DIR
    if not quarantine_dir.is_absolute():
        quarantine_dir = PROJECT_ROOT / quarantine_dir
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    destination = quarantine_dir / raw_path.name
    shutil.move(str(raw_path), str(destination))
    return destination
