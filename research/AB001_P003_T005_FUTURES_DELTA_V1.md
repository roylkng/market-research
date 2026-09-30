# AB001 P003 T005 Futures-Delta Orthogonality Diagnostic v1

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Determine whether the forecast improvement found by AE001-T005 contains a
distinct OOS ranking component that should enter the AB001 alpha library.

T005's 37-feature forecast cannot be treated as an independent alpha beside the
27-feature T003/T005 base because the augmented model contains the same 27 core
features.

P003 therefore isolates the exact OOS forecast delta:

    FUTURES_DELTA = FULL37_RAW_PREDICTION - CORE27_RAW_PREDICTION

on identical futures-complete stock/session rows.

P003 is a post-selection combination/orthogonality diagnostic. T005 outcomes are
already known. P003 cannot create an independent prospective-alpha claim.

## Frozen source chain

Reuse the exact T005 historical source chain:

- market panel SHA:
  9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e
- action-safe base feature panel SHA:
  300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8
- corporate-action ledger SHA:
  1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1
- delivery-augmented 27-feature panel SHA:
  99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90
- futures panel SHA:
  02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5
- futures-augmented 37-feature panel SHA:
  62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f

Sealed T005 report SHA:

2c72c9207ad3cfe2bc73637e4c10b7ad378c9a6c1b347fa2dd8936831a7511e2

Sealed T005 primary 5D result must reproduce before P003 diagnostics are opened:

- base mean rank IC = -0.0006030060148556494
- augmented mean rank IC = 0.021664130700606535
- base mean top-minus-bottom spread = 0.00008999948207925853
- augmented mean top-minus-bottom spread = 0.003935681355715129
- prediction count = 23084
- session count = 112

Tolerance for aggregate reproduction: 1e-15.

## Horizon and folds

Horizon: 5 completed NSE sessions.

Exact T005 primary folds:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-18

Ridge l2: 1.0.

Training is purged exactly as T005/T003 mechanics require.

## Alpha streams

### AB001-P003-CORE27

Exact OOS T005 base model prediction.

### AB001-P003-FUTURES-DELTA

For every exact common OOS record:

    raw_prediction =
        T005_FULL37_raw_prediction
        - T005_CORE27_raw_prediction

This is a model forecast delta, not a direct economic decomposition of futures
features. The augmented fit may change coefficients on the original 27 features.

### AB001-P003-FULL37

Exact OOS T005 augmented model prediction.

FULL37 is a reference stream and must not be counted as independent of CORE27
and FUTURES_DELTA.

## Additivity audit

For every common:

(feature_session, symbol, ISIN, entry_session, exit_session)

record:

    CORE27 + FUTURES_DELTA == FULL37

Absolute tolerance: 1e-15.

Targets and entry/exit sessions must match exactly across all three streams.

## AB001 normalization

Each stream is independently normalized by AB001's frozen per-session tie-aware
cross-sectional percentile transform to centered [-1, 1] score.

No outcome enters normalization.

## Diagnostics

### Standalone

For CORE27, FUTURES_DELTA and FULL37:

- mean/median rank IC;
- top-decile excess;
- bottom-decile excess;
- top-minus-bottom spread;
- top-decile churn.

### Orthogonality

For every pair:

- mean/median daily Spearman prediction correlation;
- daily top-minus-bottom spread correlation;
- overlapping sessions and stock-session rows.

Primary orthogonality quantity:

    corr(CORE27, FUTURES_DELTA)

### Incremental residual blend

Baseline:

    CORE27

Challenger:

    equal-weight AB001 normalized-score blend of CORE27 + FUTURES_DELTA

Paired Newey-West lag: 4.

Report deltas for:

- mean rank IC;
- mean top-decile excess;
- mean top-minus-bottom spread.

This blend is a diagnostic. Equal weight is not proposed as an optimal weight.

### Reference comparison

Compare the equal-weight CORE27 + FUTURES_DELTA blend against FULL37 on the same
rows. This measures the effect of AB001's independent rank normalization versus
the original single-model augmented forecast.

## Interpretation

P003 may establish whether the T005 forecast improvement behaves as a distinct
OOS ranking component inside the AB001 library.

P003 does NOT establish:

- new T005 validity;
- prospective futures-source timing;
- an optimal futures alpha weight;
- live-capital readiness.

Historical T005 outcomes were known before P003 was designed.

## Next gate

If FUTURES_DELTA is materially less correlated with CORE27 and adds useful
common-row OOS information, the next experiment may test a frozen AB001 blend
that includes the futures component alongside the strongest non-derivative
alpha.

Prospective promotion still requires a separately frozen live FO source-timing
and confirmatory prediction stream.
