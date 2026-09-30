# AB001 P003 T005 Futures Orthogonality Pilot v1

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Determine whether the already-sealed T005 NSE stock-futures feature family adds
genuinely different 5-session cross-sectional information to the existing
T003 delivery-augmented AE001 alpha.

P003 is a known-outcome combination/orthogonality diagnostic.

T005 and T003 outcomes were known before P003 was designed. P003 cannot establish
a new independent discovery claim.

## Horizon

5 completed NSE sessions.

Paired Newey-West lag:

4.

## Frozen source chain

All inputs must reproduce the sealed T003/T005 chain exactly.

Expected hashes:

- market panel:
  `9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e`

- action-safe base feature panel:
  `300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8`

- corporate-action ledger:
  `1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1`

- delivery-augmented 27-feature panel:
  `99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90`

- T005 futures panel:
  `02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5`

- T005 37-feature panel:
  `62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f`

Sealed T003 report:

`0b9cb3003b76548f35bb66ff24c3090f0e9b236a0219a6d35bcdd92a70732270`

Sealed T005 report:

`2c72c9207ad3cfe2bc73637e4c10b7ad378c9a6c1b347fa2dd8936831a7511e2`

Any mismatch fails closed before P003 diagnostics.

## Frozen folds

Exactly the shared T003/T005 five-session folds:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-09-18.

Ridge l2:

`1.0`.

## Frozen alpha A1: existing T003 delivery alpha

Alpha ID:

`AB001-P003-A1`

Construction:

- 27 T003 price/liquidity/delivery features;
- ridge;
- training uses the full action-safe delivery-complete T003 universe;
- same purged chronological folds used by sealed T003/P001.

Before common-row restriction, A1 must exactly reproduce the sealed T003 5D
augmented OOS aggregate diagnostics.

P003 then restricts A1 predictions to exact rows available in T005.

## Frozen alpha F37: T005 futures-enhanced alpha

Alpha ID:

`AB001-P003-F37`

Construction:

- 37 features;
- exact T005 futures-complete rows;
- exact frozen T005 folds and ridge l2.

Before AB001 normalization, F37 must reproduce the sealed T005 augmented 5D OOS
aggregate diagnostics exactly.

## Frozen alpha FB27: T005 base control

Alpha ID:

`AB001-P003-FB27`

Construction:

- 27 base features;
- trained only on the exact T005 futures-complete rows;
- exact T005 folds.

FB27 exists only to construct the pure incremental futures score and to reproduce
the sealed T005 control.

## Frozen alpha FDELTA: pure futures increment

Alpha ID:

`AB001-P003-FDELTA`

For every exact T005 OOS row:

    raw_prediction =
        F37_raw_prediction
        - FB27_raw_prediction

No coefficient is refit.

No residual regression is fit.

No weight is tuned.

AB001 then applies its existing tie-aware within-session percentile
normalization to FDELTA like any other alpha stream.

The target return is the exact common T005 action-safe 5D target.

## Common-row contract

All P003 pairwise and blend diagnostics use identical:

`(feature_session, symbol, ISIN, entry_session, exit_session)`

rows.

The common sample is the T005 futures-complete OOS validation set intersected
with A1.

Targets must be exactly equal across all aligned streams.

## Reproduction gates

### T003 A1

Before common-row restriction, require exact reproduction of sealed T003 5D
augmented diagnostics:

- prediction count: 145453;
- session count: 112;
- mean rank IC: 0.025015754407677233;
- mean top-decile excess: 0.005598934179157281;
- mean top-minus-bottom spread: 0.004119889007319015.

Tolerance for floating diagnostics:

`1e-12`.

### T005 FB27

Require exact reproduction of sealed T005 5D base diagnostics:

- prediction count: 23084;
- session count: 112;
- mean rank IC: -0.0006030060148556494;
- mean top-decile excess: 0.00038839032457309075;
- mean top-minus-bottom spread: 0.00008999948207925853.

### T005 F37

Require exact reproduction of sealed T005 5D augmented diagnostics:

- prediction count: 23084;
- session count: 112;
- mean rank IC: 0.021664130700606535;
- mean top-decile excess: 0.0011398627229922808;
- mean top-minus-bottom spread: 0.003935681355715129.

## Diagnostics

### Standalone

On exact common rows report for:

- A1;
- F37;
- FDELTA.

Metrics:

- mean/median rank IC;
- top-decile excess;
- bottom-decile excess;
- top-minus-bottom spread;
- selection churn.

### Pairwise orthogonality

For:

- A1 vs F37;
- A1 vs FDELTA;
- F37 vs FDELTA.

Report:

- mean daily Spearman prediction correlation;
- median daily Spearman prediction correlation;
- daily top-minus-bottom spread correlation;
- session count;
- overlapping stock/session rows.

No arbitrary correlation threshold is used as a discovery criterion.

### Fixed 50/50 blend diagnostics

P003 tests exactly two non-optimized challengers.

Baseline:

`A1`

Challenger 1:

    0.5 * normalized(A1)
    + 0.5 * normalized(F37)

Challenger 2:

    0.5 * normalized(A1)
    + 0.5 * normalized(FDELTA)

All comparisons use exact common rows.

Paired Newey-West lag:

4.

Report deltas for:

- rank IC;
- top-decile excess;
- top-minus-bottom spread.

## No dynamic blender

AB001 dynamic efficacy weighting is NOT tested in P003.

Reason:

P001 already demonstrated that correlated alphas can cause the current blender to
dilute the strongest model.

P003 first answers whether the new futures family is sufficiently distinct to
deserve a future blender trial.

## Interpretation

P003 may establish:

- how correlated T005 is with the existing T003 alpha;
- whether the mechanically isolated futures increment carries standalone OOS
  information;
- whether fixed equal-weight inclusion improves exact common-row diagnostics.

P003 does NOT establish:

- a prospective futures alpha;
- an optimal blend weight;
- dynamic-blender promotion;
- live-capital readiness.

Historical futures outcomes were already known when P003 was designed.
