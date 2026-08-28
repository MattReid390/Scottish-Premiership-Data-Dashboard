"""Back-tests the Elo and expected-points models against historical
seasons already ingested (see docs/analysis_methodology.md section 6.3).

This is a validation exercise, not an automated test gate: it prints a
report comparing each model's implied end-of-season ranking against the
actual final table (via Spearman rank correlation), for a human to sanity
-check whenever rating-model constants change - it does not assert
anything or fail a build.

Usage:
    python -m src.analysis.backtest_ratings
"""

from __future__ import annotations

from sqlalchemy import select

from src.analysis.elo import EloConfig, compute_elo_history, ratings_as_of
from src.analysis.expected_points import compute_expected_points
from src.analysis.standings import compute_league_table, get_played_matches
from src.database.models import Season
from src.database.session import session_scope
from src.utils.logging_setup import configure_logging


def spearman_rank_correlation(
    actual_order: list[int], predicted_order: list[int]
) -> float:
    """Spearman's rho between two rankings of the same set of team IDs,
    given as ordered lists (best first). 1.0 = identical order, -1.0 =
    exactly reversed, 0.0 = no relationship."""
    n = len(actual_order)
    if n < 2:
        return float("nan")
    actual_rank = {team_id: i for i, team_id in enumerate(actual_order)}
    predicted_rank = {team_id: i for i, team_id in enumerate(predicted_order)}
    sum_d_squared = sum(
        (actual_rank[team_id] - predicted_rank[team_id]) ** 2
        for team_id in actual_order
    )
    return 1.0 - (6.0 * sum_d_squared) / (n * (n**2 - 1))


def backtest_season(season_label: str) -> None:
    with session_scope() as session:
        season = session.scalar(select(Season).where(Season.label == season_label))
        if season is None:
            print(f"{season_label}: not loaded, skipping.")
            return

        matches = get_played_matches(session, season.season_id)
        if not matches:
            print(f"{season_label}: no played matches, skipping.")
            return

        actual_table = compute_league_table(session, season.season_id, matches=matches)
        actual_order = [s.team_id for s in actual_table]
        team_names = {s.team_id: s.display_name for s in actual_table}

        elo_history = compute_elo_history(session, config=EloConfig())
        elo_end_of_season = ratings_as_of(elo_history, season_label)
        elo_order = sorted(
            (t for t in actual_order if t in elo_end_of_season),
            key=lambda team_id: -elo_end_of_season[team_id],
        )

        xpts = compute_expected_points(session, season.season_id, matches=matches)
        xpts_by_team = {r.team_id: r.expected_points_per_game for r in xpts}
        xpts_order = sorted(
            (t for t in actual_order if t in xpts_by_team),
            key=lambda team_id: -xpts_by_team[team_id],
        )

    elo_rho = spearman_rank_correlation(actual_order, elo_order)
    xpts_rho = spearman_rank_correlation(actual_order, xpts_order)

    print(f"\n{season_label} (n={len(actual_order)} teams)")
    print(
        f"  Actual final table:      {', '.join(team_names[t] for t in actual_order)}"
    )
    print(f"  Elo-implied order:       {', '.join(team_names[t] for t in elo_order)}")
    print(f"  Expected-points order:   {', '.join(team_names[t] for t in xpts_order)}")
    print(f"  Elo rank correlation:              {elo_rho:+.3f}")
    print(f"  Expected-points rank correlation:  {xpts_rho:+.3f}")


def main() -> None:
    configure_logging()
    with session_scope() as session:
        season_labels = [
            s.label for s in session.scalars(select(Season).order_by(Season.start_date))
        ]
    for label in season_labels:
        backtest_season(label)


if __name__ == "__main__":
    main()
