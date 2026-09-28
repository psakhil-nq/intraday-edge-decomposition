# Project 4 — Strategy Specification

**Lock date:** 26 September 2026

This document freezes every strategy rule and parameter before any strategy backtest result is produced.

No parameter may be changed after results are observed. Any later change requires a dated amendment explaining why.

---

## 0. Research Scope and Non-Negotiable Methodology

**Research question:** Can a discretionary intraday futures strategy be decomposed into explicit, codeable rules, and what does each individual rule actually contribute to performance?

This project is not a profitability hunt. The primary deliverable is the decomposition method and the measured marginal contribution of individual rules. A negative result is a valid research outcome.

The strategy is tested on continuous back-adjusted 1-minute NQ and ES futures data after the CP0/CP1 processing already completed. Raw market data is not committed to the repository.

### Pre-commitment rules

- Strategy windows, thresholds, stop/target distances, position size, and execution semantics are fixed before any strategy P&L is produced.
- Strategy parameters live in configuration; functions must not contain hidden strategy constants.
- Signals are generated only from information available at or before the signal bar close.
- A signal on bar `t` executes at the open of the next observed 1-minute bar.
- No same-bar-close entry is permitted.
- If stop and target are both reachable within the same 1-minute bar and ordering is unknowable from OHLC, stop is assumed first.
- Trade counts must accompany every performance metric.
- Missing minutes are not forward-filled.
- Databento raw/adjusted price data and API keys are never committed.
- No strategy P&L may be produced until this specification is committed.

### Instruments and sizing

- Instruments: **NQ and ES**, evaluated independently.
- Position size: **1 contract fixed per trade**.
- Tick size: **0.25 points**.
- Commission and slippage remain **TBD** until CP2F (Costs/Units); no results may be interpreted as final net performance before CP2F.

---

## 1. Bias

The discretionary bias in the original trading method is a 1H/30m read and is not reproduced as an opaque human judgment.

The research evaluates the following bias configurations:

1. **Oracle bias** — session realized direction. Uses future information and is reported only as an upper bound, never as tradable performance.
2. **Mechanical Proxy A** — deterministic pre-09:30 HTF iFVG draw/magnet rule.
3. **Mechanical Proxy B** — deterministic 4H Fib bias experiment.
4. **Proxy A + B** — research configuration requiring agreement between Proxy A and Proxy B.
5. **No-bias control** — both bullish and bearish templates are evaluated on every eligible session.

Monday sessions are included.

The mandatory entry model in every tradable configuration remains:

> **Liquidity sweep + first qualifying 1m iFVG + rejection.**

Fib and SMT are supporting/confluence research layers; neither is required for the primary entry model.

---

## 2. Oracle Bias

Oracle bias is defined using future session information and exists only as an upper-bound research condition.

- Reference price = **09:30 ET bar open**.
- Ending price = **forced-flat reference close**, defined in Section 15.
- If ending price > reference price → **bullish**.
- If ending price < reference price → **bearish**.
- If ending price = reference price → **no-call**.

Oracle bias is never presented as tradable performance.

---

## 3. Mechanical Bias Proxy A — HTF iFVG Draw/Magnet

Proxy A approximates the discretionary 1H/30m read using only information available before the NY AM trade window.

### 3.1 HTF iFVG qualification

A 1H or 30m iFVG is a qualified HTF iFVG when:

1. The iFVG is formed according to the locked iFVG definition in Section 8.
2. The following candle on the same timeframe respects the zone.
3. No separate size threshold is used; every 1H/30m iFVG is treated as a large HTF iFVG.

Respect uses the same arithmetic as the rejection definition on that timeframe:

- bullish iFVG: price trades into the box and the candle closes back above the box top;
- bearish iFVG: price trades into the box and the candle closes back below the box bottom.

A qualified zone remains marked as a standby level after its first reaction.

### 3.2 Currentness

A qualified HTF iFVG is considered **current** only when its inversion time occurred within the **24 hours before 09:30 ET**.

### 3.3 Timeframe priority

If qualifying current zones exist on both timeframes:

> **1H has priority over 30m.**

If at least one current qualified 1H zone exists, 30m zones do not override it.

If no current qualified 1H zone exists, the 30m zones are used.

### 3.4 Reference price

Proxy A uses the **09:30 ET bar open** as its reference price.

### 3.5 Zone-distance calculation

For each qualifying zone on the applicable timeframe, distance from the 09:30 reference price is:

- price inside zone → distance = `0`
- price below zone → `zone_bottom - price`
- price above zone → `price - zone_top`

The closest qualifying zone is selected.

If multiple same-type zones are tied at the same distance, the resulting directional call is unchanged.

