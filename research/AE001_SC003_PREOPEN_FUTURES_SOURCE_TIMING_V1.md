# AE001 SC003 Previous-Session Futures Pre-Open Timing v1

Status: FROZEN BEFORE FIRST SC003 PROBE
Frozen: 2026-10-01
Earliest observation date: 2026-10-02
Live capital: DISABLED

## Objective

Prospectively establish whether the official NSE F&O UDiFF file for the most
recent completed cash-market session is available and parseable before 08:30 IST
on the following trading morning.

SC003 is source-timing evidence only. It opens no stock-return outcomes and does
not modify T006.

## Motivation

T005's historical design uses session-D cash/delivery/futures information and
enters at the next completed NSE session open.

SC001 proves session-D cash UDiFF and delivery files are available before the
same-day 18:30 cutoff.

SC002 has shown that session-D FO UDiFF may publish after 18:30. That blocks T006
but does not invalidate the historical T005 economic timing if the same official
FO file is available before the D+1 open.

SC003 tests that narrower operational question directly.

## Target session

At each SC003 probe, target the latest SC001 session satisfying:

- SC001 eligible_before_cutoff = true;
- target session date is strictly earlier than the local observation date.

This ensures the target is a completed cash-market session with already-sealed
cash/delivery evidence.

No calendar-day assumption is made. Weekends and exchange holidays are handled
by selecting the latest qualifying SC001 session.

## Frozen pre-open cutoff

08:30:00 Asia/Kolkata on the observation date.

Actual post-fetch capture timestamp is authoritative.

A target session is pre-open-ready only when:

- the official FO UDiFF source parses under the frozen T005 contract;
- the source is captured no later than 08:30 IST.

## Source

Exact T005/SC002 official NSE source:

    https://nsearchives.nseindia.com/content/fo/
    BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip

The source must pass the existing T005 stock-futures parser contract.

## Probe cadence

Weekday approximate IST probes:

- 06:30
- 07:00
- 07:30
- 08:00
- 08:15
- 08:25

GitHub scheduling delay is expected.

A delayed/missed job is operational missingness, not evidence that NSE had not
published the source.

Once READY is observed for one target session, later SC003 probes for that
target session are no-ops.

## Evidence contract

Each attempt records:

- target session date;
- observation local date;
- actual captured_at_utc;
- pre-open cutoff timestamp;
- source URL;
- source status;
- exact raw SHA-256/path;
- T005 parser diagnostics;
- ready_before_preopen_cutoff;
- immutable attempt SHA.

Canonical state:

    research/prospective/ae001-sc003/source-ledger.json

Exact source bytes:

    research/prospective/ae001-sc003/raw/<target-session>/

## Successor-trial gate

SC003 does NOT freeze a successor alpha trial.

Before a new pre-open futures confirmation may be designed, require at least
three distinct target sessions with READY source observations no later than
08:30 IST.

The future successor protocol must be frozen separately and must preserve:

- feature session = D;
- decision no later than D+1 08:30 IST;
- entry = D+1 open;
- exact T005/T006 frozen feature definitions;
- no backfill of missed source captures.

T006 remains unchanged and can still proceed if SC002 ever observes same-session
FO availability by its original 18:30 cutoff.

## Non-goals

- no model fitting;
- no prediction;
- no return label;
- no T006 repair/backfill;
- no automatic successor-trial creation;
- no live capital.
