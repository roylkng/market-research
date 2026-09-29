# AE001 T004 Prospective Delivery/VWAP Confirmation v1

Status: FROZEN BEFORE FIRST ELIGIBLE DECISION SESSION
Frozen: 2026-09-29
Live capital: DISABLED

## Objective

Prospectively test whether the nine NSE delivery/VWAP features discovered in T003
add incremental 5-session cross-sectional predictive information beyond the
existing 18-feature action-safe price/liquidity ridge.

T004 is a confirmatory follow-up. It does not reinterpret T003.

## Trial hierarchy

Primary horizon: 5 completed NSE sessions.

Secondary horizon: 20 completed NSE sessions.

The 1-session T003 endpoint failed and is not re-tested as a T004 promotion
criterion.

The 20-session T003 result was diagnostic. T004 may report a 20-session
prospective result, but T004 success is determined only by the frozen 5-session
primary endpoint.

## Earliest eligible decision session

The first completed NSE decision session on or after 2026-09-30 that satisfies
all source, feature, universe and timing gates below.

No earlier session may be backfilled.

## Decision cutoff

18:30:00 Asia/Kolkata.

## Source-timing gate

A decision session is eligible only if AE001 SC001 contains an attempt for that
same session with:

`eligible_before_cutoff = true`.

This proves that the exact current-session UDiFF and delivery source files were
captured and validated no later than the frozen decision cutoff.

A missed/delayed SC001 probe cannot be repaired retrospectively.

## Models

### Base model

- ridge regression;
- l2 = 1.0;
- frozen 18 AE001 price/liquidity features;
- within-session tie-aware percentile transforms.

### Augmented model

- identical ridge regression;
- l2 = 1.0;
- same 18 base features;
- plus the frozen nine T003 delivery/VWAP features:
  - delivery_pct
  - delivery_pct_change_1
  - delivery_pct_delta_median_20
  - delivery_pct_zscore_20
  - delivery_pct_vol_20
  - delivery_qty_surprise_20
  - delivery_value_surprise_20
  - close_vs_vwap
  - vwap_vs_open

No model or hyperparameter tuning is allowed after the first eligible T004
decision session.

## Sample contract

Base and augmented models are evaluated on exactly the same stock-date rows.

A stock-date row must satisfy:

- dynamic AE001 NSE EQ universe rules;
- exact symbol + ISIN identity continuity;
- 60 prior completed market sessions;
- prior-20-session median traded value >= INR 20,000,000;
- corporate-action-safe raw-price lookback;
- 21 contiguous delivery observations including the current session;
- current-session SC001 source timing eligibility;
- T003-P3 delivery source-quality policy;
- all required feature values finite after frozen missing-data rules.

No missing delivery value is imputed.

A decision session must contain at least 500 common eligible stock rows or the
entire session is excluded from T004.

## Labels

Entry:
next completed NSE session open after the feature session.

Primary 5-session exit:
close of holding session 5, with entry session counting as holding session 1.

Secondary 20-session exit:
close of holding session 20.

Primary target:
stock return minus Nifty 500 return over the identical open-to-close interval.

Share-changing corporate actions during the holding interval fail closed for
that stock-horizon observation.

## Prospective training rule

For every T004 decision session, model fitting may use only examples whose label
exit session completed strictly before that decision session.

The current decision session and all future labels are unavailable to training.

No random splits are allowed.

## Primary confirmatory endpoint

The primary T004 comparison is augmented minus base on daily 5-session OOS
cross-sectional performance.

T004 primary success requires BOTH:

1. paired daily rank-IC difference > 0 with two-sided Newey-West p < 0.05,
   using lag 4;
2. paired daily top-minus-bottom-decile spread difference > 0 with two-sided
   Newey-West p < 0.05, using lag 4.

This is an intersection requirement. Failure of either condition means the T004
primary endpoint is not supported.

## Minimum evidence before opening the primary result

The primary result remains sealed until:

- at least 60 distinct eligible T004 decision sessions exist;
- every included 5-session label has matured;
- at least 50 of those sessions contain a valid paired rank-IC observation.

The trial may continue beyond 60 eligible sessions if maturity or valid-pair
requirements are not met.

## Secondary 20-session endpoint

The 20-session result is secondary and does not rescue a failed primary T004
endpoint.

It is opened only after all included 20-session labels mature.

Report:

- base and augmented mean rank IC;
- paired rank-IC difference with Newey-West lag 19;
- base and augmented top-minus-bottom spread;
- paired spread difference with Newey-West lag 19.

## Trial stopping and parameter changes

No feature, fold, model, l2, cutoff, minimum session count, success threshold,
universe rule or source-quality rule may be changed after the first eligible
T004 decision session.

A materially changed design requires a new trial ID.

## Cost and portfolio interpretation

T004 tests information content, not implementable portfolio P&L.

TC001 transaction-cost and impact modeling is still required before this signal
can be promoted into a portfolio policy.

## Relationship to T003

T003 historical-development findings:

- 1D primary incremental endpoint: not supported;
- 5D secondary incremental endpoint: supported;
- 20D diagnostic: positive but non-confirmatory.

T004 is frozen after those findings were observed. Therefore T004 uses only
future eligible decision sessions and is the confirmatory test for the 5D edge.

## Live capital

Disabled.
