# AE001 SC002 Publication-Timing Analyzer v1

Status: FROZEN BEFORE SECOND DISTINCT READY SESSION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Convert SC002's prospective first-READY source observations into a deterministic,
source-only readiness signal for designing a successor stock-futures
confirmatory trial.

This analyzer does not create a successor trial and does not change T006.

## Required evidence

At least three distinct completed NSE sessions with an SC002 attempt whose:

    futures.status = READY

Only the earliest READY observation for each session is used.

T006 eligibility is irrelevant to this timing analysis. A READY source captured
after 18:30 remains ineligible for T006 but is valid source-publication evidence
for this analyzer.

## No outcome inputs

The analyzer may use only:

- session date;
- SC002 capture timestamp;
- SC002 attempt hash;
- futures source hash;
- source READY state.

It may not use:

- stock returns;
- T005/T006 predictions;
- T005/T006 alpha metrics;
- future portfolio results.

## Frozen candidate-cutoff rule

After at least three distinct READY sessions exist:

1. convert every first-READY timestamp to Asia/Kolkata;
2. measure seconds elapsed from that session's local midnight, allowing D+1;
3. select the latest observed first-READY publication time;
4. add a 30-minute operational safety buffer;
5. round upward to the next 15-minute wall-clock boundary.

The output is a successor-cutoff candidate only.

It is represented by:

- candidate_cutoff_ist;
- candidate_cutoff_session_offset_days;
- candidate_cutoff_basis_session.

Example:

If the latest observed first-READY timestamp is 21:17:10 IST on D:

    21:17:10 + 30 minutes = 21:47:10
    rounded upward = 22:00:00
    session offset = D+0

If the latest first-READY timestamp is 00:35 IST on D+1:

    +30 minutes = 01:05
    rounded upward = 01:15
    session offset = D+1

## Why use the maximum

The objective is operational source availability, not a median latency estimate.

A successor confirmatory trial should not systematically exclude sessions merely
because the source is later than its typical publication time.

The maximum of the frozen observation sample plus a buffer is deliberately
conservative.

## Why 30 minutes

SC002 observations are discrete probes rather than exchange-published source
timestamps. The exact publication instant can precede the observation, while
workflow/network delays can also affect observed capture time.

A 30-minute buffer is frozen before the second and third publication
observations and is not tuned from alpha outcomes.

## Why 15-minute rounding

The rounded cutoff is intended to be operationally simple and reproducible.
It is not an optimization variable.

## Output states

Before three distinct READY sessions:

    INSUFFICIENT_EVIDENCE

At or after three:

    SOURCE_TIMING_READY_FOR_SUCCESSOR_DESIGN

Even in the second state:

    successor_trial_cutoff_frozen = false

A new successor trial still requires a separately reviewed and frozen protocol.

## Current evidence at freeze

2026-09-30 first READY:

- captured UTC: 2026-09-30T15:39:27.254727+00:00
- captured IST: 2026-09-30T21:09:27.254727+05:30
- T006 eligible before 18:30: false

Distinct READY sessions: 1.

Two additional distinct READY sessions are required.

## Relationship to T006

T006 remains frozen at 18:30 IST.

This analyzer cannot:

- backfill T006;
- change T006's cutoff;
- turn a post-cutoff observation into T006 evidence.

## Promotion

After three distinct READY sessions, the analyzer may supply a source-only
candidate cutoff to a new trial design.

No live-capital implication.
