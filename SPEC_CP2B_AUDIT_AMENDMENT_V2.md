# Project 4 — CP2B Audit Amendment Draft

**Draft date:** 29 September 2026  
**Reason:** CP2B code audit using synthetic hand-computed tests before any strategy P&L.

This document is a draft amendment. It must not be treated as the final SPEC amendment until the unresolved strategy-behaviour decisions in Section B are explicitly locked and dated.

## A. Corrections confirmed by synthetic tests

### A1. Proxy B position
Proxy B position is measured for every completed 4H candle as:

`position = (09:30 price - 4H low) / (4H high - 4H low)`

Interpretation remains:

- `< 0.45` → BULLISH
- `0.45 ≤ position ≤ 0.55` → NO-CALL
- `> 0.55` → BEARISH

Doji remains NO-CALL.

### A2. 4H alignment
4H bars are anchored to the CME session's 18:00 ET open. This produces 18/22/02/06/10/14 ET bar starts across DST changes.

The implementation uses each row's explicit CP1 `session_date` and constructs the session anchor before binning.

**Verification status:** synthetic DST alignment test passed. Manual confirmation against an NQ1! 4H chart is still required before this amendment is finalized.

### A3. HTF iFVG qualification
For 1H/30m HTF iFVGs:

1. Form the FVG from three closed candles.
2. Search for the first later candle that closes through the FVG box and creates the inversion.
3. Require the immediately following same-timeframe candle to respect the inverted zone.
4. Record `qualification_time` as the close of that respecting candle.
5. A current zone may be used by Proxy A at 09:30 only when `qualification_time ≤ 09:30 ET`.
6. Currentness itself remains based on inversion time within the prior 24 hours.

A zone that is not qualified before 09:30 cannot influence the 09:30 Proxy A call.

### A4. Eligibility source of truth
CP2B now imports `build_session_eligibility()` from `session_quality.py` instead of reimplementing CP1 eligibility logic.

### A5. Module-level time constant
`NY_AM_START_OBJ` is defined at module import time so imported functions can be tested independently of `main()`.

## B. Strategy-behaviour decisions still required before CP2C

These items were identified by the audit as changing strategy behaviour and therefore require explicit lock/amendment.

1. **Proxy A Section 3.7:** define whether the 5-candle structure-response state changes Proxy A's directional call, or explicitly exclude the structure-response rule from Proxy A v1.

2. **Setup 1 initial stop:** define the stop for continuation trades, because the current generic stop wording refers to a sweep extreme that is not directionally defined for every continuation template.

3. **Sweep extreme inside iFVG:** define whether a setup is skipped when the required sweep extreme is not outside the active iFVG zone.

4. **4H BSL/SSL source candle:** explicitly identify which completed 4H candle supplies the BSL/SSL reference.

5. **Secondary-target 50-point substitution threshold:** define separate NQ and ES values instead of one shared 50-point threshold.

6. **Target fill semantics:** explicitly retain or change the current exact-target fill-on-touch rule.

7. **1R wording:** confirm that 1R is a stop-management milestone rather than a position-closing target, and remove any wording that treats it as an exit.

8. **NY AM Fib availability:** explicitly state that the 09:30–10:00 Fib cannot affect a signal before the 10:00 ET close of that window.

9. **Setup 2 five-candle timing:** explicitly confirm or change the locked rule that reversal entry must occur within the next five completed 1m candles after the relevant opposite London clear.

10. **Proxy A wrong-side diagnostic:** preserve the locked zone-type directional mapping and add a diagnostic count of selected zones that sit on the opposite side of the 09:30 reference price.

## C. CP1 cleanup

`config.py` now contains the 15 mapped degraded session dates from CP1, including 2025-11-28, which remains in the list for provenance even though the eligibility rule excludes that session.

The README roll-gap table path and 2025-11-28 material-exception punctuation have also been cleaned up.

## D. Test evidence

The attached CP2B synthetic checker passes:

`13/13`

No market data or strategy P&L is used by the checker.

## E. Decisions locked on 29 September 2026

### E1. Proxy A Section 3.7
The five-candle 30m structure-response mechanism is **excluded from Proxy A v1**.
It will be retained as a separate research observation for a later analysis and will not alter the tradable Proxy A directional call in v1.

### E2. Proxy A directional mapping
The frozen type-based mapping is retained exactly:

- bullish iFVG → bearish Proxy A bias
- bearish iFVG → bullish Proxy A bias

The implementation will additionally record a diagnostic for whether the selected zone is on the opposite side of the 09:30 reference price.
This diagnostic does not alter the bias call.

### E3. Continuation-trade stop concept
For Setup 1 continuation trades, the stop is based on the most recent swing extreme associated with the move below/above the active iFVG, and the stop must be outside the active iFVG box.

- Bullish continuation: use the most recent valid swing low below/outside the active bullish iFVG box, then place the stop 2 ticks below that swing low.
- Bearish continuation: use the mirror-image most recent valid swing high above/outside the active bearish iFVG box, then place the stop 2 ticks above that swing high.

The same structural idea is used for both directions.

**Implementation detail still open:** the project needs a mechanical definition of “swing low / swing high” (pivot confirmation rule) before CP2C engine behaviour can be considered fully locked. No invented swing lookback is to be added silently.

### E4. Sweep extreme inside active iFVG
If the initially identified structural/sweep extreme lies inside the active iFVG box, continue searching for the most recent structural extreme outside the active iFVG zone rather than accepting an inside-box stop.

### E5. Sweep/reverse stop
The Setup 2 sweep extreme definition remains confirmed: use the relevant high/low reached during the move that clears the London level and occurs before the reversal entry signal, with the resulting stop outside the active iFVG zone.

### E6. 4H BSL / SSL source candle
Use the **most recent completed 4H candle available before the 09:30 ET reference point**.

- 4H BSL = that candle's wick high.
- 4H SSL = that candle's wick low.

### E7. Proxy B formula
The mirror-consistent formula is approved:

`position = (09:30 price - 4H low) / (4H high - 4H low)`

with the existing 0.45 / 0.55 thresholds and doji NO-CALL rule.
The formula will receive a later real-data audit after the implementation is updated.

### E8. 1R behaviour
1R is confirmed as a **stop-management milestone only**. It does not close the position.
On reaching 1R, the protected stop takes effect and the position remains open for the secondary target or forced-flat exit.

### E9. Asia/London proximity threshold
The proximity substitution rule uses instrument-specific thresholds:

- NQ: **50 points**
- ES: **10 points**

### E10. Secondary-target fill semantics
Target fill-on-touch is intentionally retained:
when the bar reaches the target price, the target is filled at the exact target price.

### E11. NY AM Fib availability
The 09:30–10:00 NY AM Fib cannot affect a signal occurring before 10:00 ET because the full window is not known until then.

### E12. Setup 2 five-candle timing
**Deferred.** The five-completed-1m-candle restriction remains unresolved because the user does not want to impose an arbitrary fixed time limit on a market that can chop and subsequently move in the intended direction.
No alternative timing rule is to be invented before explicit review.

## F. Decisions intentionally deferred

1. **TradingView confirmation of 4H session anchoring** (18/22/02/06/10/14 ET). The synthetic DST audit passes, but manual chart confirmation is still pending.
2. **Setup 2 five-candle timing rule.**
3. **Mechanical swing-high/swing-low definition** for continuation and fallback stop placement.

These are the remaining strategy-behaviour locks that must be resolved before CP2C.

