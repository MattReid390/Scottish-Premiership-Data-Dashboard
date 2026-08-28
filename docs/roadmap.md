# Roadmap

This roadmap sequences implementation into phases. It reflects planning intent at the time of writing and is expected to evolve; see the repository's issue tracker (once created) for the authoritative up-to-date task list.

## Phase 0 — Blueprint (current)

- [x] Architecture, schema, ingestion, analysis, visualisation, testing, and configuration documentation.
- [x] Repository folder scaffolding.
- [x] Repository created on GitHub; issues opened for Phase 1 tasks.

## Phase 1 — MVP

- [x] `src/database/`: schema models and initial Alembic migration for `season`, `team`, `venue`, `match`, `ingestion_log`.
- [x] `src/ingestion/`: fetcher for one historical source (football-data.co.uk CSV) to backfill 2–3 past seasons.
- [x] `src/processing/`: validation, team-name normalization, and upsert-based loading.
- [x] `src/analysis/`: league table engine (current + point-in-time), form guide calculation.
- [x] `src/dashboard/`: Overview/League Table page and Team Profile page.
- [x] `tests/`: unit tests for table computation and form guide; integration test for the end-to-end fixture pipeline.
- [x] Local setup verified against the reproducibility checklist in [environment_configuration.md](environment_configuration.md#10-reproducibility-checklist).

## Phase 2 — Enhancements

- [x] `src/ingestion/`: SPFL official-site fetcher for current-season live results; source-priority conflict resolution.
- [x] `src/analysis/`: Elo rating model and expected-points model, with back-testing against historical seasons.
- [x] `src/dashboard/`: Match Explorer, Trends & Analytics, and Head-to-Head pages.
- [x] Data Quality / Admin page backed by `ingestion_log`.
- [x] Scheduled local ingestion (cron / Task Scheduler) documented and configured.
- [x] GitHub Actions CI workflow (lint + test, per [testing_strategy.md](testing_strategy.md#6-continuous-integration)).

## Phase 3 — Stretch Goals

- [ ] Optional third-party API source integration for richer/real-time fixture metadata.
- [ ] `match_event` ingestion (goals/cards/substitutions) where a source provides it, and corresponding timeline visualisation.
- [ ] Hosted deployment (e.g. Streamlit Community Cloud) backed by PostgreSQL.
- [ ] Cross-season comparison enhancements (multi-season team trend explorer).
- [ ] Basic player-level statistics, if a suitable free data source is identified.

## Explicitly Out of Scope

- Betting-odds data and any wagering-related features.
- Live, in-play (minute-by-minute) score updates.
- Any data source requiring a paid commercial license incompatible with a personal/non-commercial project.
