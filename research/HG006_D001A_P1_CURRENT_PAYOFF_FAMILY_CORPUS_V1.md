# HG006-D001A-P1 Current-Payoff-Family Historical Document Corpus v1

Status: **FROZEN BEFORE HISTORICAL DOCUMENT BODY ACCESS**  
Frozen: 2026-10-05  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Execute the first HG006 historical official-document corpus on the transaction families
that directly govern unresolved current payoff-ready cases.

The parent HG006-D001A contract remains the general all-family provenance design.

P1 limits the first acquisition to:

- SCHEME_REORGANISATION;
- PREFERENTIAL_WARRANT.

This family selection is frozen from current HG005 payoff-readiness states before
historical terminal labels are opened.

## Current-case rationale

SCHEME_REORGANISATION is required for:

- ANANTRAJ — live demerger entitlement / scheme effectiveness risk.

PREFERENTIAL_WARRANT is required for:

- SAMBHV — live preferential-warrant/allotment financing progression.

DEVX and NPST have already completed their relevant financing issuance and their
remaining uncertainty is operating capital productivity, which HG006-D004 explicitly
does not model.

INOXGREEN remains source-partial and does not justify expanding historical acquisition
before its current payoff economics are source-complete.

## Frozen upstream source

Use exactly HG006-D001-v1:

- workflow run: `37347148756`;
- artifact ID: `11361421023`;
- census SHA-256:
  `a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5`.

Relevant D001 chronology counts:

- SCHEME_REORGANISATION: 583;
- PREFERENTIAL_WARRANT: 460;
- combined: 1,043.

## Event inclusion

Retain every D001 event whose frozen `historical_discrete_families` includes at least
one P1 family and that belongs to at least one P1 chronology.

Every included event is accounted for exactly once.

Events without approved attachment remain explicit NO_APPROVED_ATTACHMENT states.

## Source rules

All URL validation, content identity, byte-family detection, failure handling and
evidence retention follow HG006-D001A v1 unchanged.

## Frozen sharding

Acquisition shard:

`int(SHA256(source_url)[0:8], 16) mod 8`

Shard IDs 0 through 7.

## Feasibility gates

P1 passes only if:

1. all 1,043 selected chronologies are accounted for exactly once;
2. all selected events are accounted for exactly once;
3. every approved URL maps to one acquisition result;
4. at least 95% of unique approved URLs fetch successfully;
5. at least 95% of selected attachment-ready events resolve to successful bytes;
6. at least 95% of selected attachment-ready chronologies have at least one successful
   document;
7. all successful documents have deterministic SHA-256 identity;
8. all fetched URLs are approved NSE archive hosts;
9. no historical terminal label, stock return or current-company outcome is used.

## Promotion

Passing P1 permits deterministic text extraction and HG006-L001 historical stage/anchor
extraction for these two families only.

No base rate for any other family may be produced from P1.

## Scientific boundary

P1 changes acquisition priority only. It does not alter:

- HG006-D002 outcome ontology;
- HG006-D003 episode-threading rules;
- HG006-D004 estimators or sample thresholds;
- any current-company payoff surface.
