"""Fetcher for football-data.co.uk historical Scotland Premiership CSVs.

Retrieves the raw, unmodified season CSV and writes it to data/raw/ (see
docs/data_ingestion.md section 4.1, "Fetch"). This module never writes to
the database and never interprets the CSV's football content - it only
confirms the response looks like the expected CSV rather than an error
page. Parsing, validation, and normalization happen in src/processing/
(the next Phase 1 item).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from src.utils.config import PROJECT_ROOT, get_env

logger = logging.getLogger(__name__)

SOURCE_NAME = "football-data.co.uk"
DIVISION_CODE = "SC0"  # Scottish Premiership division code on football-data.co.uk
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season_code}/{division}.csv"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "football_data_co_uk"

_SEASON_LABEL_RE = re.compile(r"^(\d{4})-(\d{2})$")


class FetchError(RuntimeError):
    """Raised when a season's CSV could not be retrieved after all retries."""


@dataclass(frozen=True)
class FetchResult:
    season_label: str
    season_code: str
    url: str
    raw_path: Path
    fetched_at: datetime
    byte_count: int
    row_count: int


def season_label_to_code(season_label: str) -> str:
    """Convert a season label like "2023-24" to football-data.co.uk's
    four-digit season code, e.g. "2324"."""
    match = _SEASON_LABEL_RE.match(season_label)
    if not match:
        raise ValueError(
            f"Season label {season_label!r} is not in the expected 'YYYY-YY' format."
        )
    start_year, end_suffix = match.groups()
    expected_end_suffix = str((int(start_year) + 1) % 100).zfill(2)
    if end_suffix != expected_end_suffix:
        raise ValueError(
            f"Season label {season_label!r} does not span consecutive years "
            f"(expected 'YYY-{expected_end_suffix}')."
        )
    return start_year[2:] + end_suffix


def _looks_like_csv(content: bytes) -> bool:
    """Reject empty bodies and HTML error/placeholder pages (e.g. a season
    that hasn't been published yet) before they are saved as if they were
    valid raw data."""
    if not content:
        return False
    if content.lstrip()[:1] == b"<":
        return False
    first_line = content.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    return "Div" in first_line and "Date" in first_line


def fetch_season_csv(
    season_label: str,
    *,
    raw_dir: Path | None = None,
    session: requests.Session | None = None,
    max_attempts: int = 3,
    backoff_base_seconds: float = 2.0,
    timeout_seconds: float = 15.0,
) -> FetchResult:
    """Download one season's CSV and save it, unmodified, under data/raw/.

    Retries transient failures (network errors, non-200 responses, or a
    response that doesn't look like the expected CSV) with exponential
    backoff, per docs/data_ingestion.md section 6.
    """
    season_code = season_label_to_code(season_label)
    url = BASE_URL.format(season_code=season_code, division=DIVISION_CODE)
    http = session or requests.Session()
    user_agent = get_env("INGESTION_USER_AGENT") or "scottish-premiership-dashboard/0.1"

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(
                "Fetching %s season %s (attempt %d/%d): %s",
                SOURCE_NAME,
                season_label,
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
            if not _looks_like_csv(response.content):
                raise FetchError(
                    f"Response for season {season_label} does not look like a CSV "
                    "(possibly an error page, or the season has not been published yet)."
                )
            return _save_raw_csv(
                season_label, season_code, url, response.content, raw_dir
            )
        except (requests.RequestException, FetchError) as exc:
            last_error = exc
            logger.warning(
                "Attempt %d/%d failed for season %s: %s",
                attempt,
                max_attempts,
                season_label,
                exc,
            )
            if attempt < max_attempts:
                delay = backoff_base_seconds * (2 ** (attempt - 1))
                time.sleep(delay)

    raise FetchError(
        f"Failed to fetch {SOURCE_NAME} season {season_label} after {max_attempts} attempts."
    ) from last_error


def _save_raw_csv(
    season_label: str,
    season_code: str,
    url: str,
    content: bytes,
    raw_dir: Path | None,
) -> FetchResult:
    target_dir = (raw_dir or DEFAULT_RAW_DIR) / season_label
    target_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(UTC)
    file_path = target_dir / f"{fetched_at:%Y%m%dT%H%M%SZ}.csv"
    file_path.write_bytes(content)
    row_count = max(content.count(b"\n") - 1, 0)  # exclude header row
    logger.info(
        "Saved %s season %s to %s (%d bytes, ~%d rows)",
        SOURCE_NAME,
        season_label,
        file_path,
        len(content),
        row_count,
    )
    return FetchResult(
        season_label=season_label,
        season_code=season_code,
        url=url,
        raw_path=file_path,
        fetched_at=fetched_at,
        byte_count=len(content),
        row_count=row_count,
    )
