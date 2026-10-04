# SS002-D002 Official Special-Situation Attachment Corpus v1

Status: **FROZEN BEFORE ATTACHMENT BODY ACCESS**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Acquire and bind the exact official NSE attachment bytes behind the current-investable
special-situation events that passed SS002-D001-P2.

D002 is the provenance layer immediately before document text extraction and LLM term
understanding. The LLM is not allowed to see an event document unless D002 can bind it
to an exact NSE event identity, official URL and SHA-256.

## Frozen source input

Use exactly:

- SS002-D001-P2-v1;
- workflow run: `37203696204`;
- artifact ID: `11303667832`;
- artifact name: `ss002-d001-p2-37203696204`;
- census SHA-256:
  `ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071`.

P2 contains:

- 1,666 CURRENT_INVESTABLE_IDENTITY events;
- 1,659 events with an approved official NSE attachment URL;
- 540 current symbols.

Only CURRENT_INVESTABLE_IDENTITY events enter D002 current-document acquisition.

Archival/non-current events remain preserved but are not downloaded in D002-v1.

## Attachment identity

For each current event:

1. use the canonical `announcement_id`;
2. read the exact NSE-supplied `attchmntFile`;
3. normalize only surrounding whitespace;
4. require HTTPS host to be exactly one of:
   - `nsearchives.nseindia.com`;
   - `archives.nseindia.com`.

No URL rewriting, search-engine lookup, fuzzy filename recovery or alternate provider is
permitted.

## URL deduplication

Multiple canonical events may point to the same official attachment URL.

D002 fetches each unique approved URL once and retains the event-to-document many-to-one
mapping.

Document identity:

`document_id = SHA256(raw_attachment_bytes)`

A URL that returns bytes already observed under another approved URL maps to the same
document_id while retaining both source URLs.

## Exact evidence retained

For each unique approved URL retain:

- source URL;
- fetch status;
- raw byte count;
- SHA-256;
- detected document family;
- filename suffix;
- leading-byte signature;
- all canonical event IDs linked to the URL;
- linked symbols and special-situation categories.

Exact raw bytes are retained content-addressed under SHA-256.

## Frozen document-family detection

Detection is based on bytes first, suffix second.

Families:

- `PDF`: bytes start with `%PDF-`;
- `ZIP_CONTAINER`: bytes start with PK ZIP signature;
- `XML_OR_XHTML`: leading decoded text is XML/XHTML;
- `HTML`: leading decoded text contains HTML markup;
- `PLAIN_TEXT`: UTF-8/ASCII-decodable non-markup text;
- `OTHER_BINARY`: everything else.

D002 does not parse ZIP contents or PDF text.

## Fetch failures

A failed URL fetch is retained as an explicit failure row with error class/message.

No failed attachment is replaced by another source.

## Frozen feasibility gates

D002 passes only when all are true:

1. every one of the 1,666 current-investable P2 events is accounted for exactly once as
   approved attachment URL or explicit no-attachment state;
2. at least 95% of unique approved attachment URLs fetch successfully;
3. at least 95% of the 1,659 attachment-ready current events resolve to successfully
   fetched bytes;
4. every successfully fetched byte object has deterministic SHA-256/document identity;
5. no fetched document comes from a non-approved host;
6. no return, valuation, quality or portfolio outcome enters source selection.

Thresholds may not be lowered after D002 output is opened.

## Promotion

Passing D002 permits:

- SS002-D003 deterministic document text extraction;
- event-thread construction from exact canonical events + exact documents;
- SS002-L001 structured LLM term extraction under a frozen JSON contract.

## LLM boundary

D002 itself uses no LLM.

The later LLM stage must:

- receive exact D002 document IDs and extracted text;
- cite source page/segment evidence for every material term;
- return `UNKNOWN` rather than invent absent terms;
- never overwrite deterministic event identity/category/source fields.

## Explicit exclusions

D002 does not:

- estimate completion probability;
- calculate arbitrage spreads;
- infer intrinsic value;
- interpret whether an event is attractive;
- use future returns;
- create ADO/PF001 eligibility;
- authorize live capital.
