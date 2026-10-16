
import heapq

import numpy as np
import pandas as pd

from config import (
    QUALITY_REQUIRED_WINDOWS,
    QUALITY_MAX_MISSING_RUN,
    SESSION_TZ,
    TICK_SIZE,
    NY_AM_START,
    PROXY_A_LOOKBACK_HOURS,
    FIB_BULLISH_THRESHOLD,
    FIB_BEARISH_THRESHOLD,
    FORCED_FLAT_END,
    FOUR_HOUR_SESSION_ANCHOR,
)

from session import (
    add_et_timestamp,
    add_session_date,
    add_session_label,
)

from session_quality import (
    build_session_quality,
    build_session_eligibility,
)


INSTRUMENT_FILES = {
    "NQ": "NQ-continuous-1m-adjusted.csv",
    "ES": "ES-continuous-1m-adjusted.csv",
}

FOUR_HOUR_RULE = "4h"
ONE_HOUR_RULE = "1h"
THIRTY_MIN_RULE = "30min"

NY_AM_START_OBJ = pd.to_datetime(NY_AM_START).time()
FORCED_FLAT_END_OBJ = pd.to_datetime(FORCED_FLAT_END).time()

FOUR_HOUR_DURATION = pd.Timedelta(hours=4)
ONE_HOUR_DURATION = pd.Timedelta(hours=1)
THIRTY_MIN_DURATION = pd.Timedelta(minutes=30)

HTF_IFVG_COLUMNS = [
    "timeframe",
    "fvg_direction",
    "ifvg_direction",
    "formation_time",
    "inversion_time",
    "qualification_time",
    "box_bottom",
    "box_top",
    "formation_id",
]


def load_instrument(symbol):
    """Load only columns required by CP2B."""
    filename = INSTRUMENT_FILES[symbol]

    data = pd.read_csv(
        filename,
        usecols=[
            "ts_event",
            "open",
            "high",
            "low",
            "close",
        ],
    )

    data["ts_event"] = pd.to_datetime(
        data["ts_event"],
        utc=True,
    )

    data = add_et_timestamp(data)
    data = add_session_date(data)
    data = add_session_label(data)

    return data.sort_values(
        "ts_event"
    ).reset_index(drop=True)


def get_eligible_sessions(data):
    """Use CP1's centralized eligibility rule."""
    quality = build_session_quality(data)
    eligibility = build_session_eligibility(quality)

    return eligibility.loc[
        eligibility["eligible"],
        "session_date",
    ].tolist()


def build_htf_bars(data, rule):
    """
    Build HTF OHLC bars.

    30m / 1H use ET clock boundaries.

    4H is anchored to the CME 18:00 ET session open:
    18:00, 22:00, 02:00, 06:00, 10:00, 14:00.

    The implementation is vectorized.
    """

    base = data[
        [
            "ts_et",
            "open",
            "high",
            "low",
            "close",
        ]
    ].copy()

    if rule != FOUR_HOUR_RULE:
        htf = (
            base.set_index("ts_et")
            .resample(
                rule,
                label="left",
                closed="left",
            )
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                }
            )
            .dropna()
            .reset_index()
        )

        return add_session_date(htf)

    # The synthetic CP2B audit passes only ts_et + OHLC,
    # so create session_date here if it is not already present.
    with_session = add_session_date(
        base.copy()
    )

    session_start = (
        pd.to_datetime(
            with_session["session_date"].astype(str)
            + " "
            + str(FOUR_HOUR_SESSION_ANCHOR)
        )
        .dt.tz_localize(SESSION_TZ)
        - pd.Timedelta(days=1)
    )

    elapsed = (
        with_session["ts_et"]
        - session_start
    )

    periods = (
        elapsed // FOUR_HOUR_DURATION
    )

    with_session["bar_start"] = (
        session_start
        + periods * FOUR_HOUR_DURATION
    )

    htf = (
        with_session.groupby(
            "bar_start",
            sort=True,
        )
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
        )
        .reset_index()
        .rename(
            columns={
                "bar_start": "ts_et"
            }
        )
    )

    return add_session_date(htf)


