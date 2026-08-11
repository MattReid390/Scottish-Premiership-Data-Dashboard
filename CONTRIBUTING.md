# Contributing

Thank you for your interest in contributing to the Scottish Premiership Data Dashboard. This project is currently in the planning/blueprint stage (see [docs/roadmap.md](docs/roadmap.md)); contributions are welcome once implementation begins, and design feedback on the documentation itself is welcome at any time.

## Ways to Contribute

- **Implementation**: pick up a task from [docs/roadmap.md](docs/roadmap.md), starting with Phase 1 (MVP) items.
- **Documentation**: improvements or corrections to anything in [docs/](docs/).
- **Data source knowledge**: if you know of an additional reliable, freely licensed source of Scottish Premiership data, please open an issue describing it (see [docs/data_ingestion.md](docs/data_ingestion.md#2-data-sources)).
- **Bug reports**: once the application exists, issues describing incorrect computed statistics (with the specific matches/season involved) are especially valuable, given the project's emphasis on correctness of derived data (see [docs/analysis_methodology.md](docs/analysis_methodology.md)).

## Development Workflow (once implementation begins)

1. Fork the repository and create a feature branch from `main`.
2. Set up your local environment per [docs/environment_configuration.md](docs/environment_configuration.md).
3. Make your change, keeping it scoped to a single concern (one architectural layer per change where possible — see [docs/architecture.md](docs/architecture.md#4-component-breakdown)).
4. Add or update tests per [docs/testing_strategy.md](docs/testing_strategy.md); all existing tests must continue to pass.
5. Update relevant documentation in `docs/` if your change affects architecture, schema, ingestion behaviour, or methodology — documentation and code are expected to stay in sync.
6. Open a pull request describing the change and its motivation.

## Code & Design Standards

- Follow the layered architecture in [docs/architecture.md](docs/architecture.md) — ingestion, processing, storage, analysis, and presentation code stay in their respective `src/` subpackages.
- Any change to derived statistics logic (league table, form, ratings) must include a corresponding unit test with a hand-verifiable expected result, per [docs/testing_strategy.md](docs/testing_strategy.md#31-unit-tests-testsunit).
- Configuration changes (new tunables) belong in `config/config.example.yaml` with accompanying documentation in [docs/environment_configuration.md](docs/environment_configuration.md), not hardcoded.
- No secrets, API keys, or personal data in commits — see [docs/environment_configuration.md](docs/environment_configuration.md#9-secrets-management-best-practices).

## Commit & PR Conventions

- Keep commits focused and descriptive.
- Reference the relevant roadmap item or issue number in the PR description where applicable.
- PRs should explain *why* a change is needed, not just *what* changed.

## Code of Conduct

Be respectful and constructive. This is a small, personal-scale open-source project — assume good faith, and raise disagreements as questions rather than demands.
