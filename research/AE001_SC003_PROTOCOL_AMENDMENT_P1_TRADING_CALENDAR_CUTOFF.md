# AE001 SC003 Protocol Amendment P1: Trading-Calendar Pre-Open Cutoff

Frozen: 2026-10-02T09:07:14Z
Status: FROZEN BEFORE FIRST P1 PROBE
Live capital: DISABLED

## Trigger

SC003-v1 defines its operational question as:

> Is session-D official NSE F&O UDiFF available before 08:30 IST on the
> following trading morning?

The first SC003 attempt targeted 2026-10-01 and used 2026-10-02 as the cutoff
date because the workflow equated the local observation date with the next
trading date.

The already-frozen NSE CM calendar identifies 2026-10-02 as Mahatma Gandhi
Jayanti, an exchange holiday. The first trading session after 2026-10-01 is
2026-10-05.

Therefore the v1 workflow's calendar-day cutoff is operationally inconsistent
with the already-frozen protocol objective.

No return or alpha outcome was opened by SC003.

## Immutable prior evidence

The existing v1 attempt for target 2026-10-01 remains unchanged.

It must not be retrospectively relabeled.

Its original fields, hash, and v1 cutoff remain canonical historical evidence of
what the v1 implementation observed.

P1 applies only to new attempts created after this amendment.

A P1 attempt whose actual capture timestamp precedes
2026-10-02T09:07:14Z fails closed.

## Frozen calendar

Authoritative snapshot:

    research/prospective/calendars/FY27-Q2-2026-09-06/
    NSE-CM-FY27Q2-v1.json

Calendar SHA-256:

    2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce

Calendar version:

    NSE-CM-FY27Q2-v1

No current-date weekday approximation may replace this calendar.

## P1 target and cutoff

Target D:

- latest SC001 session with eligible_before_cutoff=true;
- D must exist in the frozen NSE calendar;
- target source evidence is already sealed by SC001.

Cutoff session N:

- first frozen NSE CM trading session strictly after D.

P1 pre-open cutoff:

    N at 08:30:00 Asia/Kolkata

A capture may occur at any timestamp after D's frozen market close and no later
than N 08:30 IST.

This explicitly permits:

- target-evening capture;
- overnight capture;
- exchange-holiday capture;
- weekend capture.

The scientific timing question is source availability before the next trading
open, not whether GitHub happens to execute on the same calendar date as N.

Example frozen by this amendment:

    D = 2026-10-01
    next NSE session N = 2026-10-05
    cutoff = 2026-10-05 08:30 IST

## Attempt semantics

Every P1 attempt additionally records:

- protocol = AE001-SC003-P1;
- frozen_calendar_sha256;
- frozen_calendar_version;
- target_close_timestamp_utc;
- cutoff_session_date;
- preopen_cutoff_utc.

A P1 attempt is ready_before_preopen_cutoff only when:

1. exact target-D FO UDiFF parses under the frozen T005 contract;
2. captured_at_utc is after/equal to target-D frozen close;
3. captured_at_utc is before/equal to cutoff N 08:30 IST.

## Multiple observations for one target

A prior READY source observation that missed its applicable cutoff must not
prevent a later P1 attempt for the same target.

At most one attempt per target may have:

    ready_before_preopen_cutoff = true

After one pre-open-ready observation exists, later probes for that target are
idempotent no-ops.

## Operational redundancy

GitHub scheduling delay has already been observed at multi-hour scale.

P1 therefore adds redundant opportunities:

- target-evening probes after typical FO publication;
- overnight probes;
- pre-open probes;
- opportunistic main-branch push probes.

Actual capture timestamps remain authoritative.

A delayed or missed workflow remains operational missingness, not negative NSE
source evidence.

## Successor-trial gate

Unchanged:

- require at least three distinct target sessions with valid P1/v1
  ready_before_preopen_cutoff=true observations;
- successor trial must be frozen separately;
- feature session remains D;
- decision remains no later than next trading session N at 08:30 IST;
- entry remains N open;
- no backfill;
- no return/alpha outcome is used by SC003.

## Non-goals

- no T006 mutation;
- no return outcome;
- no model fit;
- no alpha promotion;
- no retrospective reinterpretation of v1 attempt hashes;
- no live capital.
