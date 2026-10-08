# SS001-D007-Q002 Official-Document Binding Pilot v1

Status: **FROZEN BEFORE PILOT MATERIALIZATION**  
Frozen: 2026-10-08  
Share-change clearance: prohibited  
Market-capitalization calculations: prohibited  
Portfolio eligibility / live capital: disabled

## Purpose

Take the exact first 50 source-first issuer packets from SS001-D007-Q001 and
bind each NSE announcement to the official SS002-D002 attachment corpus and
deterministically extracted SS002-D003 text evidence.

This is evidence routing before LLM adjudication, **not** an assertion that
outstanding shares remained unchanged. The review queue is intended to
distinguish issuer equity actions from subsidiary actions, routine notices and
false-positive special-situation headlines without losing source provenance.

## Immutable inputs

- SS001-D007-Q001: run `37818227234`, artifact `11568750510`,
  queue SHA `53aea9016adfc62abfd778a1eb7b4bd6f6de262c30d01f1b7edf91abf2dbb4be`.
  Use `ss001-d007-pilot-first50.json`, cross-checking its exact packets
  against `ss001-d007-source-packets.json`.
- SS002-D002: passed corpus SHA
  `eab922954ef20a12a7635107722b4e800b59cfa56ff0659da42afb3fc22218f9`.
  Use checked-in compact manifest
  `research/ss002/ss002-d002-corpus-manifest-v1.json`, which binds event IDs
  to official URLs and raw document SHA-256.
- SS002-D003: run `37213853198`, artifact `11309315028`,
  corpus SHA
  `92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce`.
  Use `ss002-d003-text-corpus.json` as exact segment metadata.

Source-only inspection of the frozen first 50 packets established exactly
**244** announcement candidate references. This count is frozen as a completeness
invariant, not an investability score.

## Exact binding rule

For each Q001 announcement:

1. Require its event ID and symbol from the frozen first-50 packet.
2. For approved attachment links, require exactly one D002 URL row with that
   event ID, and require URL equality against Q001.
3. Bind document identity solely from D002 `document_id = SHA256(raw bytes)`.
4. Require the same document ID in D003, whose D003 corpus is explicitly tied
   to the exact D002 SHA.
5. Require the event ID to be listed in D003's document metadata.
6. Expose its D003 extraction state and, if READY, deterministic segment IDs,
   segment count and segment-manifest SHA.
7. For missing official links retain explicit `NO_OFFICIAL_ATTACHMENT`.

Different official URLs can yield identical raw document bytes; they must not be
treated as different economic evidence merely because the D003 refetch selected
another URL. The D002 event-to-URL binding is authoritative.

No internet search, replacement URL, guessed document hash or fuzzy company match
may repair missing evidence.

## Q002 states

- `TEXT_READY`: D002 document verified and D003 exact text segments READY;
- `DOCUMENT_READY_TEXT_UNAVAILABLE`: D002 hash exists, D003 text unavailable;
- `NO_OFFICIAL_ATTACHMENT`: Q001 event has no approved official attachment;
- `DOCUMENT_SOURCE_NOT_READY`: D002 official row/source unavailable, with
  explicit reason retained.

Any conflicting D002 event/URL/document association or changed frozen input
SHA is a hard failure, not an imputation.

Corporate-action-only packets retain exact D007 action source SHA, ex-date,
ISIN and subject even when they have no announcement document.

## Frozen quality gates

Q002 passes only if:

1. exact 50 packet identities/ranks reproduce Q001;
2. all 244 announcement references are accounted for;
3. all claimed approved URLs are bound uniquely through D002 by exact event ID
   and URL;
4. all bound D003 documents match exact D002 document IDs;
5. >=90% of approved-document announcement references have ready text;
6. no clearance or capitalization is produced.

## Next permitted step

Passing Q002 permits a separately frozen **D007-L001 economic-relevance
adjudication pilot**. The LLM may label whether the document concerns the
listed issuer's equity, subsidiary economics, debt, or procedural filings,
but may not declare share-count continuity from missing keywords.

Final positive share-action clearance requires affirmative document evidence
of issued-share quantity/security-class continuity over the relevant time
interval, corporate-action reconciliation and independent validation.

## Exclusions

No market capitalization, future returns, expected IRR, valuation, capital
allocation, buy/sell/hold, ADO, PF001 or live trading decisions are produced.
