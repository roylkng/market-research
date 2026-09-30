# AB001 P001 Protocol Amendment P2: Sealed T003 OOS Reproduction Gate

Frozen: 2026-09-30
Status: FROZEN BEFORE VALID P001 MATERIALIZATION
Live capital: DISABLED

## Purpose

P001 reconstructs stock-level OOS predictions because the sealed T003 report
stored aggregate metrics rather than the canonical AB001 prediction records.

Matching historical source hashes is necessary but not sufficient. The
reconstructed A1/A2 ridge streams must also reproduce the sealed T003 5-day OOS
economics before AB001 may analyze them.

## Sealed T003 5-day references

From sealed T003 report:

`0b9cb3003b76548f35bb66ff24c3090f0e9b236a0219a6d35bcdd92a70732270`

### A1 augmented 27-feature ridge

- prediction_count: 145453
- session_count: 112
- mean_rank_ic: 0.025015754407677233
- median_rank_ic: 0.03355510590008127
- mean_top_decile_excess: 0.005598934179157281
- mean_top_minus_bottom_spread: 0.004119889007319015
- average_top_decile_selection_churn: 0.37131026000634687

### A2 base 18-feature ridge

- prediction_count: 145453
- session_count: 112
- mean_rank_ic: 0.005610514228492526
- median_rank_ic: 0.016955070643943804
- mean_top_decile_excess: 0.004546806162771425
- mean_top_minus_bottom_spread: 0.000980506682673035
- average_top_decile_selection_churn: 0.340520921749316

## Frozen tolerance

Counts must match exactly.

Absolute tolerance for floating metrics:

`1e-12`

No tolerance may be widened after a valid P001 materialization begins.

## Promotion gate

AB001 library construction may proceed only after both A1 and A2 pass this
reproduction gate.

A3 is the already-frozen T003 training-selected single-feature construction but
was not separately sealed as a compact T003 headline metric. A3 therefore
retains construction-rule lineage rather than an independent aggregate-metric
reproduction gate.

Invalid pre-P1 workflow run 36669808434 remains excluded from evidence.
