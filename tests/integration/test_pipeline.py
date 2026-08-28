"""Integration test for the end-to-end fixture pipeline: raw CSV ->
validate -> normalize -> load -> ingestion_log (see
docs/testing_strategy.md section 3.2 and docs/roadmap.md Phase 1).

Deliberately passes an explicit, minimal app_config rather than calling
process_raw_file(..., app_config=None) - the None path reads the
developer's local, gitignored config/config.yaml, which a test must not
depend on for hermeticity (it may not exist in CI or a fresh clone before
setup).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from src.database.models import IngestionLog, Match, Season, Team
from src.database.session import session_scope
from src.processing.pipeline import QuarantinedFileError, process_raw_file
from src.processing.team_aliases import UnknownTeamAliasError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE_PATH = FIXTURES_DIR / "football_data_co_uk_sample.csv"
_TEST_APP_CONFIG: dict[str, dict[str, object]] = {"season": {}, "ingestion": {}}


def test_pipeline_loads_fixture_end_to_end(isolated_database: None) -> None:
    result = process_raw_file(
        FIXTURE_PATH, season_label="2023-24", app_config=_TEST_APP_CONFIG
    )

    assert result.records_fetched == 3
    assert result.inserted == 3
    assert result.updated == 0
    assert result.unchanged == 0

    with session_scope() as session:
        season = session.scalar(select(Season).where(Season.label == "2023-24"))
        assert season is not None

        matches = session.scalars(
            select(Match).where(Match.season_id == season.season_id)
        ).all()
        assert len(matches) == 3
        assert all(
            m.status == "played" and m.source == "football-data.co.uk" for m in matches
        )

        teams = session.scalars(select(Team)).all()
        assert {t.canonical_key for t in teams} == {"celtic", "aberdeen", "rangers"}

        logs = session.scalars(select(IngestionLog)).all()
        assert len(logs) == 1
        assert logs[0].status == "success"
        assert logs[0].records_loaded == 3


def test_pipeline_is_idempotent_on_rerun(isolated_database: None) -> None:
    """Re-running against the same raw file must not duplicate matches or
    silently skip logging - see docs/data_ingestion.md section 6."""
    process_raw_file(FIXTURE_PATH, season_label="2023-24", app_config=_TEST_APP_CONFIG)
    second_result = process_raw_file(
        FIXTURE_PATH, season_label="2023-24", app_config=_TEST_APP_CONFIG
    )

    assert second_result.inserted == 0
    assert second_result.updated == 0
    assert second_result.unchanged == 3

    with session_scope() as session:
        matches = session.scalars(select(Match)).all()
        assert len(matches) == 3  # not 6

        logs = session.scalars(select(IngestionLog)).all()
        assert len(logs) == 2  # one row per run, per docs/data_ingestion.md section 4.5


def test_pipeline_quarantines_invalid_file_and_logs_failure(
    isolated_database: None, tmp_path: Path
) -> None:
    """A malformed file is quarantined rather than partially loaded (see
    docs/data_ingestion.md section 4.2), and the run is still logged (see
    section 4.5) rather than silently skipped.

    Copies the fixture into tmp_path first and points quarantine_dir at
    tmp_path too, since process_raw_file moves the raw file on failure -
    it must never move the actual committed fixture."""
    raw_copy = tmp_path / "malformed.csv"
    raw_copy.write_bytes(
        (FIXTURES_DIR / "football_data_co_uk_malformed.csv").read_bytes()
    )
    quarantine_dir = tmp_path / "quarantine"
    app_config = {"season": {}, "ingestion": {"quarantine_dir": str(quarantine_dir)}}

    with pytest.raises(QuarantinedFileError):
        process_raw_file(raw_copy, season_label="9999-00", app_config=app_config)

    assert not raw_copy.exists()
    assert (quarantine_dir / "malformed.csv").exists()

    with session_scope() as session:
        logs = session.scalars(select(IngestionLog)).all()
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert logs[0].records_loaded == 0


def test_pipeline_raises_and_logs_failure_on_unknown_team(
    isolated_database: None,
) -> None:
    """An unresolvable team name raises rather than silently creating a
    duplicate team (docs/testing_strategy.md section 3.1), and the run is
    still logged as failed."""
    raw_path = FIXTURES_DIR / "football_data_co_uk_unknown_team.csv"

    with pytest.raises(UnknownTeamAliasError):
        process_raw_file(raw_path, season_label="2023-24", app_config=_TEST_APP_CONFIG)

    with session_scope() as session:
        logs = session.scalars(select(IngestionLog)).all()
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert "normalization failed" in (logs[0].notes or "")
