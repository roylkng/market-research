# SS002-L001-P2 Expanded-Family Evidence-Bound Extraction Pilot v1

Status: **FROZEN BEFORE ANY P2 MODEL OUTPUT**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Validate the existing SS002-L001 evidence-bound extraction contract on the five
special-situation families that are present in the first HG002 hidden-gem underwriting
cohort but were not covered by L001-P1.

P2 tests model extraction quality only. It does not rank stocks or estimate returns.

## Frozen HG002 dependency

Family selection is derived only from:

- HG002-D001-v1;
- workflow run: `37260536415`;
- artifact ID: `11324486396`;
- cohort SHA-256:
  `3937b8cb83ef819ff956af4afebb80cd81d8ef233c1e4dd5b6d3688541a48db1`.

HG002 identifies the following L001-P1-unvalidated family counts:

- SCHEME_REORGANISATION: 11;
- PREFERENTIAL_WARRANT: 10;
- INSOLVENCY_RESOLUTION: 5;
- RIGHTS_ISSUE: 2;
- OFFER_FOR_SALE: 1.

No other family may enter P2-v1.

## Frozen source chain

Use exactly:

- SS002-D001-P2 census SHA:
  `ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071`;
- SS002-D003 text corpus SHA:
  `92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce`;
- SS002-L001 extraction contract v1.

## Frozen pilot families

Exactly:

1. SCHEME_REORGANISATION
2. PREFERENTIAL_WARRANT
3. INSOLVENCY_RESOLUTION
4. RIGHTS_ISSUE
5. OFFER_FOR_SALE

## Frozen deterministic sample rule

For each family independently:

1. start from SS002-D001-P2 CURRENT_INVESTABLE_IDENTITY events;
2. require an approved D002 document_id;
3. require the same document to be TEXT_READY in passed D003;
4. require the frozen P2 event taxonomy to contain the family;
5. sort by exchange publication timestamp descending;
6. tie-break by canonical announcement_id ascending;
7. retain at most one event/document per NSE symbol;
8. retain at most one occurrence of each document_id;
9. select the first **5** qualifying rows.

Expected maximum pilot size: 25 documents.

If a family has fewer than 5 qualifying documents, retain all qualifying documents.
No substitution from another family is allowed.

## Prompt / validation

Every selected document uses exactly:

`research/SS002_L001_EVIDENCE_BOUND_DOCUMENT_FACT_EXTRACTION_V1.md`

and:

`src/marketlab/ss002_llm_contract.py`

No family-specific extra hints may weaken UNKNOWN or evidence-citation rules.

## Model run identity

A P2 run must retain:

- provider/runtime;
- model ID;
- configuration SHA-256;
- complete prompt SHA-256;
- raw model response SHA-256;
- validated structured-output SHA-256.

A changed model/configuration is a new run.

## Mechanical gates

Promotion requires:

1. 100% of accepted outputs pass the L001 validator;
2. zero invalid evidence references;
3. zero invented event IDs or symbols;
4. zero forbidden return/valuation/advice fields;
5. >=80% non-UNKNOWN economic relevance;
6. >=80% at least one non-UNKNOWN transaction family.

No failed document may be reprompted with special case-specific hints inside the same run.

## Manual evidence audit

Audit exactly 10 documents:

- the first two selected documents from each of the five P2 families.

For every audited document check all material EXPLICIT facts against cited segments.

Audit states:

- SUPPORTED
- UNSUPPORTED
- MATERIAL_TERM_MISSED
- AMBIGUITY_NOT_RETAINED

Promotion requires:

- zero UNSUPPORTED material facts;
- zero AMBIGUITY_NOT_RETAINED;
- no more than 2 of 10 documents with MATERIAL_TERM_MISSED.

## Promotion

Passing P2 permits:

- broad L001 extraction across these five families;
- HG002 special-situation stage/relevance validation;
- L002 transaction threading;
- deterministic family-specific payoff models where the extracted terms are sufficient.

## Explicit exclusions

P2 does not:

- estimate expected return;
- estimate completion probability;
- calculate intrinsic value;
- rank HG002 companies;
- create buy/sell/hold advice;
- authorize ADO/PF001/live capital.
