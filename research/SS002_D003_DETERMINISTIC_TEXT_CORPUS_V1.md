# SS002-D003 Deterministic Special-Situation Text Corpus v1

Status: **FROZEN BEFORE DOCUMENT TEXT EXTRACTION**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled  
LLM inference executed: no

## Objective

Convert the exact official documents that passed SS002-D002 into deterministic,
evidence-addressable text segments suitable for the frozen SS002-L001 LLM contract.

D003 is a text/provenance layer. It does not interpret transaction economics.

## Frozen upstream authority

Use exactly:

- SS002-D002-v1;
- source run: `37206243434`;
- artifact ID: `11305626247`;
- corpus SHA-256:
  `eab922954ef20a12a7635107722b4e800b59cfa56ff0659da42afb3fc22218f9`;
- 1,539 unique document IDs;
- 1,658 approved official NSE source URLs;
- zero D002 fetch failures.

A compact copy of the D002 corpus JSON is retained as:

`research/ss002/ss002-d002-corpus-manifest-v1.json`

The compact manifest is source metadata only; raw attachment bytes remain outside Git.

## Refetch and hash binding

For each unique D002 document_id:

1. collect every approved official source URL mapped to that document_id;
2. sort URLs lexicographically;
3. refetch official URLs in that order until one byte payload SHA-256 exactly equals
   document_id;
4. retain all attempted URL/status/hash evidence;
5. if no URL reproduces document_id, mark the document HASH_REPRODUCTION_FAILED.

No alternate provider, web search, filename guessing or URL rewriting is allowed.

## Text normalization

Every extracted text string is normalized exactly by:

1. Unicode NFKC normalization;
2. convert CRLF and CR line endings to LF;
3. strip trailing horizontal whitespace from each line;
4. remove leading/trailing blank lines;
5. preserve internal line ordering and content.

D003 does not paraphrase or summarize text.

## PDF extraction

For PDF documents:

- parse with the repository's pinned pypdf version;
- preserve original page order;
- create at most one text segment per PDF page;
- omit an empty page from the segment list but retain its page-level extraction state.

Segment ID:

`<document_id>:pdf:page:<1-based-zero-padded-page-number>`

Every segment retains:

- page number;
- normalized text;
- text SHA-256;
- UTF-8 byte count;
- character count.

D003 performs **no OCR**.

A PDF with no extractable text is retained as `NO_EXTRACTABLE_TEXT`.

## ZIP-container extraction

ZIP containers are handled defensively.

Hard limits:

- <=100 members;
- <=50 MiB uncompressed per member;
- <=250 MiB total uncompressed bytes;
- no encrypted members;
- no absolute paths;
- no `..` traversal components.

Supported member families:

- PDF;
- XML/XHTML;
- HTML;
- UTF-8 plain text.

Unsupported members are retained as metadata and do not receive invented text.

Nested ZIP recursion is not performed in v1.

Member segment IDs are prefixed with:

`<document_id>:zip:<member_sha256>:`

PDF members then use page suffixes; textual members use deterministic chunk suffixes.

## Direct XML / HTML / plain-text documents

If present in a future D002-compatible corpus:

- XML/XHTML: parse textual content without executing scripts;
- HTML: BeautifulSoup text extraction, no remote resource loading;
- plain text: UTF-8 decode.

Textual documents are segmented deterministically into <=8,000-character chunks at
line boundaries when possible.

## Segment manifest

For every document, create a deterministic segment manifest containing:

- document_id;
- source URL used;
- D002 document family;
- extraction state;
- page/member metadata;
- ordered segment metadata;
- ordered segment IDs;
- text SHA-256 for each segment.

`segment_manifest_sha256` is SHA-256 of canonical JSON of that manifest before the hash
field itself is added.

This is the exact hash supplied to SS002-L001.

## Frozen feasibility gates

D003 passes only if all are true:

1. all 1,539 D002 unique document IDs are accounted for exactly once;
2. >=95% of documents reproduce their frozen D002 SHA from an official URL;
3. >=90% of all hash-reproduced documents produce at least one non-empty text segment;
4. >=92% of hash-reproduced PDF documents produce at least one text segment;
5. every emitted segment has a deterministic segment_id and valid text SHA-256;
6. no OCR, LLM inference, return outcome, valuation result or portfolio state influences
   extraction.

Thresholds may not be lowered after D003 output is opened.

## Promotion

Passing D003 permits:

- SS002-L001 evidence-bound LLM extraction;
- deterministic event/document threading;
- later family-specific payoff models.

## Explicit exclusions

D003 does not:

- perform OCR;
- infer missing words from images;
- interpret transaction terms;
- estimate probability;
- calculate arbitrage spread or intrinsic value;
- score opportunities;
- authorize ADO/PF001/live capital.
