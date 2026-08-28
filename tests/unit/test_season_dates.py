"""Unit tests for src/utils/season_dates.py."""

from __future__ import annotations

import datetime as dt

import pytest

from src.utils.season_dates import infer_season_label


@pytest.mark.parametrize(
    ("match_date", "expected_label"),
    [
        (dt.date(2026, 8, 1), "2026-27"),
        (dt.date(2026, 7, 1), "2026-27"),
        (dt.date(2026, 6, 30), "2025-26"),
        (dt.date(2027, 5, 18), "2026-27"),
        (dt.date(2099, 12, 31), "2099-00"),
    ],
)
def test_infer_season_label(match_date: dt.date, expected_label: str) -> None:
    assert infer_season_label(match_date) == expected_label
