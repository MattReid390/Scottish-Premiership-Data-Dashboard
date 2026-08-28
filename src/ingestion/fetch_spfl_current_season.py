"""CLI entry point to fetch every configured club's spfl.co.uk results page
into data/raw/ (Phase 2; see docs/roadmap.md).

This script only fetches and saves raw HTML - it does not touch the
database. Parsing and loading is handled by src/processing/pipeline_spfl.py
once each club's raw file has been fetched.

Usage:
    python -m src.ingestion.fetch_spfl_current_season
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import yaml

from src.ingestion.spfl import FetchError, FetchResult, fetch_club_results
from src.utils.config import PROJECT_ROOT, load_app_config
from src.utils.logging_setup import configure_logging

logger = logging.getLogger(__name__)

DEFAULT_SLUGS_PATH = PROJECT_ROOT / "config" / "spfl_club_slugs.yaml"


def load_club_slugs(path: Path | None = None) -> dict[str, str]:
    slugs_path = path or DEFAULT_SLUGS_PATH
    if not slugs_path.exists():
        raise FileNotFoundError(f"SPFL club slug file not found at {slugs_path}.")
    with slugs_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_spfl_fetch(club_slugs: dict[str, str] | None = None) -> list[FetchResult]:
    """Fetch every configured club's results page, continuing past
    individual failures (see docs/data_ingestion.md section 6, "partial
    failure isolation")."""
    app_config = load_app_config()
    slugs = club_slugs or load_club_slugs()
    retry_config = app_config.get("ingestion", {}).get("retry", {})
    throttle_config = app_config.get("ingestion", {}).get("request_throttle", {})
    max_attempts = retry_config.get("max_attempts", 3)
    backoff_base_seconds = retry_config.get("backoff_base_seconds", 2)
    delay_between_requests = throttle_config.get("delay_seconds_between_requests", 1.0)

    results: list[FetchResult] = []
    failures: list[tuple[str, Exception]] = []
    club_items = list(slugs.items())
    for index, (canonical_key, slug) in enumerate(club_items):
        try:
            result = fetch_club_results(
                canonical_key,
                slug,
                max_attempts=max_attempts,
                backoff_base_seconds=backoff_base_seconds,
            )
            results.append(result)
        except FetchError as exc:
            logger.error("Giving up on %s: %s", canonical_key, exc)
            failures.append((canonical_key, exc))
        if index < len(club_items) - 1:
            time.sleep(delay_between_requests)

    logger.info(
        "SPFL fetch complete: %d succeeded, %d failed.", len(results), len(failures)
    )
    for canonical_key, error in failures:
        logger.error("  FAILED %s: %s", canonical_key, error)
    return results


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    results = run_spfl_fetch()
    for result in results:
        print(f"{result.canonical_key}: {result.raw_path}")
    if not results:
        raise SystemExit("No clubs were fetched successfully; see logs for details.")


if __name__ == "__main__":
    main()