def build_qualified_htf_ifvgs(
    htf,
    rule,
):
    """
    Build qualified HTF iFVGs with event-driven heaps.

    Sequence:
        FVG forms
        -> first later close-through creates inversion
        -> NEXT candle must respect the inverted zone
        -> qualification_time = respecting candle close

    This avoids scanning every future candle for every FVG.
    """

    if htf.empty:
        return pd.DataFrame(
            columns=HTF_IFVG_COLUMNS
        )

    htf = (
        htf.sort_values("ts_et")
        .reset_index(drop=True)
    )

    if rule == THIRTY_MIN_RULE:
        duration = THIRTY_MIN_DURATION
    elif rule == ONE_HOUR_RULE:
        duration = ONE_HOUR_DURATION
    else:
        raise ValueError(
            f"HTF iFVGs support only 30m/1H, got {rule}"
        )

    bars = htf[
        [
            "ts_et",
            "open",
            "high",
            "low",
            "close",
        ]
    ]

    ts = bars["ts_et"].to_numpy()
    opens = bars["open"].to_numpy(dtype=float)
    highs = bars["high"].to_numpy(dtype=float)
    lows = bars["low"].to_numpy(dtype=float)
    closes = bars["close"].to_numpy(dtype=float)

    bullish_heap = []
    bearish_heap = []
    pending_respect = []
    records = []

    formation_id = 0

    for i in range(len(bars)):

        # ---------------------------------------------------------
        # 1. A zone inverted on the previous bar gets exactly
        #    this one bar to respect the inverted zone.
        # ---------------------------------------------------------
        if pending_respect:
            row_high = highs[i]
            row_low = lows[i]
            row_close = closes[i]
            row_close_time = ts[i] + duration

            for pending in pending_respect:

                if pending["ifvg_direction"] == "BEARISH":
                    respected = (
                        row_high >= pending["box_bottom"]
                        and row_close < pending["box_bottom"]
                    )
                else:
                    respected = (
                        row_low <= pending["box_top"]
                        and row_close > pending["box_top"]
                    )

                if respected:
                    records.append(
                        {
                            "timeframe": rule,
                            "fvg_direction": pending["fvg_direction"],
                            "ifvg_direction": pending["ifvg_direction"],
                            "formation_time": pending["formation_time"],
                            "inversion_time": pending["inversion_time"],
                            "qualification_time": row_close_time,
                            "box_bottom": pending["box_bottom"],
                            "box_top": pending["box_top"],
                            "formation_id": pending["formation_id"],
                        }
                    )

            pending_respect = []

        # ---------------------------------------------------------
        # 2. Existing FVGs can invert on the current candle.
        # ---------------------------------------------------------
        current_close = closes[i]
        current_close_time = ts[i] + duration

        while bullish_heap:
            negative_bottom = bullish_heap[0][0]
            box_bottom = -negative_bottom

            if current_close >= box_bottom:
                break

            (
                _,
                fvg_id,
                formation_time,
                box_top,
            ) = heapq.heappop(
                bullish_heap
            )

            pending_respect.append(
                {
                    "fvg_direction": "BULLISH",
                    "ifvg_direction": "BEARISH",
                    "formation_time": formation_time,
                    "inversion_time": current_close_time,
                    "box_bottom": box_bottom,
                    "box_top": box_top,
                    "formation_id": fvg_id,
                }
            )

        while bearish_heap:
            box_top = bearish_heap[0][0]

            if current_close <= box_top:
                break

            (
                _,
                fvg_id,
                formation_time,
                box_bottom,
            ) = heapq.heappop(
                bearish_heap
            )

            pending_respect.append(
                {
                    "fvg_direction": "BEARISH",
                    "ifvg_direction": "BULLISH",
                    "formation_time": formation_time,
                    "inversion_time": current_close_time,
                    "box_bottom": box_bottom,
                    "box_top": box_top,
                    "formation_id": fvg_id,
                }
            )

        # ---------------------------------------------------------
        # 3. Form a new FVG from c1/c2/c3.
        #    It cannot invert on its own formation candle because
        #    the FVG is only known when c3 closes.
        # ---------------------------------------------------------
        if i >= 2:
            c1_open = opens[i - 2]
            c1_close = closes[i - 2]
            c1_high = highs[i - 2]
            c1_low = lows[i - 2]

            c3_high = highs[i]
            c3_low = lows[i]

            box_bottom = min(
                c1_open,
                c1_close,
            )
            box_top = max(
                c1_open,
                c1_close,
            )

            if box_bottom != box_top:

                bullish_fvg = (
                    c1_high + TICK_SIZE
                    <= c3_low
                )

                bearish_fvg = (
                    c1_low - TICK_SIZE
                    >= c3_high
                )

                if bullish_fvg or bearish_fvg:
                    formation_id += 1
                    formation_time = (
                        ts[i] + duration
                    )

                    if bullish_fvg:
                        heapq.heappush(
                            bullish_heap,
                            (
                                -box_bottom,
                                formation_id,
                                formation_time,
                                box_top,
                            ),
                        )
                    else:
                        heapq.heappush(
                            bearish_heap,
                            (
                                box_top,
                                formation_id,
                                formation_time,
                                box_bottom,
                            ),
                        )

    return pd.DataFrame(
        records,
        columns=HTF_IFVG_COLUMNS,
    )


