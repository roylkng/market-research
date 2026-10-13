# AE001 SC001-P002: Same-Day Source Clock Reliability Backstop

Prepared **13 October 2026, after the 18:30 IST same-day-source
decision deadline**. This is a prospective workflow reliability
amendment for **future sessions**, not a revision of SC001's frozen
market signal, model, costs or trial accounting.

## Observed operational failure

The independently retained AE001 SC001 source ledger on 13 October
contains pre-session requests for the 2026-10-13 NSE reports made on
the previous UTC evening, but **no valid completed same-day original
equity-and-delivery source pair by 18:30 IST on 13 October**.
The canonical research-health summary therefore marks:

SC001_STALE

The official 13 October equity/index files available through the
separate H021 source pipeline **were captured later** and cannot be
relabelled as eligible SC001 information available before its frozen
source cutoff.

GitHub Actions event history reviewed during recovery shows
successful unrelated scheduled source jobs around 11:01-12:47 UTC on
13 October, but no SC001 *schedule* run at its separately declared
six 11:07-12:57 UTC times. SC001's later push runs occurred after
the source window. GitHub Actions schedules are not reliable enough
to be treated as guaranteed exactly-timed research observations.

The missed SC001 eligibility remains missed forever. No retrospective
source timestamp, stock feature, alpha score, portfolio action or
return is allowed for this failed day.

## Recovery for new sessions, not Oct 13 backfill

SC001 already has six frozen weekday crons at 16:37, 17:07, 17:37,
17:57, 18:17 and 18:27 IST. These are **preserved**.

P002 adds three independent GitHub Actions workflow-completion
wakeups, which had their own successful recurring source activities:

- H022 P001 prospective stream (around 16:31 IST);
- Company intelligence v2 prospective news capture (around 16:31 IST);
- HG008 original NSE hourly first-seen discovery clock (new pilot,
  with UTC hour 11/12 starts during the decision window).

These are only alternate opportunities to **start SC001's own
unchanged official source fetcher**. SC001 never borrows another
workflow's data, completion result, timestamp, ranking or weights.
Actual observed SC001 sources must still pass their existing price,
equity/delivery, same-day source-quality and 18:30 IST safeguards.

To minimize unrelated workflow_runs and runner load, an upstream
workflow-run event is admitted for a probe job only when it comes
from the trusted main branch and its UTC start hour is 11 or 12.
The gate then independently checks **the actual SC001 runner time**
in Asia/Kolkata. If the job was queued/delayed past 18:29 IST,
the source operation is skipped, not falsely backdated.

Automatic events (schedule, push, workflow_run) cannot fetch
outside 16:30 to just before 18:30 IST. Manual dispatch retains
its original diagnostic capability outside this window, but any
late-source eligibility is still forbidden by the existing source
ledger.

Each workflow-run source acquisition obeys the pre-existing
SC001 append-only ledger, original-source SHA and bounded Git
concurrency restrictions.

## Files and verification

- src/marketlab/ae001_sc001_window.py
- scripts/resolve_ae001_sc001_runner_window.py
- tests/test_ae001_sc001_window.py
- .github/workflows/ae001-sc001-prospective-source-timing.yml

Replay gate behavior:

    pytest -q tests/test_ae001_sc001_window.py

The newly added time-policy runner does not access external
market data and does not authorize portfolio allocation. The
existing probe_ae001_sc001.py and its independent quality rules
remain authoritative for any source eligible before cutoff.

## Falsifiable success condition

For the next officially open NSE trading sessions, look for
**at least one actual SC001 equity-plus-delivery READY source
attempt with captured_at_utc strictly before 13:00 UTC on the
same session**. Do not call the backup successful merely because
a workflow job returned a green status.

If both original NSE sources remain unpublished until after the
deadline, the prospective strategy must continue to abstain:
workflow reliability cannot solve exchange publication latency.

AE001's existing multiplicity-adjusted market alpha status and
H021's separate 20/60-session experiment remain unchanged.
Live capital disabled.
