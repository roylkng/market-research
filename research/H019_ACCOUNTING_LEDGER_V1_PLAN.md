# H019 Point-in-Time Accounting Ledger v1

Status: **FROZEN BEFORE LEDGER COVERAGE EVIDENCE**

H019 numeric extraction v3 passed every preregistered accounting-source gate. This plan promotes that parser into a reusable point-in-time accounting ledger without opening any market outcome or defining any investment score.

## Objective

Build a source-faithful accounting observation store that can answer:

> What audited accounting values could an investor have known for this exchange symbol and fiscal year at a specified historical cutoff?

The ledger must not define the investable universe. A later experiment may intersect this ledger with an independently frozen point-in-time market-eligibility universe.

## Why observations must be versioned

A later annual report can restate the comparative value for an earlier fiscal year. Replacing the earlier value globally would leak the later restatement into earlier decisions.

Therefore the atomic ledger key is an **observation**, not a company-year scalar:

- exchange symbol
- fact name
- fiscal-year `to_year`
- observation role: `CURRENT` or `PRIOR_COMPARATIVE`
- report `to_year` in which the value was observed
- conservative `available_at` timestamp
- report source identity and hash

An as-of resolver may choose the latest observation whose `available_at <= cutoff`. The raw observations remain immutable.

## Source-only coverage cohort

This first ledger audit uses exactly **100 deterministic historical reporting symbols**. The number is fixed before extraction evidence and is not a portfolio size.

Construct lifecycle-proxy populations from official NSE annual-result listings only:

- 2018 reporting population
- 2020 reporting population

Then select, by deterministic evenly-spaced ordering before any annual-report API request:

- `SURVIVOR_PROXY`: 50 symbols present in both 2018 and 2020 populations
- `EXIT_PROXY`: 25 symbols present in 2018 but not 2020
- `NEW_PROXY`: 25 symbols present in 2020 but not 2018

These are reporting-lifecycle stress labels only. They are not claims about delisting, IPO, or economic survival.

No symbol may be replaced because its reports are inconvenient, unavailable, scanned, or fail parsing.

## Historical cutoff

Primary source-only as-of cutoff:

`2020-10-01T23:59:59+05:30`

This cutoff is inherited from the source-feasibility work and is chosen without security-return evidence.

## Annual-report metadata rule

For each frozen symbol:

1. query the official NSE annual-report API;
2. retain and hash the exact API response;
3. accept only approved NSE archive report URLs;
4. parse both `broadcast_dttm` and `disseminationDateTime` when available;
5. define `available_at` conservatively as the **later** valid timestamp;
6. discard metadata records whose `available_at` is after the cutoff;
7. for each report `to_year`, choose the metadata record with the latest `available_at` at or before cutoff;
8. from those metadata-frozen report years, choose the latest **two distinct** report `to_year`s at or before 2020.

The two report records are selected before downloading report bytes. A failed download or parse does not authorize a substitute report.

Two consecutive annual reports are sufficient in principle to reconstruct three fiscal-year observations because each audited statement normally carries current and prior comparatives. The audit measures whether this works in practice rather than requiring three report documents by fiat.

## Frozen extraction engine

Use H019 numeric extraction v3 semantics unchanged:

- no OCR;
- no symbol-specific page overrides;
- explicit unit evidence only;
- permitted equity subtotal reconstruction only;
- section-scoped explicit balance totals only;
- full provenance;
- balance-identity diagnostics;
- no numeric-closeness source selection.

This audit does not tune the v3 parser. Any parser change requires a new versioned protocol.

## Ledger facts

Core monetary facts:

- `revenue`
- `pat`
- `total_assets`
- `total_equity`

Additional facts:

- `operating_cash_flow`
- `total_borrowings`
- `finance_cost`
- `basic_eps` as INR/share
- `capex` when explicitly available

Capex remains optional.

## Observation schema

Each retained fact observation must include at minimum:

- `symbol`
- `group`
- `fact`
- `fiscal_year_to`
- `period_role`
- `observed_in_report_to_year`
- `available_at`
- `value`
- `normalized_unit`
- `report_url`
- `report_sha256`
- `pdf_sha256`
- `statement`
- `page_number`
- `source_line`
- `derivation`

For monetary facts, `value` is normalized INR. For EPS, `value` is INR/share.

## As-of resolver

For a requested cutoff:

1. keep observations with `available_at <= cutoff`;
2. group by `(symbol, fact, fiscal_year_to)`;
3. choose the maximum `available_at`;
4. if multiple observations at that same maximum timestamp disagree numerically, fail that resolved fact as `AMBIGUOUS_LATEST_OBSERVATION`;
5. otherwise choose deterministically and retain the complete observation provenance.

This deliberately permits a later report's comparative restatement to supersede an earlier observation only for decisions occurring after that later report became available.

## Coverage diagnostics

Coverage is measured before deciding the eventual H019 market universe. No arbitrary model-coverage threshold is fitted here.

Report at least:

- annual-report API success by lifecycle group;
- frozen report-record count by symbol;
- report download and parse status by group;
- current/prior core fact availability;
- number of symbols with any three consecutive fiscal years of all four core facts;
- number with three consecutive years of core facts plus operating cash flow;
- the same rates by lifecycle group;
- ambiguity count from the as-of resolver;
- source-hash and provenance completeness;
- balance-identity pass counts;
- observation count by fact and fiscal year.

The coverage result may determine whether the later H019 experiment should use the broad market universe or a narrower independently sourced market universe. It may not be chosen using future returns.

## Integrity gates

These are hard gates, independent of coverage percentages:

- exactly 100 frozen symbols = 50 survivor proxy + 25 exit proxy + 25 new proxy;
- sampling occurs before annual-report API success is known;
- every successful API/report source is content-addressed and hashed;
- selected report metadata has `available_at <= cutoff`;
- no more than two report years per symbol are selected;
- report selection is metadata-first and cannot fall back after content failure;
- every resolved fact has a source observation and provenance;
- no future-dated observation enters the resolver;
- zero unresolved same-timestamp conflicting observations are silently resolved;
- H019 v3 parser code is not modified by the ledger workflow;
- market prices, benchmark values, returns, portfolio selections, H019 feature weights, and live-capital outputs remain unopened.

## Decision rule

If every integrity gate passes, the point-in-time ledger architecture is accepted and the measured coverage becomes the source-side evidence used to freeze the later H019 data-eligibility rule.

This still does not authorize opening market outcomes or choosing H019 feature weights.