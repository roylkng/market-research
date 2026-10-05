# HG005-D002A Official Payoff-Enrichment Source Corpus v1

Status: **FROZEN BEFORE D002A ACQUISITION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Materialize the exact official-source corpus defined by:

`research/hg005/hg005-d002-source-manifest-v1.json`

and extract deterministic text segments before any new HG005 LLM inference.

D002A is provenance/text infrastructure inside the already-frozen HG005-D002 research
program. It does not interpret investment attractiveness.

## Frozen manifest

Expected:

- manifest_id: `HG005-D002-SOURCE-MANIFEST-v1`;
- exactly 19 source specifications;
- symbols exactly ANANTRAJ, DEVX, INOXGREEN, NPST, SAMBHV;
- returns/portfolio/live-capital flags all false.

## Acquisition modes

### DIRECT_URL

Fetch the exact manifest HTTPS URL.

Every direct URL must be on an approved manifest host and no redirect to an unapproved
host is accepted by the source validator.

### NSE_ANNOUNCEMENT_DISCOVERY

Use exact NSE corporate-announcement source with:

- exact symbol;
- frozen from/to dates;
- every frozen case-insensitive `desc_token` present in
  `desc + attchmntText`.

Exactly one canonical matching announcement with an approved NSE attachment URL is
required.

Zero or multiple matches fail that source closed.

Retain exact discovery bytes and SHA-256.

## Raw document retention

For every successfully resolved source:

- retain source URL;
- retain raw bytes under content-addressed SHA-256;
- retain raw byte count;
- detect document family from bytes;
- run existing deterministic SS002 text extraction;
- retain segment IDs, segment text SHA-256s and segment-manifest SHA-256.

No OCR is used in D002A.

## Mandatory anchor sources

All five must be READY with deterministic text:

- ANANTRAJ_SCHEME_BOARD_OUTCOME
- DEVX_PREF_MONITORING_Q1FY27
- INOXGREEN_WWIL_PLAN_UPDATE
- NPST_Q1FY27_MONITORING
- SAMBHV_WARRANT_EGM_NOTICE

These anchors cover the primary missing payoff facts for each company.

## Frozen feasibility gates

D002A passes only if all are true:

1. exactly 19 manifest sources are accounted for;
2. every mandatory anchor source is READY_TEXT;
3. at least 18 of 19 sources resolve to exact official raw bytes;
4. at least 90% of resolved sources are READY_TEXT;
5. all READY_TEXT segments reproduce their text SHA-256;
6. no source URL or discovery attachment violates the frozen host policy;
7. no return/valuation/portfolio outcome enters acquisition.

Thresholds may not be lowered after D002A output is opened.

## Promotion

Passing D002A permits:

- HG005-D002B evidence-bound explicit fact extraction using the existing SS002-L001
  validator/prompt envelope;
- deterministic company/lane fact synthesis;
- READY/PARTIAL D002 family states.

## Scientific boundary

D002A does not:

- estimate missing values;
- interpret a missing source as zero;
- assign valuation multiples;
- estimate completion probability;
- calculate expected returns;
- rank companies;
- authorize ADO/PF001/live capital.
