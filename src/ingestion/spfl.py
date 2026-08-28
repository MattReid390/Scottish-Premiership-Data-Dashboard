"""Fetcher for spfl.co.uk's per-club results page (current-season live
results; see docs/data_ingestion.md section 4.1 and
config/spfl_club_slugs.yaml).

Unlike football-data.co.uk's full-season CSV, this source only exposes a
club's few most recent results/fixtures across all competitions it plays
in, as server-rendered HTML - verified directly against the live site
while building this fetcher. Its full league table and deeper archives are
powered by a third-party Opta widget, not accessible via plain HTTP
requests, so this fetcher doesn't attempt to reach them (the project
computes its own league table from raw match data anyway - see
src/analysis/standings.py). Fetching all 12 current clubs' pages and
relying on natural upsert deduplication (a match appears on two clubs'
pages) keeps this robust as long as ingestion runs at least about as often
as clubs play (docs/data_ingestion.md section 5's daily in-season cadence
- a club would need 4+ unfetched matches to lose data here).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from src.utils.config import PROJECT_ROOT, get_env

logger = logging.getLogger(__name__)

SOURCE_NAME = "spfl.co.uk"
BASE_URL = "https://spfl.co.uk"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "spfl"


class FetchError(RuntimeError):
    """Raised when a club's results page could not be retrieved after all retries."""


@dataclass(frozen=True)
class FetchResult:
    canonical_key: str
    slug: str
    url: str
    raw_path: Path
    fetched_at: datetime


def _looks_like_results_page(content: bytes) -> bool:
    if not content:
        return False
    if content.lstrip()[:1] != b"<":
        return False
    return b"fixtures-list" in content


def fetch_club_results(
    canonical_key: str,
    slug: str,
    *,
    raw_dir: Path | None = None,
    session: requests.Session | None = None,
    max_attempts: int = 3,
    backoff_base_seconds: float = 2.0,
    timeout_seconds: float = 15.0,
) -> FetchResult:
    """Download one club's results page and save it, unmodified, under
    data/raw/. Retries transient failures with exponential backoff, per
    docs/data_ingestion.md section 6."""
    url = f"{BASE_URL}/clubs/{slug}/results"
    http = session or requests.Session()
    user_agent = get_env("INGESTION_USER_AGENT") or "scottish-premiership-dashboard/0.1"

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(
                "Fetching %s results for %s (attempt %d/%d): %s",
                SOURCE_NAME,
                canonical_key,
                attempt,
                max_attempts,
                url,
            )
            response = http.get(
                url, timeout=timeout_seconds, headers={"User-Agent": user_agent}
            )
            if response.status_code != 200:
                raise FetchError(
                    f"Unexpected status {response.status_code} fetching {url}"
                )
            if not _looks_like_results_page(response.content):
                raise FetchError(
                    f"Response for {canonical_key} does not look like an SPFL results page."
                )
            return _save_raw_html(canonical_key, slug, url, response.content, raw_dir)
        except (requests.RequestException, FetchError) as exc:
            last_error = exc
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt,
                max_attempts,
                canonical_key,
                exc,
            )
            if attempt < max_attempts:
                time.sleep(backoff_base_seconds * (2 ** (attempt - 1)))

    raise FetchError(
        f"Failed to fetch {SOURCE_NAME} results for {canonical_key} after {max_attempts} attempts."
    ) from last_error


def _save_raw_html(
    canonical_key: str, slug: str, url: str, content: bytes, raw_dir: Path | None
) -> FetchResult:
    target_dir = (raw_dir or DEFAULT_RAW_DIR) / canonical_key
    target_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(UTC)
    file_path = target_dir / f"{fetched_at:%Y%m%dT%H%M%SZ}.html"
    file_path.write_bytes(content)
    logger.info("Saved %s results for %s to %s", SOURCE_NAME, canonical_key, file_path)
    return FetchResult(
        canonical_key=canonical_key,
        slug=slug,
        url=url,
        raw_path=file_path,
        fetched_at=fetched_at,
    )
