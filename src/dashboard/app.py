"""Overview / League Table page - the dashboard's landing page (see
docs/visualisation_plan.md section 3.1).

Run with: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from src.dashboard.data_access import (
    get_season_date_range,
    get_standings_table,
    list_seasons,
)
from src.utils.config import load_app_config

st.set_page_config(
    page_title="Scottish Premiership Dashboard", page_icon="⚽", layout="wide"
)


def _zone_positions() -> tuple[set[int], set[int]]:
    try:
        table_config = load_app_config().get("table", {})
    except FileNotFoundError:
        table_config = {}
    european = set(table_config.get("european_qualification_positions", []))
    relegation = set(table_config.get("relegation_positions", []))
    return european, relegation


def _highlight_zones(
    row: pd.Series, european: set[int], relegation: set[int]
) -> list[str]:
    if row["Pos"] in european:
        return ["background-color: rgba(46, 160, 67, 0.18)"] * len(row)
    if row["Pos"] in relegation:
        return ["background-color: rgba(220, 53, 69, 0.18)"] * len(row)
    return [""] * len(row)


def main() -> None:
    st.title("Scottish Premiership — League Table")

    seasons_df = list_seasons()
    if seasons_df.empty:
        st.info(
            "No seasons ingested yet. Run `python -m src.ingestion.backfill_historical` "
            "then `python -m src.processing.run_pipeline` first."
        )
        return

    with st.sidebar:
        st.header("Filters")
        season_label = str(st.selectbox("Season", seasons_df["label"], index=0))
        season_row = seasons_df.loc[seasons_df["label"] == season_label].iloc[0]
        season_id = int(season_row["season_id"])

        as_of_date: dt.date | None = None
        date_range = get_season_date_range(season_id)
        if date_range is not None:
            show_earlier = st.checkbox("View table as of an earlier date")
            if show_earlier:
                as_of_date = st.date_input(
                    "As of date",
                    value=date_range[1],
                    min_value=date_range[0],
                    max_value=date_range[1],
                )

    table_df = get_standings_table(season_id, as_of_date)
    if table_df.empty or table_df["P"].sum() == 0:
        st.info("No matches have been played yet as of this date.")
        return

    display_df = table_df.drop(columns=["team_id"])
    european, relegation = _zone_positions()
    styled = display_df.style.apply(
        _highlight_zones, axis=1, european=european, relegation=relegation
    )
    st.dataframe(styled, hide_index=True, width="stretch")

    caption = season_label
    if as_of_date is not None:
        caption += f" — as of {as_of_date.isoformat()}"
    st.caption(caption)

    if european or relegation:
        legend_bits = []
        if european:
            legend_bits.append("🟢 European qualification")
        if relegation:
            legend_bits.append("🔴 Relegation")
        st.caption(" · ".join(legend_bits))


main()
