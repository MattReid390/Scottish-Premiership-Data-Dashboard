"""Unit tests for the pure logic in src/ingestion/football_data_co_uk.py -
season-code conversion and response sanity-checking. Fetching itself makes
a live network call and isn't exercised here, per
docs/testing_strategy.md section 5.
"""

from __future__ import annotations

import pytest

from src.ingestion.football_data_co_uk import _looks_like_csv, season_label_to_code


@pytest.mark.parametrize(
    ("label", "expected_code"),
    [
        ("2022-23", "2223"),
        ("2023-24", "2324"),
        ("2024-25", "2425"),
        ("2099-00", "9900"),
    ],
)
def test_season_label_to_code(label: str, expected_code: str) -> None:
    assert season_label_to_code(label) == expected_code


@pytest.mark.parametrize("bad_label", ["2022-24", "bogus", "2022", "22-23"])
def test_season_label_to_code_rejects_invalid_labels(bad_label: str) -> None:
    with pytest.raises(ValueError):
        season_label_to_code(bad_label)


def test_looks_like_csv_accepts_expected_header() -> None:
    assert _looks_like_csv(b"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nSC0,05/08/2023,...")


def test_looks_like_csv_rejects_empty_body() -> None:
    assert not _looks_like_csv(b"")


def test_looks_like_csv_rejects_html_error_page() -> None:
    assert not _looks_like_csv(
        b"<!DOCTYPE html>\n<html><body>404 Not Found</body></html>"
    )


def test_looks_like_csv_rejects_unrelated_csv() -> None:
    assert not _looks_like_csv(b"Name,Age\nAlice,30\n")
