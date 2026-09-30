# AE001 SC002 Protocol Amendment P1: Post-Cutoff Publication Timing

Frozen: 2026-09-30
Status: OPERATIONAL DIAGNOSTIC AMENDMENT
Live capital: DISABLED

## Reason

The first SC002 decision-date observation on 2026-09-30 established that the
official same-session NSE F&O UDiFF source was still unavailable at:

- 18:22:47 IST; and
- 18:31:45 IST.

T006 remains frozen to the original 18:30 IST decision cutoff. No 2026-09-30
T006 decision exists and no T006 return outcome has been opened.

The operational question is now:

> At what time does the same-session official NSE F&O UDiFF source actually
> become available?

That source-timing question must be answered before defining any new later-cutoff
confirmatory trial.

## Post-cutoff diagnostic probes

SC002 will additionally attempt same-session source capture at approximately:

- 21:07 IST;
- 21:37 IST;
- 22:07 IST;
- 22:37 IST;
- 23:07 IST;
- 23:37 IST.

These observations use the existing SC002 parser and exact-byte retention
contract.

## Eligibility semantics

Post-cutoff observations are diagnostic only.

Even when the source status is READY:

`eligible_before_cutoff = false`

remains authoritative for T006.

No post-cutoff observation may:

- repair a missed T006 session;
- create a T006 decision;
- change T006's 18:30 cutoff;
- be treated as prospective T006 alpha evidence.

## Observation stopping rule

For one session date, once any SC002 attempt records:

`futures.status = READY`

later SC002 source probes for that same date are no-ops.

The first READY capture timestamp is the publication-availability observation
for that session under SC002-P1.

## Evidence needed before a new later-cutoff trial

Do not choose a new cutoff from a single session.

Before freezing a successor trial, collect first-READY publication observations
for at least three distinct completed NSE sessions.

The later cutoff, if any, must be selected from source-availability evidence
only. It must not use stock-return outcomes or T005/T006 performance.

## Relationship to T006

T006 remains unchanged and may proceed only on sessions where the source was
READY by 18:30 IST.

If SC002-P1 demonstrates that same-session F&O UDiFF is systematically published
after 18:30 IST, T006 may remain operationally starved. A successor trial with a
later same-day cutoff would require a new trial ID and a separately frozen
protocol.

Live capital remains disabled.


## Manual diagnostic trigger

A main-branch push may intentionally request an immediate post-cutoff diagnostic
probe by including:

`[sc002-postcutoff]`

in the commit message.

This trigger is permitted only as an operational source-timing observation.
It never changes the frozen 18:30 eligibility boundary.

For a manual post-cutoff probe:

- actual post-fetch UTC timestamp remains authoritative;
- READY after 18:30 remains `eligible_before_cutoff = false`;
- the first READY observation still stops later probes for that session;
- the observation may inform a future new-trial cutoff only after the frozen
  three-session publication-timing requirement is satisfied.
