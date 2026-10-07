# HG006-D003 P2 Ingestion-Envelope Chronology Identity Amendment v1

Status: **FROZEN AFTER P1 EXECUTION FAILURE, BEFORE HISTORICAL TERMINAL LABELS ARE OPENED**  
Frozen: 2026-10-07  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P2 exists

HG006-D003-P1 passed lint/unit validation after a timezone-format repair, then failed
during real episode construction with:

`HG006 D003 extraction identity incomplete`.

Source-only diagnosis showed that the validated HG006-L001 extraction contract contains:

- document_id;
- event_ids;
- symbol;
- family;
- transaction anchors;

but intentionally does **not** contain `chronology_id`.

The authoritative `chronology_id` is already present in the validated P2 ingestion
envelope that binds each model response back to its frozen HG006-L001 request.

Therefore P1 incorrectly required a model-output field that the frozen L001 contract
never allowed.

No historical terminal label, completion probability, market return or current-company
outcome was opened during this diagnosis.

## Frozen P2 correction

For every P2 ingestion row:

1. require status = VALIDATED;
2. require non-empty envelope:
   - chronology_id;
   - document_id;
   - symbol;
   - family;
3. require a sealed `validated_extraction`;
4. require exact equality between envelope and sealed extraction for:
   - document_id;
   - symbol;
   - family;
5. copy only the trusted envelope `chronology_id` into the in-memory extraction view
   consumed by D003 threading.

The model never supplies, changes or infers chronology_id.

Event IDs continue to come only from the sealed validated extraction because they are
part of the frozen L001 contract and evidence validation.

## Deliberately unchanged

P2 does not change:

- any strong episode-link anchor;
- any hard-conflict anchor;
- graph construction;
- singleton handling;
- event-count requirement of 1,564;
- minimum 30 episodes per priority family;
- source ingestion SHA;
- S002 pack SHA;
- terminal-label boundary.

## Fail-closed behavior

D003 must reject an ingestion row when:

- chronology_id is empty;
- document_id, symbol or family in the envelope differs from the sealed extraction;
- validated extraction is missing;
- any existing P1 identity rule fails.

## Scientific boundary

This amendment repairs only the deterministic source-envelope join.

It does not:

- alter model output;
- infer transaction identity from chronology proximity;
- use stage or terminal language for grouping;
- open historical outcomes;
- change current hidden-gem research.
