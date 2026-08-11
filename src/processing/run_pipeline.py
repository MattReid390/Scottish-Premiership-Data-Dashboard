"""CLI entry point to process the most recently fetched raw file for each
configured season (Phase 1 MVP; see docs/roadmap.md).

Usage:
    python -m src.processing.run_pipeline
    python -m src.processing.run_pipeline --seasons 2022-23 2023-24
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.ingestion.football_data_co_uk import DEFAULT_RAW_DIR
from src.processing.pipeline import QuarantinedFileError, process_raw_file
from src.utils.config import load_app_config
from src.utils.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def _latest_raw_file(season_label: str, raw_dir: Path) -> Path | None:
    season_dir = raw_dir / season_label
    if not season_dir.exists():
        return None
    candidates = sorted(season_dir.glob("*.csv"))
    return candidates[-1] if candidates else None


def run_pipeline(
    season_labels: list[str] | None = None, *, raw_dir: Path = DEFAULT_RAW_DIR
) -> tuple[int, int]:
    """Process each season's latest raw file, continuing past individual
    failures (see docs/data_ingestion.md section 6, "partial failure
    isolation"). Returns (succeeded_count, failed_count)."""
    app_config = load_app_config()
    labels = season_labels or app_config["season"]["backfill_labels"]

    succeeded = 0
    failed = 0
    for label in labels:
        raw_path = _latest_raw_file(label, raw_dir)
        if raw_path is None:
            logger.error(
                "No raw file found for season %s under %s; run "
                "'python -m src.ingestion.backfill_historical' first.",
                label,
                raw_dir / label,
            )
            failed += 1
            continue
        try:
            result = process_raw_file(
                raw_path, season_label=label, app_config=app_config
            )
            print(
                f"{label}: {result.inserted} inserted, {result.updated} updated, "
                f"{result.unchanged} unchanged (from {result.raw_path.name})"
            )
            succeeded += 1
        except QuarantinedFileError as exc:
            logger.error("Season %s failed: %s", label, exc)
            failed += 1

    logger.info("Pipeline run complete: %d succeeded, %d failed.", succeeded, failed)
    return succeeded, failed


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=None,
        metavar="YYYY-YY",
        help="Season labels to process. Defaults to config.yaml's season.backfill_labels.",
    )
    args = parser.parse_args()

    _succeeded, failed = run_pipeline(args.seasons)
    if failed:
        raise SystemExit(f"{failed} season(s) failed to process; see logs for details.")


if __name__ == "__main__":
    main()
