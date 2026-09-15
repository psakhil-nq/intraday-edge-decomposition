import pandas as pd 

DATA_DIR = r"C:\trading-data\project4"

# load raw nq data and its measured roll gaps
nq = pd.read_csv(f"{DATA_DIR}/NQ-continuous-1m-raw.csv", parse_dates=["ts_event"])
nq_gaps = pd.read_csv(f"{DATA_DIR}/NQ-roll-gap-table.csv", parse_dates=["roll_time"])

# load raw es data and its measured roll gaps
es = pd.read_csv(f"{DATA_DIR}/ES-continuous-1m-raw.csv", parse_dates=["ts_event"])
es_gaps = pd.read_csv(f"{DATA_DIR}/ES-roll-gap-table.csv", parse_dates=["roll_time"])

print("NQ gaps:", nq.shape , nq_gaps.shape)
print("ES gaps:", es.shape , es_gaps.shape) 

def back_adjust(data, gaps):
    adjusted = data.copy()
    adjustment = 0.0

    for _, row in gaps.iloc[::-1].iterrows():
        roll_time = row["roll_time"]
        adjustment += row["gap"]

        mask = adjusted["ts_event"] < roll_time

        adjusted.loc[mask, ["open", "high", "low", "close"]] += row["gap"]

    adjusted["adjustment_method"] = "difference_back_adjust"

    return adjusted


nq_adjusted = back_adjust(nq, nq_gaps)
es_adjusted = back_adjust(es, es_gaps)

print("NQ adjusted:", nq_adjusted.shape)
print("ES adjusted:", es_adjusted.shape)

print("\nNQ latest:")
print(nq_adjusted.tail(3)[
    ["ts_event", "open", "high", "low", "close", "adjustment_method"]
])

print("\nNQ earliest:")
print(nq_adjusted.head(3)[
    ["ts_event", "open", "high", "low", "close"]
])
for _, row in nq_gaps.iterrows():
    t = row["roll_time"]

    window = nq_adjusted[
        (nq_adjusted["ts_event"] >= t - pd.Timedelta(minutes=2)) &
        (nq_adjusted["ts_event"] <= t + pd.Timedelta(minutes=2))
    ]

    print(f"\n--- NQ roll: {t} ---")
    print(window[["ts_event", "instrument_id", "open", "high", "low", "close"]]
          .to_string(index=False))

# Verify that bar-to-bar price changes are preserved
es_raw_returns = es["close"].diff()
es_adj_returns = es_adjusted["close"].diff()

diff = (es_raw_returns - es_adj_returns).abs()

print("\nES return differences:")
print("Max difference:", diff.max())
print("Non-zero differences:", (diff > 1e-9).sum())

nq_adjusted.to_csv(
    f"{DATA_DIR}\\NQ-continuous-1m-adjusted.csv",
    index=False
)

es_adjusted.to_csv(
    f"{DATA_DIR}\\ES-continuous-1m-adjusted.csv",
    index=False
)

print("Adjusted datasets saved.")