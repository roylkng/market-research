# HG006-D001B-P2 Full-Priority Historical Text Corpus v1

Status: **FROZEN AFTER P001 SUPPORT FAILURE, BEFORE EXPANDED DOCUMENT TEXT ACCESS**  
Frozen: 2026-10-07  
Historical terminal labels from the original 300-case calibration run are known.  
Expanded-population terminal labels: unopened.  
Expanded-population completion probabilities: unassigned.  
Return outcomes opened: no.  
Portfolio eligibility: disabled.  
Live capital: disabled.

## Why P2 exists

HG006-P001-v1 applied the frozen 300-chronology historical calibration evidence to the
current payoff-ready transaction lanes.

The result correctly refused to publish any survivor-conditioned current probability
surface:

- 4 lanes had insufficient survivor-conditioned future terminal support;
- 1 lane had no publishable exact-stage historical surface;
- 1 issuance lane was already deterministically completed.

The frozen P001 support thresholds remain unchanged.

The original HG006 source corpus already contains a much larger outcome-blind priority
population:

- PREFERENTIAL_WARRANT: 460 chronologies;
- SCHEME_REORGANISATION: 583 chronologies;
- combined: 1,043 chronologies.

P2 expands evidence processing mechanically to this complete priority-family population.
It does not choose additional cases based on historical success, failure, duration,
current-company similarity, or stock returns.

## Frozen source

Use exactly HG006-D001A-P1-v1:

- workflow run: `37354593321`;
- artifact ID: `11364128773`;
- corpus SHA-256:
  `3d47f24a5cbd4f551eae577ad0ed32fde7f5f15567ce775f60c0bb51ee9989dd`.

Frozen source population:

- selected chronology count: 1,043;
- selected event count: 5,818;
- attachment-ready chronologies: 1,038;
- chronologies with successful document evidence: 1,038;
- unique document IDs: 5,353;
- successful source URLs: 5,730;
- no-approved-attachment chronologies: 5.

All 1,043 chronologies remain in P2 accounting.

## Population rule

P2 includes every D001A-P1 chronology.

There is no sampling order.

The 300 chronologies previously used by HG006-S001 remain part of the population; P2 does
not treat their prior labels as selection criteria.

The remaining 743 chronologies are included solely because they already belong to the
same two frozen current-relevant transaction families.

## Document request construction

For every D001A-P1 READY source document:

1. group rows by exact `document_id`;
2. require `document_id = SHA256(raw_source_bytes)` from D001A provenance;
3. retain all official source URLs linked to the same document ID;
4. union exact chronology IDs, event IDs, symbols and families from those source rows;
5. create exactly one text-extraction request per unique document ID.

Expected unique requests: exactly **5,353**.

No document may be introduced by symbol/date similarity, web search or alternate source.

## Refetch and hash reproduction

For each request:

1. sort official NSE source URLs lexicographically;
2. fetch URLs in order;
3. accept the first byte payload whose SHA-256 exactly equals the frozen document ID;
4. retain all attempts;
5. if no source URL reproduces the hash, emit `HASH_REPRODUCTION_FAILED`.

Approved source hosts remain exactly:

- `nsearchives.nseindia.com`;
- `archives.nseindia.com`.

## Text extraction

Use exactly the deterministic SS002-D003 extraction semantics already used by
HG006-D001B-v1:

- no OCR;
- PDF original page order;
- Unicode NFKC normalization;
- one segment per non-empty PDF page;
- deterministic segment ID;
- deterministic text SHA-256;
- unsupported document families fail closed.

P2 may not change text normalization because the expansion is intended to be comparable
to the original 300-case calibration evidence.

## Frozen sharding

Shard by exact document identity:

`int(document_id[0:8], 16) mod 16`

Shard IDs: 0 through 15.

Sharding contains no transaction or outcome information.

## Chronology states

Every one of the 1,043 source chronologies must resolve to exactly one state:

- `TEXT_READY`: at least one linked document produced deterministic text;
- `DOCUMENT_PRESENT_TEXT_FAILED`: linked official documents exist but none produced text;
- `NO_APPROVED_ATTACHMENT`: source chronology has no approved official attachment.

The five already-known D001A no-approved-attachment chronologies remain in the final
population and are never treated as failed transactions.

## Frozen feasibility gates

P2 passes only if all are true:

1. all 1,043 source chronologies are accounted for exactly once;
2. all 5,353 unique document requests are accounted for exactly once across 16 shards;
3. at least 95% of document IDs reproduce their frozen SHA-256;
4. at least 90% of hash-reproduced documents produce deterministic text;
5. at least 95% of the 1,038 attachment-ready chronologies have at least one TEXT_READY
   document;
6. all segment IDs are globally unique;
7. all segment text hashes verify;
8. no stock return, current-company outcome, historical terminal label, or previously
   estimated base rate affects inclusion or extraction.

The P001 probability publication gates remain unchanged:

- survivor-conditioned support >= 30;
- future completed + failed terminal outcomes >= 10.

## Promotion

Passing HG006-D001B-P2 permits:

- full-priority historical L001 inference using the unchanged
  HG006-L001-v1 evidence contract;
- deterministic episode threading using the unchanged D003-P2 rules;
- terminal labeling using the unchanged D002-P1 ontology;
- expanded historical D004 competing-risk estimation;
- rerunning P001 against the expanded historical evidence.

## Scientific boundary

P2 does not:

- loosen P001 support thresholds;
- introduce a parametric survival model;
- change stage ordering;
- change warrant issuance vs full-exercise semantics;
- add stock-return outcomes;
- create current expected return;
- create buy/sell/hold;
- create portfolio eligibility;
- authorize live capital.
