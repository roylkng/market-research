# SS002-L001-P1 GPT-5.6 Sol Native Interactive Run v1

Status: **FROZEN MODEL OUTPUT BEFORE ANY RETURN/VALUATION OUTCOME REVIEW**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Seal the first model run against the already-frozen 30-document SS002-L001-P1 pilot
selection.

The model decisions were produced by GPT-5.6 Sol in the native ChatGPT reasoning runtime
using only the exact frozen prompt envelopes. No web search, company profile, market price,
future return, analyst target or external context entered the extraction.

## Frozen source

- selection ID: `SS002-L001-P1-SELECTION-v1`;
- selection SHA-256:
  `c040c519b8d28344a607838d2f025555b92fb9391582855e2dab7323aa805bc0`;
- source selection workflow run: `37224191432`;
- source selection artifact: `11311630848`;
- selected documents: 30;
- 6 each from BUYBACK, OPEN_OFFER_CONTROL, TENDER_OFFER, DELISTING and
  ASSET_SALE_DIVESTMENT.

## Model configuration

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- temperature semantic target: 0.0;
- top_p semantic target: 1.0;
- maximum structured output budget: 4096 tokens per document;
- output contract: `SS002-L001-v1`;
- structured output: JSON object.

This is a native interactive run rather than an HTTP/OpenAI-compatible endpoint run.
The deterministic materializer checked into this branch is the sealed representation of
the model's 30 frozen outputs.

## Conservative extraction policy

The run deliberately prioritizes precision over recall.

For the 10 documents in the frozen manual-audit set, material explicit transaction terms
are retained with exact evidence segment IDs.

For the remaining 20 documents, the model still classifies economic relevance,
transaction family and stage, but unsupported transaction terms remain UNKNOWN.

The model explicitly distinguishes misleading upstream keyword categories, including:

- subsidiary/step-down-subsidiary buybacks versus listed-company equity buybacks;
- debt tender offers versus listed-equity tenders;
- acquisition tenders where the listed company is the acquirer;
- CSE-only delistings that do not remove NSE/BSE listing;
- subsidiary debt delistings versus listed-company equity delistings;
- asset-sale keywords on documents where the listed company is actually the acquirer.

## Deterministic validation

Every model output is rebuilt from the exact selection artifact and passed through:

`marketlab.ss002_llm_contract.validate_extraction`

The run fails closed for:

- invented event IDs or symbols;
- unsupported evidence segment IDs;
- EXPLICIT facts without evidence;
- values on UNKNOWN facts;
- forbidden valuation/return/advice fields;
- incomplete provenance.

## Manual audit

Exactly the first two selected documents from each frozen family are audited, matching
the preregistered P1 protocol.

Two documents are conservatively marked `MATERIAL_TERM_MISSED`:

- TIPSMUSIC: detailed post-buyback economics sit in poorly extracted newspaper pages;
- SHRIRAMFIN: the frozen generic transaction schema does not separately represent each
  accepted bond principal/purchase-price component.

No unsupported material facts are accepted.

## Scientific boundary

This run tests evidence-bound document understanding only.

It does not:

- estimate completion probability;
- calculate arbitrage spread;
- calculate intrinsic value;
- rank companies;
- use future returns;
- create ADO/PF001 eligibility;
- authorize live capital.
