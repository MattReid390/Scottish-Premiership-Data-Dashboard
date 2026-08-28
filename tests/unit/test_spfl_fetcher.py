"""Unit tests for the pure logic in src/ingestion/spfl.py - response
sanity-checking. Fetching itself makes a live network call and isn't
exercised here, per docs/testing_strategy.md section 5.
"""

from __future__ import annotations

from src.ingestion.spfl import _looks_like_results_page


def test_looks_like_results_page_accepts_expected_markup() -> None:
    assert _looks_like_results_page(b'<div class="fixtures-list__group">...</div>')


def test_looks_like_results_page_rejects_empty_body() -> None:
    assert not _looks_like_results_page(b"")


def test_looks_like_results_page_rejects_unrelated_html() -> None:
    assert not _looks_like_results_page(b"<html><body>Not found</body></html>")
