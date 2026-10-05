# SS002-L001-P2 GPT-5.6 Sol Native Interactive Run v1

Status: **FROZEN MODEL OUTPUT BEFORE RETURN/VALUATION REVIEW**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Seal the second evidence-bound GPT-5.6 Sol native extraction run against the frozen
25-document SS002-L001-P2 expanded-family selection.

The run covers exactly:

- SCHEME_REORGANISATION;
- PREFERENTIAL_WARRANT;
- INSOLVENCY_RESOLUTION;
- RIGHTS_ISSUE;
- OFFER_FOR_SALE.

## Frozen selection

- selection ID: `SS002-L001-P2-SELECTION-v1`;
- selection SHA-256:
  `bb18dede6c56e07d8beff78852f8e089ac3d7bd124fb76c6cc0d22e9fecec7ce`;
- source workflow run: `37261077921`;
- source artifact: `11324194877`;
- selected documents: 25, five per family.

## Model configuration

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- temperature semantic target: 0.0;
- top_p semantic target: 1.0;
- maximum structured-output budget: 4096 tokens per document;
- output contract: `SS002-L001-v1`.

Only the exact frozen prompt envelopes were used. No web search, market price, analyst
target, later return, company profile or external context entered the extraction.

## Conservative extraction policy

All 25 documents receive:

- economic relevance;
- corrected transaction family/families;
- transaction stage;
- ambiguity/caveat retention.

Detailed explicit transaction facts are populated for exactly the ten preregistered
manual-audit documents: the first two selected documents from each family.

The run deliberately corrects misleading upstream keyword families, including:

- NCLT/amalgamation filings classified upstream as insolvency;
- listed parents subscribing to subsidiary rights issues;
- internal subsidiary/group schemes;
- OFS disclosures where the listed company is selling an investment rather than its
  own equity;
- historical rights-issue call/conversion updates rather than new rights offerings.

## Deterministic validation

Every sealed output passes through:

`marketlab.ss002_llm_contract.validate_extraction`

The run fails closed for unsupported evidence, invented event/symbol IDs, values on
UNKNOWN facts, forbidden investment fields or incomplete provenance.

## Manual audit

Exactly ten documents are manually audited, matching the P2 preregistration:

- WIPRO;
- GVPIL;
- RAYMOND;
- TDPOWERSYS;
- AMBUJACEM;
- ASIANENE;
- ZOTA;
- SJS;
- INDIANB;
- COCHINSHIP.

## Scientific boundary

This run validates document understanding only. It does not estimate intrinsic value,
completion probability, expected return or portfolio action.