def add_session_date_to_inversions(
    inversions
):
    if inversions.empty:
        if "session_date" not in inversions.columns:
            result = inversions.copy()
            result["session_date"] = pd.Series(
                dtype="object"
            )
            return result
        return inversions

    result = inversions.copy()

    temp = pd.DataFrame(
        {
            "ts_et": result["inversion_time"]
        }
    )

    temp = add_session_date(temp)

    result["session_date"] = (
        temp["session_date"].to_numpy()
    )

    return result


def get_0930_open(
    data,
    session_date,
):
    bars = data[
        (data["session_date"] == session_date)
        & (
            data["ts_et"].dt.time
            == NY_AM_START_OBJ
        )
    ]

    if bars.empty:
        return None

    return float(
        bars.iloc[0]["open"]
    )


def zone_distance(
    price,
    bottom,
    top,
):
    if bottom <= price <= top:
        return 0.0

    if price < bottom:
        return bottom - price

    return price - top


def classify_proxy_a(
    session_date,
    reference_price,
    htf_ifvgs,
):
    """
    Proxy A:

    1H has priority over 30m.

    Current:
        inversion_time strictly inside the previous 24h

    Availability:
        qualification_time <= 09:30

    Selection:
        closest zone to 09:30 reference price

    Mapping:
        bullish iFVG -> bearish bias
        bearish iFVG -> bullish bias
    """

    reference_time = (
        pd.Timestamp(session_date)
        .tz_localize(SESSION_TZ)
        + pd.Timedelta(
            hours=9,
            minutes=30,
        )
    )

    lookback_start = (
        reference_time
        - pd.Timedelta(
            hours=PROXY_A_LOOKBACK_HOURS
        )
    )

    required_columns = {
        "inversion_time",
        "qualification_time",
        "timeframe",
        "ifvg_direction",
        "box_bottom",
        "box_top",
    }

    if (
        htf_ifvgs.empty
        or not required_columns.issubset(
            htf_ifvgs.columns
        )
    ):
        return "NO_CALL"

    current = htf_ifvgs[
        (htf_ifvgs["inversion_time"] > lookback_start)
        & (htf_ifvgs["inversion_time"] < reference_time)
        & (
            htf_ifvgs["qualification_time"]
            <= reference_time
        )
    ]

    if current.empty:
        return "NO_CALL"

    one_hour = current[
        current["timeframe"] == ONE_HOUR_RULE
    ]

    if not one_hour.empty:
        selected_pool = one_hour
    else:
        selected_pool = current[
            current["timeframe"] == THIRTY_MIN_RULE
        ]

    if selected_pool.empty:
        return "NO_CALL"

    bottoms = selected_pool[
        "box_bottom"
    ].to_numpy(dtype=float)

    tops = selected_pool[
        "box_top"
    ].to_numpy(dtype=float)

    distances = np.maximum(
        bottoms - reference_price,
        0.0,
    ) + np.maximum(
        reference_price - tops,
        0.0,
    )

    minimum_distance = distances.min()

    nearest = selected_pool[
        distances == minimum_distance
    ]

    directions = set(
        nearest["ifvg_direction"]
    )

    if (
        "BULLISH" in directions
        and "BEARISH" in directions
    ):
        return "TRANSITION"

    if "BULLISH" in directions:
        return "BEARISH"

    if "BEARISH" in directions:
        return "BULLISH"

    return "NO_CALL"


