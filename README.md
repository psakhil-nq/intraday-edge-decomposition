## CP0 — Futures Roll Handling

### Continuous Contract Construction

The Project 4 dataset uses Databento continuous futures symbols (`NQ.n.0` and
`ES.n.0`). The continuous series contains price discontinuities when the
underlying contract changes.

We therefore construct a back-adjusted price series while preserving the
original raw data.

### Roll Detection

Rolls are identified from changes in the underlying `instrument_id` within
the continuous dataset.

For each roll:

- The outgoing contract price is its final bar immediately before the roll.
- The incoming contract price is its first bar at or after the roll timestamp.
- The roll gap is:

  `gap = incoming_price - outgoing_price`

The measured roll gaps are stored separately in the NQ and ES roll-gap tables.

### Adjustment Method

We use **difference-based back-adjustment**.

Each historical contract segment is shifted by the cumulative sum of all
subsequent roll gaps.

This preserves absolute point movements. Since futures P&L is calculated from
point movement multiplied by the contract multiplier, a historical 50-point
move must remain a 50-point move after adjustment.

### Fields Adjusted

The adjustment is applied to:

- Open
- High
- Low
- Close

**Volume is not adjusted.**

### Data Provenance

The original Databento CSV files are treated as immutable raw data.

The adjusted dataset is written to a separate file and retains provenance
information identifying the source continuous symbol, adjustment method, and
rolls used.

Raw Databento data is not committed to the public repository.

# CP1 — Session Segmentation and Data Quality

## Session Definitions

All session times are defined in America/New_York (ET) and are evaluated after
converting the UTC Databento timestamps to ET.

| Session | ET window |
|---|---|
| Asia | 20:00–00:00 |
| London | 02:00–05:00 |
| NY AM | 09:30–11:00 |
| NY Lunch | 12:00–13:00 |
| NY PM | 13:30–16:00 |

The CME session_date convention assigns the overnight session beginning at
18:00 ET to the following calendar date. The daily 17:00–18:00 ET maintenance
period is treated as off-session.

## Timestamp Convention

Databento OHLCV bars use `ts_event` as the inclusive start timestamp of the
aggregation period. Therefore, a bar stamped 09:30 represents the minute
09:30:00–09:30:59 and becomes available only after that minute has closed.

Higher-timeframe bars follow the same closed-bar principle. A 1H bar stamped
09:00 cannot be used until 10:00 ET.

## Data Quality Exceptions

The session-quality analysis uses an expected-minute grid rather than inferring
missing data from neighbouring observed bars. This allows completely empty
windows and missing minutes at window boundaries to be detected.

Four material exceptions were identified:

| Session date | Cause | Effect on strategy windows |
|---|---|---|
| 2023-04-07 | Good Friday | NY AM unavailable; session closed before NY AM |
| 2025-01-09 | U.S. National Day of Mourning for former President Jimmy Carter | NY AM unavailable; session closed before NY AM |
| 2025-11-28 | CME market outage | Asia and London incomplete; NY AM complete |
| 2026-04-03 | Good Friday | NY AM unavailable; session closed before NY AM |

The 2023-04-07 Good Friday schedule is documented by CME Group. :contentReference[oaicite:1]{index=1}

The January 9, 2025 National Day of Mourning schedule is documented by CME
Group. :contentReference[oaicite:2]{index=2}

The 2026 Good Friday schedule is documented by CME Group. :contentReference[oaicite:3]{index=3}

## Databento Data-Quality Flags

The following dates were identified during CP0/CP1 as Databento-degraded dates:

- 2021-12-05
- 2022-01-02
- 2024-09-18
- 2025-09-17
- 2025-09-24
- 2025-11-28
- 2026-01-31
- 2026-03-15
- 2026-03-16
- 2026-03-21
- 2026-04-10
- 2026-05-24
- 2026-07-30
- 2026-08-29

These dates are retained in the dataset and flagged rather than automatically
removed. Their effect will be evaluated separately during later validation.
The 2025-11-28 Databento-degraded date overlaps the material session-quality
exceptions. The other three material exceptions are not in the Databento-
degraded-date list.