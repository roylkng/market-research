# HG006-D001B Deterministic Historical Document Text Extraction v1

Status: **FROZEN BEFORE D001A CORPUS OUTPUT IS OPENED**  
Frozen: 2026-10-05  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Convert the exact successful document bytes from HG006-D001A-P1 into deterministic,
evidence-addressable text segments for historical stage/anchor extraction.

D001B is transport/text infrastructure only. It does not use an LLM and does not assign
transaction stage, episode, outcome, probability or return.

## Upstream boundary

D001B may consume only a passed:

`HG006-D001A-P1-v1`

combined corpus and the exact raw-shard artifacts produced by the same workflow run.

The exact successful D001A workflow run ID and corpus SHA-256 are bound in the execution
result before any HG006-L001 model output is accepted.

No later re-fetch or alternate provider may silently replace a D001A document.

## Document ownership across shards

A content-addressed document may appear under more than one approved URL and therefore in
more than one raw acquisition shard.

For deterministic extraction, each unique document_id is assigned:

`owner_shard = min(source shard IDs whose READY row has that document_id)`

Exactly one shard extracts each document.

## Hash reproduction

Before text extraction:

1. locate the content-addressed raw object in the owner shard;
2. calculate SHA-256;
3. require exact equality with document_id.

Failure is:

`HASH_REPRODUCTION_FAILED`

and no text is emitted.

## Text extraction

Reuse the frozen deterministic SS002-D003 extraction semantics:

- PDF: page-by-page text extraction;
- ZIP_CONTAINER: bounded safe member traversal;
- XML/XHTML: deterministic itertext extraction;
- HTML: deterministic visible-text extraction;
- PLAIN_TEXT: UTF-8 text;
- unsupported/image-only content: explicit non-ready state.

No OCR is used in D001B-v1.

## Segment identity

Every non-empty text segment retains:

- deterministic segment_id;
- kind;
- locator (page/chunk/member);
- normalized text;
- text SHA-256;
- byte/character counts.

Segment IDs must be globally unique across the D001B corpus.

## Frozen readiness states

Per document:

- READY;
- NO_EXTRACTABLE_TEXT;
- PARSE_FAILED;
- UNSUPPORTED_FAMILY;
- HASH_REPRODUCTION_FAILED.

Only READY documents may enter HG006-L001.

## Frozen feasibility gates

D001B passes when all are true:

1. every unique successful D001A document is accounted for exactly once;
2. at least 99% reproduce their frozen document SHA from the raw owner-shard artifact;
3. at least 80% of hash-reproduced documents are READY with non-empty text;
4. at least 80% of hash-reproduced PDF documents are READY;
5. every emitted segment has deterministic globally unique ID and matching text SHA;
6. no historical terminal label, completion probability, return or current-company
   outcome is used.

If text-ready coverage is below threshold, the next allowed action is a separately frozen
OCR/source-recovery extension. Thresholds may not be lowered.

## Promotion

Passing D001B permits HG006-L001 evidence-bound historical stage/anchor extraction on
READY documents only.

D001B does not decide whether missing documents imply transaction failure.

## Scientific boundary

D001B does not:

- infer missing text;
- OCR images;
- group transaction episodes;
- label completion/failure;
- estimate probabilities;
- use stock prices/returns;
- authorize portfolio or live capital.
