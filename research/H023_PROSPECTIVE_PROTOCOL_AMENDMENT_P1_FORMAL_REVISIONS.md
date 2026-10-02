# H023 Protocol Amendment P1: Formal NSE Record-ID Revisions

Frozen: 2026-10-03
Status: FROZEN BEFORE RESUMING H023 AFTER SOURCE-SEMANTICS FAILURE
Live capital: DISABLED

## Trigger

H023 prospective scan run 37044610412 failed closed on 2026-10-02 with:

`TCS/210064: official source identity drift detected`

The exact failed-run evidence proves NSE reused record ID `210064` for a formal
revision of the same TCS 2026-03-31 shareholding filing.

Sealed original source:

- report date: 2026-03-31;
- broadcast: 2026-04-21T10:24:45Z;
- record ID: 210064;
- original XBRL retained in the sealed H023 source ledger.

Observed official revision:

- report date: 2026-03-31;
- broadcast: 2026-09-17 13:00:28 Asia/Kolkata;
- record ID: 210064;
- `revisedStatus=Revised`;
- `revisionDate=16-Sep-2026`;
- a different approved NSE XBRL URL.

No H023 return outcome or signal rule is changed by this amendment.

## Corrected source semantics

NSE `recordId` is treated as a filing-family identifier, not as a globally
immutable filing-version identifier.

The deterministic H023 source identity remains the already frozen tuple:

- source contract;
- symbol;
- record ID;
- report date;
- official broadcast timestamp;
- approved XBRL URL.

Therefore a later formal revision naturally receives a new `source_id` even
when NSE reuses the same record ID.

## Reused-record acceptance rule

A second source version may reuse an existing `(symbol, record_id)` only if all
of the following are true:

1. report date is unchanged;
2. NSE marks the new master row `revisedStatus=Revised`;
3. a valid NSE `revisionDate` is present;
4. the new official broadcast timestamp is strictly later than every previously
   sealed version of that symbol/record ID;
5. the source identity is otherwise valid under the frozen H023 source contract.

Any same-record mutation that fails these gates remains a hard source-identity
error.

A formal revision with an equal or earlier broadcast time is rejected.

## Ledger treatment

Every valid revision is appended as a distinct source record.

Previously sealed source records are never rewritten or deleted.

The original filing and every accepted revision remain independently hash-bound
to their first-seen timestamps and master-row evidence.

## Primary H023 signal semantics remain unchanged

The frozen H023-v1 protocol already specifies:

- the primary current filing is the first official broadcast for the quarter;
- a later current-quarter revision never replaces a sealed primary current
  filing;
- a pre-boundary quarter remains permanently pre-boundary even if revised after
  the prospective boundary;
- the prior filing is the latest valid prior-quarter revision public no later
  than the current filing's first official broadcast;
- a newly discovered older revision that would invalidate sealed prior context
  remains a `RETROACTIVE_SOURCE_GAP`.

P1 changes no signal-selection rule.

## TCS 210064 classification

The 2026-09-17 TCS revision is append-only diagnostic source evidence.

Because the first 2026-03-31 TCS filing broadcast predates the H023 prospective
boundary, the quarter remains pre-boundary. The revision does not create a new
prospective H023 event.

## Scientific boundary

This amendment was triggered by official source semantics, not by stock-return
or alpha outcomes.

No H023 return outcome was inspected or used to define this amendment.

Live capital remains disabled.