If a bullish and bearish qualifying zone are exactly equidistant, the state is:

> **TRANSITION**

`TRANSITION` produces no normal bullish/bearish Proxy A call.

If no current qualifying zone exists, Proxy A returns **NO-CALL**.

### 3.6 Directional mapping

The selected HTF zone is treated as the current liquidity draw/magnet.

- Closest **bullish iFVG** → **bearish bias**
- Closest **bearish iFVG** → **bullish bias**

The selected zone therefore implies movement toward the opposite side represented by the selected draw.

Example:

- qualified bullish 1H iFVG below price
- qualified bearish 30m iFVG above price
- 1H has priority
- resulting Proxy A bias = **bearish**

### 3.7 HTF structure response after penetration

When price passes through a qualified HTF iFVG, the zone is not permanently invalidated by the first penetration.

After the first **close through** the zone, the next **5 completed 30-minute candles** are evaluated:

- two successive higher highs → bullish structure response
- two successive lower lows → bearish structure response

The first qualifying sequence to complete determines the classification.

If neither sequence occurs within the 5-candle observation window, the previous state is retained.

The 15-minute timeframe is not used in this proxy.

---

## 4. Mechanical Bias Proxy B — 4H Fib

Proxy B is a separate research experiment. It does not replace the mandatory liquidity-sweep + iFVG entry model.

### 4.1 4H source candle

Use the **most recent completed 4H candle available before the 09:30 ET reference point**.

Use that candle's wick high and wick low.

### 4.2 Fib orientation

- If the completed 4H candle is bullish (`close > open`) → draw Fib **low → high**.
- If the completed 4H candle is bearish (`close < open`) → draw Fib **high → low**.
- If the completed 4H candle is a doji (`close = open`), Proxy B returns **NO-CALL** because the directional Fib orientation is undefined under the locked rule.

### 4.3 Fib position

Use the **09:30 ET bar open** to determine the 09:30 price location within the 4H Fib leg.

Precommitted interpretation:

| Fib position | Proxy B state |
|---|---|
| `< 0.45` | Bullish |
| `0.45 ≤ position ≤ 0.55` | CHOP / NO-CALL |
| `> 0.55` | Bearish |

The 0.45–0.55 band is a precommitted neutral zone intended to prevent trades from being generated when price is chopping around the 0.50 midpoint.

Proxy B disagreement, CHOP, or NO-CALL never deletes the session from the research dataset; the configuration simply produces no trade for that bias experiment.

---

## 5. Proxy A + B Agreement Configuration

Proxy A + B is a separate research configuration.

- If Proxy A and Proxy B produce the **same directional bias**, the configuration is eligible to use that bias.
- If either proxy is `TRANSITION`, `CHOP`, or `NO-CALL`, there is no directional call for this configuration.
- If Proxy A and Proxy B produce opposite directional calls, the configuration **skips the trade**.
- The session and all observed information remain logged; “skip” means no trade is taken, not that the observation is deleted.

This configuration exists to measure the contribution of combining the two bias mechanisms.

---

## 6. No-Bias Control

The no-bias control evaluates both bullish and bearish templates on every eligible session.

It does **not** assume in advance that two trades will be taken.

Execution logic is sequential:

1. The first valid trade signal from either template becomes Trade 1.
2. No second trade is considered until Trade 1 has ended.
3. Trade 2 may only be considered after Trade 1 ends in:
   - the initial stop/loss, or
   - the protected-stop outcome after 1R.
4. Trade 2 is not considered after:
   - a primary or secondary target, or
   - a forced-flat/time exit.

The no-bias configuration is intended to model the research question “what happens when both directional templates are allowed?” rather than to manufacture two simultaneous positions.

If bullish and bearish valid signals ever occur on the exact same bar, that event is treated as a validation anomaly and must be flagged rather than resolved through an arbitrary priority rule.

---

## 7. London Sweep

A London liquidity sweep occurs during NY AM when price trades through a London extreme by at least **1 tick**.

A wick through the level is sufficient. A 1-minute close beyond the level is not required.

Therefore:

- London high sweep: NY AM price reaches at least `London high + 1 tick`
- London low sweep: NY AM price reaches at least `London low - 1 tick`

The sweep may occur intrabar and price may immediately reverse after liquidity is taken.

---

## 8. iFVG Definition (v1)

The iFVG is the mandatory entry mechanism. The same definition applies on 1H, 30m, 5m and 1m unless a section explicitly excludes that timeframe from a research layer. Closed bars only.

### 8.1 Bars

- 1m bars come from the adjusted continuous series.
- Higher timeframes are resampled from 1m:
  - open = first
  - high = max
  - low = min
  - close = last
