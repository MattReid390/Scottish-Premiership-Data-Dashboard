# Analysis Methodology

## 1. Purpose

This document defines how raw match data is transformed into the derived statistics shown on the dashboard: league tables, form guides, home/away splits, rating models, and trend series. All calculations are deterministic and reproducible from the canonical `match` table (see [database_schema.md](database_schema.md)); nothing here depends on manually entered figures.

## 2. League Table Computation

### 2.1 Standard rules
Standard football league scoring is applied to every `played` match in a season:

- Win = 3 points, Draw = 1 point each, Loss = 0 points.
- Teams are ranked by: **points (desc) → goal difference (desc) → goals for (desc) → alphabetical** (as a deterministic final tiebreaker; head-to-head tiebreakers are noted as a documented simplification — see §2.3).

### 2.2 Point-in-time reconstruction
The league table engine can compute the standings **as they stood after any given matchweek**, not just the current snapshot, by filtering `match` to `matchweek <= N AND status = 'played'` before aggregating. This is what populates `team_season_stats.matchweek` and powers the "table progression" trend view (§5).

**Implementation status (Phase 1):** football-data.co.uk — the only source ingested so far — doesn't supply round/matchday numbers, so `match.matchweek` is `NULL` for all rows it loads. `src/analysis/standings.py` therefore implements this as `as_of_date` (a date cutoff) rather than `as_of_matchweek`, verified to correctly zero out an unstarted season and reflect a single played match the day after. An `as_of_matchweek` variant can be added once a source that supplies matchweek is ingested (Phase 2).

### 2.3 Known simplifications
- Official SPFL tiebreaker rules (which may include head-to-head results/points in some competition phases, e.g. the post-split fixtures) are approximated by goal difference/goals-for; any divergence from the official published table on edge-case ties is a documented limitation, not a bug.
- The Scottish Premiership's mid-season "split" (top-six/bottom-six after 33 matches) is treated as a configurable rule: matchweek numbering and table computation account for the split once fixture data indicates it has occurred, per season configuration in `config/config.yaml`.

## 3. Form Guide

- **Rolling form window**: configurable, default **last 5 played matches** per team, computed as of any given date.
- Represented as a W/D/L sequence (most recent last) plus a **form points-per-game** figure (points earned in the window ÷ matches in the window), enabling like-for-like comparison even where a team has played fewer than 5 matches recently (e.g. early season).

## 4. Home / Away Splits

For each team and season, points-per-game, goals-for-per-game, and goals-against-per-game are computed separately for home and away fixtures, to surface home-advantage effects.

## 5. Trend Analysis

- **Cumulative points progression**: points total after each matchweek, per team, across the season — the primary series for the Trends page's season-progression chart.
- **Rolling points-per-game**: a smoothed (e.g. 5-match rolling average) points-per-game series, reducing noise from individual results for form-trend visualisation.
- **League position over time**: team `position` from `team_season_stats` plotted by matchweek.

## 6. Rating Models

### 6.1 Elo rating
A standard Elo implementation adapted for football, used to track relative team strength over time independent of raw league position:

- All teams begin a season at a **carried-over rating** from the end of the previous season (regressed partially toward the league mean, a common practice to avoid over-crediting past form — e.g. `new_season_rating = mean + carry_over_factor * (old_rating - mean)`, with `carry_over_factor` configurable, default `0.75`).
- After each match, both teams' ratings are updated based on the match result versus the *expected* result implied by the pre-match rating difference, scaled by a configurable K-factor.
- Draws are treated as a half-win for each side in the expected-vs-actual comparison, as per standard Elo-for-football adaptations.
- Home advantage is modelled as a fixed rating bonus applied to the home team's rating only for the purposes of computing the expected result (configurable, default a modest fixed offset), not a permanent rating change.

Exact constants (K-factor, home advantage offset, carry-over factor) are defined in `config/config.example.yaml` so they can be tuned without code changes, and are documented alongside the config file.

### 6.2 Expected points (simple model)
A lightweight, explainable alternative to Elo: for each team, an **expected points per game** figure is derived from a Poisson-based comparison of a team's goals-for/against rates against the league average, without requiring external Expected Goals (xG) data (which is not reliably available from free sources for this league). This is explicitly a simplified proxy, not a full xG model, and is documented as such wherever displayed.

### 6.3 Model validation
Both rating models are back-tested against historical seasons already ingested: a model's implied end-of-season ranking is compared against the actual final table, and the comparison (e.g. rank correlation) is documented in the repository's analysis notes as a sanity check whenever model parameters change — this is a validation exercise, not an automated test gate. Implemented in `src/analysis/backtest_ratings.py` (`python -m src.analysis.backtest_ratings`), using Spearman rank correlation.

**Results (Phase 2, against the 4 seasons loaded at the time):** both models correlate strongly with the actual final table for every completed season — Elo ρ = +0.965 / +0.993 / +0.937 and expected-points ρ = +0.951 / +0.951 / +0.937 across 2022-23 / 2023-24 / 2024-25 respectively. The partial in-progress 2026-27 season (13 matches at the time of this back-test) is the one instructive exception: Elo's correlation drops to +0.392, because 2025-26 hasn't been ingested, so Elo has no rating continuity to carry into 2026-27 and every team restarts at the baseline rating — while expected-points, which only needs the current season's own goals data, still reaches +0.972 on the same 13 matches. This is a genuine, expected limitation of a season-over-season rating model facing a gap in its input history, not a bug; it will resolve once 2025-26 is backfilled.

## 7. Head-to-Head Analysis

For any pair of teams, aggregate historical results (all seasons ingested) are summarised: total meetings, win/draw/loss counts per side, aggregate goals, and the most recent N meetings with scorelines — powering the Head-to-Head comparison page.

## 8. Data Quality Assumptions & Limitations

- Analysis is only as complete as the ingested data; seasons or matches not yet ingested are simply absent rather than estimated.
- Postponed/abandoned matches are excluded from all statistical computation until they are replayed and recorded with a final score.
- Team identity across historical name changes (e.g. sponsorship-related renames) is resolved via `team.canonical_key`; any such mapping is documented in `config/team_aliases.yaml` and treated as configuration, not analysis logic.
- All computed figures are recomputed in full on each ingestion run (no incremental/partial recomputation for MVP), which is tractable at this data volume (a few thousand matches) and avoids a class of incremental-aggregation bugs.

## 9. Glossary

| Term | Definition |
|---|---|
| Matchweek | Sequential round number within a season, where available from source data |
| Points-per-game (PPG) | Points earned divided by matches played, used to compare teams/periods with different match counts |
| Elo rating | A relative skill rating updated after each match based on expected vs. actual result |
| Expected points (xPts) | This project's simplified, Poisson-based proxy for a team's underlying performance level (not derived from shot-level xG data) |
| Split fixtures | The Scottish Premiership's post-33-match reorganisation into top-six/bottom-six mini-leagues |