def get_most_recent_completed_4h(
    four_hour,
    session_date,
):
    """
    Latest completed 4H candle before 09:30 ET.
    """

    reference_time = (
        pd.Timestamp(session_date)
        .tz_localize(SESSION_TZ)
        + pd.Timedelta(
            hours=9,
            minutes=30,
        )
    )

    completed = four_hour[
        (
            four_hour["ts_et"]
            + FOUR_HOUR_DURATION
        ) <= reference_time
    ]

    if completed.empty:
        return None

    return completed.iloc[-1]


def classify_proxy_b(
    four_hour,
    session_date,
    reference_price,
):
    """
    Proxy B:

    Most recent completed 4H candle.

    Doji -> NO_CALL.

    position = (price - low) / (high - low)

    < 0.45       -> BULLISH
    0.45-0.55    -> NO_CALL
    > 0.55       -> BEARISH
    """

    candle = get_most_recent_completed_4h(
        four_hour,
        session_date,
    )

    if candle is None:
        return "NO_CALL"

    candle_open = float(
        candle["open"]
    )
    candle_close = float(
        candle["close"]
    )
    candle_high = float(
        candle["high"]
    )
    candle_low = float(
        candle["low"]
    )

    if candle_high == candle_low:
        return "NO_CALL"

    if candle_close == candle_open:
        return "NO_CALL"

    ratio = (
        reference_price - candle_low
    ) / (
        candle_high - candle_low
    )

    if ratio < FIB_BULLISH_THRESHOLD:
        return "BULLISH"

    if ratio > FIB_BEARISH_THRESHOLD:
        return "BEARISH"

    return "NO_CALL"


def classify_oracle(
    data,
    session_date,
):
    """
    Oracle:

    09:30 ET open versus the final observed close
    at or before FORCED_FLAT_END.
    """

    session_data = data[
        data["session_date"] == session_date
    ]

    reference_bars = session_data[
        session_data["ts_et"].dt.time
        == NY_AM_START_OBJ
    ]

    if reference_bars.empty:
        return "NO_CALL"

    reference_price = float(
        reference_bars.iloc[0]["open"]
    )

    final_candidates = session_data[
        session_data["ts_et"].dt.time
        <= FORCED_FLAT_END_OBJ
    ]

    if final_candidates.empty:
        return "NO_CALL"

    final_close = float(
        final_candidates.iloc[-1]["close"]
    )

    if final_close > reference_price:
        return "BULLISH"

    if final_close < reference_price:
        return "BEARISH"

    return "NO_CALL"


