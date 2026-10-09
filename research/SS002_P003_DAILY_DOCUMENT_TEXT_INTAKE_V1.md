# SS002-P003 Daily Official Filing Intake and Text Segments v1

Status: **FROZEN BEFORE ANY P003 DOCUMENT BYTE ACQUISITION**
Frozen: 2026-10-10 (Asia/Kolkata)
LLM inference, return outcomes, capitalization, share clearance, portfolio and live
capital: disabled.

## Objective

Extend the existing append-only SS002 daily research inbox to a small, exact,
source-hashed document corpus that can be passed to the already-frozen SS002-L001
economic relevance and transaction-term extraction contract.

P003 is source intake/text extraction only, **not** LLM inference, transaction
underwriting, or a stock-picking algorithm.

## Exact frozen upstream

- SS002-P002-v1, GitHub workflow run `37980956560`;
- artifact `ss002-p002-37980956560`, ID `11640553584`;
- inbox SHA-256 `1c2b89cb89ee7c83fb5720b95152eab704d3575547ce924366f4df7f5888c84f`;
- exact four source days, 2026-10-05 to 2026-10-08;
- 54 canonical announcement event IDs;
- 36 exact capture-time current EQ matches with `DOCUMENT_INTAKE_READY`;
- 18 unmatched/archival events retained as source-only review cases;
- 30 distinct capture-time EQ symbols with ready documents.

No event is added or deleted because of an attractive title, category, liquidity
or research prior.

## URL and identity rules

For the 36 `DOCUMENT_INTAKE_READY` events, require:

- `mapping_state=SYMBOL_IN_EQ_MASTER_AT_CAPTURE`;
- `isin_at_capture` not blank;
- exact approved HTTPS host: `nsearchives.nseindia.com` or
  `archives.nseindia.com`;
- approved URL from the frozen P002 field, not a search result;
- canonical P001 announcement identity;
- the original event timestamp and historical HG001 caution context retained.

All 54 events must appear in the final event-to-document index, including explicit
`ARCHIVAL_OR_UNMATCHED` source states. P003 does not infer historical share
identity from capture-time master membership.

Deduplicate approved URLs before acquisition. Fetch each URL **once**. Do not
rewrite a URL, substitute another provider or retrieve a later version using a
different filename.

## Byte and text identity

For each fetched document:

- `document_id = SHA256(original_raw_bytes)`;
- retain exact original raw bytes, download time, source URL and byte count;
- allow at most 60 MiB per attachment in P003;
- detect document family **from bytes first** using the existing SS002-D002
  family detector;
- use the existing deterministic SS002-D003 text extractor and segment sealer;
- retain all page extraction states and text segment IDs, page numbers, text hashes,
  and `segment_manifest_sha256`;
- no OCR, no model-generated substitute text.

One or more URLs with identical bytes may share `document_id` while their URL and
event associations remain explicit.

A document with no extractable text is not discarded. It is `NO_EXTRACTABLE_TEXT`
and requires a separately versioned visual-review/OCR path.

## Mandatory provenance separation

The announcement publication timestamp is exchange-sourced from the earlier P001
capture. Attachment bytes are acquired **later** under P003. Do not claim the
attachment bytes were snapshotted at the announcement publication time.

The P002 prior HG001 context is **historical research context**, not updated issuer
fundamentals or contemporaneous validation.

## Frozen operational thresholds

P003 passes source-text feasibility only if all hold:

1. exactly all 54 P002 events accounted once;
2. exactly all 36 approved current-document events accounted once;
3. at least 95% unique official URLs fetch successfully;
4. at least 80% of fetched documents have at least one deterministic nonempty segment;
5. every fetched document and segment SHA can be independently reproduced;
6. no non-approved URL is fetched;
7. any unready text, archive identity, failure or missing field remains explicit;
8. no LLM, future return, intrinsic value, market cap or portfolio outcome enters.

These are infrastructure thresholds; they are not alpha significance tests.

## Output

- `ss002-p003-corpus.json`: compact document/event manifest with no raw text
  duplication; exact IDs, SHA, family, readiness states and source references.
- `documents/<document_id>.json`: page-addressable extracted text and hashes.
- `raw/sha256/<document_id>.bin`: original exact source bytes.
- `summary.json`: independent counts and gates.

All output stays in a run artifact until separately sealed. Do not place bulky
raw NSE filings into Git.

## Promotion

Passing P003 permits SS002-L001 structured LLM fact extraction on the text-ready
population with the existing validation contract. A model's valid JSON alone does
not prove semantic correctness. Independent source-page review and issuer-specific
share-action reconciliation remain mandatory before economic valuation or trading.

P003 may not create buy/sell decisions, probability-weighted IRRs, ADO, PF001, or
live-capital authority.
