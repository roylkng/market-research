# SS002-L001 Evidence-Bound Document Fact Extraction Contract v1

Status: **FROZEN BEFORE ANY LLM INFERENCE**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Define the first LLM role in the Small-Sum Alpha system.

L001 converts deterministic text segments from one exact official special-situation
document into a strict structured fact object.

The LLM is an evidence extractor, not an investment decision-maker.

## Upstream authority

L001 may consume only documents that are bound through:

- SS002-D001-P2 canonical current event identities;
- SS002-D002 official NSE attachment document IDs;
- SS002-D003 deterministic document text segments.

No web search, model memory, alternate data provider or unsupported company knowledge may
fill missing document terms inside L001.

## Input object

Every L001 request must contain:

- document_id;
- source_url;
- canonical announcement/event IDs linked to the document;
- NSE symbol(s);
- frozen SS002 category hints;
- ordered text segments;
- each segment's deterministic segment_id and text SHA-256.

Category hints are context only. The LLM must describe the economics present in the
document, including when the original keyword category is misleading or only indirect.

## Economic relevance

Exactly one primary relevance state:

- DIRECT_LISTED_SECURITY
- LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR
- SUBSIDIARY_OR_INVESTEE_ONLY
- PROCEDURAL_OR_NEWSPAPER_UPDATE
- OTHER_CORPORATE_CONTEXT
- UNKNOWN

Examples:

A listed issuer offering rights to its own shareholders:
DIRECT_LISTED_SECURITY.

A listed parent subscribing to a rights issue of its wholly-owned subsidiary:
LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR or SUBSIDIARY_OR_INVESTEE_ONLY, based on the
document's actual economics.

A newspaper notice repeating an already announced transaction:
PROCEDURAL_OR_NEWSPAPER_UPDATE.

## Transaction family vocabulary

L001 may assign zero or more of:

- BUYBACK
- OPEN_OFFER_CONTROL
- DELISTING
- SCHEME_REORGANISATION
- RIGHTS_ISSUE
- PREFERENTIAL_WARRANT
- ASSET_SALE_DIVESTMENT
- INSOLVENCY_RESOLUTION
- CAPITAL_REDUCTION
- OFFER_FOR_SALE
- TENDER_OFFER
- ACQUISITION_INVESTMENT
- FUND_RAISE_OTHER
- OTHER
- UNKNOWN

The LLM does not have to preserve an upstream keyword category when the document shows a
different economic transaction.

## Transaction stage vocabulary

Exactly one primary stage:

- PROPOSAL
- BOARD_APPROVED
- SHAREHOLDER_APPROVED
- REGULATORY_OR_COURT_APPROVED
- PUBLIC_ANNOUNCEMENT
- OFFER_OPEN
- OFFER_CLOSED
- RECORD_DATE_FIXED
- ALLOTMENT_COMPLETED
- TRANSACTION_COMPLETED
- CANCELLED_OR_WITHDRAWN
- PROCEDURAL_UPDATE
- UNKNOWN

## Evidence-bound fact rule

Every material fact is represented as:

```json
{
  "status": "EXPLICIT" | "UNKNOWN",
  "value": <typed value or null>,
  "unit": <controlled unit or null>,
  "evidence_segment_ids": ["..."]
}
```

Rules:

1. `EXPLICIT` requires at least one valid input segment ID.
2. `UNKNOWN` requires `value=null` and no invented evidence.
3. L001 may normalize formatting, currency notation and dates.
4. L001 may not derive a missing value from arithmetic.
5. Arithmetic belongs to deterministic downstream code.
6. L001 may not use facts from outside the supplied document segments.

## Frozen fact families

### Parties

- issuer_name
- target_name
- acquirer_name
- seller_name
- promoter_or_promoter_group
- other_named_counterparties

### Security economics

- offer_price_per_share
- issue_price_per_share
- exercise_price_per_share
- floor_price_per_share
- number_of_securities
- maximum_securities
- offer_size_percentage
- stake_before_percentage
- stake_after_percentage
- face_value_per_share

### Consideration

- total_consideration
- cash_consideration
- non_cash_consideration_description
- debt_assumed
- enterprise_value_stated
- asset_or_business_value_stated

### Ratios / entitlement

- rights_entitlement_numerator
- rights_entitlement_denominator
- bonus_ratio_numerator
- bonus_ratio_denominator
- exchange_ratio_text
- tender_or_acceptance_ratio_stated

### Dates

- announcement_date
- board_approval_date
- shareholder_approval_date
- record_date
- ex_date
- offer_open_date
- offer_close_date
- expected_completion_date
- effective_date
- court_or_regulatory_order_date

Dates are canonical ISO YYYY-MM-DD when the exact calendar date is explicit; otherwise
UNKNOWN. L001 may retain a separate date_text for explicit but non-canonical periods such
as "within 30 days".

### Conditions / approvals

- approvals_required
- conditions_precedent
- regulatory_bodies
- voting_or_tender_thresholds
- financing_conditions

### Business economics

- stated_transaction_rationale
- stated_use_of_proceeds
- asset_or_business_description
- capacity_or_operating_metric_disclosed
- debt_reduction_or_financing_use
- dilution_or_new_share_count_description

These are concise normalized descriptions, not model opinions.

## Ambiguity and contradiction output

L001 must retain:

- unresolved_questions;
- contradictions_within_document;
- extraction_caveats.

A conflicting term must not be silently resolved.

## Forbidden L001 fields

The model must not output:

- target price;
- intrinsic value;
- expected return;
- probability of completion;
- bullish/bearish labels;
- buy/sell/hold;
- portfolio weight;
- quality score;
- governance score;
- catalyst score.

## Model provenance

Every accepted extraction must bind:

- provider/runtime identifier;
- model identifier;
- model configuration hash;
- prompt contract ID;
- prompt SHA-256;
- input document ID;
- input segment-manifest SHA-256;
- raw model response SHA-256;
- validated structured-output SHA-256.

This allows later model changes to be compared rather than silently replacing prior
interpretation.

## Validation

The deterministic validator must reject output when:

- document_id differs from request;
- event IDs or symbols not supplied in input are introduced;
- an EXPLICIT fact lacks evidence segments;
- evidence segment IDs are not in the input manifest;
- UNKNOWN facts carry values;
- enum values are outside the frozen vocabularies;
- expected-return/valuation/advice fields appear;
- JSON contains NaN/Infinity;
- provenance is incomplete.

## Promotion

A validated L001 extraction may enter:

- SS002-L002 transaction threading;
- deterministic family-specific payoff models;
- red-team deep research.

L001 does not authorize portfolio eligibility or live capital.
