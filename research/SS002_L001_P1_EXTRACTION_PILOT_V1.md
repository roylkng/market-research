# SS002-L001-P1 Evidence-Bound LLM Extraction Pilot v1

Status: **FROZEN BEFORE ANY PILOT MODEL OUTPUT**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Validate the frozen SS002-L001 evidence-bound document extraction contract on a
deterministic cross-section of current special-situation documents.

This pilot evaluates document understanding and source discipline. It does not rank
stocks or estimate returns.

## Required upstream state

The pilot may run only after SS002-D003 passes its frozen deterministic text-corpus gates.

Authoritative upstream chain:

- SS002-D001-P2 current-vs-archival event partition;
- SS002-D002 official attachment corpus;
- SS002-D003 deterministic text corpus;
- SS002-L001 evidence-bound extraction contract.

No model may receive raw material outside this chain.

## Frozen pilot transaction families

Exactly five families:

1. BUYBACK
2. OPEN_OFFER_CONTROL
3. TENDER_OFFER
4. DELISTING
5. ASSET_SALE_DIVESTMENT

These were selected before D003 text contents or any LLM output were inspected because
their economics are comparatively concrete and suitable for extraction validation.

## Frozen deterministic sample rule

For each family independently:

1. start from SS002-D001-P2 CURRENT_INVESTABLE_IDENTITY events;
2. require an approved D002 document_id;
3. require the same document to be TEXT_READY in passed D003;
4. retain only events carrying the selected family in the frozen P2 taxonomy;
5. sort by exchange publication timestamp descending;
6. tie-break by canonical announcement_id ascending;
7. keep at most one event/document for each NSE symbol;
8. keep at most one occurrence of each document_id;
9. select the first 6 qualifying rows.

Expected maximum pilot size: 30 documents.

If a family has fewer than 6 qualifying documents, retain all qualifying documents.
No replacement from another family is allowed.

## Prompt input

For each selected document supply exactly:

- document_id;
- source URL used by D003;
- canonical event IDs linked to that document;
- current NSE symbol(s);
- frozen P2 category hints;
- ordered deterministic D003 text segments;
- segment IDs;
- segment text SHA-256 values;
- D003 segment_manifest_sha256.

No web search or company profile is included in L001.

## Model configuration

Each pilot run must freeze and retain:

- provider/runtime identifier;
- model ID;
- endpoint/runtime class;
- temperature;
- top_p when configurable;
- maximum output tokens;
- structured-output/JSON mode configuration;
- complete configuration SHA-256.

A different model or configuration is a different pilot run, not an overwrite.

## Pilot output

Every raw model response and validated structured extraction is retained separately.

Validation uses exactly:

`src/marketlab/ss002_llm_contract.py`

A failed validation remains a failed observation; the model is not reprompted with
special hints for that document inside the same registered pilot run.

## Frozen mechanical success gates

A pilot model/configuration is mechanically usable only if:

1. 100% of accepted outputs pass the deterministic L001 schema/provenance validator;
2. zero accepted EXPLICIT facts cite a segment absent from the request;
3. zero accepted outputs introduce an event ID or symbol absent from the request;
4. zero accepted outputs contain a forbidden valuation/return/advice field;
5. at least 80% of selected documents receive non-UNKNOWN economic_relevance;
6. at least 80% receive at least one non-UNKNOWN transaction family.

These are extraction-operability gates, not accuracy claims.

## Frozen manual evidence audit

Before promotion beyond the pilot, manually audit exactly 10 selected documents:

- the first 2 selected documents from each of the five families.

For every audited document check all material EXPLICIT fields against cited segments.

Material extraction audit states:

- SUPPORTED
- UNSUPPORTED
- MATERIAL_TERM_MISSED
- AMBIGUITY_NOT_RETAINED

Promotion requires:

- zero UNSUPPORTED material facts;
- zero unretained material contradictions;
- no more than 2 of 10 documents with MATERIAL_TERM_MISSED.

This audit examines extraction quality only. It must not inspect future stock returns.

## Promotion

Passing P1 permits:

- broader L001 extraction across mechanically tractable SS002 families;
- SS002-L002 event/document threading;
- deterministic family-specific payoff models.

## Explicit exclusions

The pilot does not:

- calculate arbitrage spread;
- estimate completion probability;
- calculate intrinsic value;
- rank opportunities;
- use future returns;
- create buy/sell/hold advice;
- authorize ADO/PF001/live capital.
