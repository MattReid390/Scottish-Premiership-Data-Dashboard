"""Single entry point for the scheduled daily ingestion job (cron /
Windows Task Scheduler; see docs/data_ingestion.md section 5).

Runs the current-season SPFL fetch and processing pipeline back to back -
the "daily, in-season" cadence documented for keeping current results up
to date. Historical backfill (football-data.co.uk) is a separate,
occasional operation per docs/data_ingestion.md section 5's cadence table
("one-off, manual trigger"), not part of this daily job:

    python -m src.ingestion.backfill_historical
    python -m src.processing.run_pipeline

Usage:
    python -m src.run_daily_ingestion
"""

from __future__ import annotations

import logging

from src.ingestion.fetch_spfl_current_season import run_spfl_fetch
from src.processing.run_spfl_pipeline import run_spfl_pipeline
from src.utils.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    logger.info("Starting daily ingestion run.")

    fetch_results = run_spfl_fetch()
    if not fetch_results:
        logger.error(
            "SPFL fetch returned no results for any club; skipping processing."
        )
        raise SystemExit("Daily ingestion failed: no clubs were fetched successfully.")

    run_spfl_pipeline()
    logger.info("Daily ingestion run complete.")


if __name__ == "__main__":
    main()