def build_reference_table(
    data,
    eligible_dates,
):
    """
    Precompute the 09:30 reference price and Oracle close once.

    This avoids scanning the 1.77M-row dataset once per session.
    """

    eligible_index = pd.Index(
        eligible_dates,
        name="session_date",
    )

    reference_prices = (
        data[
            data["ts_et"].dt.time
            == NY_AM_START_OBJ
        ]
        .groupby("session_date")["open"]
        .first()
        .reindex(eligible_index)
    )

    final_closes = (
        data[
            data["ts_et"].dt.time
            <= FORCED_FLAT_END_OBJ
        ]
        .groupby("session_date")["close"]
        .last()
        .reindex(eligible_index)
    )

    if reference_prices.isna().any():
        missing = reference_prices[
            reference_prices.isna()
        ].index.tolist()
        raise AssertionError(
            f"Missing 09:30 reference bars: {missing}"
        )

    oracle = np.where(
        final_closes.isna(),
        "NO_CALL",
        np.where(
            final_closes.to_numpy()
            > reference_prices.to_numpy(),
            "BULLISH",
            np.where(
                final_closes.to_numpy()
                < reference_prices.to_numpy(),
                "BEARISH",
                "NO_CALL",
            ),
        ),
    )

    reference_table = pd.DataFrame(
        {
            "session_date": eligible_index,
            "reference_price": reference_prices.to_numpy(
                dtype=float
            ),
            "reference_time": pd.to_datetime(
                eligible_index.astype(str)
                + " "
                + NY_AM_START
            ).tz_localize(
                SESSION_TZ
            ),
            "oracle": oracle,
        }
    )

    return reference_table


def build_proxy_b_table(
    reference_table,
    four_hour,
):
    """
    Use merge_asof to select the most recent completed
    4H candle for each eligible session.
    """

    fh = four_hour.copy()

    fh["end_time"] = (
        fh["ts_et"]
        + FOUR_HOUR_DURATION
    )

    fh = fh.sort_values(
        [
            "session_date",
            "end_time",
        ]
    )

    refs = reference_table[
        [
            "session_date",
            "reference_time",
            "reference_price",
        ]
    ].sort_values(
        [
            "session_date",
            "reference_time",
        ]
    )

    matched = pd.merge_asof(
        refs,
        fh[
            [
                "session_date",
                "end_time",
                "open",
                "high",
                "low",
                "close",
            ]
        ],
        left_on="reference_time",
        right_on="end_time",
        by="session_date",
        direction="backward",
        allow_exact_matches=True,
    )

    candle_range = (
        matched["high"]
        - matched["low"]
    )

    position = (
        matched["reference_price"]
        - matched["low"]
    ) / candle_range

    proxy_b = np.where(
        matched["high"].isna()
        | matched["open"].isna()
        | matched["close"].isna()
        | (candle_range == 0)
        | (matched["close"] == matched["open"]),
        "NO_CALL",
        np.where(
            position < FIB_BULLISH_THRESHOLD,
            "BULLISH",
            np.where(
                position > FIB_BEARISH_THRESHOLD,
                "BEARISH",
                "NO_CALL",
            ),
        ),
    )

    return pd.DataFrame(
        {
            "session_date": matched["session_date"],
            "proxy_b": proxy_b,
        }
    )


