# HG002-D001 Triple-Convergence Hidden-Gem Underwriting Cohort v1

Status: **FROZEN BEFORE DEEP-RESEARCH MATERIALIZATION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Create the first finite underwriting cohort for the Small-Sum Alpha program from the
already-materialized HG001 full-market research router.

HG002-D001 is a deep-research routing cohort, not an expected-return ranking.

## Frozen source

Use exactly:

- HG001-D001-v1;
- workflow run: `37258053642`;
- artifact ID: `11323461912`;
- artifact name: `hg001-d001-37258053642`;
- router SHA-256:
  `79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff`;
- identity count: 2,319.

No later rerun may be substituted under HG002-D001-v1.

## Frozen cohort rule

Retain every HG001 row satisfying all conditions:

1. `active_opportunity_lane_count == 3`;
2. active lanes are exactly:
   - EARNINGS_INFLECTION;
   - ASSET_OR_CAPACITY_ANOMALY;
   - CURRENT_SPECIAL_SITUATION;
3. `governance_caution_count == 0`;
4. `asset_caution_flags` is empty;
5. `in_existing_u001 == false`.

No liquidity band, company name, price performance or market-cap estimate may remove a
qualifying row.

Expected cohort size under the frozen source: **28 names**.

## Why all 28 are retained

This is the first expensive-research cohort. Selecting only a handful after seeing company
names would introduce discretionary cherry-picking.

All 28 advance to underwriting. Research can be staged operationally, but none is removed
from the cohort because it looks unfamiliar, illiquid or inconvenient.

## Special-situation LLM readiness

SS002-L001-P1 validated the following transaction families:

- BUYBACK;
- OPEN_OFFER_CONTROL;
- TENDER_OFFER;
- DELISTING;
- ASSET_SALE_DIVESTMENT.

For each HG002 company retain:

- `l001_p1_validated_family_present`;
- intersection with the validated family set;
- unvalidated special-situation families requiring a separate pilot.

This field routes model work only. It does not increase research priority.

## Evidence retained per company

Retain exactly the HG001 evidence needed for underwriting:

- symbol / ISIN;
- earnings-inflection state;
- positive and negative inflection flags;
- earnings metrics;
- asset opportunity flags;
- liquidity band and median daily turnover;
- special-situation event count and categories;
- promoter percentage and quarter-on-quarter promoter delta;
- research-capacity state.

## Underwriting workstreams

Every HG002 company receives three parallel workstreams.

### A. Earnings normalization

- verify the inflection against exact filings;
- identify one-offs and base effects;
- estimate normalized revenue, margins, EPS and cash conversion;
- identify operational drivers and disconfirming evidence.

### B. Asset / capacity verification

- identify what caused each HA001 flag;
- distinguish distributable financial assets from operating assets;
- verify investment holdings, investment property, CWIP/capacity and debt claims;
- avoid treating accounting book value as realizable value without evidence.

### C. Special-situation economics

- construct the event thread;
- classify whether the transaction directly affects the listed security;
- extract exact terms from source documents;
- identify catalyst dates, approvals, conditionality and failure modes.

## Promotion

HG002-D001 authorizes:

- company-level deep research;
- evidence-bound LLM document extraction under validated family contracts;
- separately frozen expanded-family L001 pilot;
- deterministic scenario valuation and red-team work after source facts are assembled.

It does not authorize ADO, PF001 or live capital.

## Scientific boundary

HG002-D001 must not:

- add a numeric expected-return score;
- rank names by subsequent price moves;
- drop names after recognizing company identities;
- infer intrinsic value from flags alone;
- treat governance cleanliness as upside;
- treat illiquidity as a positive signal;
- authorize capital.
