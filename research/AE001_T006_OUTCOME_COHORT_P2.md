# AE001 T006 Outcome Cohort Amendment P2

Status: FROZEN BEFORE FIRST ELIGIBLE T006 DECISION SESSION
Frozen: 2026-09-30
Live capital: DISABLED

## Purpose

Remove stopping-date and cohort-selection discretion before prospective T006
predictions begin.

## Canonical decision ordering

T006 decisions are ordered by their immutable decision-ledger sequence, which is
chronological by unique session date.

## Primary 5D cohort

The primary result uses the smallest chronological prefix of canonical T006
decisions for which ALL of the following are true:

1. prefix contains at least 60 distinct decision sessions;
2. every decision in the prefix has a matured canonical 5-session outcome;
3. at least 50 prefix sessions have a valid paired base/augmented rank-IC
   observation.

If the first 60 decisions do not satisfy maturity/valid-pair requirements, extend
the prefix one decision at a time until they do.

No later or alternative subset may be chosen.

## Primary inference

On that frozen prefix:

- augmented minus base paired daily rank-IC difference;
- augmented minus base paired daily top-minus-bottom-spread difference.

Newey-West lag: 4.

Primary support requires BOTH mean differences > 0 with two-sided p < 0.05.

## Secondary 1D cohort

The 1-session secondary uses exactly the same decision-session prefix selected by
the primary 5D rule.

It is reported only after the primary result is frozen.

Newey-West lag: 5.

The secondary result cannot rescue a failed primary result.

## Immutability

No change to:

- minimum decision count;
- minimum valid paired-IC count;
- canonical-prefix rule;
- inference lag;
- success thresholds;
- secondary cohort linkage

is permitted after the first eligible T006 decision.

A material change requires a new trial ID.
