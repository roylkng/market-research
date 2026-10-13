# AE001 SC001-P003: Two-Stage Runtime Clock Before NSE Source Fetch

Frozen for future sessions on 13 October 2026 IST after the daily cutoff.
No attempt is made to rehabilitate the missed 13 October SC001 source
observation or edit the parent signal/trial.

## Failure mode addressed

P002 added independent wakeups for the existing SC001 same-day
16:30 to 18:30 IST source window. However, SC001's full GitHub
Actions job installs the Python dev package, runs lint/tests and
verifies several existing source ledgers before its original
time gate. That can take minutes.

A delayed workflow_run, unrelated after-hours push, or scheduled job
that starts too close to 18:30 would needlessly consume CI capacity
and could miss an otherwise eligible source-poll opportunity.

## Conservative change

P003 introduces two independent actual runner-clock checks using
the previously reviewed immutable P002 policy.

1. EARLY preflight after checkout and Python setup, but before
   the costly dependency install/tests. If not READY, skip source
   verification, market retrieval and potential decision assembly.
2. LATE recheck after source-code tests and ledger verification
   but immediately before the original NSE equity-plus-delivery
   source request. If cutoff passed while the job installed or
   tested, no fetch or decision is run.

Both checks use the actual currently executing UTC timestamp,
converted to Asia/Kolkata. Neither uses the upstream trigger time,
job scheduled clock, first historical document publication timestamp,
or filenames as evidence of availability.

The late gate remains the sole source-probe eligibility trigger.
It invokes unchanged official fetch code, quality checks, original
byte custody and transaction/portfolio risk boundaries.

No manual adjustment of 2026-10-13 eligibility is permitted.

## Expected operational benefit

- Fewer unnecessary long test runs for workflow_run wakeups outside
  16:30-18:29 IST.
- No automatic after-cutoff source attempts treated as eligible.
- Reduced latency for near-live source polls when official reports
  may become available near the cutoff.
- Regression showing 18:29:55 preflight READY does not authorize a
  source probe whose second clock check occurs at 18:30:02.

This is a reliability opportunity, not evidence of actual successful
next-session SC001 data. A quality-READY NSE equity/delivery pair
captured before the frozen cutoff is still necessary to clear
SC001_STALE.

## Source and CI

- .github/workflows/ae001-sc001-prospective-source-timing.yml
- tests/test_ae001_sc001_window.py
- src/marketlab/ae001_sc001_window.py

No changes to original alpha feature or statistical thresholds.
Existing source ledger and missing-data states remain unmodified.

Current live-capital authorization is false. The four health blockers
from 13 October cannot be cleared by changing job status alone.
