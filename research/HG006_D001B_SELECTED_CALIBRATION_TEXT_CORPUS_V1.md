# HG006-D001B Selected Calibration Text Corpus v1

Status: **FROZEN BEFORE SELECTED HISTORICAL DOCUMENT TEXT EXTRACTION**  
Frozen: 2026-10-06  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Create deterministic, evidence-addressable text segments for the exact 300 historical
chronologies frozen by HG006-S001.

D001B is the final provenance/text layer before HG006-L001 historical stage/anchor
extraction. It does not label completion or failure.

## Frozen inputs

### Calibration cohort

Use exactly:

- HG006-S001-v1;
- workflow run: `37412353114`;
- artifact ID: `11389870466`;
- selection SHA-256:
  `4bc9659c1111f0694bbbec8754b6193116871367b78f126c39e09bc329c961f5`;
- 300 chronologies:
  - 150 PREFERENTIAL_WARRANT;
  - 150 SCHEME_REORGANISATION.

### Historical document corpus

Use exactly:

- HG006-D001A-P1-v1;
- workflow run: `37354593321`;
- artifact ID: `11364128773`;
- corpus SHA-256:
  `3d47f24a5cbd4f551eae577ad0ed32fde7f5f15567ce775f60c0bb51ee9989dd`.

Only D001A documents linked to at least one frozen S001 chronology are eligible.

## Document selection

For every READY D001A document:

1. intersect its chronology_ids with the exact 300 S001 chronology IDs;
2. retain the document only when the intersection is non-empty;
3. group duplicate source URLs/content by exact D001A document_id;
4. retain all official source URLs bound to that document_id;
5. retain linked canonical event IDs, symbols, families and selected chronology IDs.

No document may be selected from symbol/date similarity alone.

## Refetch and hash binding

D001B does not trust a newly downloaded file merely because the URL matches.

For every selected document_id:

1. sort its approved NSE URLs lexicographically;
2. refetch URLs in order;
3. accept bytes only when SHA-256 exactly equals the frozen D001A document_id;
4. retain every attempted URL/status/hash;
5. if no URL reproduces the frozen hash, state HASH_REPRODUCTION_FAILED.

No alternate provider, web search, filename guessing or URL rewriting is permitted.

## Text extraction

Use the already-frozen SS002-D003 deterministic extraction semantics:

- Unicode NFKC normalization;
- original PDF page order;
- one text segment per non-empty PDF page;
- no OCR;
- deterministic text SHA-256;
- deterministic segment IDs;
- defensive ZIP handling if encountered.

All D001A-P1 successful documents were classified as PDF, but D001B still fails closed
on unsupported families rather than assuming PDF.

## Sharding

Selected document shard:

`int(document_id[0:8], 16) mod 8`

Shard IDs 0 through 7.

Sharding depends only on frozen document identity.

## Output

Every selected document retains:

- document_id;
- exact selected chronology IDs;
- exact linked event IDs;
- symbols/families;
- attempted official URLs;
- hash reproduction state;
- deterministic text extraction state;
- segment_manifest_sha256;
- exact ordered segment IDs and text SHA-256s.

The full text remains in workflow evidence artifacts; the combined corpus retains compact
document/segment metadata and exact shard identity.

## Frozen feasibility gates

D001B passes only if all are true:

1. all 300 S001 chronologies are accounted for exactly once in chronology coverage;
2. every selected document request is accounted for exactly once across eight shards;
3. at least 95% of selected documents reproduce the frozen D001A SHA;
4. at least 90% of hash-reproduced documents produce at least one deterministic text
   segment;
5. at least 95% of the 300 selected chronologies have at least one TEXT_READY document;
6. every emitted segment ID is globally unique;
7. every emitted text SHA-256 matches its normalized text;
8. no historical terminal label, completion probability, stock return or current hidden-
   gem conclusion influences extraction.

Thresholds may not be lowered after D001B output is opened.

## Promotion

Passing D001B permits:

- HG006-L001 evidence-bound historical stage/anchor extraction;
- HG006-D003 episode threading on the exact selected cohort.

## Scientific boundary

D001B does not:

- infer transaction stage;
- assign terminal state;
- group transaction episodes;
- estimate historical completion rates;
- use market returns;
- calculate current-company probabilities;
- create portfolio or live-capital eligibility.
