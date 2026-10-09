# SS001-D007-L001-P2 Full 12-Issuer Chronology Extraction Queue v1

Status: **FROZEN BEFORE ANY P2 MODEL OUTPUT**  
Frozen: 2026-10-09  
Share continuity / market capitalization: prohibited  
Return outcomes opened: no  
Portfolio eligibility / live capital: disabled

## Purpose

Expand the passed SS001-D007-L001-P1 single-document pilot into complete
pre-cutoff official-document coverage for the same exact 12 issuer packets.

The goal is to remove single-document blind spots before any issuer-level
share-count adjudication.

P2 still does **not** decide whether current share count changed.

## Frozen issuers

Exactly the P0/P1 issuer order:

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

No issuer may be substituted after P1 output.

## Immutable inputs

### Q002 official-document binding

- SS001-D007-Q002-v1
- run: `37825546492`
- artifact: `11571052476`
- binding SHA:
  `c3c28d55b98a08c91e99b76d5ae2732f2ca24406fa12752be2f0e75fa0624f36`

Use exactly the first 12 Q002 packets.

Those packets contain exactly:

- 95 announcement references;
- 12 corporate-action evidence rows;
- 82 distinct TEXT_READY D003 document IDs.

### D003 deterministic text corpus

- SS002-D003-v1
- run: `37213853198`
- artifact: `11309315028`
- corpus SHA:
  `92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce`

### Passed P1 native extraction

- SS001-D007-L001-P1-v1
- run: `37883572697`
- artifact: `11595515888`
- run SHA:
  `1a3a2f73eaed8ba09c84ab7c8d60699fa895f39d25d5797bd16138b09fd620cb`
- validated document count: 12.

The exact 12 P1 document IDs are reused. They are not re-inferred.

## Complete-document coverage rule

For each of the 12 issuers:

1. traverse every Q002 announcement reference in its frozen order;
2. retain every distinct `TEXT_READY` D003 document ID exactly once;
3. bind each document to exact Q002 event IDs and D003 source/segment hashes;
4. include every D003 text segment for every retained document;
5. do not select segments using investment relevance, model output, prices or later facts.

Across the 12 issuers, exactly 82 distinct documents are expected.

## P1 response reuse

The 12 exact P1 document IDs are marked `P1_REUSE`.

Reuse requires exact equality of:

- document ID;
- issuer symbol;
- Q002-linked event IDs;
- D003 segment-manifest SHA;
- P1 prompt SHA;
- P1 model-config SHA;
- P1 validated output provenance.

A mismatch fails closed.

P1 reuse is inference deduplication only.

## Fresh P2 transport rule

The remaining 70 distinct documents are covered by **every D003 segment**.

Each fresh request contains exactly one complete D003 segment/page.

No page or segment is truncated.

No relevance keyword selects pages.

No page is skipped because it appears unimportant.

The frozen source produces exactly:

- 70 fresh documents;
- 1,240 fresh segment requests.

One-page requests preserve the original D003 `segment_id` and text SHA-256.

## Request identity

Fresh request ID is deterministic over:

- queue ID;
- issuer packet rank;
- issuer symbol;
- document ID;
- segment ID;
- D003 segment-manifest SHA;
- model-config SHA.

No random IDs are permitted.

## Model/runtime

Fresh P2 requests reuse the passed P1 configuration exactly:

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- temperature target: 0.0;
- top_p target: 1.0;
- maximum structured-output budget: 4096;
- contract: `SS002-L001-v1`;
- model-config SHA:
  `133b5705036d1782f671d6a171fe5f24298939cf6d84314875c2e8452e7169dc`.

No web, memory, current price, later document or portfolio context may enter a request.

## Deterministic sharding

Sort fresh requests by:

1. issuer packet rank;
2. Q002 first occurrence order of document;
3. D003 segment order;
4. request ID.

Assign sequentially to 16 frozen shards using:

`shard_id = (global_request_index - 1) mod 16`.

This is transport only and carries no investment meaning.

## Corporate-action evidence

All 12 Q002 corporate-action evidence rows are retained as deterministic chronology
hints with source SHA, ex-date, subject, symbol and source ISIN.

They are **not** converted into L001 model requests in P2 because they are already
structured exchange evidence and may lack a D003 document.

They do not prove issued-share changes by themselves.

## Frozen P2 queue gates

Queue materialization passes only when:

1. exact first 12 Q002 issuer packets reproduce;
2. exact 95 announcement references are accounted for;
3. exact 12 corporate-action rows are retained;
4. exact 82 distinct TEXT_READY document IDs reproduce;
5. exact 12 P1 document IDs bind and are marked reuse;
6. exact 70 remaining documents are fresh;
7. every segment of every fresh document appears exactly once;
8. exact 1,240 fresh requests materialize;
9. every segment text SHA verifies against D003;
10. all 16 shard IDs are present;
11. no model inference, share clearance, market cap or return outcome is produced.

## Promotion after model execution

Only after all fresh requests are executed, validated and aggregated may the project
freeze a D007 issuer-chronology adjudication contract.

That later adjudication may determine whether an event is:

- direct issuer-equity change;
- proposed/not completed;
- procedural only;
- subsidiary/investee action;
- debt/non-equity action;
- share-class/ISIN continuity issue;
- explicit completed issuer-equity change.

Even then, capitalization requires affirmative point-in-time issued-share evidence.

## Explicit exclusions

P2 queue construction does not:

- infer unchanged share count from silence;
- calculate market capitalization;
- use stock prices or returns;
- rank hidden gems;
- estimate expected returns;
- authorize ADO/PF001/live capital.
