# SS001-D007-L001-P1 GPT-6 Native Evidence-Relevance Pilot v1

Status: **FROZEN BEFORE OPENING SELECTED SOURCE TEXT OR MODEL OUTPUTS**  
Frozen: 2026-10-08  
Portfolio / live capital: disabled  
Share-continuity certification and market capitalization: prohibited

## Purpose

Run the first actual LLM extraction against the frozen SS001-D007-L001-P0
issuer-relevance source queue.

This measures whether a model can correctly distinguish issuer equity actions,
subsidiary transactions, schemes and procedural notices using **only** the exact
official NSE filing text with page-level citations.

## Frozen inputs

- SS001-D007-L001-P0-v1;
- source run `37826755723`, artifact `11571427335`;
- queue SHA
  `cbd36ef8c868a8a54610f0fb3e7f30e8a4746c897333140e3f1d9521b1c7622a`;
- exactly twelve complete issuer-document prompt envelopes;
- the SS002-L001-v1 structured output contract and deterministic validator.

No selection change after reading texts; all 12 selected documents must be reported,
including unknown/failed outputs.

## Model identity

- model ID: `GPT-6`;
- runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- extraction mode: `SINGLE_DOCUMENT_EVIDENCE_BOUND`;
- frozen prompt contract: `SS002-L001-v1`;
- inference settings like temperature and top_p: `NOT_EXPOSED_BY_NATIVE_RUNTIME`
  (do not claim they were set to zero).

Version every response with the exact prompt SHA, input document ID, segment
manifest SHA, response SHA, and model configuration SHA.

## Model role and outputs

For every selected document, produce the complete SS002-L001 JSON schema:

- economic relevance to the *listed issuer*;
- true transaction family, not the original keyword hint if misleading;
- transaction stage;
- material explicit terms with source segment IDs;
- unresolved questions and material caveats.

Unstated facts remain UNKNOWN. No external data, user financial information,
market prices, future outcomes, analyst views or web search may enter extraction.

## Frozen mechanical gates

1. 12/12 requests accounted for, without discarding hard documents;
2. every accepted extraction passes the unchanged
   `marketlab.ss002_llm_contract.validate_extraction` contract;
3. zero invented issuer or event IDs and zero unsupported segment references;
4. zero forbidden valuation/return/advice fields;
5. at least 10/12 non-UNKNOWN economic-relevance states;
6. at least 10/12 non-UNKNOWN transaction family states.

No retries tuned for individual issuer results within this registered run.

## Evidence review

Audit the first six selected documents in P0 order for:

- every material EXPLICIT term supported by cited segment;
- transaction relevance not confused with subsidiary-only operations;
- missing material terms and unretained contradictions;
- uncertainty clearly retained.

Acceptance for preliminary *extraction usability* requires zero unsupported
material facts, zero unretained contradictions and no more than two documents
with material term omissions.

An internal model-performed audit is **not independent human verification** and
cannot clear share quantities for capitalization. Independent reviewer sign-off
is required for any later issuer share-continuity decision.

## Scientific boundary

Even a perfect document extraction does not prove no intervening share issuance
or conversion. A future D007-L002 issuer-thread adjudication must reconcile
all relevant dated documents, exact security classes, shareholding snapshots and
corporate-action effective dates.

P1 computes no market cap, intrinsic value, predicted return, completion
probability, opportunity ranking, ADO, PF001 or live trade.
