# SS001-D007-L001-P1 Native Issuer Relevance Extraction Pilot v1

Status: **FROZEN BEFORE P1 MODEL OUTPUT**  
Frozen: 2026-10-09  
Share continuity / market capitalization: prohibited  
Return outcomes opened: no  
Portfolio eligibility / live capital: disabled

## Purpose

Execute the first real issuer-level SS002-L001 extraction on the already-frozen
SS001-D007-L001-P0 prompt queue.

P1 asks one narrow question:

> What corporate transaction is explicitly described by this exact official document,
> and how directly does it affect the listed issuer/security?

P1 is not final share-count adjudication and is not an investment model.

## Frozen source queue

Use exactly:

- queue ID: `SS001-D007-L001-P0-v1`;
- workflow run: `37826755723`;
- artifact ID: `11571427335`;
- artifact name: `ss001-l001-p0-37826755723`;
- queue SHA-256:
  `cbd36ef8c868a8a54610f0fb3e7f30e8a4746c897333140e3f1d9521b1c7622a`;
- issuer count: 12;
- selected document count: 12.

The exact queue order is:

1. JAYKAY
2. INDIAGLYCO
3. HEGAM
4. IITL
5. ORBTEXP
6. PVRINOX
7. GANDHITUBE
8. RATNAVEER
9. TEAMLEASE
10. TRIVENI
11. DUCON
12. INOXGREEN

No issuer or document may be substituted after model output is observed.

## Frozen extraction contract

Use exactly:

`SS002-L001-v1`

implemented by:

`marketlab.ss002_llm_contract.validate_extraction`.

All EXPLICIT facts require exact supplied segment IDs. UNKNOWN remains UNKNOWN.

## Model/runtime

Exactly:

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- temperature target: `0.0`;
- top_p target: `1.0`;
- maximum structured-output budget: `4096` tokens per request;
- structured-output mode: `JSON_OBJECT`;
- model-config SHA-256:
  `133b5705036d1782f671d6a171fe5f24298939cf6d84314875c2e8452e7169dc`.

No web search, saved memory, later filing, current price, current company profile,
portfolio state or post-document outcome may enter an extraction.

## Native response convention

For each frozen prompt:

1. GPT-5.6 Sol produces only the substantive SS002-L001 JSON payload;
2. provenance is host-managed;
3. canonical JSON bytes of the pre-provenance substantive payload are retained as the
   raw-model-response bytes;
4. SHA-256 of those bytes becomes `raw_model_response_sha256`;
5. host code injects exact queue/model provenance;
6. `validate_extraction` validates and seals the response.

No request-specific retry hint or prompt rewrite is permitted inside P1.

## Mechanical gates

P1 passes mechanically only if:

1. exactly 12 outputs are present;
2. all 12 pass `validate_extraction`;
3. zero invalid evidence references;
4. zero invented event IDs, symbols or document IDs;
5. zero forbidden return/valuation/advice fields;
6. all 12 preserve the exact frozen prompt SHA-256;
7. all 12 preserve the exact D003 segment-manifest SHA-256;
8. at least 10 of 12 contain at least one EXPLICIT material fact or a non-UNKNOWN
   relevance/family/stage observation.

A genuinely sparse document may remain sparse.

## Full manual audit

All 12 outputs are manually checked against their complete supplied document segments.

For each output retain:

- unsupported_explicit_claim_count;
- material_fact_or_relevance_missed;
- unretained_material_contradiction_count;
- manual_audit_notes.

The manual audit passes only if:

1. unsupported explicit claim count = 0 across all 12;
2. unretained material contradictions = 0 across all 12;
3. no more than 1 of 12 has a material fact/relevance miss.

No output is repaired using outside information.

## Promotion

Passing P1 permits an issuer-level chronology review that may combine multiple
pre-cutoff official documents for the same issuer.

P1 does **not** prove unchanged or changed issuer share count by itself.

## Explicit exclusions

P1 does not:

- calculate historical or current market capitalization;
- infer share-count continuity from one document;
- infer completion probability;
- estimate expected return;
- rank hidden gems;
- create ADO/PF001/live-capital eligibility.
