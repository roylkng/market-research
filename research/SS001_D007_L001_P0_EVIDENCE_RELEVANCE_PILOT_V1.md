# SS001-D007-L001-P0 Evidence-Bound Economic-Relevance Pilot Queue v1

Status: **FROZEN BEFORE ANY D007 MODEL INFERENCE**  
Frozen: 2026-10-08  
Share continuity / market capitalization: prohibited  
Portfolio eligibility / live capital: disabled

## Purpose

Prepare the first real LLM investigation of possible issuer-level share changes.
This is an **economic-relevance extraction pilot**, not final share-count adjudication.

A corporate-action keyword can refer to subsidiary equity, restructuring steps,
unrelated financial instruments, or a completed capital change. The model's first
job is to read the exact official document and distinguish those situations with
page-level evidence, before a later multi-document issuer chronology review.

## Immutable upstream inputs

- SS001-D007-Q002-v1, run `37825546492`, artifact `11571052476`,
  binding SHA
  `c3c28d55b98a08c91e99b76d5ae2732f2ca24406fa12752be2f0e75fa0624f36`.
- SS002-D003-v1, run `37213853198`, artifact `11309315028`,
  corpus SHA
  `92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce`.
- SS002-L001-v1 extraction contract:
  `research/SS002_L001_EVIDENCE_BOUND_DOCUMENT_FACT_EXTRACTION_V1.md`.

No model memories, web lookup, news, prices, portfolio outcomes or company profiles
may supplement document evidence within L001.

## Frozen selection

1. Take exactly the first 12 issuer packets in Q002 `review_queue_rank` order.
2. For each issuer, traverse its Q002 announcement evidence in the frozen order.
3. A document is eligible only if its Q002 state is `TEXT_READY`, its D003
   record/document ID and segment-manifest SHA match exactly, and its complete
   text consists of at most 10 nonempty segments totaling at most 32,000
   characters.
4. Select the first eligible distinct document for that issuer. Do not choose a
   later document based on its economic facts.
5. If none is eligible, mark the issuer `SOURCE_OR_CONTEXT_LIMIT` without
   replacement from another issuer.
6. A document cannot be assigned to multiple pilot issuers.

Exactly 12 selected issuer-document pairs are expected for the frozen source.
No segments may be truncated to fit the budget. An oversized document is skipped
as a whole, with its reason retained.

The context bounds are transport/quality limits, **not learned investment
thresholds**.

## Prompt

Use the existing frozen SS002-L001 `build_prompt_envelope`.

Every request contains:

- document ID;
- original approved NSE source URL from D003;
- linked canonical event IDs;
- linked current NSE symbols;
- source-category hints;
- complete deterministic D003 text segments;
- segment IDs/text SHA-256;
- D003 segment-manifest SHA-256;
- frozen required output template and prompt SHA-256.

## Model inference and validation boundary

P0 only materializes immutable prompts; it performs no inference.

A later run may execute those exact prompts with a versioned model/runtime and
must validate every extraction using
`marketlab.ss002_llm_contract.validate_extraction`.

Every material EXPLICIT term must cite a supplied segment ID. UNKNOWN must remain
unknown.

Outputs must distinguish economic relevance, transaction family and stage, but
must never independently infer unchanged issuer share count or publish market cap.

## Frozen P0 feasibility gates

- 12 exact issuer packet positions examined and accounted for;
- 12 eligible complete document prompts;
- each selected event/document is in exact Q002 and D003 records;
- every segment text SHA-256 verifies;
- no page/segment truncation;
- no model inference, share clearance, capitalization or investment decision.

## Later pilot review

Even a valid L001 output is a **single-document extraction**. Issuer share-count
continuity requires complete pre-cutoff action chronology, positive effective-date
evidence, source share-class reconciliation and an independent reviewer.

## Explicit exclusions

No estimated market cap, expected return, probability of completion, alpha
claim, buy/sell/hold, ADO, PF001 or live-capital authorization.
