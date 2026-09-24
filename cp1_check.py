import pandas as pd

from session import (
    add_et_timestamp,
    add_session_date,
    add_session_label,
)

from config import QUALITY_MAX_MISSING_RUN

from session_quality import (
    build_session_quality,
    build_session_eligibility,
)


DATA_PATHS = {
    "NQ": r"C:\trading-data\project4\NQ-continuous-1m-adjusted.csv",
    "ES": r"C:\trading-data\project4\ES-continuous-1m-adjusted.csv",
}


def run_cp1_checks(instrument, data_path):

    # Load data
    data = pd.read_csv(
        data_path,
        parse_dates=["ts_event"]
    )

    # Run CP1 session pipeline
    result = add_et_timestamp(data)
    result = add_session_date(result)
    result = add_session_label(result)

    quality = build_session_quality(result)
    eligibility = build_session_eligibility(quality)

    print("\nEligibility:")
    print(eligibility["eligible"].value_counts())

    print(f"\n===== {instrument} =====")

    print("\nSession quality:")
    print(quality.head(10).to_string(index=False))

    # --------------------------------------------------
    # 1. Basic sanity
    # --------------------------------------------------
    print("\nRows:", len(result))
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
        "NY PM",
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

    return result, quality,eligibility


# --------------------------------------------------
# CP1D: Run the same checks on NQ and ES
# --------------------------------------------------

nq_result, nq_quality, nq_eligibility = run_cp1_checks(
    "NQ",
    DATA_PATHS["NQ"]
)

es_result, es_quality, es_eligibility = run_cp1_checks(
    "ES",
    DATA_PATHS["ES"]
)


# --------------------------------------------------
# CP1D: NQ vs ES comparison
# --------------------------------------------------

print("\n===== CP1D: NQ vs ES =====")

print("NQ rows:", len(nq_result))
print("ES rows:", len(es_result))
print("Row difference:", len(nq_result) - len(es_result))


# --------------------------------------------------
# Compare session-date sets
# --------------------------------------------------

nq_dates = set(nq_result["session_date"].unique())
es_dates = set(es_result["session_date"].unique())

print("\nNQ session dates:", len(nq_dates))
print("ES session dates:", len(es_dates))

print(
    "NQ-only session dates:",
    sorted(nq_dates - es_dates)
)

print(
    "ES-only session dates:",
    sorted(es_dates - nq_dates)
)


# --------------------------------------------------
# Locate the NQ / ES timestamp differences
# --------------------------------------------------

nq_times = set(nq_result["ts_event"])
es_times = set(es_result["ts_event"])

nq_only_times = sorted(nq_times - es_times)
es_only_times = sorted(es_times - nq_times)

print("\nNQ-only timestamps:", len(nq_only_times))
print("ES-only timestamps:", len(es_only_times))

print("\nFirst NQ-only timestamps:")
print(nq_only_times[:20])

print("\nFirst ES-only timestamps:")
print(es_only_times[:20])
# --------------------------------------------------
# CP1D: Final cross-check diagnostics
# --------------------------------------------------

# 1. Net row-count difference by session date
nq_daily_counts = nq_result.groupby("session_date").size()
es_daily_counts = es_result.groupby("session_date").size()

daily_difference = (
    nq_daily_counts
    .subtract(es_daily_counts, fill_value=0)
    .astype(int)
)

daily_difference = daily_difference[daily_difference != 0]

print("\n===== Row-count differences by session date =====")
print("Dates with a non-zero difference:", len(daily_difference))
print(
    daily_difference
    .sort_values(key=lambda x: x.abs(), ascending=False)
    .head(20)
)


# 2. NQ-only / ES-only timestamps by session label
nq_only = nq_result[
    ~nq_result["ts_event"].isin(es_result["ts_event"])
].copy()

es_only = es_result[
    ~es_result["ts_event"].isin(nq_result["ts_event"])
].copy()

print("\n===== Timestamp differences by session =====")

print("\nNQ-only timestamps by session:")
print(nq_only.groupby("session_label").size())

print("\nES-only timestamps by session:")
print(es_only.groupby("session_label").size())


# 3. zero bars, or a missing run longer than QUALITY_MAX_MISSING_RUN.
for instrument, quality in [
    ("NQ", nq_quality),
    ("ES", es_quality),
]:
    material = quality[
        (quality["observed_bars"] == 0) |
        (quality["longest_missing_run"] > QUALITY_MAX_MISSING_RUN)
    ].copy()

    print(f"\n===== {instrument} material session-quality exceptions =====")

    print(
        material[
            [
                "session_date",
                "session_label",
                "expected_bars",
                "observed_bars",
                "missing_bars",
                "longest_missing_run",
            ]
        ].to_string(index=False)
    )


# 4. Inspect the ES maintenance-hour anomaly
es_maintenance = es_result[
    (es_result["ts_et"].dt.time >= pd.to_datetime("17:00").time()) &
    (es_result["ts_et"].dt.time < pd.to_datetime("18:00").time())
].copy()

print("\n===== ES 17:00–18:00 ET anomaly =====")

print(
    es_maintenance[
        [
            "ts_event",
            "ts_et",
            "session_date",
            "session_label",
            "instrument_id",
            "open",
            "high",
            "low",
            "close",
        ]
    ].to_string(index=False)
)
print("\n===== CP1E eligibility comparison =====")

print(
    "NQ eligible sessions:",
    nq_eligibility["eligible"].sum()
)

print(
    "ES eligible sessions:",
    es_eligibility["eligible"].sum()
)

print(
    "NQ/ES eligibility disagreement:",
    (
        nq_eligibility.set_index("session_date")["eligible"]
        != es_eligibility.set_index("session_date")["eligible"]
    ).sum()
)