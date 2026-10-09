# SS001-D007-L002 Issuer Evidence Assembly v1

Status: **FROZEN BEFORE ANY FULL 1,240-REQUEST R001 INFERENCE COLLECTION**
Frozen: 2026-10-09
Return outcomes opened: no
Market capitalization: prohibited
Issuer share-count clearance: prohibited
Portfolio eligibility and live capital: disabled

## Purpose

Turn source-validated **page-level evidence** into a lossless, issuer-indexed review
ledger for the exact first 12 SS001-D007 issuers. This is not an automatic issuer
chronology verdict.

The language model extracts explicit facts from original NSE pages. Deterministic
code brings those facts together with preserved source identity and highlights
unresolved terms; an independent semantic review must reconcile them.

## Frozen inputs

1. `SS001-D007-L001-P2-v1`:
   - source run `37884584355`, artifact `11595955883`;
   - SHA `59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618`;
   - exactly 12 issuer symbols, 82 documents, 70 fresh and 12 reused;
   - exactly 1,240 fresh page requests and 12 corporate-action rows.
2. `SS001-D007-L001-P1-v1`:
   - source run `37883572697`, artifact `11595515888`;
   - SHA `1a3a2f73eaed8ba09c84ab7c8d60699fa895f39d25d5797bd16138b09fd620cb`;
   - exactly 12 previously audited native extractions.
3. A future verified `SS001-D007-L001-R001-v1` collection:
   - exact frozen queue and request IDs, zero extras or duplicates;
   - host-managed model provenance and one runtime configuration;
   - each page must validate using the immutable `SS002-L001-v1` contract.
   - an API model is a distinct execution cohort, **not** assumed equivalent to
     the prior GPT-5.6 Sol native P1/P2-P0 pilot.

## Source-to-issuer join

The 12 reused document identities must match exactly, including:

- symbol;
- document ID;
- source event IDs;
- P1 prompt SHA;
- model config SHA;
- segment-manifest SHA;
- validated structured output SHA.

The 70 fresh documents must match exact queue `fresh_documents` records.
Each page's request, prompt, segment and model configuration hashes are checked by R001.

No semantic or financial outcome determines which pages are admitted.

## Evidence ledger

For every issuer, produce one ordered entry per frozen document and one sub-entry
per page-level extraction or preserved P1 extraction. Retain:

- document ID and official source URL;
- Q002 source event IDs and category hints;
- source document order and page/segment IDs;
- runtime/model configuration identity;
- page-level relevance, transaction families and stage;
- every explicit fact **as a separate claim**, with field path, value, unit,
  evidence segment IDs and original page request ID;
- UNKNOWN facts are counted but never imputed;
- unresolved questions, caveats and document-local contradiction notes;
- corporate-action evidence rows with source SHA, ex-date and ISIN.

The assembler **does not merge** facts from different documents into one fact.
Different prices/stages/quantities over time may reflect genuine amendments rather
than errors.

## Mechanical review flags

Flags are descriptive only:

- `UNRESOLVED_SOURCE_COVERAGE`: one or more frozen fresh pages lacks validated output;
- `MULTIPLE_EXPLICIT_VALUES_REVIEW`: a field has distinct explicit values across
  an issuer's pages/documents;
- `DIRECT_SECURITY_RELEVANCE_REVIEW`: model reported direct listed-security economics;
- `MIXED_MODEL_COHORTS`: P1 reused native model and R001 API cohort differ;
- `SOURCE_CONFLICT_REVIEW`: extraction self-reports contradictions.

None is a ranking signal, return forecast or proof of issued-share change.

## Frozen gates

A full L002 evidence assembly is complete only if:

1. exactly 12 frozen issuers are present;
2. exactly 12 P1 document IDs are bound with their original hashes;
3. exactly 1,240 R001 page requests are represented and validated;
4. exactly 82 document IDs and 12 corporate-action rows are retained;
5. zero unsupported new symbols, documents, pages or event IDs;
6. independent semantic audit remains pending;
7. no share-count clearance, market cap, alpha or capital authorization is output.

Before all pages are inferred, an incremental assembly may be reported only as
`PARTIAL_EVIDENCE_PENDING_MODEL_OUTPUT`.

## Next step

Only an independently checked full assembly can enter a separately frozen
`SS001-D007-A001` issuer-share-action adjudication protocol. Even then,
capitalization needs affirmative point-in-time issued-capital and security-class
evidence and action-date reconciliation.

## Scientific boundary

No outcome peeking, economic threshold tuning, automatic buy/sell/hold,
issuer capitalization, expected IRR, model probability, PF001 eligibility or
live capital is permitted.
