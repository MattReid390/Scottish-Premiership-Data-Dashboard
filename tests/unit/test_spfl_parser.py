"""Unit tests for spfl.co.uk parsing (src/processing/spfl_parser.py). See
docs/data_ingestion.md sections 4.2-4.3.
"""

from __future__ import annotations

import datetime as dt

import pytest

from src.processing.spfl_parser import (
    SpflParseError,
    parse_club_results_html,
    parse_spfl_date,
)

# A trimmed but structurally real sample, based directly on spfl.co.uk's
# actual markup (verified live while building this parser): one played
# Premiership result, one played cup result (must be filtered out), and one
# upcoming Premiership fixture (must be filtered out - no score yet).
_SAMPLE_HTML = """
<div class="fixtures-list__groups">
    <div class="fixtures-list__group">
        <p class="fixtures-list__group__title">William Hill Premiership</p>
        <p class="fixtures-list__group__day">Saturday 22nd August 2026</p>
        <div class="fixtures-list__results">
            <span class="fixtures-list__results__team"><a href="/clubs/dundee-united/results"> Dundee United </a></span>
            <span class="fixtures-list__results__score">0 - 2</span>
            <span class="fixtures-list__results__team"><a href="/clubs/dundee/results"> Dundee </a></span>
        </div>
    </div>
    <div class="fixtures-list__group">
        <p class="fixtures-list__group__title">Premier Sports Cup</p>
        <p class="fixtures-list__group__day">Tuesday 15th July 2026</p>
        <div class="fixtures-list__results">
            <span class="fixtures-list__results__team"><a href="/clubs/dundee-united/results"> Dundee United </a></span>
            <span class="fixtures-list__results__score">3 - 1</span>
            <span class="fixtures-list__results__team"><a href="/clubs/arbroath/results"> Arbroath </a></span>
        </div>
    </div>
    <div class="fixtures-list__group" data-fixture="g1" data-state="PreMatch">
        <p class="fixtures-list__group__title">William Hill Premiership</p>
        <p class="fixtures-list__group__day">Saturday 29th August 2026</p>
        <dl class="fixtures-list__group__fixtures">
            <dt> 15:00 </dt>
            <dd><span><a href="/clubs/celtic/fixtures"> Celtic </a> v
                    <a href="/clubs/falkirk/fixtures"> Falkirk </a></span></dd>
        </dl>
    </div>
</div>
"""


def test_parse_club_results_html_filters_to_premiership_results_only() -> None:
    results = parse_club_results_html(_SAMPLE_HTML, "dundee_united")

    assert len(results) == 1
    result = results[0]
    assert result.match_date == dt.date(2026, 8, 22)
    assert result.home_team_name == "Dundee United"
    assert result.away_team_name == "Dundee"
    assert result.home_goals == 0
    assert result.away_goals == 2


def test_parse_club_results_html_handles_no_premiership_results() -> None:
    html = """
    <div class="fixtures-list__group">
        <p class="fixtures-list__group__title">Premier Sports Cup</p>
        <p class="fixtures-list__group__day">Tuesday 15th July 2026</p>
        <div class="fixtures-list__results">
            <span class="fixtures-list__results__team"><a href="#"> A </a></span>
            <span class="fixtures-list__results__score">1 - 0</span>
            <span class="fixtures-list__results__team"><a href="#"> B </a></span>
        </div>
    </div>
    """
    assert parse_club_results_html(html, "some_club") == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Saturday 22nd August 2026", dt.date(2026, 8, 22)),
        ("Sunday 1st March 2026", dt.date(2026, 3, 1)),
        ("Tuesday 3rd January 2027", dt.date(2027, 1, 3)),
        ("Wednesday 21st June 2026", dt.date(2026, 6, 21)),
    ],
)
def test_parse_spfl_date_handles_ordinal_suffixes(raw: str, expected: dt.date) -> None:
    assert parse_spfl_date(raw) == expected


def test_parse_spfl_date_rejects_unrecognised_format() -> None:
    with pytest.raises(SpflParseError):
        parse_spfl_date("not a date")
