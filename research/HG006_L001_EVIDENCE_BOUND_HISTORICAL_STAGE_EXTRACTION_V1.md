# HG006-L001 Evidence-Bound Historical Stage and Anchor Extraction v1

Status: **FROZEN BEFORE HISTORICAL MODEL OUTPUT**  
Frozen: 2026-10-05  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Define the historical LLM extraction layer needed to turn exact HG006 event documents
into evidence-bound transaction-stage and transaction-anchor facts.

The model does not decide the historical completion rate.

## Input

Each request is bound to:

- one exact official document_id;
- one or more exact canonical announcement IDs;
- one exact NSE symbol;
- one frozen HG006 discrete family;
- deterministic ordered text segments;
- segment IDs and text SHA-256s;
- exact official source URL.

The model receives no market price, return, current-company conclusion or future outcome.

## Required output identity

The model must reproduce exactly:

- contract_id;
- document_id;
- event IDs;
- symbol;
- frozen family.

It may not change the family based on preference. If the document proves the upstream
family is misleading, it must retain the frozen family and emit a
`FAMILY_SEMANTIC_CONFLICT` caveat with evidence.

## Stage observations

The model may emit one or more explicit stage observations from:

- PROPOSAL;
- BOARD_APPROVED;
- SHAREHOLDER_APPROVED;
- REGULATORY_OR_COURT_APPROVED;
- PUBLIC_ANNOUNCEMENT;
- RECORD_DATE_FIXED;
- OFFER_OPEN;
- OFFER_CLOSED;
- ALLOTMENT_COMPLETED;
- WARRANT_EXERCISE_OR_CONVERSION_COMPLETED;
- TRANSACTION_COMPLETED;
- CANCELLED_OR_WITHDRAWN;
- PROCEDURAL_UPDATE;
- UNKNOWN.

Every non-UNKNOWN stage observation requires source segment IDs.

## Explicit terminal-language claim

Exactly one:

- NO_EXPLICIT_TERMINAL_LANGUAGE;
- EXPLICIT_COMPLETION_LANGUAGE;
- EXPLICIT_FAILURE_OR_WITHDRAWAL_LANGUAGE;
- CONFLICTING_TERMINAL_LANGUAGE.

This is document language only.

The deterministic HG006-D002 family ontology, not the LLM, decides whether that language
constitutes a terminal outcome for a transaction episode.

## Transaction anchors

The model may extract zero or more evidence-bound anchors using only:

- BOARD_APPROVAL_DATE;
- SHAREHOLDER_APPROVAL_DATE;
- RECORD_DATE;
- OFFER_OPEN_DATE;
- OFFER_CLOSE_DATE;
- EFFECTIVE_DATE;
- REGULATORY_OR_COURT_ORDER_DATE;
- ACQUIRER_OR_OFFEROR;
- TARGET_OR_TRANSFEROR;
- TRANSFEREE_OR_RESULTING_ENTITY;
- OFFER_OR_ISSUE_PRICE;
- SECURITY_COUNT;
- OFFER_OR_ISSUE_SIZE;
- ENTITLEMENT_OR_EXCHANGE_RATIO;
- SCHEME_OR_TRANSACTION_NAME;
- CASE_ORDER_REFERENCE;
- ALLOTTEE_OR_ALLOTTEE_GROUP;
- SECURITY_TYPE;
- OTHER_EXPLICIT_TRANSACTION_REFERENCE.

Each anchor contains:

- anchor_type;
- normalized value;
- evidence_segment_ids.

No derived arithmetic is allowed.

## Same-transaction references

When a document explicitly references:

- a prior board meeting;
- a prior public announcement;
- a scheme date/name;
- an earlier allotment;
- a specific NCLT/SEBI/exchange reference;
- a record date or offer period;

the model may extract that reference as an anchor.

The model may not state that two documents are the same episode merely because they are
close in time.

## Ambiguity

Required arrays:

- unresolved_questions;
- contradictions_within_document;
- extraction_caveats.

A document that does not clearly establish stage or transaction anchors remains
evidence-sparse. It is not filled from model memory.

## Forbidden output

The model must not emit:

- completion probability;
- expected return;
- target price;
- intrinsic value;
- buy/sell/hold;
- portfolio weight;
- historical stock-return outcome;
- current hidden-gem ranking.

## Deterministic validation

An accepted output must pass checks that:

1. input identity is unchanged;
2. every evidence segment exists in the input;
3. every explicit stage/anchor cites evidence;
4. no forbidden field appears;
5. enums are within the frozen vocabulary;
6. JSON is finite/canonicalizable;
7. model/prompt/document provenance is complete.

## Threading boundary

HG006-D003 consumes validated L001 anchors to construct transaction episodes.

L001 itself does not group episodes or decide same-transaction identity.

## Outcome boundary

HG006-D002 consumes the validated stage/terminal evidence after D003 threading to assign:

- COMPLETED;
- FAILED_OR_WITHDRAWN;
- RIGHT_CENSORED;
- UNRESOLVED_SOURCE_CONFLICT.

L001 does not assign those episode outcomes directly.

## Scientific boundary

No L001 output creates expected-return or portfolio eligibility.
