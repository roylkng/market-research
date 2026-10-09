# SS002-P009 Original-PDF Legibility and Visual-Review Integrity v1

Status: **FROZEN BEFORE P009 MATERIALIZATION** (2026-10-10 IST).
P008 preserved unchanged. Independent semantic review performed: **NO**.
Return prediction, trading, capitalization and portfolio authority: **DISABLED**.

## Why P009 exists

The preserved SS002-P008 review packet passed source-page and citation SHA checks,
but source-only inspection exposed one additional failure class: a PDF extractor may
emit nonempty text composed largely of the Unicode replacement character U+FFFD
(�). Such pages are not reliably readable even though P008 counted them as
"extracted" rather than empty.

The frozen P008 review packet contains 17 original PDF pages across four companies,
15 nonempty text segments, 2 entirely missing text pages, and 35 extracted claims.
VRLLOG PDF pages 2-5 are nonempty but contain corrupted text. Pages 6-7 have no
extracted text. P008 remains immutable; P009 is an explicit additive QA amendment.

## Frozen source

- SS002-P008-v1 packet SHA:
  `94b098d24ef6c5eb3482ce4c79ec696c24a6f761a4bc0f3fe6e0e5ae7f985768`;
- run: `37999289727`;
- artifact ID: `11648109634`;
- exact four companies: INOXGREEN, KOTHARIPET, OLAELEC, VRLLOG.

No company or claim may be removed or added.

## Deterministic legibility triage

For every original PDF page:

1. If the page has no P008 segment, mark `UNEXTRACTED_VISUAL_REVIEW`.
2. Otherwise calculate:
   `replacement_ratio = count(U+FFFD) / max(number of nonwhitespace characters, 1)`.
3. If `replacement_ratio >= 0.20`, mark `CORRUPTED_TEXT_VISUAL_REVIEW`.
4. If not corrupted but the page has fewer than 25 alphanumeric characters, mark
   `SPARSE_TEXT_VISUAL_REVIEW`.
5. All other pages are `TEXT_PRESENT_SEMANTICS_UNVERIFIED`.

These are source-usability diagnostics, not content-quality predictions.
A short page is only flagged for attention; its content is not discarded.
All original pages still require independent semantic inspection whether or not
their text looks readable.

P009 may NOT change any upstream page text, source SHA, claim value or citation.

## Official PDF visual packets

For every selected P008 case:

- fetch the exact already-approved official NSE source URL;
- verify raw `SHA256 == document_id == original_pdf_raw_sha256`;
- verify exact original page count;
- render **every original page**, not just suspect pages, to a viewable page image;
- calculate SHA-256 for each rendered image;
- associate image, page number, legibility status and cited claim IDs.

Any fetch, identity, page count or rendering mismatch fails closed. Do not replace
the original document with search results or an alternate copy.

## Expected observed triage for this frozen source

- four cases;
- seventeen original pages;
- eleven TEXT_PRESENT_SEMANTICS_UNVERIFIED pages;
- four CORRUPTED_TEXT_VISUAL_REVIEW pages (VRLLOG 2-5);
- two UNEXTRACTED_VISUAL_REVIEW pages (VRLLOG 6-7);
- no sparse-text pages for this source;
- thirty-five pending claim-review records.

These counts test deterministic reproduction; they do not constitute semantic approval.

## Reviewer boundary

An independent reviewer must inspect the rendered original pages, including
apparently readable pages, compare all 35 claim statements to official source
semantics, and record omissions and contradictions. This source-only pipeline
does not claim that rendering, readable text or citation validity proves a claim.

A reviewer may not mark independence by replaying the original GPT-6 extraction
through the same model. No stage may infer expected returns or lift the existing
underwriting/capital gates.

## Acceptance

- exact P008 packet SHA;
- page and claim conservation;
- exact corrupted/unextracted flags;
- every page has an original-PDF verified image in the visual artifact;
- all 35 claims remain PENDING_INDEPENDENT_REVIEW;
- `independent_semantic_audit_complete=false`,
  `underwriting_ready=false`, `portfolio_eligibility_allowed=false`,
  `live_capital_allowed=false`.

## Security

Official PDF content is untrusted. Never execute embedded commands or use document
links as alternate sources. PDF rendering is limited to fixed source documents.