- Bars are labelled by bar start and aligned to ET clock boundaries.
- 30m bars start at `:00` and `:30`.
- 1H bars start at `:00`.
- A higher-timeframe bar is usable only after it closes.

### 8.2 FVG formation

Three consecutive closed candles `c1`, `c2`, `c3` on the same timeframe.

- Bullish FVG: `high(c1) < low(c3)`
- Bearish FVG: `low(c1) > high(c3)`
- Strict inequality is required; on the 0.25 tick grid this means at least 1 tick.
- No additional minimum-size threshold exists.
- Formation time = close of `c3`.

### 8.3 Box

- Box = body of `c1`, the left-side candle.
- `bottom = min(open, close)`
- `top = max(open, close)`
- Wicks are excluded.
- If `open == close` for `c1`, no box is created.
- The box is fixed once formed and never expands.

### 8.4 Inversion

- Bullish FVG becomes a bearish iFVG/resistance when a candle **closes below** the box bottom.
- Bearish FVG becomes a bullish iFVG/support when a candle **closes above** the box top.
- A wick through the box does not invert it.
- Inversion time = close of the inverting candle.
- An FVG that has not inverted cannot produce an entry.

### 8.5 Eligible 1m iFVG

For a setup trade:

- Direction must match the setup trade direction.
- Inversion must occur **after the setup's level-clear event**.
- Inversion must occur inside **09:30–11:00 ET**.
- The underlying FVG may have formed earlier.
- “First iFVG” = the first eligible iFVG to invert after the relevant liquidity-clear event.
- If two eligible iFVGs invert on the same candle, use the more recently formed one.
- If the first iFVG is invalidated before entry, the setup is dead for the session; do not move to a later iFVG.

### 8.6 Entry after rejection

The rejection candle `t` must occur strictly after the inversion candle.

- Bearish iFVG short:
  - `high(t) >= box bottom`
  - `close(t) < box bottom`
- Bullish iFVG long:
  - `low(t) <= box top`
  - `close(t) > box top`

Signal time = close of candle `t`.

Entry = market order at the open of the **next observed 1-minute bar**.

The entry must occur before 11:00 ET. Therefore:

> A signal on the 10:59 ET bar is invalid because its earliest entry would be the 11:00 ET open.

No limit is imposed on touch depth. The discretionary phrase “wick barely touches” is simplified to:

> trades into the box and closes back outside.

### 8.7 1m invalidation

For a bearish iFVG:

- close through = close above box top.

For a bullish iFVG:

- close through = close below box bottom.

A close inside the box is neither rejection nor close-through.

One close through does not invalidate.

Two consecutive closes through invalidate.

An invalidated iFVG cannot produce an entry.

### 8.8 1m expiry

An eligible 1m iFVG that has not produced an entry by 11:00 ET expires.

### 8.9 Higher-timeframe iFVGs

For 1H and 30m:

- Every iFVG qualifies; no size threshold.
- The zone is marked only after the next candle on the same timeframe respects it.
- “Current” means inversion time within the 24 hours before 09:30 ET.
- A qualified zone remains a standby level after its first reaction.
- Structure after penetration is handled as specified in Section 3.7.

### 8.10 5m iFVGs

5m iFVGs are excluded from the mandatory v1 entry model and are not used as an independent entry trigger.

They may appear only in later, separately measured research if a future amendment explicitly adds them.

### 8.11 SMT

SMT is not part of the iFVG definition.

Every eligible trade is tagged:

- SMT present
- SMT absent

SMT is a separate supporting-confluence research layer and is never mandatory for the primary entry.

---

## 9. Setup Grammar

The scenario sheet is rewritten each trading day. Scene numbers are not fixed identifiers and are not encoded as permanent four-row cases.

The code represents the underlying setup types below, applied to that day's reference levels.

The bearish template is the exact mirror of the bullish template: highs become lows, bullish direction becomes bearish direction, long becomes short.

### 9.1 Setup 1 — Continuation

**Bullish**

1. Day bias = bullish.
2. NY AM clears **London High** by at least 1 tick.
3. First qualifying bullish 1m iFVG forms/inverts after the London High clearance.
4. A later rejection candle satisfies the bullish rejection rule.
5. Enter long at the next observed 1m bar open.

**Bearish mirror**

1. Day bias = bearish.
2. NY AM clears **London Low** by at least 1 tick.
3. First qualifying bearish 1m iFVG forms/inverts after the London Low clearance.
4. A later rejection candle satisfies the bearish rejection rule.
5. Enter short at the next observed 1m bar open.

