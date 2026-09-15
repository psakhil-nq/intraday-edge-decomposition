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