# FA001-D002 Full-Market Financial / Asset Fact Plane v1

Status: **FROZEN BEFORE FULL-MARKET FACT MATERIALIZATION**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Materialize an auditable current financial fact plane across the frozen SS001 broad NSE
EQ universe using the exact XBRL semantics that passed FA001-D001.

D002 is a source/fact layer only. It does not calculate hidden-asset value, earnings
inflection scores, intrinsic value, expected return or portfolio eligibility.

## Frozen universe

Use exactly the 2,319 current NSE EQ identities from:

- SS001-D001-v1;
- run `37197575401`;
- artifact `ss001-d001-37197575401`;
- census SHA-256
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`.

No security is removed for small size, illiquidity, sector or missing analyst coverage.

## Frozen discovery source

Reuse the exact Integrated Filing - Financials discovery pages already preserved inside
the SS001-D001 artifact.

No new discovery semantics are introduced.

## Frozen filing endpoints

For each symbol:

### Annual balance-sheet / cash-flow filing

Exact period end:

`2026-03-31`

Basis preference:

1. Consolidated;
2. Standalone.

Select the earliest official NSE source on the preferred available basis.

### Current quarterly filing

Exact period end:

`2026-06-30`

Prefer the annual accounting basis when available; otherwise:

1. Consolidated;
2. Standalone.

No substitute period endpoint is introduced.

## Frozen concept authority

Use exactly the annual and quarter alias families frozen and audited in:

`research/FA001_D001_FULL_MARKET_FINANCIAL_ASSET_XBRL_SCHEMA_AUDIT_V1.md`

Implementation authority:

`src/marketlab/fa001_schema_audit.py`

No fuzzy concept matching is allowed.

## Frozen context rules

Annual balance-sheet facts:

- non-dimensional context;
- instant = 2026-03-31.

Annual duration facts:

- non-dimensional;
- endDate = 2026-03-31;
- duration 350-380 days.

Current-quarter facts:

- non-dimensional;
- endDate = 2026-06-30;
- duration 80-100 days.

When an alias family produces more than one distinct numeric value in the frozen context
scope, the family is `AMBIGUOUS`. No value is chosen.

Alias precedence follows the exact frozen alias order. A later alias is considered only
when an earlier alias has no deterministic numeric value.

## Retained annual facts

D002 retains source state plus exact numeric value, selected concept and unitRef for:

- total assets;
- total equity;
- cash and cash equivalents;
- bank balances other than cash;
- current investments;
- non-current investments;
- other current financial assets;
- other non-current financial assets;
- current borrowings;
- non-current borrowings;
- current lease liabilities;
- non-current lease liabilities;
- current liabilities;
- non-current liabilities;
- PPE;
- capital work in progress;
- investment property;
- goodwill;
- other intangibles;
- inventories;
- trade receivables;
- other current assets;
- other non-current assets;
- paid-up equity share capital;
- face value;
- annual basic EPS;
- operating cash flow;
- PPE purchases/sales;
- investment purchases/sales.

No missing value is imputed as zero.

## Retained current-quarter facts

D002 retains:

- revenue;
- total income;
- profit before exceptional items and tax;
- exceptional items;
- PBT;
- PAT;
- finance costs;
- depreciation/amortisation;
- employee benefit expense;
- materials consumed;
- stock-in-trade purchases;
- inventory change;
- other expenses;
- basic EPS.

## Numeric semantics

D002 retains the exact XBRL numeric value and unitRef.

It does not yet claim cross-company currency normalization for hidden-asset valuation.

A later HA001/EI001 contract may use only fact rows whose units/currency semantics are
explicitly compatible.

## Source provenance

Every filing row retains:

- symbol;
- accounting basis;
- period end;
- exchange publication timestamp;
- source URL;
- discovery row SHA-256;
- exact filing SHA-256;
- selected concept and context semantics for every READY fact.

## Deterministic six-shard acquisition

Shard count is exactly 6.

For each current symbol:

`shard = int(SHA256(symbol), 16) mod 6`

Every symbol belongs to exactly one shard.

Each shard:

1. downloads the exact SS001-D001 artifact;
2. reads the preserved Integrated Filing discovery pages;
3. selects annual/current-quarter candidates;
4. fetches only the selected official filing URLs;
5. emits one row for every assigned current identity.

A merge stage rejects missing or duplicate identities.

## Frozen feasibility gates

D002 passes only if all are true:

1. exactly 2,319 identities are accounted for;
2. >=75% have an exact FY26 annual filing source;
3. >=80% have an exact Q1 FY27 filing source;
4. >=65% of all identities have READY annual total-assets + total-equity + cash facts;
5. >=60% have READY current + non-current borrowings;
6. >=60% have at least one READY current/non-current investment family;
7. >=70% have READY current-quarter revenue + PAT;
8. every READY filing is bound to exact official bytes and SHA-256;
9. no stock-return or valuation outcome enters parsing or source selection.

Thresholds may not be lowered after D002 output is opened.

## Promotion

Passing D002 permits separately frozen:

- HA001 hidden-asset candidate detection;
- EI001 earnings-inflection candidate detection;
- deterministic joins to GF001 governance facts;
- LLM deep research on promoted candidate dossiers.

## Explicit exclusions

D002 does not:

- derive market capitalization;
- compute net cash or tangible book;
- value land/subsidiaries/investments;
- calculate earnings growth;
- rank stocks;
- use LLM inference;
- estimate returns;
- create ADO/PF001/live-capital eligibility.
