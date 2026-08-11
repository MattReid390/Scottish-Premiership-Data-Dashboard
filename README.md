# Scottish Premiership Data Dashboard

> A Python-based data pipeline and interactive dashboard for exploring Scottish Premiership football (soccer) results, league standings, team form, and historical trends.

[![Status](https://img.shields.io/badge/status-planning-lightgrey)]()
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()

> **Project status:** This repository currently contains the **project blueprint** only — architecture, documentation, schema design, and folder scaffolding. No application code has been implemented yet. See [docs/roadmap.md](docs/roadmap.md) for build phases.

---

## Overview

The Scottish Premiership Data Dashboard ingests match results and league data for the Scottish Premiership (Scotland's top football division), stores it in a structured relational database, computes derived statistics (league tables, form guides, rating models, trends), and presents the results through an interactive multi-page dashboard.

The project is designed as a small, reproducible **data engineering + analytics** case study: a clear ingestion → storage → analysis → presentation pipeline that can run locally on a schedule, backed entirely by free/public data sources.

### Key Features (planned)

- **Automated data ingestion** from public football data sources, normalized into a consistent schema.
- **Historical + live-season data**: full match results, fixtures, and computed standings across multiple seasons.
- **League table engine** that reconstructs the table at any point in the season (not just the current snapshot).
- **Form and trend analytics**: rolling form guides, home/away splits, points-per-game trends, Elo-style team ratings.
- **Interactive dashboard** with league table, team profile, match explorer, head-to-head comparison, and trend views.
- **Reproducible environment** via pinned dependencies, `.env`-based configuration, and a documented local/CI setup.

---

## Documentation

Full project documentation lives in [docs/](docs/):

| Document | Description |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System architecture, components, data flow, folder structure |
| [docs/database_schema.md](docs/database_schema.md) | Entity-relationship design and table-level schema |
| [docs/data_ingestion.md](docs/data_ingestion.md) | Data sources, ingestion pipeline, validation, scheduling |
| [docs/analysis_methodology.md](docs/analysis_methodology.md) | League table, form, rating, and trend calculation methodology |
| [docs/visualisation_plan.md](docs/visualisation_plan.md) | Dashboard framework, page layouts, chart selection, UX |
| [docs/testing_strategy.md](docs/testing_strategy.md) | Test pyramid, tooling, coverage targets, CI plan |
| [docs/environment_configuration.md](docs/environment_configuration.md) | Environment setup, configuration files, secrets management |
| [docs/roadmap.md](docs/roadmap.md) | Phased delivery plan (MVP → enhancements → stretch goals) |

---

## Project Structure

```text
Scottish_Premiership_Data_Dashboard/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CHANGELOG.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── docs/                     # Full project documentation (this index)
│   └── assets/               # Diagrams / exported images referenced by docs
├── config/
│   └── config.example.yaml   # Non-secret application configuration template
├── src/
│   ├── ingestion/            # Source fetchers (API/CSV/HTML) and raw data handlers
│   ├── processing/           # Cleaning, validation, and normalization logic
│   ├── database/             # Schema, models, migrations, data access layer
│   ├── analysis/             # League table, form, ratings, and trend calculations
│   ├── dashboard/            # Streamlit multi-page dashboard application
│   └── utils/                # Shared helpers (logging, config loading, dates)
├── data/
│   ├── raw/                  # Immutable, as-fetched source data (gitignored)
│   ├── interim/              # Intermediate cleaned data (gitignored)
│   └── processed/            # Final, analysis-ready datasets (gitignored)
├── notebooks/                # Exploratory analysis notebooks (not part of the pipeline)
└── tests/
    ├── unit/                 # Fast, isolated unit tests
    ├── integration/          # End-to-end pipeline tests against fixture data
    └── fixtures/             # Small sample datasets used by tests
```

Full rationale for this layout is documented in [docs/architecture.md](docs/architecture.md#folder-structure).

---

## Getting Started

> These are the *planned* setup steps for when implementation begins; see [docs/environment_configuration.md](docs/environment_configuration.md) for full details.

### Prerequisites

- Python 3.11+
- `pip` and `venv` (or `conda`)
- SQLite (bundled with Python) for local development; PostgreSQL optional for a production-like setup
- API keys for any optional third-party data providers (see [docs/data_ingestion.md](docs/data_ingestion.md#data-sources))

### Planned setup flow

1. Clone the repository and create a virtual environment.
2. Install dependencies from `requirements.txt` (and `requirements-dev.txt` for development/testing tools).
3. Copy `.env.example` to `.env` and `config/config.example.yaml` to `config/config.yaml`, then fill in local values.
4. Run the ingestion pipeline to populate the local database with historical and current-season data.
5. Launch the dashboard application to explore the data.

Exact commands will be added once the corresponding modules are implemented (see [docs/roadmap.md](docs/roadmap.md)).

---

## Data Sources & Attribution

Data is sourced from publicly available football data providers (e.g. SPFL official results, football-data.co.uk historical CSVs, and optionally a football statistics API). Full source list, licensing notes, and update cadence are documented in [docs/data_ingestion.md](docs/data_ingestion.md#data-sources). This project is an independent, non-commercial data analytics project and is not affiliated with the Scottish Professional Football League (SPFL).

---

## Testing

Testing strategy, tooling (`pytest`, data-validation schemas), and coverage targets are documented in [docs/testing_strategy.md](docs/testing_strategy.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on proposing changes, coding standards, and the review process.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the phased build plan (MVP, enhancements, stretch goals).

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
