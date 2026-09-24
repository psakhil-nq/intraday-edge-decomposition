# Intraday Edge Decomposition

**Research question:** Can a discretionary intraday futures strategy be decomposed into explicit, codeable rules, and what does each individual rule actually contribute to performance?

This project is not an attempt to publish a profitable strategy. The deliverable is the decomposition method and an honest measurement of each rule's marginal contribution. A negative result is a valid outcome and will be reported as one.

**Data:** Databento `GLBX.MDP3`, `ohlcv-1m`, continuous E-mini Nasdaq-100 (`NQ.n.0`) and E-mini S&P 500 (`ES.n.0`) futures, 2021-09-09 to 2026-09-09.

---

## CP0 — Futures Roll Handling

### Continuous Contract Construction

The continuous series (`NQ.n.0` and `ES.n.0`) switches to a new underlying contract at each roll, which creates a price discontinuity. The two contracts trade at different prices, so the jump at the seam is a contract spread, not a market move.

A back-adjusted price series is constructed while the original raw data is preserved unchanged.

### Roll Detection

Rolls are identified from changes in the underlying `instrument_id` within the continuous dataset. Both NQ and ES contain 20 roll transitions over the sample period, and the transitions match the mappings returned by Databento's `symbology.resolve()`.

For each roll:

- The outgoing price is the **close** of the outgoing contract's final bar before the roll.
- The incoming price is the **open** of the incoming contract's first bar at or after the roll timestamp.
- The roll gap is `gap = incoming open − outgoing close`.

The measured gaps are stored in `data/NQ-roll-gap-table.csv` and `data/ES-roll-gap-table.csv`.

### Adjustment Method

Difference-based back-adjustment is used. Each historical contract segment is shifted by the cumulative sum of all later roll gaps.

This preserves absolute point movements. Futures P&L is calculated as point movement multiplied by the contract multiplier, so a historical 50-point move must remain a 50-point move after adjustment. Ratio adjustment would preserve percentage returns instead, which is not the quantity this project measures.

Only Open, High, Low and Close are adjusted. **Volume is not adjusted.**

### Validation

- **Seam check:** in the adjusted series, the incoming contract's first open equals the outgoing contract's last close at all 20 roll boundaries for both instruments.
- **Return invariance:** bar-to-bar close changes in the raw and adjusted series are identical everywhere except at the roll boundaries. NQ shows exactly 20 non-zero differences (largest 317.75 points), and ES shows exactly 20 (largest 74.0 points).
- **Cross-instrument consistency:** the ratio of the largest NQ gap to the largest ES gap (≈4.3) matches the ratio of the two index levels, as expected because calendar spreads scale with the underlying price level.

### Data Provenance

The original Databento files are treated as immutable raw data. The adjusted dataset is written to a separate file and records the source continuous symbol and the adjustment method. The roll dates and gaps used are recorded in the roll-gap tables.

---

## CP1 — Session Segmentation and Data Quality

### Session Definitions

All session times are defined in America/New_York (ET) and evaluated after converting Databento's UTC timestamps to ET, with daylight-saving time handled automatically.

| Session | ET window |
|---|---|
| Asia | 20:00–00:00 |
| London | 02:00–05:00 |
| NY AM | 09:30–11:00 |
| NY Lunch | 12:00–13:00 |
| NY PM | 13:30–16:00 |

These windows define the session highs and lows the strategy rules depend on, so they are part of the strategy specification. **Locked on 22 September 2026.** They will not be changed after any backtest result is seen.

The CME `session_date` convention assigns the overnight session beginning at 18:00 ET to the following calendar date. The daily 17:00–18:00 ET maintenance break is treated as off-session; NQ has no bars during this time, and ES has exactly one bar at 2023-10-30 17:00 ET, which is labelled Off and excluded from every window.

### Timestamp Convention

Databento OHLCV bars use `ts_event` as the inclusive start of the aggregation period. A bar stamped 09:30 therefore covers 09:30:00–09:30:59 and becomes available only after that minute has closed.

Higher-timeframe bars follow the same closed-bar principle: a 1H bar stamped 09:00 cannot be used until 10:00 ET.

### Session-Quality Method

Databento only publishes an OHLCV bar for a minute in which at least one trade occurred, so a missing bar can mean a quiet minute, a scheduled closure, or genuinely lost data.

Completeness is measured against an expected-minute grid for each session and window, rather than inferred from gaps between neighbouring observed bars. This detects completely empty windows and missing minutes at the start or end of a window, which a gap-between-bars method cannot see.

Missing minutes are **not** forward-filled. Filling would create artificial bars with zero range, which could create or suppress signals in rules that react to wicks and gaps.

### NQ Results (strategy windows, 1,293 sessions)

| Window | Complete | Incomplete | Longest missing run |
|---|---:|---:|---:|
| Asia | 1,236 | 57 | 135 minutes |
| London | 1,280 | 13 | 180 minutes |
| NY AM | 1,290 | 3 | 90 minutes |

Apart from the four material exceptions below, incomplete windows contain only short missing runs. These do not independently fail the session eligibility rule defined below.

### Material Exceptions

