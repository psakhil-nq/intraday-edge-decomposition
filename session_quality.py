import numpy as np
import pandas as pd
from datetime import datetime

from config import (
    SESSION_TZ,
    ASIA_START,
    ASIA_END,
    LONDON_START,
    LONDON_END,
    NY_AM_START,
    NY_AM_END,
    QUALITY_REQUIRED_WINDOWS,
    QUALITY_MAX_MISSING_RUN,
)


QUALITY_WINDOWS = {
    "Asia": (ASIA_START, ASIA_END),
    "London": (LONDON_START, LONDON_END),
    "NY AM": (NY_AM_START, NY_AM_END),
}


def time_to_minutes(time_string):
    parsed = datetime.strptime(time_string, "%H:%M")
    return parsed.hour * 60 + parsed.minute


def build_expected_grid(session_dates):
    session_dates = pd.DatetimeIndex(
        pd.to_datetime(session_dates)
    ).normalize()

    grids = []

    for window_name, (start_str, end_str) in QUALITY_WINDOWS.items():

        start_minutes = time_to_minutes(start_str)
        end_minutes = time_to_minutes(end_str)

        crosses_midnight = end_minutes <= start_minutes

        if crosses_midnight:
            expected_minutes = (
                end_minutes + 1440 - start_minutes
            )
            # Overnight windows begin on the previous calendar date.
            start_dates = session_dates - pd.Timedelta(days=1)
        else:
            expected_minutes = end_minutes - start_minutes
            start_dates = session_dates

        start_strings = (
            start_dates.strftime("%Y-%m-%d")
            + " "
            + start_str
        )

        start_timestamps = pd.DatetimeIndex(
            pd.to_datetime(start_strings)
        ).tz_localize(SESSION_TZ)

        minute_offsets = np.arange(expected_minutes)

        timestamps = (
            start_timestamps.repeat(expected_minutes)
            + pd.to_timedelta(
                np.tile(
                    minute_offsets,
                    len(start_timestamps)
                ),
                unit="m",
            )
        )

        grid = pd.DataFrame({
            "session_date": np.repeat(
                session_dates.date,
                expected_minutes,
            ),
            "session_label": window_name,
            "ts_et": timestamps,
        })

        grids.append(grid)

    expected_grid = pd.concat(
        grids,
        ignore_index=True,
    )

    return expected_grid


def build_session_quality(data, session_dates=None):

    if session_dates is None:
        session_dates = data["session_date"].drop_duplicates()

    expected_grid = build_expected_grid(session_dates)

    observed = (
        data[
            data["session_label"].isin(
                QUALITY_WINDOWS.keys()
            )
        ][
            [
                "session_date",
                "session_label",
                "ts_et",
            ]
        ]
        .drop_duplicates()
    )

    observed["present"] = True

    merged = expected_grid.merge(
        observed,
        on=[
            "session_date",
            "session_label",
            "ts_et",
        ],
        how="left",
        indicator=True,
    )

    merged["present"] = merged["_merge"].eq("both")
    merged["missing"] = ~merged["present"]

    merged = merged.sort_values(
        [
            "session_date",
            "session_label",
            "ts_et",
        ]
    ).reset_index(drop=True)

    merged["run_id"] = (
        merged
        .groupby(
            [
                "session_date",
                "session_label",
            ]
        )["present"]
        .cumsum()
    )

    missing_runs = (
        merged[merged["missing"]]
        .groupby(
            [
                "session_date",
                "session_label",
                "run_id",
            ]
        )
        .size()
        .groupby(
            [
                "session_date",
                "session_label",
            ]
        )
        .max()
    )

    quality = (
        merged
        .groupby(
            [
                "session_date",
                "session_label",
            ]
        )
        .agg(
            expected_bars=("present", "size"),
            observed_bars=("present", "sum"),
            first_minute_missing=(
                "present",
                lambda values: not values.iloc[0],
            ),
            last_minute_missing=(
                "present",
                lambda values: not values.iloc[-1],
            ),
        )
        .reset_index()
    )

    quality["missing_bars"] = (
        quality["expected_bars"]
        - quality["observed_bars"]
    )

    quality["completeness_ratio"] = (
        quality["observed_bars"]
        / quality["expected_bars"]
    )

    quality["longest_missing_run"] = (
        missing_runs
        .reindex(
            pd.MultiIndex.from_frame(
                quality[
                    [
                        "session_date",
                        "session_label",
                    ]
                ]
            ),
            fill_value=0,
        )
        .to_numpy()
    )

    quality["longest_missing_run"] = (
        quality["longest_missing_run"]
        .astype(int)
    )

    return quality

def build_session_eligibility(quality):

    required = quality[
        quality["session_label"].isin(
            QUALITY_REQUIRED_WINDOWS
        )
    ].copy()

    required["window_ok"] = (
        (required["observed_bars"] > 0)
        & (required["longest_missing_run"] <= QUALITY_MAX_MISSING_RUN)
    )

    eligibility = (
        required
        .groupby("session_date", as_index=False)["window_ok"]
        .all()
        .rename(columns={"window_ok": "eligible"})
    )

    return eligibility