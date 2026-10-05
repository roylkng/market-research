# HG006-D001A Historical Official Document Corpus v1

Status: **FROZEN BEFORE HISTORICAL DOCUMENT BODY ACCESS**  
Frozen: 2026-10-05  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Acquire and bind the exact official NSE attachment bytes referenced by the passed
HG006-D001 historical discrete-event source census.

HG006-D001A is a provenance/source layer only. It does not assign stage, episode,
terminal outcome, completion probability or expected return.

## Frozen upstream source

Use exactly:

- HG006-D001-v1;
- workflow run: `37347148756`;
- artifact ID: `11361421023`;
- artifact name: `hg006-d001-p4-37347148756`;
- census SHA-256:
  `a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5`.

The source census contains:

- 9,733 retained historical discrete-family announcement rows;
- 1,607 symbol-family source chronologies;
- 1,582 chronologies with at least one approved attachment URL;
- source window 2023-01-01 through 2026-09-30.

## Included source population

Every retained HG006-D001 event is accounted for.

For each event:

- if `approved_attachment_url` is present, it enters document acquisition;
- otherwise it remains an explicit NO_APPROVED_ATTACHMENT event state.

Only exact HTTPS URLs on:

- `nsearchives.nseindia.com`;
- `archives.nseindia.com`

are accepted.

No URL rewriting, web search, fuzzy filename recovery or alternate provider is allowed.

## URL deduplication

The same official document may support multiple announcements, symbols/families or
chronologies.

Acquisition unit:

`unique approved official URL`.

Each URL is fetched once.

The many-to-many event/chronology/family mapping is retained.

## Content identity

For every successfully fetched byte object:

`document_id = SHA256(raw_bytes)`

Different approved URLs returning identical bytes map to the same document_id while all
source URLs remain retained.

## Frozen document-family detection

Use the same byte-first family detection as SS002-D002:

- PDF;
- ZIP_CONTAINER;
- XML_OR_XHTML;
- HTML;
- PLAIN_TEXT;
- OTHER_BINARY.

Document family does not determine transaction outcome.

## Sharded acquisition

Historical acquisition may be parallelized.

The frozen shard assignment is:

`shard = int(SHA256(source_url)[0:8], 16) mod 8`

with shard IDs 0 through 7.

Sharding changes only transport topology. The combined corpus must be invariant to shard
execution order.

## Chronology coverage

For each of the 1,607 D001 source chronologies retain:

- chronology_id;
- symbol;
- family;
- event count;
- count of events with approved URLs;
- count of events resolved to successful documents;
- unique document IDs;
- source state.

Chronology source states:

- READY_DOCUMENT_EVIDENCE;
- NO_APPROVED_ATTACHMENT;
- DOCUMENT_FETCH_PARTIAL;
- DOCUMENT_FETCH_FAILED.

No source state is a success/failure transaction label.

## Frozen feasibility gates

HG006-D001A passes only if all are true:

1. every 9,733 retained event is accounted for exactly once;
2. every approved URL maps to exactly one acquisition result;
3. at least 95% of unique approved URLs fetch successfully;
4. at least 95% of attachment-ready events resolve to successful document bytes;
5. at least 95% of the 1,582 attachment-ready chronologies have at least one successful
   document;
6. every successful document has deterministic SHA-256 identity;
7. every fetched URL is on an approved NSE archive host;
8. no terminal labels, completion probabilities, returns or portfolio outcomes are
   opened.

Thresholds may not be lowered after output is opened.

## Promotion

Passing HG006-D001A permits:

- HG006-D001B deterministic historical document text extraction;
- HG006-L001 evidence-bound historical stage/anchor extraction;
- HG006-D003 transaction episode threading.

## Scientific boundary

HG006-D001A does not:

- infer transaction completion from later company status;
- treat missing later announcements as failure;
- use current stock prices or historical returns;
- group events into transaction episodes;
- assign current-company probability;
- create expected return;
- authorize ADO/PF001/live capital.
