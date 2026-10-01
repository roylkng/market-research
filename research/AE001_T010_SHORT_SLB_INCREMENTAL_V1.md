# AE001 T010 Short-Selling / SLB Incremental Feature Trial v1

Status: FROZEN BEFORE RETURN OUTCOMES
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Test whether the seven source-stable D010 P4A short-selling / securities-lending
features add incremental cross-sectional information beyond the already-passed
37-feature T005 price/liquidity/delivery/futures stack.

T010 is a new feature-family trial. It does not modify T005, D010 P4A, AB001 or
any prospective ledger.

## Upstream evidence

### Base alpha family

T005 historical-development result:

- trial: AE001-T005;
- result SHA:
  7cd152a452db7cf50944c8729afd299aa2a2cdceacf988b27094447168f01605;
- base 27-feature panel:
  99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90;
- passed 37-feature futures panel:
  62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f;
- primary 5D incremental signal supported.

### Short / borrow feature family

D010 P4A source-only result:

- result file: research/ae001-d010-p4a-result-v1.json;
- P4A feature panel SHA:
  1b629fee85e7430466d81e5c8e5a3497cca77221ab7d38633b23c7db5b49f4b0;
- feature artifact SHA:
  dcb9d4e59df3992dbc71b0633c51c27e20dcd81de5eb5570c0e7d0f9fbb92513;
- report SHA:
  58ce64d9a247f30da13a535991658a36a6696e2b61e2b3094a71741963fb3b41;
- no return labels opened before P4A;
- no predictive model fit before P4A.

## Frozen comparison

Base:

    exact T005 37-feature set

Augmented:

    same 37 T005 features
    + seven D010 P4A features
    = 44 features

Model family:

    ridge

L2:

    1.0

Base and augmented models must use the exact same symbol+ISIN stock/session rows.

The only difference is the seven D010 features.

## Frozen D010 features

1. short_volume_share_lag1
2. short_volume_share_change_1
3. short_volume_share_percentile_20
4. slb_outstanding_days_volume20
5. slb_outstanding_change_days_volume20
6. slb_outstanding_percentile_20
7. slb_active_series_count

The removed unstable z-score fields are prohibited.

## Exact source/common-row construction

T010 must independently reproduce:

1. exact T005 37-feature panel;
2. exact D010 P4A 25-feature panel.

The T010 44-feature panel is an inner join on:

    feature_session + symbol + ISIN

For every common row, the overlapping 18 base AE001 feature values must agree
between the T005 and P4A panels.

If an overlapping base feature differs materially, the row fails closed.

D010-only values are copied from the P4A panel.

No missing D010 value is imputed beyond the already-frozen P4A semantics.

The combined panel contains no return outcome.

## Source-only amendment before outcome opening

Before any T010 return label or model fit is opened, a T010 protocol amendment
must record exact hashes for:

- market panel;
- corporate-action ledger;
- T005 37-feature panel;
- D010 P4A panel;
- T010 combined 44-feature panel;
- common-row/session counts.

The outcome workflow may run only after that amendment exists.

## Horizons

### Primary: 5 sessions

Same folds as T005:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-09-18.

Paired Newey-West lag:

    4

Primary success requires BOTH:

- augmented-minus-base mean rank IC > 0 with two-sided p < 0.05;
- augmented-minus-base mean top-minus-bottom spread > 0 with two-sided p < 0.05.

### Secondary: 1 session

Same folds as T005:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-09-24.

Paired Newey-West lag:

    5

Secondary cannot rescue a failed primary.

### Diagnostic: 20 sessions

Same folds as T005:

1. 2026-04-01 through 2026-06-30;
2. 2026-07-01 through 2026-08-27.

Paired Newey-West lag:

    19

Diagnostic cannot rescue a failed primary.

## Source timing

Historical D010 archive availability does not establish decision-time publication.

Historical T010 evidence class:

    HISTORICAL_RECONSTRUCTION_DEVELOPMENT_SOURCE_TIMING_UNVERIFIED

Historical T010 may establish information content only.

Prospective confirmation requires future sessions satisfying all relevant
point-in-time source gates, including:

- AE001 SC001 / current cash+delivery timing;
- AE001 SC002/SC003 as applicable for futures;
- AE001 SC004 for short-selling and SLB.

A later SC004 pass may never relabel T010 as prospective evidence.

## Multiple testing

T010 increments the AE001 feature-family trial count by one.

No hyperparameter search.

No post-outcome clipping, feature deletion, alternate horizon, alternate fold,
alternate ridge penalty or alternate success rule is allowed under T010.

Any revised short/SLB signal requires a new trial identity.

## Interpretation

If primary passes, the seven-feature short/SLB family may be promoted as an
independent AB001 candidate for orthogonality testing against existing alpha
families.

If primary fails, T010 is recorded as failed and is not retuned.

No live-capital implication.