### 9.2 Setup 2 — Sweep and Reverse

**Bullish**

1. Day bias = bullish.
2. NY AM clears **London Low** by at least 1 tick.
3. The first qualifying bullish 1m iFVG after the London Low clearance provides the mechanically defined reversal trigger.
4. A later bullish rejection candle satisfies the iFVG entry rule.
5. Enter long at the next observed 1m bar open.

**Bearish mirror**

1. Day bias = bearish.
2. NY AM clears **London High** by at least 1 tick.
3. The first qualifying bearish 1m iFVG after the London High clearance provides the mechanically defined reversal trigger.
4. A later bearish rejection candle satisfies the iFVG entry rule.
5. Enter short at the next observed 1m bar open.

For Setup 2, the sweep extreme used for the initial stop is the relevant high/low reached during the move that clears the London level and occurs before the reversal entry signal.

### 9.3 Setup 3 — No Clear Draw on Liquidity

If NY AM moves through the entry window without clearing a qualifying reference liquidity level required by the selected setup:

> **Skip.**

### 9.4 Setup 4 — Bias Failing

After the opposite London liquidity level is cleared, if no qualifying reversal entry occurs within the next **5 completed 1-minute candles**, the original bias is classified as failed and the setup is skipped.

Counter-bias discretionary trades described in the journal are excluded from v1 because their “structure sustains” condition is not sufficiently defined.

---

## 10. Reference Levels

Before the NY AM trading window, the implementation may use the following locked reference levels:

- Asia High / Asia Low
- London High / London Low
- NY AM open
- previous session NY AM High / Low
- previous session NY PM High / Low
- 4H BSL / SSL
- 4H Fib
- NY AM 09:30–10:00 Fib
- qualified current 1H / 30m iFVG zones

Only levels explicitly used by a setup or research layer should affect that layer's decision.

### 10.1 4H BSL / SSL

The 4H liquidity references are defined directly from the 4H timeframe:

- **4H BSL = wick high of a 4H candle**
- **4H SSL = wick low of a 4H candle**

No additional swing/pivot qualification is used.

### 10.2 NY AM Fib

Use the **09:30–10:00 ET** window from 5-minute candles.

- high = highest wick high in that window
- low = lowest wick low in that window
- bullish Fib = low → high
- bearish Fib = high → low

The NY AM Fib is a supporting research/confluence layer and is not a mandatory entry condition.

---

## 11. Entry Model and Supporting Confluence

The primary entry model is:

> **Liquidity sweep + first qualifying 1m iFVG + rejection.**

This is the only mandatory entry structure.

### Supporting confluence

- SMT may support the trade but is not required.
- 4H Fib / NY AM Fib may support the trade but are not required.
- Supporting confluence does not redefine or replace the liquidity-sweep + iFVG trigger.

### iFVG marginal-contribution control

Because the discretionary method never enters without an iFVG, the primary method baseline includes the first qualifying 1m iFVG.

A separate **non-traded control** is predeclared solely to isolate the marginal contribution of the iFVG mechanism:

- Continuation control = next observed bar open after the first bar that clears the relevant level.
- Sweep/reversal control = next observed bar open after the first 1m close back across the swept level.

The control is not the trader's method and is never presented as a tradable strategy.

---

## 12. Position Management and Stops

### 12.1 Position size

- **1 contract fixed** for every trade.

### 12.2 Initial stop

Bearish trade:

`stop = sweep high + 2 ticks`

Bullish trade:

`stop = sweep low - 2 ticks`

The sweep extreme must be outside the active iFVG zone.

### 12.3 1R definition

`1R = absolute(entry price - initial stop price)`

Costs are not included in R.

### 12.4 Primary target

The primary target is always:

> **Fixed 1R.**

Reaching 1R is a milestone and does **not** close the position.

### 12.5 Profit-protection stop

When price reaches 1R:

- long → stop moves to **1R - 3 ticks**
- short → stop moves to **1R + 3 ticks**

The 1 contract remains open after this move and may continue toward the secondary target or forced-flat.

### 12.6 Stop-first ambiguity

If a 1-minute bar can reach both the active protective stop and a target but OHLC cannot establish the intrabar order:

> **Stop is assumed first.**

This applies to the initial stop and to the protected stop.

If a single bar can contain both the 1R trigger and the newly activated protected-stop level, the event is treated conservatively as **stop-first** and recorded as an ambiguous-bar case.

---

## 13. Secondary Targets

The secondary target is a liquidity objective used after the 1R milestone.

### 13.1 Liquidity universe

Eligible secondary liquidity references are:

- London High / London Low
- Asia High / Asia Low
- 4H BSL / 4H SSL

