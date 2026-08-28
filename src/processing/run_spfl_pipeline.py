"""CLI entry point to process the most recently fetched spfl.co.uk raw
file for each configured club (Phase 2; see docs/roadmap.md).

Usage:
    python -m src.processing.run_spfl_pipeline
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.ingestion.fetch_spfl_current_season import load_club_slugs
from src.ingestion.spfl import DEFAULT_RAW_DIR
from src.processing.pipeline_spfl import process_club_raw_files
from src.utils.config import load_app_config
from src.utils.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def _latest_raw_file(canonical_key: str, raw_dir: Path) -> Path | None:
    club_dir = raw_dir / canonical_key
    if not club_dir.exists():
        return None
    candidates = sorted(club_dir.glob("*.html"))
    return candidates[-1] if candidates else None


def run_spfl_pipeline(*, raw_dir: Path = DEFAULT_RAW_DIR) -> None:
    app_config = load_app_config()
    slugs = load_club_slugs()

    raw_files: dict[str, Path] = {}
    missing: list[str] = []
    for canonical_key in slugs:
        raw_path = _latest_raw_file(canonical_key, raw_dir)
        if raw_path is None:
            missing.append(canonical_key)
        else:
            raw_files[canonical_key] = raw_path

    if missing:
        logger.warning(
            "No raw file found for %d club(s) (%s); run "
            "'python -m src.ingestion.fetch_spfl_current_season' first.",
            len(missing),
            ", ".join(missing),
        )
    if not raw_files:
        raise SystemExit(
            "No SPFL raw files found for any configured club; nothing to process."
        )

    result = process_club_raw_files(raw_files, app_config=app_config)
    print(
        f"Processed {result.clubs_processed} clubs: {result.records_parsed} parsed "
        f"({result.records_deduped} after dedup) -> {result.inserted} inserted, "
        f"{result.updated} updated, {result.unchanged} unchanged, "
        f"{result.skipped_lower_priority} skipped (lower priority)."
    )
    if result.parse_errors:
        print(
            f"{len(result.parse_errors)} club(s) failed to parse; see logs for details."
        )


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run_spfl_pipeline()


if __name__ == "__main__":
    main()