def build_proxy_a_table(
    reference_table,
    htf_ifvgs,
):
    """
    Compute Proxy A once per session using sorted inversion times.

    This avoids filtering the full HTF iFVG table from scratch
    for every session.
    """

    required_columns = {
        "inversion_time",
        "qualification_time",
        "timeframe",
        "ifvg_direction",
        "box_bottom",
        "box_top",
    }

    if (
        htf_ifvgs.empty
        or not required_columns.issubset(
            htf_ifvgs.columns
        )
    ):
        return pd.DataFrame(
            {
                "session_date":
                    reference_table["session_date"],
                "proxy_a":
                    "NO_CALL",
            }
        )

    ordered = (
        htf_ifvgs.sort_values(
            "inversion_time"
        )
        .reset_index(drop=True)
    )

    inversion_ns = (
        ordered["inversion_time"]
        .astype("int64")
        .to_numpy()
    )

    labels = []

    for row in reference_table.itertuples(
        index=False
    ):

        ref_time = row.reference_time
        ref_ns = ref_time.value
        lookback_ns = (
            ref_time
            - pd.Timedelta(
                hours=PROXY_A_LOOKBACK_HOURS
            )
        ).value

        left = np.searchsorted(
            inversion_ns,
            lookback_ns,
            side="right",
        )

        right = np.searchsorted(
            inversion_ns,
            ref_ns,
            side="left",
        )

        if left >= right:
            labels.append("NO_CALL")
            continue

        current = ordered.iloc[
            left:right
        ]

        current = current[
            current["qualification_time"]
            <= ref_time
        ]

        if current.empty:
            labels.append("NO_CALL")
            continue

        one_hour = current[
            current["timeframe"]
            == ONE_HOUR_RULE
        ]

        if not one_hour.empty:
            selected = one_hour
        else:
            selected = current[
                current["timeframe"]
                == THIRTY_MIN_RULE
            ]

        if selected.empty:
            labels.append("NO_CALL")
            continue

        bottoms = selected[
            "box_bottom"
        ].to_numpy(dtype=float)

        tops = selected[
            "box_top"
        ].to_numpy(dtype=float)

        distances = np.maximum(
            bottoms - row.reference_price,
            0.0,
        ) + np.maximum(
            row.reference_price - tops,
            0.0,
        )

        minimum_distance = distances.min()

        directions = set(
            selected.iloc[
                np.flatnonzero(
                    distances
                    == minimum_distance
                )
            ]["ifvg_direction"]
        )

        if (
            "BULLISH" in directions
            and "BEARISH" in directions
        ):
            labels.append("TRANSITION")
        elif "BULLISH" in directions:
            labels.append("BEARISH")
        elif "BEARISH" in directions:
            labels.append("BULLISH")
        else:
            labels.append("NO_CALL")

    return pd.DataFrame(
        {
            "session_date":
                reference_table["session_date"],
            "proxy_a": labels,
        }
    )


def build_bias_table(
    data,
    eligible_dates,
    proxy_a_ifvgs,
    four_hour,
):
    """
    Build all bias labels from precomputed tables.

    No per-session full-data scan is performed.
    """

    reference_table = build_reference_table(
        data,
        eligible_dates,
    )

    proxy_a_table = build_proxy_a_table(
        reference_table,
        proxy_a_ifvgs,
    )

    proxy_b_table = build_proxy_b_table(
        reference_table,
        four_hour,
    )

    bias_table = (
        reference_table
        .merge(
            proxy_a_table,
            on="session_date",
            how="left",
            validate="one_to_one",
        )
        .merge(
            proxy_b_table,
            on="session_date",
            how="left",
            validate="one_to_one",
        )
    )

    proxy_a = bias_table["proxy_a"]
    proxy_b = bias_table["proxy_b"]

    bias_table["a_b_result"] = np.select(
        [
            (
                proxy_a.isin(
                    ["BULLISH", "BEARISH"]
                )
                & (
                    proxy_a == proxy_b
                )
            ),
            (
                proxy_a.isin(
                    ["BULLISH", "BEARISH"]
                )
                & proxy_b.isin(
                    ["BULLISH", "BEARISH"]
                )
            ),
        ],
        [
            proxy_a,
            "DISAGREE",
        ],
        default="NO_CALL",
    )

    return bias_table


def count_labels(
    labels,
    ordered_labels,
):
    counts = {}

    for label in ordered_labels:
        counts[label] = int(
            (labels == label).sum()
        )

    return counts


def print_counts(
    title,
    counts,
):
    print()
    print(title)

    for label, count in counts.items():
        print(
            f"  {label:<14} {count}"
        )


