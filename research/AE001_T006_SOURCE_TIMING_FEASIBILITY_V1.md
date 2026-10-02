# AE001 T006 Same-Session Futures Timing Feasibility v1

Status: FROZEN BEFORE COMPLETION OF EVIDENCE WINDOW
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Determine whether T006-v1's frozen same-session SC002 futures source gate is
operationally achievable by the frozen 18:30 Asia/Kolkata decision cutoff.

This is a source-timing feasibility audit only. It does not open alpha or return
outcomes and it does not modify T006.

## Evidence source

Canonical prospective source ledger:

`research/prospective/ae001-sc002/source-ledger.json`

Frozen NSE trading calendar:

`research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json`

## Evidence window

Use the first five completed NSE sessions in the frozen calendar beginning on
2026-09-30.

Expected sessions:

1. 2026-09-30
2. 2026-10-01
3. 2026-10-05
4. 2026-10-06
5. 2026-10-07

September 30 is valid timing evidence under the frozen T006 protocol even though
it cannot be a T006 prediction session.

## Per-session classification

For one expected session:

### ELIGIBLE_BEFORE_CUTOFF

At least one SC002 attempt has:

`eligible_before_cutoff = true`

This is positive evidence that T006-v1 source timing is operationally feasible.

### READY_AFTER_CUTOFF

No eligible-before-cutoff attempt exists, but at least one SC002 attempt has:

`futures.status = READY`

This proves the official same-session futures file eventually appeared, but only
after the frozen decision cutoff.

### OBSERVED_NOT_READY

Attempts exist but none reached READY.

This is not enough to infer when the source eventually published.

### NO_OBSERVATION

No SC002 attempt exists for the expected session.

This is missing operational evidence, not source-timing failure.

## Final feasibility classification

### TIMING_FEASIBLE

If ANY of the five expected sessions is ELIGIBLE_BEFORE_CUTOFF.

### TIMING_INFEASIBLE_FOR_FROZEN_T006

Only when ALL five expected sessions have a conclusive source observation and:

- zero sessions are ELIGIBLE_BEFORE_CUTOFF;
- all five are READY_AFTER_CUTOFF.

This means the source exists but systematically misses the frozen 18:30 cutoff
over the predeclared observation window.

### ACCUMULATING_EVIDENCE

Before either final condition is satisfied.

## Consequence

If TIMING_INFEASIBLE_FOR_FROZEN_T006:

- T006 remains immutable;
- no retrospective source capture may repair T006;
- T006 must not be reinterpreted as a lagged-futures trial;
- scheduled T006 scoring may be disabled in a separate operational change;
- any future futures trial requires a new trial identity.

T011 already tested previous-session lagged futures and failed its frozen primary
endpoint, so timing infeasibility does not automatically justify a new lagged
successor.

No live-capital implication.
