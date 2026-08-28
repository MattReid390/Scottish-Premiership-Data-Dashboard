"""Head-to-Head Comparison page (see docs/visualisation_plan.md section 3.5).

Scoped across every loaded season, not one season at a time - head-to-head
history is inherently a cross-season view.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.data_access import get_head_to_head, list_all_teams

st.set_page_config(
    page_title="Head-to-Head — Scottish Premiership Dashboard",
    page_icon="⚽",
    layout="wide",
)


def main() -> None:
    st.title("Head-to-Head Comparison")

    teams_df = list_all_teams()
    if len(teams_df) < 2:
        st.info(
            "Not enough teams loaded yet. Visit the Overview page for setup instructions."
        )
        return

    with st.sidebar:
        st.header("Teams")
        team_a_name = str(st.selectbox("Team A", teams_df["name"], index=0))
        remaining = teams_df[teams_df["name"] != team_a_name]
        team_b_name = str(st.selectbox("Team B", remaining["name"], index=0))

    team_a_id = int(teams_df.loc[teams_df["name"] == team_a_name, "team_id"].iloc[0])
    team_b_id = int(teams_df.loc[teams_df["name"] == team_b_name, "team_id"].iloc[0])

    h2h = get_head_to_head(team_a_id, team_b_id)
    if h2h["total_meetings"] == 0:
        st.info(
            f"{team_a_name} and {team_b_name} haven't played each other in any loaded season."
        )
        return

    st.subheader(f"{h2h['team_a_name']} vs {h2h['team_b_name']}")
    cols = st.columns(4)
    cols[0].metric("Meetings", h2h["total_meetings"])
    cols[1].metric(f"{h2h['team_a_name']} wins", h2h["team_a_wins"])
    cols[2].metric("Draws", h2h["draws"])
    cols[3].metric(f"{h2h['team_b_name']} wins", h2h["team_b_wins"])
    st.caption(
        f"Aggregate goals: {h2h['team_a_name']} {h2h['team_a_goals']} - {h2h['team_b_goals']} {h2h['team_b_name']}"
    )

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown("**Result share**")
        share_df = pd.DataFrame(
            {
                "Outcome": [
                    f"{h2h['team_a_name']} win",
                    "Draw",
                    f"{h2h['team_b_name']} win",
                ],
                "Count": [h2h["team_a_wins"], h2h["draws"], h2h["team_b_wins"]],
            }
        )
        fig = px.bar(
            share_df,
            x="Count",
            y=[""] * len(share_df),
            color="Outcome",
            orientation="h",
        )
        fig.update_layout(yaxis_visible=False, xaxis_title="Meetings", height=200)
        st.plotly_chart(fig, width="stretch")

    with right:
        st.markdown("**Recent meetings**")
        st.dataframe(h2h["recent_meetings"], hide_index=True, width="stretch")


main()
