"""Integration test for the SPFL fixture pipeline: raw HTML (already
fetched per club) -> parse -> normalize -> dedupe -> load ->
ingestion_log (see docs/testing_strategy.md section 3.2 and
docs/data_ingestion.md's spfl.co.uk implementation notes).

Uses two small fixture files that share one match (Celtic vs Rangers) to
verify cross-club deduplication - the same coverage
tests/integration/test_pipeline.py provides for the football-data.co.uk
pipeline. Passes an explicit app_config for the same hermeticity reason as
that test: process_club_raw_files(..., app_config=None) would otherwise
read the developer's local, gitignored config/config.yaml.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from src.database.models import IngestionLog, Match, Season, Team
from src.database.session import session_scope
from src.processing.pipeline_spfl import process_club_raw_files

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
_TEST_APP_CONFIG: dict[str, dict[str, object]] = {"season": {}, "ingestion": {}}


def _raw_files() -> dict[str, Path]:
    return {
        "celtic": FIXTURES_DIR / "spfl_celtic_results.html",
        "rangers": FIXTURES_DIR / "spfl_rangers_results.html",
    }


def test_spfl_pipeline_dedupes_shared_match_across_clubs(
    isolated_database: None,
) -> None:
    result = process_club_raw_files(_raw_files(), app_config=_TEST_APP_CONFIG)

    # 2 results from celtic's page + 1 from rangers' page, but the
    # Celtic-Rangers fixture appears on both -> 2 unique matches.
    assert result.records_parsed == 3
    assert result.records_deduped == 2
    assert result.inserted == 2
    assert not result.parse_errors

    with session_scope() as session:
        season = session.scalar(select(Season).where(Season.label == "2026-27"))
        assert season is not None

        matches = session.scalars(
            select(Match).where(Match.season_id == season.season_id)
        ).all()
        assert len(matches) == 2
        assert all(m.source == "spfl.co.uk" for m in matches)

        teams = session.scalars(select(Team)).all()
        assert {t.canonical_key for t in teams} == {"celtic", "rangers", "aberdeen"}

        logs = session.scalars(select(IngestionLog)).all()
        assert len(logs) == 1
        assert logs[0].status == "success"
        assert logs[0].records_loaded == 2


def test_spfl_pipeline_is_idempotent_on_rerun(isolated_database: None) -> None:
    process_club_raw_files(_raw_files(), app_config=_TEST_APP_CONFIG)
    second_result = process_club_raw_files(_raw_files(), app_config=_TEST_APP_CONFIG)

    assert second_result.inserted == 0
    assert second_result.unchanged == 2

    with session_scope() as session:
        matches = session.scalars(select(Match)).all()
        assert len(matches) == 2  # not 4
