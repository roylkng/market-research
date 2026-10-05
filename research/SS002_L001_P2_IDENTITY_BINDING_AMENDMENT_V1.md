# SS002-L001 P2 Event/Symbol Identity Binding Amendment v1

Status: **FROZEN BEFORE HG001-C001 LLM INFERENCE**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P2 exists

The first frozen SS002-L001-P1 GPT-5.6 Sol pilot validly tested:

- evidence-segment citation discipline;
- structured fact extraction;
- transaction-family/economic-relevance interpretation;
- forbidden return/valuation/advice fields;
- manual material-fact support.

However, source-only audit before the HG001-C001 run found an identity-binding gap in the
pilot selector:

- SS002-D003's corpus manifest carries each document's linked event IDs, symbols and
  categories;
- the individual `documents/*.json` text records do not repeat those link fields;
- the P1 selector built prompt envelopes directly from the text record, so the pilot
  request carried empty event-ID and symbol arrays.

Therefore the P1 checks for "no new event ID or symbol" were mechanically true but did
not test non-empty identity binding.

No return, valuation or subsequent company outcome was opened to make this diagnosis.

## P2 correction

### Manifest authority

When a D003 document record is loaded, L001 selection must join it to the exact
`SS002-D003-v1.documents` manifest row by `document_id`.

The following fields come only from the manifest row:

- `event_ids`;
- `symbols`;
- `categories`;
- `source_url`;
- `segment_manifest_sha256`.

The text record remains authoritative for:

- extraction state;
- ordered segments;
- segment IDs;
- segment text SHA-256 values.

Any disagreement in shared identity fields fails closed.

### Non-empty identity requirement

Every L001 prompt envelope must contain:

- at least one canonical event ID;
- at least one NSE symbol.

`build_prompt_envelope` rejects empty identity arrays.

`validate_extraction` rejects an output when the allowed input event-ID or symbol sets
are empty.

### No retroactive overwrite

The original P1 pilot result remains preserved as
`PASSED_EVIDENCE_BOUND_LLM_EXTRACTION_PILOT` for document-understanding quality.

Its promotion boundary is amended:

- P1 alone is insufficient for L002 transaction threading;
- L002 requires a subsequent identity-bound run under this P2 amendment.

## HG001-C001 use

The first P2 identity-bound run will use the frozen HG001-C001 cohort and its
deterministically selected special-situation document bundle.

Every validated extraction must therefore be bound to real canonical event IDs and one
or more real current NSE symbols.

## Scientific boundary

P2 changes identity binding only.

It does not:

- change transaction-family semantics;
- change evidence fact schemas;
- use valuation or market returns;
- estimate completion probability;
- rank companies;
- authorize ADO/PF001/live capital.
