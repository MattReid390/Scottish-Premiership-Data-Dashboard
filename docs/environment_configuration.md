# Environment & Configuration

## 1. Runtime Requirements

| Requirement | Version / Notes |
|---|---|
| Python | 3.11+ |
| OS | Cross-platform (developed on Windows; no OS-specific dependencies planned) |
| Database (dev) | SQLite (bundled with Python, no separate install) |
| Database (optional prod-like) | PostgreSQL 14+ |

## 2. Dependency Management

Dependencies are declared in two files at the repository root:

- **`requirements.txt`** — runtime dependencies needed to run ingestion, processing, analysis, and the dashboard.
- **`requirements-dev.txt`** — additional dependencies needed only for development and testing (`pytest`, `pytest-cov`, linters/formatters), layered on top of `requirements.txt`.

`pyproject.toml` holds project metadata (name, description, Python version constraint) for packaging/tooling purposes. Dependencies are pinned to compatible-release version ranges to balance reproducibility with the ability to receive patch updates.

### Planned local setup sequence

1. Create a virtual environment (`venv` or `conda`).
2. Install runtime dependencies from `requirements.txt`.
3. Install development dependencies from `requirements-dev.txt` (for contributors).
4. Copy `.env.example` → `.env` and fill in local secrets.
5. Copy `config/config.example.yaml` → `config/config.yaml` and adjust non-secret settings.

## 3. Configuration Files

Configuration is deliberately split into two files with different sensitivity levels:

| File | Purpose | Committed to git? |
|---|---|---|
| `.env` | **Secrets**: API keys, database connection strings if pointing at a non-local DB | No — gitignored; `.env.example` (no real values) is committed as a template |
| `config/config.yaml` | **Non-secret settings**: current season label, rating-model constants, scheduling cadence, quarantine/retention paths | No — gitignored; `config/config.example.yaml` is committed as a template |

This split ensures no credential can be accidentally committed via a settings change, while still keeping non-secret tunables under version control (via the example file) and documented.

## 4. Environment Variables

Defined in `.env` (see `.env.example` for the template with placeholder values):

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | No (defaults to a local SQLite file) | SQLAlchemy connection string; e.g. `sqlite:///data/premiership.db` or `postgresql://user:pass@host:5432/dbname` |
| `FOOTBALL_API_KEY` | Only if the optional API source is enabled | Credential for the third-party football data API (see [data_ingestion.md](data_ingestion.md#2-data-sources)) |
| `LOG_LEVEL` | No (defaults to `INFO`) | Standard Python logging level for the ingestion/analysis pipeline |
| `INGESTION_USER_AGENT` | No | Custom User-Agent string used for HTTP requests to source sites, for identifiable/polite scraping |

## 5. Non-Secret Settings (`config/config.yaml`)

Documented in `config/config.example.yaml`, covering:

- **Current season label** and the list of seasons to ingest for historical backfill.
- **Split-fixture matchweek threshold** (see [analysis_methodology.md](analysis_methodology.md#23-known-simplifications)).
- **Rating model constants**: Elo K-factor, home advantage offset, season carry-over factor.
- **European qualification / relegation zone cutoffs** used for table highlighting (see [visualisation_plan.md](visualisation_plan.md#31-overview--league-table-landing-page)).
- **Ingestion retry policy**: max attempts, backoff base delay.
- **Request throttling**: delay between HTTP requests per source.
- **Form guide window size** (default 5 matches).

## 6. Team Name Alias Mapping

`config/team_aliases.yaml` (referenced in [data_ingestion.md](data_ingestion.md#43-normalize)) is a separate, version-controlled configuration file mapping each known raw team-name variant (across all sources) to a canonical key. It is treated as data configuration rather than a secret, and is expected to be extended over time as new source-specific spellings are encountered.

## 7. Logging

- Standard Python `logging` module, configured centrally in `src/utils/`.
- Log level controlled via `LOG_LEVEL` env var; defaults to `INFO` locally, with `DEBUG` available for troubleshooting ingestion issues.
- Structured log output (module, timestamp, level, message) to both console and a rotating file handler (`logs/` directory, gitignored) for local runs.
- No sensitive values (API keys, connection strings) are ever logged.

## 8. Local vs. CI Configuration Differences

| Aspect | Local | CI (GitHub Actions, planned) |
|---|---|---|
| Database | File-based SQLite in `data/` | Ephemeral in-memory/temp-file SQLite created per test run |
| Secrets | `.env` file (gitignored) | GitHub Actions encrypted secrets, injected as environment variables |
| External network calls | Real (against live sources) during actual ingestion runs | Disabled — tests run only against fixture data (see [testing_strategy.md](testing_strategy.md#3-test-layers)) |

## 9. Secrets Management Best Practices

- Real credentials never committed; `.env` and `config/config.yaml` are both gitignored, with `.example` templates committed instead.
- API keys are scoped to the minimum access the provider allows (read-only, if available).
- If a production/hosted deployment is introduced (see [architecture.md](architecture.md#8-deployment-model-planned)), secrets are managed via the hosting platform's secret store (e.g. Streamlit Community Cloud secrets, or a hosting provider's environment-variable configuration) rather than files on the host.

## 10. Reproducibility Checklist

A fresh clone should be able to go from zero to a running dashboard by:

1. Installing pinned dependencies from `requirements.txt`.
2. Filling in `.env` and `config/config.yaml` from their example templates.
3. Running the (future) ingestion entry point to populate the local database.
4. Running the (future) dashboard entry point.

No manual database seeding or hand-edited data files are required at any step.
