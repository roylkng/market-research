# FA001-D001 Full-Market Current Financial/Asset XBRL Schema Audit v1

Status: **FROZEN BEFORE CURRENT-FILING BODY ACCESS**  
Frozen: 2026-10-07  
Return outcomes opened: no  
Hidden-asset scores assigned: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Establish the official NSE XBRL concept surface needed for a later full-market
financial/asset intelligence engine.

FA001 is intended to support hidden-gem research such as:

- net-cash / net-debt analysis;
- quoted and unquoted investment visibility;
- tangible-asset and investment-property context;
- working-capital intensity;
- capital expenditure and cash conversion;
- earnings / margin / balance-sheet inflection.

D001 is schema/source audit only. It does not calculate value or rank companies.

## Frozen market universe source

Use exactly SS001-D001-v1:

- run: `37197575401`;
- artifact ID: `11301695772`;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`;
- 2,319 current NSE EQ identities.

## Deterministic audit cohort

Eligible companies must satisfy:

1. SS001-D001 has `has_integrated_financial_filing=true`;
2. at least 15 of the frozen 20 market sessions are observed;
3. finite positive median daily traded value.

Partition eligible names using the frozen 20-session median daily traded value:

- L1: >= INR 10 crore;
- L2: INR 2 crore to < INR 10 crore;
- L3: INR 50 lakh to < INR 2 crore;
- L4: < INR 50 lakh.

Within each band compute:

`selection_key = SHA256("FA001-D001-v1|" + symbol + "|" + isin)`

Sort ascending by selection_key and select exactly 16 names per band.

Total audit cohort: exactly 64 companies.

No accounting fact, valuation, future return, current special-situation state or later
hidden-gem conclusion enters selection.

## Filing selection

For every selected symbol query official NSE Integrated Filing - Financials discovery.

Cutoff:

`2026-10-07T18:30:00+05:30`

Only rows with an official exchange timestamp on or before the cutoff are eligible.

Select one current filing using:

1. latest reporting-period end;
2. Consolidated preferred over Standalone when both are available for the same latest
   reporting-period end;
3. within the selected period/basis choose the latest official exchange publication;
4. require an approved official NSE XBRL URL.

The audit intentionally studies the latest available current taxonomy, not historical
taxonomy stability.

## Source retention

Retain:

- exact discovery bytes and SHA-256;
- selected discovery row;
- exact XBRL URL;
- exact XBRL bytes and SHA-256;
- symbol / ISIN / company identity fields;
- current report period / basis;
- complete local-name concept catalog;
- context-shape metadata.

No alternate provider may replace a failed NSE source.

## XBRL context catalog

For every filing catalog each context as:

- instant or duration;
- start/end/instant dates;
- dimensional vs non-dimensional.

For every local-name concept retain:

- fact count;
- distinct context count;
- non-dimensional fact count;
- instant-context fact count;
- duration-context fact count;
- dimensional fact count.

D001 does not interpret a value merely because a concept name exists.

## Frozen semantic discovery groups

D001 reports candidate concept names whose normalized local names contain any frozen
token below.

### Cash / liquidity

- cash
- bankbalance
- bankbalances

### Borrowings / debt

- borrowing
- borrowings
- debt

### Investments / financial assets

- investment
- investments
- financialasset
- financialassets

### Inventory / working capital

- inventor
- receivable
- payable

### Tangible / property assets

- propertyplant
- investmentproperty
- rightofuse

### Intangible assets

- intangible
- goodwill

### Equity / share capital

- equitysharecapital
- sharecapital
- paidup

### Cash flow / capex

- netcashflow
- netcashflows
- purchaseofproperty
- paymentstoacquire

### Earnings / operating state

- revenuefromoperations
- profitbeforetax
- profitlossforperiod
- financecost
- depreciation

These groups are search aids only. D001 does not freeze final aliases from substring
matching.

## Feasibility gates

D001 passes only if all are true:

1. exactly 64 deterministic audit names are selected;
2. at least 60 of 64 selected latest filings are fetched and parse as XBRL;
3. every parsed filing has one unambiguous NSE symbol identity;
4. every parsed filing has at least one non-dimensional context;
5. at least 90% of parsed filings expose explicit presentation currency;
6. all selected/failure states are accounted for exactly once;
7. no return, price-performance or valuation outcome affects concept interpretation.

Thresholds may not be lowered after output is opened.

## Promotion

Passing D001 permits only:

- FA001-D002 exact alias/statement-semantics freezing;
- a separately frozen full-market fact extraction run.

It does not permit a hidden-asset or earnings-inflection score yet.

## Scientific boundary

D001 does not:

- classify cash as excess cash;
- treat investments at book value as recoverable market value;
- value land or subsidiaries;
- calculate enterprise value;
- calculate NCAV;
- infer fraud or governance quality;
- infer future earnings;
- use LLM judgment;
- use stock returns;
- create ADO/PF001/live-capital eligibility.
