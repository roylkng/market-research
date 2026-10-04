# SS002-D001 P2 Current-vs-Archival Event Partition v1

Status: **FROZEN AFTER P1 SOURCE DIAGNOSTIC, BEFORE P2 RERUN**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P2 exists

P1 fixed the false-positive SAST phrase and reduced candidate events from 6,435 to 2,272,
but failed the inherited 90% current-identity mapping gate.

Source-only review shows the remaining unmapped population contains genuine special
situations for securities that are no longer members of the current NSE EQ security
master, including CIRP/resolution processes, compulsory delistings and restructurings.

Therefore a current-security mapping ratio is not a valid completeness criterion for an
historical/current special-situation announcement archive.

D001 and P1 remain preserved failed source hypotheses.

## Frozen candidate taxonomy

P2 uses the P1 taxonomy unchanged.

In particular OPEN_OFFER_CONTROL matches only:

- open offer;
- change of control;
- takeover offer.

All other P1 category tokens remain unchanged.

## Frozen source

Reuse exactly:

- the daily whole-market NSE announcement acquisition;
- source window 2026-04-01 through 2026-10-04 inclusive;
- canonical announcement identity;
- frozen SS001-D001 current EQ census SHA
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`.

## P2 event partition

Every candidate event is assigned exactly one identity state.

### CURRENT_INVESTABLE_IDENTITY

The announcement symbol exactly matches one current SS001-D001 NSE EQ symbol.

Retain the frozen current context:

- ISIN;
- listing date/age;
- median 20-session traded value;
- observed session count;
- U001 overlap.

Only this population may proceed to current opportunity attachment/LLM analysis.

### ARCHIVAL_NONCURRENT_IDENTITY

The announcement symbol has no exact current SS001-D001 EQ match.

The event remains in the archive for:

- historical analog research;
- special-situation pattern learning;
- corporate-action lineage.

It is not treated as a current investable candidate.

No fuzzy name mapping is permitted.

## Attachment readiness

For CURRENT_INVESTABLE_IDENTITY events, the NSE-supplied `attchmntFile` must be either:

- an approved HTTPS URL on `nsearchives.nseindia.com` or
  `archives.nseindia.com`; or
- explicitly absent.

P2 reports attachment-ready coverage.

P2 passes the attachment-readiness gate when at least 95% of current-investable events
carry an approved official NSE attachment URL.

The threshold is source-operational only and does not rank opportunities.

## Frozen feasibility gates

P2 passes only when:

1. every frozen calendar day is acquired;
2. canonical announcement identities are unique across daily sources;
3. every candidate event is partitioned exactly once into current-investable or archival;
4. every current-investable mapping is an exact current SS001 symbol match;
5. approved NSE attachment URL coverage among current-investable events is >=95%;
6. no return, valuation or portfolio outcome is used.

There is no minimum ratio requiring archival events to map to today's security master.

## Promotion

Passing P2 permits:

- SS002-D002 official attachment acquisition for CURRENT_INVESTABLE_IDENTITY events;
- deterministic symbol/category event-thread construction;
- SS002-D003 LLM term extraction from exact source documents;
- archival events to be retained for later historical analog work.

## Scientific boundary

P2 does not:

- discard genuine archival special situations;
- reinterpret archival events as current opportunities;
- use fuzzy company-name matching;
- estimate completion probabilities;
- calculate expected returns;
- authorize ADO/PF001/live capital.
