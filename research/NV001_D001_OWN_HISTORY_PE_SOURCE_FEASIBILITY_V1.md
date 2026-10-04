# NV001-D001 Own-History Trailing P/E Source Feasibility v1

Status: **FROZEN BEFORE SOURCE DIAGNOSTIC**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Determine whether official NSE financial filings plus official NSE cash-market
bhavcopy archives can reconstruct a company-specific trailing P/E history for
enough of frozen U001 to support a later normalized-valuation research lens.

NV001-D001 is source feasibility only. It does not rank companies, fit returns,
or alter RR001, DR001, H021, FQ001, ADO or PF001.

## Frozen universe

Use exactly:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

Expected universe SHA-256:

`cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb`

## Frozen valuation dates

Annual fiscal-year endpoints:

- 2023-03-31;
- 2024-03-31;
- 2025-03-31;
- 2026-03-31.

Current valuation anchor:

- 2026-10-01 completed NSE cash-market session.

Only March-year companies can contribute to v1. Non-March financial-year companies
remain source-ineligible rather than being remapped after coverage is observed.

## Filing source families

### FY25 and FY26

Use official NSE Integrated Filing - Financials discovery.

For each symbol and basis, use the earliest official filing whose period end equals
the required March 31 endpoint.

### FY23 and FY24

Use official NSE legacy Financial Results discovery:

`/api/corporates-financial-results?index=equities&symbol=<SYMBOL>&period=Quarterly`

The selected row must:

- have exact required period end;
- expose an official NSE XBRL URL;
- have basis normalized to Consolidated or Standalone;
- have a valid official publication timestamp.

For a year with multiple filings at the same earliest timestamp but different URLs,
fail closed.

## Frozen accounting basis rule

For each company, choose one basis for the entire four-year P/E history:

1. Consolidated if all four required years have a usable Consolidated annual filing;
2. otherwise Standalone if all four required years have a usable Standalone annual filing;
3. otherwise source-ineligible.

No switching between Consolidated and Standalone across years is allowed.

## Annual EPS definition

Use explicit annual-duration basic EPS from the filing:

preferred concept:

`BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations`

fallback only when the preferred concept is absent:

`BasicEarningsLossPerShareFromContinuingOperations`

Annual context must:

- be non-dimensional;
- start on the filing's explicit financial-year start;
- end on the selected March 31 fiscal-year endpoint.

EPS must be finite and strictly positive to form a P/E observation.

No PAT/share-count reconstruction is used in v1.

## Historical price anchor

For each annual filing:

1. convert the exchange publication timestamp to Asia/Kolkata;
2. start with the next calendar date;
3. choose the first completed NSE cash-market session with an official bhavcopy;
4. use the EQ close for the filing's contemporaneous security identity.

The publication day itself is never used, even for filings released before market open.

For sessions before 2024-07-08, use official NSE legacy CM bhavcopy archives.

For sessions on or after 2024-07-08, use official NSE UDiFF CM common bhavcopy.

NSE states that the old CM Bhavcopy was discontinued from 2024-07-08 in favor of
CM-UDiFF Common Bhavcopy Final.

## Historical identity rule

At the price anchor, identity is resolved in this order:

1. exact filing symbol + EQ series + filing ISIN when available;
2. if symbol has changed, a unique EQ row with the exact filing ISIN.

No fuzzy issuer-name matching is allowed.

Because price and EPS are contemporaneous at each historical observation, no split
adjustment is applied to the P/E ratio itself.

## Historical P/E

For each valid annual observation:

`trailing_pe = first_post_filing_close / annual_basic_eps`

The P/E observation is unavailable when EPS is nonpositive or the price identity cannot
be resolved exactly.

## Current trailing P/E

Current trailing P/E uses:

- 2026-10-01 official NSE close;
- the same FY26 annual basic EPS selected above;
- exact frozen U001 symbol/ISIN.

`current_trailing_pe = close_2026_10_01 / FY26_basic_eps`

Current P/E is unavailable when FY26 basic EPS is nonpositive.

## D001 output

For each U001 symbol retain:

- selected accounting basis;
- each annual filing URL, publication timestamp and raw SHA-256;
- annual basic EPS;
- price-anchor session, source URL, raw SHA-256 and close;
- each annual trailing P/E;
- current trailing P/E;
- explicit failure reason codes.

No normalized valuation score is computed in D001.

## Frozen feasibility thresholds

D001 passes only if all are true:

1. at least 60 U001 companies have current trailing P/E;
2. at least 60 companies have at least 3 valid historical annual P/E observations from FY23-FY26;
3. at least 50 companies have all 4 historical annual P/E observations;
4. at least 50 companies have both all 4 historical observations and current trailing P/E.

Thresholds may not be lowered after output is opened.

## Promotion

If D001 passes, the next allowed step is a separately frozen NV001-S001 normalized
valuation research score.

A later score may compare current trailing P/E with the company's own four historical
post-result P/E observations, but D001 itself does not define the transform or weights.

## Explicit exclusions

D001 does not:

- use future stock returns;
- use analyst target prices;
- use forward P/E;
- use EV/EBITDA;
- fit a predictive model;
- optimize valuation cutoffs;
- sector-normalize values;
- create ADO or PF001 eligibility;
- permit live capital.

Any extension to forward valuation, EV/EBITDA, FCF yield, sector-relative valuation,
or more historical years requires a separately frozen version.
