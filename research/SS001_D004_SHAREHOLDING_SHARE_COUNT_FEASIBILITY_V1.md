# SS001-D004 NSE Shareholding XBRL Issued-Share Count Feasibility v1

Status: **FROZEN BEFORE FULL 2,050-SOURCE MEASUREMENT**  
Frozen: 2026-10-08  
Return outcomes opened: no  
Market-cap outputs: prohibited in D004  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

The official NSE `quote-equity?section=trade_info` company-size source failed for
all 2,319 current EQ identities with HTTP 403 in SS001-D003-v1. Preserve that failure.

Test an **independent, official** share-quantity source: aggregate shareholding facts
from frozen GF001-D002 NSE shareholding XBRL, without retrying the blocked endpoint.

A source-only 48-filing audit was inspected before this protocol was frozen. It showed
consistent promoter/public/employee-trust category share counts and percentages.
Those 48 samples are **source-schema exploration**, not an untouched test set. The
full 2,050-source coverage remains the untouched D004 diagnostic.

## Exact immutable source

- GF001-D002-v1, run `37202941712`, artifact `11303742567`;
- panel SHA-256
  `dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7`;
- source census SS001-D002 SHA-256
  `214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293`;
- frozen 2,319 SS001 identities; 2,050 READY latest shareholding source rows.

Use **only latest** GF001-D002 source entries for D004. The remaining 269 identities
must remain explicitly SOURCE_UNAVAILABLE; no substitute source or ticker/name fuzzy
matching is permitted.

Source bytes are content addressed under `raw/xbrl/sha256/<raw_sha256>.xml`.
Verify each retrieved file against its expected SHA-256.

## Frozen XBRL quantities

From the exact non-summary category contexts, read the following two facts:

- `NumberOfShares`;
- `ShareholdingAsAPercentageOfTotalNumberOfShares`.

Exact category contexts:

- `ShareholdingOfPromoterAndPromoterGroup_ContextI`;
- `PublicShareholding_ContextI`;
- optional `EmployeeBenefitsTrusts_ContextI`.

A category present in the XBRL must have exactly one number and one fraction.
Employee-trust context structural absence is permitted. Its absence is **not** asserted
to mean the company owns zero employee-trust shares.

If present, the employee-trust category is added **once**; do not separately add
`SharesHeldByNonPromoterNonPublicShareholders_ContextI`, since it can overlap.

All share counts must be nonnegative integers; all ownership fractions must be finite
numbers in [0,1].

The issued-share candidate is the sum of the three **disjoint exact category**
`NumberOfShares` counts.

## Consistency gates per company

A count is `SHARE_COUNT_READY` only when:

1. both promoter and public categories have exact count and percentage facts;
2. any present employee-trust category has both facts;
3. sum of category percentages is within **0.001 absolute fraction** of 1.0;
4. every category's (count / candidate total) agrees with its reported fraction
   within **0.0015 absolute fraction**;
5. candidate issued-share count is a strictly positive integer;
6. no conflicting duplicate fact values are present.

A missing, malformed, or incompatible category is explicitly NOT_READY; do not
impute or infer values from another category.

## Partly-paid restriction

Read `WhetherTheListedEntityHasIssuedAnyPartlyPaidUpShares` from exact `MainI`.

- `false` means the quantity can become a future capitalization candidate;
- `true` means share count may remain reported, but
  `capitalization_source_eligible=false`, since price × shares of a single EQ line
  may not represent the full equity capitalization;
- absent/ambiguous flag means capitalization eligibility is false.

D004 does not attempt partly-paid security price adjustments.

## Frozen full-source thresholds

D004 source feasibility passes only if:

1. exact accounting for all 2,319 identities;
2. exact accounting for all 2,050 READY latest sources;
3. at least **90%** of the 2,050 latest source rows are SHARE_COUNT_READY;
4. at least **85%** of the 2,050 latest source rows are both SHARE_COUNT_READY
   and capitalization-source eligible;
5. zero accepted rows have unresolved category sum/count consistency;
6. every accepted row is bound to an exact, SHA-verified GF001 XBRL source.

Thresholds must not be lowered after D004 output is opened.

## Point-in-time boundary

D004 **does not** calculate market capitalization. Reporting date is not the same as
publication date, and a June/September share count cannot silently be multiplied by
October 1 price.

A later D005 may combine share counts with UDiFF closes only after independently
verifying:

- source filing's exchange publication timestamp <= requested price observation cutoff;
- no intervening unadjusted share-changing action (split, bonus, rights, conversion,
  new allotment, merger, reduction) between the share-count effective date and price;
- EQ ISIN/security continuity;
- all relevant share classes and partly-paid flags.

If any condition is unresolved, market cap remains UNKNOWN.

## Scientific boundary

No outcome returns, small-cap performance, market-price valuation, intrinsic value,
quality signal, expected IRR, ADO, PF001 or live-capital decisions are used in D004.
