# AE001 T010 Short-Selling / SLB Incremental Alpha Trial v1

Status: FROZEN BEFORE OUTCOME MATERIALIZATION
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Test whether the historically validated CM short-selling and SLB positioning
features add incremental cross-sectional information beyond the passed AE001
T005 price/liquidity/delivery/futures model.

T010 is a new trial. It does not modify T005, T007, T008 or T009.

## Why this base is frozen

The control model is exactly the latest feature family that passed its frozen
primary endpoint:

AE001 T005 = 37 features

comprising:

- 18 price/liquidity features;
- 9 delivery/VWAP features;
- 10 stock-futures features.

Failed feature families are explicitly excluded from the T010 base:

- T007 announcement taxonomy;
- T008 fundamentals;
- T009 stock options.

T010 therefore tests incremental information, not a kitchen-sink model.

## Historical evidence class

HISTORICAL_RECONSTRUCTION_DEVELOPMENT

Historical archive availability does not establish same-day publication time.
T010 can establish historical incremental information only.
It cannot count as prospective validation.

## Frozen source lineage

### T005 control panel

Sealed T005 37-feature panel SHA-256:

62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f

T005 result: research/ae001-t005-result-v1.json

T005 report SHA-256:
2c72c9207ad3cfe2bc73637e4c10b7ad378c9a6c1b347fa2dd8936831a7511e2

T005 successful workflow:
- run: 36696476204
- artifact: 11088556814
- artifact name: ae001-t005-36696476204

### D010 P4A feature panel

Sealed P4A seven-feature source panel lineage:
- P4A panel SHA-256: 1b629fee85e7430466d81e5c8e5a3497cca77221ab7d38633b23c7db5b49f4b0
- P4A artifact SHA-256: dcb9d4e59df3992dbc71b0633c51c27e20dcd81de5eb5570c0e7d0f9fbb92513
- P4A report SHA-256: 58ce64d9a247f30da13a535991658a36a6696e2b61e2b3094a71741963fb3b41

P4A fresh-source run:
- run: 36894325553
- artifact: 11178344679

Independent sealed-source replay:
- run: 36895731596
- artifact: 11178579573

Both reproduced the P4A hashes exactly.
P4A opened zero return labels and fit zero models.

## Frozen T010 feature family

Seven D010 P4A features:
1. short_volume_share_lag1
2. short_volume_share_change_1
3. short_volume_share_percentile_20
4. slb_outstanding_days_volume20
5. slb_outstanding_change_days_volume20
6. slb_outstanding_percentile_20
7. slb_active_series_count

No removed P4 z-score field is allowed.

## Feature-panel construction

T010 first performs a source-only join.

For every stock/session:
- T005 row identity = exact (feature_session, symbol, ISIN);
- P4A row identity = exact (feature_session, symbol, ISIN);
- retain only identities present in BOTH panels;
- preserve the exact 37 T005 values;
- append exactly the seven P4A values;
- no interpolation;
- no symbol-only join;
- no return label is accessed during this join.

The joined panel must contain exactly 44 features.

The exact joined-panel SHA-256 and common-row/session counts must be frozen
under T010-P1 before any model fit or return metric is opened.

## Model

Base: exact 37 T005 features
Augmented: same 37 + seven D010 P4A features = 44
Model family: ridge
Frozen l2: 1.0
Base and augmented models use identical T010-complete rows.

## Primary horizon

5 completed NSE sessions.
Folds:
1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-18
Paired Newey-West lag: 4

Primary success requires BOTH:
- augmented-minus-base mean rank IC > 0 with two-sided p < 0.05;
- augmented-minus-base mean top-minus-bottom spread > 0 with two-sided p < 0.05.

Top-decile excess is reported but is not a frozen success criterion.

## Secondary horizon

1 completed NSE session.
Folds:
1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-24
Paired Newey-West lag: 5
Secondary cannot rescue a failed primary.

## Diagnostic horizon

20 completed NSE sessions.
Folds:
1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-08-27
Paired Newey-West lag: 19
Diagnostic cannot rescue a failed primary.

## Exact comparison contract

For every horizon:
- same symbol+ISIN rows;
- same feature sessions;
- same action-safe labels;
- same folds;
- same ridge l2;
- only difference is 37 versus 44 features.

Missing P4A rows are excluded from BOTH sides.
No outcome-dependent imputation or row selection is allowed.

## Timing boundary

Historical T005 futures archive timing is not prospective proof.
Historical D010 short/SLB timing is not prospective proof.

Future confirmation, if T010 passes, requires separately frozen prospective
timing evidence for BOTH the futures inputs used by the model and the short/SLB
inputs. SC004 is the short/SLB timing authority.

SC004 passing later can never reclassify T010 as prospective evidence.

## Promotion

If T010 passes its frozen primary endpoint:
1. seal the historical result;
2. test the T010 incremental prediction against T005 in AB001 orthogonality;
3. separately design prospective confirmation only after timing gates are satisfied.

If T010 fails:
- seal the failure;
- do not retune these seven P4A features under T010;
- any revised short/borrow signal requires a new trial ID.

No live-capital implication.
