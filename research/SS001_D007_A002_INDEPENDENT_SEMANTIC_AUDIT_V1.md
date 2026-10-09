# SS001-D007-A002 Pre-Registered Independent Semantic Audit v1

Status: **FROZEN BEFORE FULL R001 MODEL INFERENCE**
Frozen: 2026-10-09
Return outcomes opened: no
Share-count clearance, capitalization, ADO/PF001 and live capital: disabled

## Purpose

Create a deterministic, outcome-blind human/independent semantic-review sample and
review-packet generator for the 1,240 frozen SS001-D007-L001-P2 page requests.

A model's JSON passing `validate_extraction` **does not** prove it interpreted the
original NSE document correctly. The audit must inspect material claims and
entity/transaction stages against the original supplied page.

This protocol does not change the frozen prompts, models, 12-issuer cohort, 70 fresh
documents, 16 shards or underlying NSE evidence.

## Frozen source

- queue `SS001-D007-L001-P2-v1`
- run `37884584355`, artifact `11595955883`
- queue SHA-256:
  `59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618`
- 12 issuers, 70 fresh documents, 1,240 fresh page requests, 16 shards
- native P1's 12 previously audited documents remain separately identified
- L001 full R001 inference not yet executed as of protocol freeze

## Frozen source-only sampling

For **each of the 70 fresh documents**, sort its frozen page requests by
`segment_order`, breaking ties by request ID. Select the union of:

1. the first original page (`FIRST`);
2. the last original page (`LAST`);
3. the lower middle original page, `floor((n-1)/2)` (`MIDDLE`);
4. the page whose request ID has minimum SHA-256 digest (`HASH_CONTROL`);
5. the **first** page matching one of the frozen issuer/capital terms below
   (`CAPITAL_LANGUAGE`), when present;
6. the **first** page matching one of the frozen entity-distinction terms below
   (`MULTI_ENTITY_LANGUAGE`), when present.

The text match is a simple case-insensitive substring check after whitespace
normalization. It uses **only original NSE document text**, never model output,
market prices, subsequent outcomes or analyst judgment.

Capital substrings:

- `issued share capital`, `equity share capital`, `equity shares`;
- `rights entitlement`, `share swap`, `capital reduction`;
- `preferential allotment`, `warrants`, `exercise price`.

Entity substrings:

- `subsidiary`, `demerged`, `transferee`, `resulting company`;
- `associate company`, `group company`, `target company`.

One page may satisfy several rules and is selected once with all reason codes.
Never replace selected pages after seeing model answers. If an original page
cannot be scored, source validation fails closed.

No fixed target number of audited pages is manufactured: the exact count is the
deterministic outcome of the above source-only rules. It must be between 70 and 420,
include every fresh document and all 12 issuers, and remain bounded by 1,240 original
requests.

## Audit packet after inference

When R001 receipts exist, verify the exact frozen queue, immutable request IDs,
model cohort SHA, prompt hashes and all supplied page text hashes.

For each preselected request attach:

- frozen page text and text SHA;
- issuer, document ID, segment ID, request ID and selection reasons;
- model's validated economic relevance, families and stage;
- every EXPLICIT claim, value, unit and supporting segment ID;
- unresolved questions, caveats and self-reported contradictions;
- `PENDING_INDEPENDENT_REVIEW` / `MISSING_INFERENCE` status.

A missing model output stays explicitly missing. No empty or guessed extraction
is treated as a reviewed result. The packet builder can ingest R001's original
`run-config.json` and append-only `requests/shard-XX/<request-id>/attempt-NNN.json`
receipt tree directly. Every accepted receipt must reproduce its SHA and the pinned
model configuration; duplicate accepted attempts fail closed.

## Independent audit rule

For **each selected page**, a reviewer independent of the model output must check:

- all explicit material fact values against the original page;
- issuer versus subsidiaries, targets, investors and security issuers;
- transaction stage (proposal, approval, allotment, closing);
- overlooked material share changes, dilution, conditions and contradictions;
- whether UNKNOWN masked readily available material terms.

Any unsupported claim or omitted material risk must be logged individually with
a document/page reference. Sample errors prompt a separately versioned remediation
and full rerun; they may not be silently corrected in the extracted response.

The sampling audit is a **model-interpretation quality gate only**. Even a perfect
sample does not establish issuer share continuity, a denominator for market cap,
or full-page semantic accuracy. Any statement supporting an issuer's issued-share
capital must undergo *exhaustive* source-level reconciliation under a separately
frozen share-capital adjudication protocol.

## Safety and provenance

- never add, drop or change original source requests;
- never mix native GPT-5.6 Sol P1 outputs with a new API cohort without explicit
  separate model/runtime labels;
- never accept a model-authored review verdict;
- preserve failures and the original raw responses;
- no portfolio eligibility, expected return or trading permission.

## Promotion

A002 selection may be published with **zero inference calls**.
A002 review packets require genuine validated R001 receipts.
Neither permits capital/return predictions without independent semantic audit and
dated entity-specific share reconciliation.
