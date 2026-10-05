# HG006-D001 P2 Canonical NSE Calendar-Day Semantics v1

Status: **FROZEN AFTER SHARD ACQUISITION, BEFORE A COMBINED D001 CENSUS EXISTS**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Completion probabilities assigned: no  
Scientific population changed: no

## Why P2 exists

The four frozen HG006-D001 source shards all completed successfully, but the deterministic
combine step failed before producing a historical census with:

`HG006 D001 canonical day mismatch`.

The already-audited canonical announcement parser
`marketlab.alpha_announcements.normalize_announcement_payload` assigns an announcement
to a requested NSE calendar day by converting its timezone-aware exchange timestamp to
Asia/Kolkata before comparing dates.

HG006-D001 then performed a second redundant day check using UTC calendar date.

For announcements published between 00:00 and 05:29 Asia/Kolkata, the same instant lies
on the prior UTC calendar date. Such an announcement therefore correctly passes the NSE
calendar-day source validator and incorrectly fails the HG006 UTC recheck.

No combined HG006-D001 census, chronology counts, terminal labels, probabilities,
returns, or current-company outcomes were opened before this amendment.

## P2 correction

HG006-D001 `_published_day` must return:

`exchange_published_at_utc -> Asia/Kolkata calendar date`

using the same timezone semantics as
`normalize_announcement_payload`.

The source key/day remains the exact requested NSE calendar day.

## Explicitly unchanged

P2 does not change:

- source window 2023-01-01 through 2026-09-30;
- initiation window through 2025-12-31;
- four frozen acquisition shards;
- exact retained raw source bytes;
- daily SHA-256 evidence;
- canonical announcement identity;
- SS002-P1 event taxonomy;
- discrete family set;
- chronology construction;
- attachment coverage gate;
- minimum chronology thresholds;
- right-censoring cutoff;
- stage ontology;
- episode threading;
- base-rate estimator;
- bootstrap uncertainty method;
- any current HG005/HG006 company input.

## Validation requirement

Add a regression test in which an announcement with a UTC timestamp on the prior
calendar day but an Asia/Kolkata timestamp on the requested NSE day is accepted.

An announcement whose Asia/Kolkata date differs from the requested source day must
still fail in the canonical parser.

## Scientific boundary

P2 is a timezone/source-calendar repair only. It does not authorize probability
estimation until the unchanged D001 source-feasibility gates pass.
