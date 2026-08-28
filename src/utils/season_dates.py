"""Season-window helpers (see docs/architecture.md section 4.6)."""

from __future__ import annotations

import datetime as dt

_SEASON_START_MONTH = 7  # Scottish league play resumes around July/August


def infer_season_label(match_date: dt.date) -> str:
    """Infer a "YYYY-YY" season label from a match date, for sources (like
    spfl.co.uk's results widget) that don't state the season explicitly.

    A date from July onward belongs to the season starting that calendar
    year; earlier in the year belongs to the season that started the
    previous calendar year.
    """
    start_year = (
        match_date.year
        if match_date.month >= _SEASON_START_MONTH
        else match_date.year - 1
    )
    end_year_suffix = str((start_year + 1) % 100).zfill(2)
    return f"{start_year}-{end_year_suffix}"
