"""Match Explorer page (see docs/visualisation_plan.md section 3.3).

Phase 2 scope: filterable results table plus a league-wide scoring trend.
Per-match event detail (goals/cards/substitutions) is Phase 3 - no source
ingested so far provides that data (see docs/roadmap.md).
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.dashboard.data_access import (
    get_league_goals_trend,
    get_season_matches_table,
    list_seasons,
)

st.set_page_config(
    page_title="Match Explorer — Scottish Premiership Dashboard",
    page_icon="⚽",
    layout="wide",
)

_RESULT_OPTIONS = ["All", "Home win", "Away win", "Draw"]


def main() -> None:
    st.title("Match Explorer")

    seasons_df = list_seasons()
    if seasons_df.empty:
        st.info(
            "No seasons ingested yet. Visit the Overview page for setup instructions."
        )
        return

    with st.sidebar:
        st.header("Filters")
        season_label = str(st.selectbox("Season", seasons_df["label"], index=0))
        season_id = int(
            seasons_df.loc[seasons_df["label"] == season_label, "season_id"].iloc[0]
        )

    matches_df = get_season_matches_table(season_id)
    if matches_df.empty:
        st.info(f"No matches played yet in {season_label}.")
        return

    with st.sidebar:
        teams = sorted(set(matches_df["Home"]) | set(matches_df["Away"]))
        team_filter = st.selectbox("Team", ["All"] + teams)
        result_filter = st.selectbox("Result", _RESULT_OPTIONS)
        min_date, max_date = matches_df["Date"].min(), matches_df["Date"].max()
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

    filtered = matches_df
    if team_filter != "All":
        filtered = filtered[
            (filtered["Home"] == team_filter) | (filtered["Away"] == team_filter)
        ]
    if result_filter != "All":
        filtered = filtered[filtered["Result"] == result_filter]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["Date"] >= start_date) & (filtered["Date"] <= end_date)
        ]

    st.caption(f"{len(filtered)} of {len(matches_df)} matches in {season_label}")
    st.dataframe(
        filtered.drop(columns=["TotalGoals"]).sort_values("Date", ascending=False),
        hide_index=True,
        width="stretch",
    )

    st.divider()
    st.markdown("**League-wide scoring trend**")
    goals_df = get_league_goals_trend(season_id)
    fig = px.line(
        goals_df,
        x="MatchIndex",
        y="RollingAvgGoals",
        title="Rolling average goals per match (league-wide)",
        hover_data=["Date"],
    )
    fig.update_layout(
        xaxis_title="Match number (season order)", yaxis_title="Avg goals/match"
    )
    st.plotly_chart(fig, width="stretch")


main()
