import pandas as pd

from session import add_et_timestamp, add_session_date, add_session_label
from session_quality import build_session_quality


DATA_PATH = r"C:\trading-data\project4\NQ-continuous-1m-adjusted.csv"


# Load data
data = pd.read_csv(
    DATA_PATH,
    parse_dates=["ts_event"]
)

# Run CP1 session pipeline
result = add_et_timestamp(data)
result = add_session_date(result)
result = add_session_label(result)
quality = build_session_quality(result)

print("\nSession quality:")
print(quality.head(10).to_string(index=False))


# --------------------------------------------------
# 1. Basic sanity
# --------------------------------------------------

print("Rows:", len(result))
print("Unique session dates:", result["session_date"].nunique())

session_dates = result[["session_date"]].drop_duplicates()
session_dates["year"] = pd.to_datetime(
    session_dates["session_date"]
).dt.year

print("\nSessions by year:")
print(
    session_dates.groupby("year")
    .size()
    .sort_index()
)


# --------------------------------------------------
# 2. Session-window counts
# --------------------------------------------------

window_counts = (
    result.groupby(["session_date", "session_label"])
    .size()
    .unstack(fill_value=0)
)

windows = [
    "Asia",
    "London",
    "NY AM",
    "NY Lunch",
    "NY PM"
]

window_summary = (
    window_counts[windows]
    .agg(["min", "median", "max"])
)

print("\nWindow min / median / max:")
print(window_summary)


# --------------------------------------------------
# 3. CME maintenance-hour check
# --------------------------------------------------

halt_counts = (
    result[
        (result["ts_et"].dt.time >= pd.to_datetime("17:00").time()) &
        (result["ts_et"].dt.time < pd.to_datetime("18:00").time())
    ]
    .groupby("session_date")
    .size()
)

print("\n17:00–18:00 ET bars:")
print(halt_counts)


# --------------------------------------------------
# 4. NY AM completeness
# --------------------------------------------------

ny_am_counts = window_counts["NY AM"]

print("\nWorst 10 sessions by NY AM bar count:")
print(
    ny_am_counts
    .sort_values()
    .head(10)
)

summary = (
    quality
    .groupby("session_label")
    .agg(
        complete_sessions=(
            "completeness_ratio",
            lambda x: (x == 1).sum()
        ),
        incomplete_sessions=(
            "completeness_ratio",
            lambda x: (x < 1).sum()
        ),
        max_missing_run=(
            "longest_missing_run",
            "max"
        ),
    )
)