| Session date | Cause | Observed in data | Effect on strategy windows | Source |
|---|---|---|---|---|
| 2023-04-07 | Good Friday abbreviated session | Last bar 09:14 ET | NY AM unavailable | [CME advisory](https://www.cmegroup.com/tools-information/holiday-calendar/files/2023-good-friday-advisory.pdf) |
| 2025-01-09 | National Day of Mourning for former President Jimmy Carter | Last bar 09:29 ET | NY AM unavailable | [CME Group release](https://investor.cmegroup.com/news-releases/news-release-details/cme-group-announces-trading-hours-us-national-day-mourning-honor) |
| 2025-11-28 | CME Globex outage (data-centre cooling failure) | 645-minute gap; trading resumed 08:30 ET | Asia 103/240 bars (NQ),105/240 (ES) London 0/180; NY AM complete | [CNBC](https://www.cnbc.com/2025/11/28/cme-halts-fx-commodities-futures-trading-after-data-center-issue.html) |
| 2026-04-03 | Good Friday abbreviated session | Last bar 09:14 ET | NY AM unavailable | [CME advisory](https://www.cmegroup.com/tools-information/holiday-calendar/files/2026/2026-good-friday-clearing-advisory.pdf) |

Excluding the 4 exceptions, there are 44 early-close sessions where the last bar occurs at 12:59 or 13:14 ET. On these dates, the London and NY AM sessions remain unaffected, while the NY PM session has no bars.

### Databento Data-Quality Flags

Databento flags 14 dates as degraded. These are **UTC calendar dates**, not CME session dates, so each was mapped to the sessions it overlaps:

| Degraded UTC date | Day | CME session_date(s) affected |
|---|---|---|
| 2021-12-05 | Sun | 2021-12-06 |
| 2022-01-02 | Sun | 2022-01-03 |
| 2024-09-18 | Wed | 2024-09-18, 2024-09-19 |
| 2025-09-17 | Wed | 2025-09-17, 2025-09-18 |
| 2025-09-24 | Wed | 2025-09-24, 2025-09-25 |
| 2025-11-28 | Fri | 2025-11-28 |
| 2026-01-31 | Sat | None (market closed) |
| 2026-03-15 | Sun | 2026-03-16 |
| 2026-03-16 | Mon | 2026-03-16, 2026-03-17 |
| 2026-03-21 | Sat | None (market closed) |
| 2026-04-10 | Fri | 2026-04-10 |
| 2026-05-24 | Sun | 2026-05-25 |
| 2026-07-30 | Thu | 2026-07-30, 2026-07-31 |
| 2026-08-29 | Sat | None (market closed) |

This gives 15 affected session dates. The session on 2025-11-28 is excluded by the eligibility rule, while the other 14 flagged session dates remain eligible. The effect on results will be evaluated separately during validation by running final results both with and without these 14 remaining flagged sessions.

### Session Eligibility Rule

A session is eligible for strategy testing only when both required strategy windows — London and NY AM — satisfy:

- observed bars > 0
- longest missing run <= 2 minutes

Asia is monitored for data quality but is not an independent eligibility gate.

This rule was fixed before any strategy backtest results were produced and will not be changed based on backtest outcomes.

Across 1,293 session dates:

- NQ: 1,289 eligible, 4 ineligible
- ES: 1,289 eligible, 4 ineligible
- NQ/ES eligibility disagreement: 0

The four ineligible session dates are:

| Session date | Reason |
|---|---|
| 2023-04-07 | Good Friday; NY AM unavailable |
| 2025-01-09 | National Day of Mourning; NY AM unavailable |
| 2025-11-28 | CME outage; London unavailable |
| 2026-04-03 | Good Friday; NY AM unavailable |

### CP1 Validation

The session module was validated for:

- automatic ET conversion and DST handling
- explicit CME session-date assignment
- strategy-window completeness
- cross-instrument session coverage
- session eligibility consistency
- synthetic missing-data edge cases

DST checks verified the 2022 transitions across four dates: 2022-03-11 (14:30 UTC), 2022-03-14 (13:30 UTC), 2022-11-04 (13:30 UTC), and 2022-11-07 (14:30 UTC). For all four dates, the first bar correctly mapped to a 09:30 ET start with exactly 90 bars.

Both instruments contained 1,293 session dates. No NQ-only or ES-only session dates were found. Session eligibility agreed across all 1,293 dates.

Synthetic CP1F tests passed for:
1. zero-bar window
2. missing first 10 minutes
3. scattered single missing minutes

### Session Levels

Session high and low are computed per session_date for each window from 1-minute highs and lows. A window with no bars returns NaN rather than zero or a filled value, so a missing window can never produce a level.

Validation: three NY AM sessions were drawn with a fixed random seed (42) and compared against TradingView (NQ1!, New York time zone, back-adjustment off) using the raw, unadjusted series. All three matched exactly: 2021-11-22 (H 16767.50 / L 16638.25), 2022-08-03 (H 13173.25 / L 12989.50), 2023-11-27 (H 16051.50 / L 15970.25). Within a contract segment, back-adjustment shifts all prices by a constant, so adjusted levels differ from raw levels only by that constant.

### Cross-Instrument Timestamp Differences

NQ has 1,770,978 bars and ES 1,770,870. The net difference of 108 is made up of 641 NQ-only and 533 ES-only minutes, all of them minutes where one market traded and the other printed no bar. They fall in Off hours (443 / 384), Asia (180 / 120), London (16 / 29) and NY Lunch (2 NQ-only). There are none in NY AM or NY PM. Several of the largest daily differences fall in contract roll weeks.