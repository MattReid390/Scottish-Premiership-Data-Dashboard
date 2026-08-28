"""Team Profile page (see docs/visualisation_plan.md section 3.2).

Phase 1 scope: header stats, home/away split, season points progression,
and the full results table. Elo/expected-points rating trends are Phase 2
(those models don't exist yet - see docs/roadmap.md).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.data_access import (
    get_team_matches,
    get_team_summary,
    list_seasons,
    list_teams_for_season,
)

st.set_page_config(
    page_title="Team Profile — Scottish Premiership Dashboard",
    page_icon="⚽",
    layout="wide",
)


def main() -> None:
    st.title("Team Profile")

    seasons_df = list_seasons()
    if seasons_df.empty:
        st.info(
            "No seasons ingested yet. Visit the Overview page for setup instructions."
        )
        return

    with st.sidebar:
        st.header("Filters")
        season_label = str(st.selectbox("Season", seasons_df["label"], index=0))
        season_row = seasons_df.loc[seasons_df["label"] == season_label].iloc[0]
        season_id = int(season_row["season_id"])

        teams_df = list_teams_for_season(season_id)
        if teams_df.empty:
            st.info("No teams found for this season.")
            return
        team_name = str(st.selectbox("Team", teams_df["name"]))
        team_id = int(teams_df.loc[teams_df["name"] == team_name, "team_id"].iloc[0])

    summary = get_team_summary(season_id, team_id)
    matches_df = get_team_matches(season_id, team_id)

    if summary is None or matches_df.empty:
        st.info(f"{team_name} has no played matches in {season_label} yet.")
        return

    st.subheader(f"{summary['display_name']} — {season_label}")
    cols = st.columns(4)
    cols[0].metric("Position", f"{summary['position']} / {summary['teams_in_table']}")
    cols[1].metric("Played", summary["played"])
    cols[2].metric("Points", summary["points"])
    cols[3].metric("Goal difference", f"{summary['goal_difference']:+d}")

    st.divider()

    left, right = st.columns(2)
    with left:
        st.markdown("**Home vs away record**")
        split = (
            matches_df.groupby("Venue")
            .agg(Played=("Points", "size"), Points=("Points", "sum"))
            .reindex(["Home", "Away"])
            .fillna(0)
        )
        split["Points per game"] = (
            (split["Points"] / split["Played"].replace(0, pd.NA)).fillna(0).round(2)
        )
        fig = px.bar(
            split.reset_index(),
            x="Venue",
            y="Points per game",
            text="Points per game",
            title="Points per game: home vs away",
        )
        fig.update_layout(yaxis_title="Points per game", xaxis_title=None)
        st.plotly_chart(fig, width="stretch")

    with right:
        st.markdown("**Points progression**")
        fig2 = px.line(
            matches_df,
            x="MatchNumber",
            y="CumulativePoints",
            markers=True,
            title="Cumulative points across the season",
        )
        fig2.update_layout(xaxis_title="Match number", yaxis_title="Cumulative points")
        st.plotly_chart(fig2, width="stretch")

    st.markdown("**Results**")
    results_df = matches_df[
        ["Date", "Venue", "Opponent", "Score", "Result"]
    ].sort_values("Date", ascending=False)
    st.dataframe(results_df, hide_index=True, width="stretch")


main()
