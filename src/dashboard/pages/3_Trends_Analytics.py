"""Trends & Analytics page (see docs/visualisation_plan.md section 3.4).

Charts default to the top 6 teams by current position, per the docs, to
avoid a 12-line chart becoming unreadable; a multiselect lets the viewer
choose a different subset.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.dashboard.data_access import (
    get_cross_season_ppg,
    get_elo_trend_for_season,
    get_points_progression_all_teams,
    get_position_over_time,
    get_standings_table,
    list_all_teams,
    list_seasons,
)

st.set_page_config(
    page_title="Trends & Analytics — Scottish Premiership Dashboard",
    page_icon="⚽",
    layout="wide",
)

_DEFAULT_TEAM_COUNT = 6


def main() -> None:
    st.title("Trends & Analytics")

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

    standings_df = get_standings_table(season_id)
    if standings_df.empty or standings_df["P"].sum() == 0:
        st.info(f"No matches played yet in {season_label}.")
        return

    all_teams_in_season = list(standings_df["Team"])
    default_teams = all_teams_in_season[:_DEFAULT_TEAM_COUNT]
    with st.sidebar:
        selected_teams = st.multiselect(
            "Teams to chart", all_teams_in_season, default=default_teams
        )
    if not selected_teams:
        st.info(
            "Select at least one team in the sidebar to see the trend charts below."
        )
        return

    st.markdown("**Points progression**")
    progression_df = get_points_progression_all_teams(season_id)
    progression_df = progression_df[progression_df["Team"].isin(selected_teams)]
    fig1 = px.line(
        progression_df,
        x="MatchNumber",
        y="CumulativePoints",
        color="Team",
        markers=True,
        hover_data=["Date"],
    )
    fig1.update_layout(xaxis_title="Match number", yaxis_title="Cumulative points")
    st.plotly_chart(fig1, width="stretch")

    st.markdown("**League position over time**")
    position_df = get_position_over_time(season_id)
    position_df = position_df[position_df["Team"].isin(selected_teams)]
    fig2 = px.line(position_df, x="Date", y="Position", color="Team", markers=True)
    fig2.update_layout(yaxis_title="Position", yaxis={"autorange": "reversed"})
    st.plotly_chart(fig2, width="stretch")

    st.markdown("**Elo rating trend**")
    team_ids = tuple(
        int(standings_df.loc[standings_df["Team"] == name, "team_id"].iloc[0])
        for name in selected_teams
    )
    elo_df = get_elo_trend_for_season(season_id, team_ids)
    if elo_df.empty:
        st.caption("No Elo history available for the selected teams in this season.")
    else:
        fig3 = px.line(elo_df, x="Date", y="Rating", color="Team", markers=True)
        st.plotly_chart(fig3, width="stretch")

    st.divider()
    st.markdown("**Cross-season comparison**")
    all_teams_df = list_all_teams()
    compare_team_name = str(
        st.selectbox("Team", all_teams_df["name"], key="cross_season_team")
    )
    compare_team_id = int(
        all_teams_df.loc[all_teams_df["name"] == compare_team_name, "team_id"].iloc[0]
    )
    ppg_df = get_cross_season_ppg(compare_team_id)
    if ppg_df.empty:
        st.caption(f"No completed seasons found for {compare_team_name}.")
    else:
        fig4 = px.bar(ppg_df, x="Season", y="PointsPerGame", text="PointsPerGame")
        fig4.update_layout(yaxis_title="Points per game")
        st.plotly_chart(fig4, width="stretch")


main()
