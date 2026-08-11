"""CLI entry point to backfill historical seasons from football-data.co.uk
into data/raw/ (Phase 1 MVP; see docs/roadmap.md).

This script only fetches and saves raw CSVs - it does not touch the
database. Loading raw data into the schema is handled by src/processing/
once a source's raw file has been fetched.

Usage:
    python -m src.ingestion.backfill_historical
    python -m src.ingestion.backfill_historical --seasons 2022-23 2023-24
"""

from __future__ import annotations

import argparse
import logging
import time

from src.ingestion.football_data_co_uk import FetchError, FetchResult, fetch_season_csv
from src.utils.config import load_app_config
from src.utils.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def run_historical_backfill(
    season_labels: list[str] | None = None,
) -> list[FetchResult]:
    """Fetch each requested season's CSV, continuing past individual
    failures so one bad/missing season doesn't block the rest (see
    docs/data_ingestion.md section 6, "partial failure isolation")."""
    app_config = load_app_config()
    labels = season_labels or app_config["season"]["backfill_labels"]
    retry_config = app_config.get("ingestion", {}).get("retry", {})
    throttle_config = app_config.get("ingestion", {}).get("request_throttle", {})
    max_attempts = retry_config.get("max_attempts", 3)
    backoff_base_seconds = retry_config.get("backoff_base_seconds", 2)
    delay_between_requests = throttle_config.get("delay_seconds_between_requests", 1.0)

    results: list[FetchResult] = []
    failures: list[tuple[str, Exception]] = []
    for index, label in enumerate(labels):
        try:
            result = fetch_season_csv(
                label,
                max_attempts=max_attempts,
                backoff_base_seconds=backoff_base_seconds,
            )
            results.append(result)
        except FetchError as exc:
            logger.error("Giving up on season %s: %s", label, exc)
            failures.append((label, exc))
        if index < len(labels) - 1:
            time.sleep(delay_between_requests)

    logger.info(
        "Backfill complete: %d succeeded, %d failed.", len(results), len(failures)
    )
    for label, error in failures:
        logger.error("  FAILED %s: %s", label, error)
    return results


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=None,
        metavar="YYYY-YY",
        help=(
            "Season labels to fetch, e.g. --seasons 2022-23 2023-24. "
            "Defaults to config.yaml's season.backfill_labels."
        ),
    )
    args = parser.parse_args()

    results = run_historical_backfill(args.seasons)
    for result in results:
        print(
            f"{result.season_label}: {result.raw_path} "
            f"({result.byte_count} bytes, ~{result.row_count} rows)"
        )
    if not results:
        raise SystemExit("No seasons were fetched successfully; see logs for details.")


if __name__ == "__main__":
    main()
