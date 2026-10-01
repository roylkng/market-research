# AE001 T011 Lagged Stock-Futures Positioning Trial v1

Status: FROZEN BEFORE RETURN OUTCOMES
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Test whether previous-completed-session NSE stock-futures positioning and
term-structure information adds incremental cross-sectional information beyond
the current-session 27-feature cash/delivery model.

T011 exists because T005's same-session futures family passed historically, but
SC002 has observed that the official same-session FO UDiFF file publishes after
the frozen 18:30 IST EOD decision cutoff.

T011 changes the information timing rather than retroactively changing T005 or
T006.

## Causal information set

For decision session D:

Current information:
- exact current-session D 27-feature AE001 price/liquidity/delivery row.

Lagged derivatives information:
- the exact ten T005 futures features computed for previous completed NSE
  session D-1.

The D-1 futures values are renamed as lagged features and are never recomputed
using D prices.

Decision time:

    D 18:30 IST

Entry:

    next completed NSE session D+1 open

This means the derivative information is at least one completed session old at
decision time.

## Historical source construction

Use the exact sealed T005 source artifacts from workflow run 36696476204.

Required authoritative T005 lineage:

- market panel:
  9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e
- corporate-action ledger:
  1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1
- current-session 27-feature delivery panel:
  99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90
- T005 same-session 37-feature futures panel:
  62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f

## Identity and session join

For one current decision session D:

1. determine D-1 from the ordered official NSE market panel, never from calendar
   subtraction;
2. take one current D row from the frozen 27-feature panel;
3. take the exact same symbol+ISIN row from the frozen T005 37-feature panel on
   D-1;
4. copy ONLY the ten T005 futures values from the D-1 row;
5. require exact same ISIN continuity from D-1 to D.

Missing D-1 futures row:

    EXCLUDE_CURRENT_D_ROW_NO_IMPUTATION

No symbol-only carry-forward.

## Frozen lagged futures features

The ten new feature names are:

1. lag1_fut_front_basis
2. lag1_fut_front_log_basis_per_day
3. lag1_fut_next_log_basis_per_day
4. lag1_fut_curve_slope_per_day
5. lag1_fut_front_oi_change_fraction
6. lag1_fut_total_oi_change_fraction
7. lag1_fut_front_oi_share
8. lag1_fut_total_volume_to_oi
9. lag1_fut_notional_to_cash_turnover
10. lag1_fut_front_settlement_return_1

Each value is numerically identical to the corresponding T005 feature on D-1.
Only the name and information-time semantics change.

## Base and augmented models

Base:

    exact current-session 27-feature AE001 price/liquidity/delivery set

Augmented:

    same current-session 27
    + ten D-1 lagged futures features
    = 37 features

Base and augmented models use the identical lagged-futures-complete rows.

Model:

    ridge

L2:

    1.0

No hyperparameter search.

## Primary horizon

5 completed NSE sessions.

Folds:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-18

Paired Newey-West lag:

    4

Primary succeeds only when BOTH are true:

- augmented-minus-base mean rank IC > 0 and two-sided p < 0.05;
- augmented-minus-base mean top-minus-bottom spread > 0 and two-sided p < 0.05.

## Secondary horizon

1 completed NSE session.

Folds:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-24

Paired Newey-West lag:

    5

Secondary cannot rescue a failed primary.

## Medium horizon

No 20-session endpoint.

Reason:

T005's 20-session futures diagnostic was unsupported. T011 is a causal
implementation test of the surviving short-horizon futures edge, not another
medium-horizon fishing exercise.

## Source-only pre-outcome gate

Before any T011 return label/model fit is opened, a source-only artifact must
freeze exact hashes and counts for:

- market panel;
- corporate-action ledger;
- current-session 27-feature panel;
- D-1 T005 37-feature source panel;
- resulting lagged 37-feature panel;
- common row count;
- common session count;
- excluded missing-lagged-futures row count;
- maximum absolute copied-feature difference versus the D-1 T005 source row.

Minimum source-only sample gates:

- at least 150 feature sessions;
- at least 30,000 common feature rows.

If those are not met, T011 fails before outcomes.

## Prospective relationship

Historical T011 may establish information content only.

A future confirmatory successor may be designed only after SC003 has at least
three distinct target sessions with D-1 FO UDiFF captured no later than
08:30 IST.

A future lagged-futures prospective decision would require:

- current D cash/delivery timing under SC001;
- previous-session D-1 futures timing under SC003;
- fixed pretrial T011 models;
- no historical backfill.

T006 remains unchanged. T011 does not repair or reinterpret T006.

## Multiple testing

T011 increments the AE001 feature-family trial count by one.

No post-outcome parameter changes are permitted under T011.

A revised lag choice, alternate source timing, changed folds, changed l2 or
changed success rule requires a new trial identity.

## Promotion

If primary passes:

- promote lagged futures as the operationally causal futures candidate for
  AB001 / future prospective confirmation.

If primary fails:

- record failure;
- do not retune lagged futures under T011.

No live-capital implication.
