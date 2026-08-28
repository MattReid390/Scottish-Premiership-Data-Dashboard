# Visualisation Plan

## 1. Framework Choice

**Streamlit** is the planned dashboard framework, chosen for:

- Native multi-page app support (`src/dashboard/pages/`), matching the page breakdown below without custom routing.
- Fast iteration for a data-focused, single-purpose app with modest interactivity needs (filters, selects, tabs).
- Straightforward integration with **Plotly** for interactive charting (hover tooltips, zoom, legend toggling) and with the SQLAlchemy data-access layer from `src/database/`.
- Simple local execution model consistent with the project's local-first deployment approach (see [architecture.md](architecture.md#8-deployment-model-planned)).

Charts are rendered with **Plotly** (interactive) as the default, with **Altair** considered as an alternative for smaller static summary charts if Plotly proves heavier than needed for a given view.

## 2. Global UX Principles

- **Season and team filters are persistent** across pages (a shared sidebar), so switching pages doesn't lose context.
- **Point-in-time awareness**: wherever a league table is shown, the user can pick "current" or "as of matchweek N" (see [analysis_methodology.md](analysis_methodology.md#22-point-in-time-reconstruction)).
- **Loading from precomputed summaries**: pages query the derived tables (`team_season_stats`, `team_rating`) rather than recomputing aggregates live, keeping page loads fast.
- **Accessibility**: colour choices avoid red/green-only encodings for win/draw/loss (paired with icons/text), sufficient contrast in both light and dark mode, and all charts include descriptive titles/axis labels rather than relying on colour alone.
- **Responsiveness**: layouts use Streamlit's column/container system with sensible breakpoints; wide tables/charts scroll horizontally on narrow viewports rather than overflowing.
- **Empty/partial-data states**: every page defines an explicit empty state (e.g. "No matches ingested yet for this season") rather than showing a blank or broken chart.

## 3. Page-by-Page Plan

### 3.1 Overview / League Table (landing page)

**Purpose**: at-a-glance current standings.

- Sortable table: position, team, played, W/D/L, GF, GA, GD, points, last-5 form (icon sequence).
- Toggle: "current table" vs. "table as of matchweek N" (slider).
- Highlight rows for European qualification / relegation zone thresholds (configurable cutoffs per `config/config.yaml`).
- Small inline sparkline per team showing points-per-game trend over the last 5 matchweeks.

```text
┌─────────────────────────────────────────────────────────┐
│ Season: [2025-26 ▾]      Matchweek: [current ▾] [slider] │
├───┬──────────────┬────┬───┬───┬───┬────┬────┬────┬──────┤
│ # │ Team         │ P  │ W │ D │ L │ GF │ GA │ GD │ Pts  │
├───┼──────────────┼────┼───┼───┼───┼────┼────┼────┼──────┤
│ 1 │ Celtic       │ 10 │ 8 │ 1 │ 1 │ 24 │  8 │ 16 │  25  │
│ … │ …            │  … │ … │ … │ … │  … │  … │  … │  …   │
└───┴──────────────┴────┴───┴───┴───┴────┴────┴────┴──────┘
```

### 3.2 Team Profile

**Purpose**: deep-dive on a single selected team.

- Header: club crest placeholder, venue, current position/points/form.
- Season results table (all matches, filterable by home/away, result).
- Home vs. away split bar chart (points-per-game, goals-for/against per game).
- Points-per-game trend line across the season (rolling average, per §5 of [analysis_methodology.md](analysis_methodology.md)).
- Elo/expected-points rating trend line across the season.

### 3.3 Match Explorer

**Purpose**: browse and filter individual fixtures.

- Filterable table (season, date range, team, result type) of all matches.
- Goals trend chart across the league as a whole (league-wide scoring trend).

**Implementation status (Phase 2):** built without a `Venue` filter or row-expansion match detail. No ingested source (football-data.co.uk or spfl.co.uk) provides venue data, and `match_event` doesn't exist yet (Phase 3, §6 above) so there's nothing further to expand a row into - both are natural follow-ons once those data gaps close, not omissions of the filtering/trend functionality itself.

### 3.4 Trends & Analytics

**Purpose**: season-wide and cross-season statistical views.

- Cumulative points progression: multi-line chart, one line per team (the signature "league season race" chart).
- League position over time: multi-line chart of `position`.
- Rating comparison: Elo trend lines, selectable subset of teams to avoid clutter (default: top 6 by current position).
- Cross-season comparator: a chosen team's points-per-game across multiple seasons, bar chart.

**Implementation status (Phase 2):** "by matchweek" above is implemented as "by match date / that team's own match number" instead - see [analysis_methodology.md](analysis_methodology.md#22-point-in-time-reconstruction)'s note that `match.matchweek` is `NULL` for every source ingested so far. Rating comparison charts Elo only; expected-points is a single per-team summary figure (see [analysis_methodology.md](analysis_methodology.md#62-expected-points-simple-model)), not something with a meaningful trend line to chart.

### 3.5 Head-to-Head Comparison

**Purpose**: compare two selected teams' historical record.

- Team-A vs. Team-B selectors.
- Summary stat tiles: total meetings, wins each, draws, aggregate goals.
- Recent-meetings table (most recent N fixtures with scorelines).
- Simple win/draw/loss share visualised as a stacked bar.

Scoped across every loaded season (not one season at a time) - head-to-head history is inherently cross-season, unlike the other pages.

### 3.6 Data Quality / Admin Page

**Purpose**: operational visibility into the ingestion pipeline (primarily for the maintainer, not end users).

- Table of recent `ingestion_log` entries (source, status, record counts, timestamp).
- Count of matches by `status` per season (sanity check for stuck `scheduled` rows past their date).
- Manual "trigger recompute" action description (documented behaviour; actual control wiring is an implementation detail).

## 4. Chart Type Summary

| Page | Primary chart types |
|---|---|
| Overview / League Table | Sortable data table, inline sparklines |
| Team Profile | Bar chart (home/away split), line charts (PPG trend, rating trend), results table |
| Match Explorer | Filterable data table, line chart (league scoring trend) |
| Trends & Analytics | Multi-line charts (points progression, position, ratings), bar chart (cross-season PPG) |
| Head-to-Head | Stat tiles, stacked bar chart, results table |
| Data Quality / Admin | Data table, simple bar/count chart |

## 5. Styling & Theming

- A neutral, accessible base palette is used for chart series (not the visually similar green/white/blue of specific clubs' branding, to avoid implying official affiliation) — categorical colours are chosen for maximum distinguishability across the 12-team league, with a documented consistent colour-per-team mapping so a given team keeps the same colour across all charts and pages within a session.
- Both light and dark mode are supported, matching Streamlit's native theming; chart colours are validated for sufficient contrast in both modes.
- Consistent number formatting (goal difference always signed, e.g. `+12`/`-4`; dates in `DD Mon YYYY`).

## 6. Out of Scope (for MVP)

- Player-level visualisations (no player data ingested — see [data_ingestion.md](data_ingestion.md#8-out-of-scope-for-mvp)).
- Geographic/map-based visualisation of venues.
- Real-time/live-updating in-match charts.
