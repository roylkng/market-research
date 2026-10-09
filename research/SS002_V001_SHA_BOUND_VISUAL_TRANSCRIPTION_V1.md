# SS002-V001 SHA-Bound Visual Transcription Fallback v1

Status: **FROZEN BEFORE ANY V001 MODEL INFERENCE** (2026-10-10 IST).
Independent semantic review: **NOT COMPLETED**.
Price prediction, portfolio and live-capital authorization: **DISABLED**.

## Purpose

Recover legible, source-located wording from official NSE PDF pages whose deterministic
text extraction is unusable or absent. SS002-V001 is a **vision-model transport and
transcription contract**, not a replacement for human/independent document review.

## Immutable sources

- SS002-P009-v1 packet SHA:
  `750cbe9d5a3b7be7664bb4db32f2a5da899f0760ad054fda3457d805ebd6bdbc`;
- P009 visual manifest SHA:
  `6d7644392ccf3d5ced1dde4e6b696b802ece8f7e86932d2724d00fc075baeb44`;
- P009 run `38003348976`, artifact `11649578864`.

The original 17 pages across four symbols, their exact document IDs, official URLs,
page counts, SHA-verified JPEG renderings and reviewer claims are immutable.

## Frozen V001 input selection

Exactly pages 2, 3, 4, 5, 6, 7 of the VRLLOG original buyback announcement are selected,
because their P009 legibility state is:

- CORRUPTED_TEXT_VISUAL_REVIEW, or
- UNEXTRACTED_VISUAL_REVIEW.

All 11 readable extracted pages stay in the existing SS002-L001 text lane.
No other company/page may be inserted into this pilot after source inspection.

## Image provenance

Each request contains:

- deterministic request ID;
- P009 source pack and rendering-manifest SHA;
- exact symbol, NSE URL and original PDF document SHA;
- 1-based page number;
- JPEG SHA-256 and relative image path;
- original text-legibility state;
- frozen model-facing prompt contract ID.

The inference adapter must **rehash JPEG bytes** before sending them to a model.
No URL fetched by the model may replace a source image.

## Permitted V001 output

Each request returns:

- the same request/document/page/image identity;
- page classification: TEXT_VISIBLE, NO_MATERIAL_TEXT or UNREADABLE_IMAGE;
- transcription records, each with:
  - original-language text reproduced as seen;
  - language code;
  - optional faithful English translation;
  - integer bounding box in normalized 0–1000 page coordinates;
  - uncertainty flag: CLEAR, PARTIALLY_UNCERTAIN or UNREADABLE;
- named transcription problems and reviewer questions;
- complete model/runtime/prompt/input/output provenance.

This is a transcription *hypothesis*. It is never a verified source quote until
checked against the original rendered page by a separate reviewer.

Do not synthesize share counts, tender eligibility, payout terms, rights calls, missing
dates or an investment conclusion. A visually unreadable area must be marked unreadable,
not guessed.

## Strict validation

The deterministic output validator rejects:

- extra/missing request or event identity;
- changed document or page-image SHA;
- invalid page number or bounding box;
- unsupported enum, empty CLEAR transcription or contradictory status;
- missing prompt/model provenance;
- invented portfolio, expected return, intrinsic value, recommendation or
  probability fields;
- NaN/Infinity or malformed JSON.

Neither a syntactically valid response nor a good-looking transcription is independent
semantic approval.

## Completion

V001 queue/prompt materialization may pass when:

- precisely six frozen VRLLOG pages are selected;
- every image reference is SHA-bound to the P009 rendering manifest;
- original PDF SHA and page identity are conserved;
- no research or capital gate is elevated.

Actual vision model inference is a **separate execution** requiring an available
vision-capable model. No model is assumed to be connected here.

## Future promotion

Validated visual transcriptions may be presented alongside original page images to an
independent reviewer, then—with separately recorded approval—can support
transaction-term reconstruction.

V001 does not alter P008, P009, the original L001 extraction or the SS002-P007
conditional tender/rights mathematics.
