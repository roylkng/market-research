# AE001 H021 Expectations Feature Family v1

Status: FROZEN BEFORE FIRST VALID H021 REVISION COHORT
Frozen: 2026-10-03
Live capital: DISABLED
Return outcomes opened by this integration: NO

## Objective

Integrate the independently frozen H021 analyst-consensus experiment into the
shared AE001 information plane without changing H021's scientific rules.

This layer is a derived point-in-time feature adapter only.

It does not:

- reconstruct historical analyst consensus;
- alter H021's 28-35 calendar-day matching rule;
- alter H021's >=5 analyst primary coverage threshold;
- alter H021's EPS-only primary rank;
- open H021 or AE001 return outcomes;
- create a new trading recommendation.

## Source contract

Only immutable, sealed H021 full-U001 captures are accepted.

Required source protocol:

- H021 prospective protocol v1;
- H021 comparison contract v1;
- H021 weekly acquisition contract v1;
- frozen U001 universe;
- frozen H021 source version.

The prior/current pair is selected exclusively by the frozen H021 comparison
logic. Historical consensus reconstruction remains prohibited.

## Universe

The adapter emits every symbol in the frozen H021 U001 universe exactly once.

Identity is exact symbol + ISIN from the frozen U001 universe.

A missing/ineligible H021 primary signal remains a row with null primary numeric
features and an explicit reason. It is never silently dropped.

## Frozen numeric features

1. h021_primary_eps_revision_30d_pct
   - H021 EPS revision percentage;
   - populated only when the H021 primary signal is ELIGIBLE;
   - otherwise null.

2. h021_primary_eps_revision_rank_pct
   - tie-aware within-cohort percentile of feature 1;
   - ranked only across H021 primary-eligible names;
   - otherwise null.

3. h021_revenue_growth_change_pp
   - H021 secondary diagnostic;
   - same-period/same-period-end semantics only.

4. h021_profit_growth_change_pp
   - H021 secondary diagnostic;
   - same-period/same-period-end semantics only.

5. h021_target_price_revision_pct
   - H021 secondary diagnostic;
   - same-period/same-period-end semantics only.

6. h021_min_analyst_count
   - minimum of prior/current analyst counts when both are explicit;
   - otherwise null.

7. h021_primary_coverage_flag
   - 1 when analyst count >=5 at both captures;
   - 0 otherwise.

8. h021_primary_signal_available_flag
   - 1 only when H021 primary_signal_reason == ELIGIBLE;
   - 0 otherwise.

The H021 reason code is retained as row metadata and is not numerically encoded
in v1.

## Timing

Feature known-at time is the exact current H021 capture completion timestamp.

The artifact records:

- whether the current capture completed by AE001's 18:30 IST EOD cutoff;
- the first frozen NSE session whose open occurs after capture completion.

A capture that finishes after 18:30 IST is not same-day AE001 EOD information.
It remains valid H021 information for its own frozen next-session-open execution
rule.

If the path to the next session crosses an unresolved NSE special-session date,
the adapter fails closed until the calendar is resolved.

## Provenance

The derived artifact binds to:

- prior H021 capture gzip SHA;
- prior H021 canonical JSON SHA;
- current H021 capture gzip SHA;
- current H021 canonical JSON SHA;
- derived H021 comparison SHA;
- frozen universe SHA;
- frozen calendar SHA;
- frozen source version.

Every row carries the current capture timestamp as known-at time.

## Future modeling

This adapter does not authorize an AE001 expectations model.

Any model/blender test using these features must receive a separate trial ID,
freeze its horizon/splits/metrics before outcomes, and respect the actual
feature availability timestamp.

## Promotion

H021 remains governed by its own prospective promotion gates.

AE001/AB001 may not treat this adapter as validated alpha merely because the
feature artifact exists.

Live capital remains disabled.
