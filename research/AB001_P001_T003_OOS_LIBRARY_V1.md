# AB001 P001 T003 OOS Alpha-Library Pilot v1

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Materialize the first real AB001 historical OOS alpha library using only alpha
construction rules that already existed in the sealed T003 research program.

P001 does not create a new alpha hypothesis. It measures redundancy,
orthogonality and blend behavior among existing T003 OOS constructions.

## Frozen source period

Historical-development source window:

2025-09-01 through 2026-09-25.

Expected upstream hashes:

- market panel:
  9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e
- action-safe base feature panel:
  300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8
- corporate-action ledger:
  1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1
- delivery-augmented feature panel:
  99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90
- sealed T003 report:
  0b9cb3003b76548f35bb66ff24c3090f0e9b236a0219a6d35bcdd92a70732270

Any upstream hash mismatch fails closed.

## Frozen horizon and folds

Horizon: 5 completed NSE sessions.

Folds:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-18

Ridge l2: 1.0.

Purging and action-safe labels use the merged T003 mechanics.

## Frozen alpha sources

### AB001-P001-A1: T003 augmented ridge

27 frozen AE001 price/liquidity + delivery/VWAP features.

Per fold:
- fit ridge on purged pre-fold training examples;
- emit OOS validation predictions only.

### AB001-P001-A2: T003 base ridge

18 frozen AE001 price/liquidity features.

Per fold:
- fit ridge on the identical purged training rows projected to base features;
- emit OOS validation predictions only.

### AB001-P001-A3: T003 training-selected single feature

Uses the existing signed-single-feature rule from T003:

1. determine each feature sign from purged training mean rank IC;
2. select the feature with highest absolute signed training rank IC;
3. apply that signed feature to the validation fold;
4. emit OOS predictions only.

The selection is repeated independently per fold using training evidence only.

No new feature, sign rule or model family is introduced by P001.

## Canonical AB001 analysis

P001 creates one AB001-v1 library containing A1/A2/A3.

Required outputs:

### Standalone

For each alpha:
- mean/median 5D rank IC;
- top-decile excess;
- top-minus-bottom spread;
- selection churn.

### Pairwise orthogonality

For each pair:
- mean/median daily Spearman prediction correlation;
- daily spread correlation;
- overlapping session and stock-session counts.

### Incremental augmented-ridge test

Existing set:

- A2 base ridge;
- A3 training-selected single feature.

Candidate:

- A1 augmented ridge.

Compare equal-weight blend(A2,A3) versus equal-weight
blend(A2,A3,A1) on exact common OOS rows.

Paired Newey-West lag: 4.

### Dynamic AB001 blend

Blend A1/A2/A3 using merged AB001-v1 rules:

- trailing OOS lookback = 60 sessions;
- minimum efficacy = 20 sessions;
- negative efficacy floored to zero;
- correlation shrink;
- single-alpha cap = 50%;
- deterministic equal-weight fallback when evidence is insufficient.

Compare the mature dynamic blend against A1 augmented ridge on the exact same
stock-session rows.

Paired Newey-West lag: 4.

## Interpretation

P001 is a redundancy/combination diagnostic.

It may establish:

- whether T003 sources are largely redundant;
- whether AB001 blending improves OOS rank/spread metrics;
- whether a simpler source retains independent information.

It does NOT establish:

- a new alpha discovery;
- prospective validation;
- portfolio improvement;
- live-capital readiness.

No post-hoc alpha source may be added to P001 after materialization.
