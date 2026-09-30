# AE001 Delivery Warm-up Diagnostic — 2026-09-30

Status: OPERATIONAL DIAGNOSTIC
Live capital: DISABLED

## Observation

SC001 captured valid same-session NSE cash UDiFF and delivery evidence on
2026-09-30 before the frozen 18:30 IST cutoff.

T004 nevertheless produced zero eligible feature rows.

This was not caused by the current-session sources.

## Frozen delivery-history requirement

T004 and T006 require:

- 20 prior completed delivery sessions;
- current delivery session;
- one contiguous 21-session delivery feature window;
- no imputation;
- T003-P3 whole-session exclusion when the official delivery source is internally
  inconsistent.

## Blocking source session

The prior-20-session window for the 2026-09-30 decision was:

- 2026-09-01
- 2026-09-02
- 2026-09-03
- 2026-09-04
- 2026-09-07
- 2026-09-08
- 2026-09-09
- 2026-09-10
- 2026-09-11
- 2026-09-15
- 2026-09-16
- 2026-09-17
- 2026-09-18
- 2026-09-21
- 2026-09-22
- 2026-09-23
- 2026-09-24
- 2026-09-25
- 2026-09-28
- 2026-09-29

The 2026-09-11 NSE delivery file is frozen as:

`EXCLUDE_SESSION_INTERNAL_FIELD_INCONSISTENCY`

with 2,575 violating complete EQ rows under the T003-P3 delivery-quality rule.

## Warm-up state as of 2026-09-30

Consecutive clean prior delivery sessions after the blocker:

11

Additional clean prior sessions required before the prior-20 window can be
entirely READY:

9

This count is based on completed-session count, not calendar days.

No exact future eligibility date is predicted because future NSE sessions and
future source quality must themselves be observed.

## Consequence

T004 correctly fails closed until the blocking 11 Sep session rolls out of its
frozen prior-20-session window.

T006 has the same delivery-history requirement. Even if SC002 later establishes
same-session futures availability, T006 cannot create a decision while this
delivery warm-up state remains blocked.

## Operational change

The prospective scorers now run an explicit source-level warm-up preflight after
prior delivery acquisition and before corporate-action/model construction.

When blocked, they report:

- blocking source dates/statuses;
- consecutive clean prior sessions;
- additional clean prior sessions needed;
- market/delivery support hashes.

This does not change feature eligibility. It only makes the already-frozen
fail-closed rule explicit and auditable.

No retrospective backfill is permitted.