### 13.2 Directionality

For a long, only levels strictly above the trade entry are valid.

For a short, only levels strictly below the trade entry are valid.

Already-cleared/passed levels are not eligible.

### 13.3 Selection

The default rule is:

> **Choose the nearest valid liquidity level in the trade direction.**

### 13.4 Asia/London proximity rule

If:

- Asia High is within **50 points** of London High → use **4H BSL** instead of Asia High.
- Asia Low is within **50 points** of London Low → use **4H SSL** instead of Asia Low.

If the resulting selected target is not valid in the trade direction, continue to the next valid liquidity level.

### 13.5 No valid secondary target

If no valid secondary liquidity target remains, the position stays under the active protected stop until that stop is hit or the position is forcibly closed at the session exit.

---

## 14. Trade Count and Sequential Trade Rules

Maximum:

> **2 trades per session.**

However, the method is not precommitted to taking two trades.

### Trade 1

Take the first valid qualifying trade produced by the selected configuration.

### Trade 2

Trade 2 may only be considered after Trade 1 ends in:

- initial stop/loss, or
- protected-stop outcome after reaching 1R.

Trade 2 is prohibited after:

- primary target,
- secondary target,
- forced-flat/time exit.

A second trade must independently satisfy all setup, liquidity, iFVG, timing, and risk conditions.

---

## 15. Execution Semantics

### 15.1 Signal and entry

- Signal is known at the close of the rejection candle.
- Entry occurs at the **open of the next observed 1-minute bar**.
- No same-bar-close execution.

### 15.2 Entry cutoff

A signal whose next observed 1-minute bar opens at or after 11:00 ET is invalid.

Therefore:

> 10:59 signal → invalid.

### 15.3 Target fills

When price reaches a target level during a bar, fill at the exact target price.

### 15.4 Gap-through fills

If the market opens beyond a stop or target level, fill at the **bar open** rather than assuming execution at the already-crossed level.

### 15.5 Forced flat

A position may remain open after 11:00 ET.

It exits at the close of the **last observed eligible bar at or before 16:59 ET**.

On an early-close session, the session's final observed bar is used.

Forced-flat/time exit is logged separately from stop and target exits.

---

## 16. Costs and Units — Deferred to CP2F

The strategy specification is frozen independently of the cost model.

Current placeholders:

- Commission: **TBD — CP2F**
- Slippage: **TBD — CP2F**

The later CP2F checkpoint will lock:

- commission per contract round-turn
- slippage in ticks
- NQ/ES dollar multipliers
- exact cost application semantics

No post-result change to costs is permitted without a dated amendment.

---

## 17. Research Configurations and Reporting

The research must keep configurations separate so that each rule's contribution can be measured.

At minimum, later checkpoints must preserve:

1. **Primary method configuration**
   - selected tradable bias mode
   - liquidity sweep
   - first 1m iFVG
   - rejection
   - fixed risk/target rules

2. **iFVG control**
   - same setup logic
   - non-traded control entry described in Section 11

3. **Oracle bias upper bound**
   - future-information bias only
   - never interpreted as tradable performance

4. **No-bias control**
   - both directional templates allowed
   - sequential trade logic

5. **Proxy B**
   - 4H Fib bias experiment

6. **Proxy A + B**
   - agreement experiment

7. **SMT layer**
   - SMT present/absent tagging and separate contribution analysis

Fib and SMT must not be promoted to mandatory entry rules merely because they appear useful in observed results.

Every reported performance metric must include the corresponding trade count.

---

## 18. Known Ambiguity and Data-Quality Controls

The implementation must preserve the following research safeguards:

- Same-bar stop/target ordering is conservative: stop first.
- Missing minutes are never forward-filled.
- HTF bars are usable only after close.
- Incomplete FVGs are not used before formation is complete.
- An unqualified/invalidated iFVG cannot later become an entry trigger.
- Session segmentation uses the CP1 `session_date` convention and ET/DST handling.
- Degraded sessions remain identifiable by the CP1 `data_quality` flags.
- Final sensitivity analysis must report results with and without the remaining eligible degraded sessions.
- Back-adjusted prices are used for relative/path-dependent rules; absolute-price interpretation remains subject to the documented back-adjustment limitation.

---

## 19. CP2A Status

This specification represents the **strategy-specification lock** for CP2A.

Before proceeding to strategy P&L:

- all strategy rules above must be committed;
- implementation must follow this document exactly;
- any newly discovered ambiguity that affects strategy behavior must be resolved and added as a dated amendment before results are generated;
- CP2F costs/units remain intentionally deferred to their designated checkpoint.

**No parameter tuning is permitted after observing results.**
