# AB001 P002 Protocol Amendment P1: Source-Filing Dissemination Time

Frozen: 2026-09-30
Status: FROZEN BEFORE P002 MATERIALIZATION
Live capital: DISABLED

## Trigger

The sealed H024 event builder aggregates multiple surviving Original filings for
one (symbol, planned-entry-session) event.

Its displayed event-level `exchange_disseminated_at_ist` field is constructed
with a string minimum over filing timestamps.

For ordinary same-month timestamps this is equivalent to chronological order,
but string ordering is not a defensible causal primitive across month
boundaries.

P002 has not been materialized and no P002 return comparison has been opened.

## Frozen resolution

For P002 EOD causality, the authoritative event-knowledge timestamp is:

> the earliest parsed `exchange_disseminated_at_ist` among the exact surviving
> H024 source filings referenced by the sealed event's `app_ids`.

Source panel:

`research/historical/h024/prefreeze-original-purchase-source-panel-v1.json`

Frozen raw source-panel SHA-256:

`94bb81839c7d868736f830e88a3feb83538a04dfc7be01d546a7839e2bf3d101`

Every event app_id must resolve to exactly one source-panel record with the same
symbol.

The binary event becomes known when the first such qualifying filing becomes
public. Later same-event filings do not delay an already-known binary signal.

The event-level aggregate timestamp is checked against the source-derived
earliest timestamp and any mismatch is reported in P002 diagnostics.

## Pre-materialization audit

Read-only audit before this amendment was frozen:

- sealed H024 event count: 209;
- source app_id resolution failures: 0;
- event aggregate timestamp vs parsed earliest-source mismatch count: 0.

Therefore this clarification does not change the already-recorded P002
feasibility counts.

## Non-changes

P1 does not change:

- H024 event membership;
- H024 revision blocking;
- H024 score;
- H024 entry session;
- 18:30 IST cutoff;
- 20-session P002 horizon;
- any AE001 model or fold;
- any outcome.

No live-capital implication.
