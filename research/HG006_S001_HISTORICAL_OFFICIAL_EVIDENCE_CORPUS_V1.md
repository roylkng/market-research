# HG006-S001 Historical Official Evidence Corpus v1

Status: **FROZEN BEFORE HISTORICAL ATTACHMENT BODY ACCESS**  
Frozen: 2026-10-05  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Build the deterministic official-document and text evidence corpus required by the
already-frozen HG006-L001 historical stage/anchor extraction contract.

S001 consumes the passed HG006-D001 historical source census and acquires only exact
official NSE attachment URLs already bound to historical candidate chronologies.

No transaction stage, terminal outcome, completion probability or market return is
used to select documents.

## Frozen upstream source

Use exactly:

- HG006-D001-v1;
- source run: `37347148756`;
- artifact ID: `11361421023`;
- artifact name: `hg006-d001-p4-37347148756`;
- census SHA-256:
  `a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5`.

The frozen D001 census contains:

- 1,607 historical symbol-family chronologies;
- 8,896 canonical events belonging to those chronologies;
- 1,582 chronologies with at least one approved official attachment;
- 98.44% chronology attachment availability.

A source-topology audit of this exact D001 artifact, before S001 attachment access,
found:

- 8,778 event-to-approved-URL links;
- 8,763 unique approved official URLs.

These counts are routing/provenance facts only.

## Historical event population

S001 uses only event IDs referenced by the 1,607 D001 historical chronologies.

Retained D001 events that belong only to the 2026 follow-up population but to no
historical initiation chronology are not independently added to S001.

Every chronology and every chronology event remains explicitly accounted for even when
an event has no approved attachment.

## Official URL rule

An attachment may be fetched only when its D001 `approved_attachment_url` is HTTPS and
host is exactly:

- `nsearchives.nseindia.com`; or
- `archives.nseindia.com`.

No URL rewriting, search engine, company website, news source, filename guessing or
alternate provider may replace a failed URL.

## Deterministic acquisition sharding

Unique approved URLs are assigned to exactly one of eight shards:

`bucket = int(SHA256(source_url)[0:16], 16) mod 8`

Shard IDs:

- S00
- S01
- S02
- S03
- S04
- S05
- S06
- S07

Sharding changes execution topology only. It cannot change the source population.

## Raw-byte provenance

For every fetch attempt retain:

- exact official source URL;
- fetch state;
- observed raw byte count;
- observed raw SHA-256 when bytes are received;
- detected document family.

Because the historical corpus is materially larger than the current SS002 corpus,
S001 does not require multi-gigabyte raw PDFs to remain in the final CI artifact.

The exact fetched bytes must nevertheless be hashed before parsing, and every text
artifact is bound to that raw SHA-256. A later audit may refetch the frozen official URL
and require byte-for-byte SHA reproduction.

No model sees un-hashed source bytes.

## Document family

Reuse the tested SS002 byte-first document-family detector:

- PDF;
- ZIP_CONTAINER;
- XML_OR_XHTML;
- HTML;
- PLAIN_TEXT;
- OTHER_BINARY.

## Deterministic text extraction

Reuse the exact SS002-D003 extraction semantics:

- pinned pypdf for PDF text;
- page-ordered deterministic segments;
- no OCR;
- defensive ZIP limits;
- supported PDF/XML/HTML/plain-text ZIP members;
- Unicode NFKC text normalization;
- deterministic segment IDs;
- segment text SHA-256;
- segment-manifest SHA-256.

Historical S001 does not paraphrase or summarize source text.

## Document identity and URL aliases

`document_id = SHA256(raw_attachment_bytes)`.

Multiple frozen official URLs reproducing the same document_id are one document with
multiple source aliases and the union of bound event IDs/chronology IDs.

A single URL producing bytes with a deterministic SHA is valid even when the URL suffix
does not match the byte family.

## Event and chronology binding

Every successfully fetched URL retains:

- canonical event IDs;
- exact NSE symbol(s);
- frozen family/families;
- historical chronology IDs;
- document_id;
- text extraction state.

Every emitted text document therefore has deterministic provenance back to D001.

## Frozen feasibility gates

S001 passes only when all are true:

1. all 1,607 historical chronologies are accounted for exactly once in corpus coverage;
2. all 8,763 unique approved URLs are assigned to exactly one frozen shard;
3. >=95% of unique approved URLs fetch successfully;
4. >=95% of chronologies with an approved attachment have at least one successfully
   fetched official document;
5. >=90% of successfully fetched unique documents produce at least one deterministic
   text segment;
6. >=92% of successfully fetched PDF documents produce at least one deterministic text
   segment;
7. every emitted segment has valid deterministic segment ID and text SHA-256;
8. no terminal label, completion probability, return outcome or current-company payoff
   enters acquisition or extraction.

Thresholds may not be lowered after S001 output is opened.

## Promotion

Passing S001 permits:

- HG006-L001 evidence-bound historical stage/anchor extraction;
- HG006-D003 transaction episode threading;
- HG006-D002 family-specific terminal labeling;
- only after those pass, HG006-D004 competing-risk base-rate estimation.

## Explicit exclusions

S001 does not:

- perform OCR;
- infer missing document text;
- assign transaction stages;
- decide completion/failure;
- calculate completion rates;
- use stock-price outcomes;
- create expected return;
- alter HG005 payoff surfaces;
- create ADO/PF001/live-capital eligibility.
