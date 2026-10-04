# SS001-D001 Full-Market Opportunity Census v1

Status: **FROZEN BEFORE SOURCE DIAGNOSTIC**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Build the first broad-market source spine for the Small-Sum Alpha research program.

SS001-D001 does not rank stocks and does not claim alpha. Its job is to answer a more
basic question first:

> Can the research system deterministically enumerate the broad NSE main-board equity
> universe and attach enough official point-in-time market, filing and corporate-action
> evidence to support later hidden-gem and special-situation detectors?

The target opportunity set is deliberately much broader than the existing frozen
100-name U001/Nifty-200 research universe.

## Frozen security universe source

Official NSE listed-equity security master:

`https://archives.nseindia.com/content/equities/EQUITY_L.csv`

D001 includes only rows whose security series is exactly `EQ`.

The raw master is retained and SHA-256 bound into the census.

No company is excluded because it is small, lacks analyst coverage, has low turnover,
or falls outside an index.

SME/Emerge securities are not included in D001-v1. They require a separate extension
after the main-board source spine is proven.

## Frozen market-data window

Use exactly the final 20 completed NSE cash-market sessions ending 2026-10-01 from the
already-frozen calendar:

`research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json`

Official NSE UDiFF cash-market bhavcopy is the only price/liquidity source.

For each current EQ identity retain:

- observed session count out of 20;
- first and last observed close;
- raw 20-session price return when both endpoints exist;
- median daily traded value;
- median daily traded volume;
- median daily trade count;
- number of sessions with positive traded value;
- whether the security traded in all 20 sessions.

No corporate-action adjustment is applied in D001. Price return is context only, not a
research signal. Later opportunity detectors that use price histories must separately
audit share-changing actions.

## Frozen current identity matching

Current market rows are joined to the security master by exact current:

- NSE symbol;
- ISIN;
- EQ series.

A mismatch fails closed for that identity.

## Frozen financial-filing coverage source

Official NSE Integrated Filing - Financials discovery:

`https://www.nseindia.com/api/integrated-filing-results`

Acquire the exchange-wide window:

- from date: 2026-04-01;
- to date: 2026-10-04.

Use deterministic pagination until the source returns no more rows.

For each security retain:

- filing-row count in the window;
- latest reported period end when parseable;
- latest exchange publication timestamp when present;
- whether any Integrated Filing - Financials evidence is available.

D001 does not parse financial values and does not derive valuation, growth, ROCE or
earnings signals from these rows.

## Frozen corporate-action coverage source

Official NSE corporate-actions endpoint:

`https://www.nseindia.com/api/corporates-corporateActions`

Acquire exchange-wide evidence from 2025-10-05 through 2026-10-04 in deterministic
60-calendar-day chunks.

Retain exact raw bytes/hashes for every source chunk.

For each current symbol retain counts of:

- all observed corporate-action rows;
- dividend rows;
- split/sub-division/consolidation rows;
- bonus rows;
- rights rows;
- merger/demerger/amalgamation/scheme rows;
- buyback rows;
- delisting rows;
- other rows.

These counts are event-source context only. D001 does not rank an action as attractive
or unattractive.

Absence of a corporate-action row is valid and is not considered source failure.

## Existing research-universe overlap

Join the current census to the frozen 100-name U001 snapshot only as context.

Retain:

- `in_existing_u001`;
- count inside U001;
- count outside U001.

U001 membership has no effect on SS001-D001 eligibility.

## D001 source-feasibility thresholds

The census passes only if all are true:

1. at least 1,500 current NSE EQ identities are parsed from the official security master;
2. at least 85% of those identities have an exact 2026-10-01 UDiFF row;
3. at least 70% have observations in at least 15 of the frozen 20 sessions;
4. at least 60% have at least one Integrated Filing - Financials discovery row in the
   frozen 2026-04-01 through 2026-10-04 window;
5. all frozen corporate-action source chunks are successfully acquired and parseable.

Thresholds may not be lowered after the diagnostic output is opened.

## D001 output

Produce an immutable census with one row per current NSE EQ security containing:

- identity and listing metadata from the security master;
- current-market/liquidity context;
- financial-filing source coverage;
- corporate-action source context;
- existing-U001 overlap;
- exact source hashes and rule identifiers.

## Promotion

Passing SS001-D001 permits the next source layers only:

- SS001-D002 ownership/shareholding and pledge coverage;
- GF001 governance-forensics source coverage;
- SS001-I001 small-sum investability policy;
- separately frozen opportunity-detector designs.

D001 itself does not permit a hidden-gem score.

## Explicit exclusions

SS001-D001 does not:

- use future returns;
- compute intrinsic value;
- estimate target prices;
- infer market capitalization;
- parse annual-report prose;
- use LLM judgment;
- rank companies;
- filter for low P/E or high growth;
- create an ADO;
- alter PF001;
- authorize live capital.

The LLM/deep-research layer begins only after the market/source spine is frozen and
auditable.
