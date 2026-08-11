"""Declarative validation schemas for raw ingested data (see
docs/data_ingestion.md section 4.2, "Validate").

These validate the *source-specific* raw shape (football-data.co.uk's own
column names and conventions) before normalization into the canonical
schema - catching malformed/unexpected files before they reach the
database, per docs/testing_strategy.md section 3.4.
"""

from __future__ import annotations

import pandera.pandas as pa

# football-data.co.uk's Scotland Premiership CSVs carry dozens of betting-odds
# columns we don't use; the schema only constrains the columns the processing
# pipeline actually reads, and otherwise allows extra columns through.
FOOTBALL_DATA_CO_UK_SCHEMA = pa.DataFrameSchema(
    columns={
        "Div": pa.Column(str, pa.Check.isin(["SC0"])),
        "Date": pa.Column(str, nullable=False),
        "HomeTeam": pa.Column(str, pa.Check.str_length(min_value=1), nullable=False),
        "AwayTeam": pa.Column(str, pa.Check.str_length(min_value=1), nullable=False),
        "FTHG": pa.Column(
            float, pa.Check.greater_than_or_equal_to(0), nullable=True, coerce=True
        ),
        "FTAG": pa.Column(
            float, pa.Check.greater_than_or_equal_to(0), nullable=True, coerce=True
        ),
        "FTR": pa.Column(str, pa.Check.isin(["H", "D", "A"]), nullable=True),
    },
    strict=False,
    coerce=False,
)