def summarise_bias(
    bias_table,
    symbol,
):
    total = len(
        bias_table
    )

    print()
    print(
        f"=== {symbol} CP2B BIAS FREQUENCY ==="
    )

    print(
        f"Eligible sessions: {total}"
    )

    oracle_counts = count_labels(
        bias_table["oracle"],
        [
            "BULLISH",
            "BEARISH",
            "NO_CALL",
        ],
    )

    proxy_a_counts = count_labels(
        bias_table["proxy_a"],
        [
            "BULLISH",
            "BEARISH",
            "TRANSITION",
            "NO_CALL",
        ],
    )

    proxy_b_counts = count_labels(
        bias_table["proxy_b"],
        [
            "BULLISH",
            "BEARISH",
            "NO_CALL",
        ],
    )

    ab_counts = count_labels(
        bias_table["a_b_result"],
        [
            "BULLISH",
            "BEARISH",
            "DISAGREE",
            "NO_CALL",
        ],
    )

    print_counts(
        "Oracle:",
        oracle_counts,
    )

    print_counts(
        "Proxy A:",
        proxy_a_counts,
    )

    print_counts(
        "Proxy B:",
        proxy_b_counts,
    )

    print_counts(
        "Proxy A + B:",
        ab_counts,
    )

    oracle_total = sum(
        oracle_counts.values()
    )

    if oracle_total != total:
        raise AssertionError(
            f"{symbol}: Oracle labels do not partition sessions"
        )

    proxy_a_total = sum(
        proxy_a_counts.values()
    )

    if proxy_a_total != total:
        raise AssertionError(
            f"{symbol}: Proxy A labels do not partition sessions"
        )

    proxy_b_total = sum(
        proxy_b_counts.values()
    )

    if proxy_b_total != total:
        raise AssertionError(
            f"{symbol}: Proxy B labels do not partition sessions"
        )

    ab_total = sum(
        ab_counts.values()
    )

    if ab_total != total:
        raise AssertionError(
            f"{symbol}: A+B labels do not partition sessions"
        )

    agreement_sessions = (
        ab_counts["BULLISH"]
        + ab_counts["BEARISH"]
    )

    print()
    print(
        f"Proxy A+B directional agreement: "
        f"{agreement_sessions}"
    )

    print(
        f"Proxy A+B directional disagreement: "
        f"{ab_counts['DISAGREE']}"
    )

    print(
        f"Proxy A+B unavailable/transition: "
        f"{ab_counts['NO_CALL']}"
    )


def main():
    for symbol in INSTRUMENT_FILES:

        print()
        print(
            f"Loading {symbol}...",
            flush=True,
        )

        data = load_instrument(
            symbol
        )

        eligible_dates = (
            get_eligible_sessions(
                data
            )
        )

        if len(eligible_dates) != 1289:
            raise AssertionError(
                f"{symbol}: expected 1289 eligible "
                f"sessions, got {len(eligible_dates)}"
            )

        print(
            "Building 30m HTF bars...",
            flush=True,
        )

        thirty_min = build_htf_bars(
            data,
            THIRTY_MIN_RULE,
        )

        print(
            "Building 1H HTF bars...",
            flush=True,
        )

        one_hour = build_htf_bars(
            data,
            ONE_HOUR_RULE,
        )

        print(
            "Building 4H HTF bars...",
            flush=True,
        )

        four_hour = build_htf_bars(
            data,
            FOUR_HOUR_RULE,
        )

        print(
            "Building qualified 30m iFVGs...",
            flush=True,
        )

        thirty_min_ifvgs = (
            build_qualified_htf_ifvgs(
                thirty_min,
                THIRTY_MIN_RULE,
            )
        )

        print(
            "Building qualified 1H iFVGs...",
            flush=True,
        )

        one_hour_ifvgs = (
            build_qualified_htf_ifvgs(
                one_hour,
                ONE_HOUR_RULE,
            )
        )

        htf_ifvgs = pd.concat(
            [
                thirty_min_ifvgs,
                one_hour_ifvgs,
            ],
            ignore_index=True,
        )

        htf_ifvgs = (
            add_session_date_to_inversions(
                htf_ifvgs
            )
        )

        print(
            f"Qualified HTF iFVG inversions: "
            f"{len(htf_ifvgs)}",
            flush=True,
        )

        bias_table = build_bias_table(
            data=data,
            eligible_dates=eligible_dates,
            proxy_a_ifvgs=htf_ifvgs,
            four_hour=four_hour,
        )

        summarise_bias(
            bias_table,
            symbol,
        )


if __name__ == "__main__":
    main()
