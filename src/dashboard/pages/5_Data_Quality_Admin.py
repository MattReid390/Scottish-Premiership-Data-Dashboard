"""Data Quality / Admin page (see docs/visualisation_plan.md section 3.6).

Operational visibility into the ingestion pipeline, primarily for the
maintainer rather than end users.
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.data_access import (
    get_match_status_counts,
    get_stuck_scheduled_matches,
    list_recent_ingestion_logs,
)

st.set_page_config(
    page_title="Data Quality / Admin — Scottish Premiership Dashboard",
    page_icon="⚽",
    layout="wide",
)


def main() -> None:
    st.title("Data Quality / Admin")

    if st.button("Clear cached data"):
        st.cache_data.clear()
        st.success(
            "Cache cleared - every page will recompute from the database on next load."
        )

    st.markdown("**Recent ingestion runs**")
    logs_df = list_recent_ingestion_logs()
    if logs_df.empty:
        st.info("No ingestion runs recorded yet.")
    else:
        status_counts = logs_df["Status"].value_counts()
        cols = st.columns(3)
        cols[0].metric("Total runs shown", len(logs_df))
        cols[1].metric("Successful", int(status_counts.get("success", 0)))
        cols[2].metric(
            "Failed / partial",
            int(status_counts.get("failed", 0) + status_counts.get("partial", 0)),
        )
        st.dataframe(logs_df, hide_index=True, width="stretch")

    st.divider()
    st.markdown("**Match status counts by season**")
    status_df = get_match_status_counts()
    if status_df.empty:
        st.info("No matches loaded yet.")
    else:
        pivot = status_df.pivot_table(
            index="Season", columns="Status", values="Count", fill_value=0
        )
        st.dataframe(pivot, width="stretch")

    st.divider()
    st.markdown("**Stuck scheduled matches**")
    st.caption(
        'Matches still marked "scheduled" more than a week after their date - usually a sign a source stopped updating that fixture\'s result.'
    )
    stuck_df = get_stuck_scheduled_matches()
    if stuck_df.empty:
        st.success("None found.")
    else:
        st.warning(f"{len(stuck_df)} match(es) found.")
        st.dataframe(stuck_df, hide_index=True, width="stretch")


main()
