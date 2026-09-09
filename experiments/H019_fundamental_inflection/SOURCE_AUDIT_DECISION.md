# H019 source audit decision

Recorded: 2026-09-09

Status: **INPUT DESIGN MAY PROCEED. RETURN OUTCOMES UNOPENED. SCORE NOT YET FROZEN.**

## Evidence base

Two outcome-blind source audits were completed before any H019 score, selection, or return outcome was frozen.

### Historical listing audit

Official NSE financial-result listing requests covering 2017-01-01 through 2023-12-31 completed 56/56 successfully and retained exact response bytes.

The archive contained 79,654 normalized machine-filing rows across 2,198 symbols from 2018 onward. The 2017 listing rows are real and metadata-rich, but their XBRL field is uniformly the placeholder `https://nsearchives.nseindia.com/corporate/xbrl/-`. H019 therefore treats 2017 as pre-machine-XBRL for this source route rather than attempting to repair or scrape missing filings.

### Deep deterministic XBRL audit

A second audit fetched 120 unique official NSE XBRL documents using a fixed rule: the 20 lowest SHA-256 URL hashes in each publication year 2018-2023. All 120 downloaded and parsed as XBRL.

Exact finite fact coverage:

- `RevenueFromOperations`: 120/120
- `ProfitBeforeTax`: 120/120
- `Expenses`: 120/120
- `PaidUpValueOfEquityShareCapital`: 120/120
- `FaceValueOfEquityShareCapital`: 120/120
- `ProfitLossForPeriod`: 119/120
- `ProfitBeforeExceptionalItemsAndTax`: 119/120
- `BasicEarningsLossPerShareFromContinuingOperations`: 119/120
- `DilutedEarningsLossPerShareFromContinuingOperations`: 119/120

The two share-capital primitives were both strictly positive in 118/120 deterministic documents. Their units are `INR` and `INRPerShare`, so their ratio is a filing-date share-count primitive without an external share-count vendor.

For the same documents, full-balance-sheet concepts are structurally era-dependent:

- `Equity`: 0/80 across 2018-2021, then 8/20 in 2022 and 12/20 in 2023
- `Assets`: same pattern as `Equity`
- current/non-current borrowings, current assets/liabilities and receivables: absent from the deterministic sample before 2022 and only partial afterwards
- operating cash flow: partial even before 2022 and not universal afterwards

Therefore a 2018-2023 test using ROE, ROCE, leverage, working-capital or cash-conversion factors would have a hidden source-era regime shift. H019-v1 must not do that.

## Frozen source architecture for H019-v1 design phase

H019-v1 design may use only the broad-era facts that are demonstrably stable before 2022:

1. revenue from operations;
2. profit/loss for period;
3. profit before exceptional items and tax;
4. basic EPS;
5. paid-up equity share capital;
6. face value per share;
7. exact NSE publication timestamp and quarter end;
8. official NSE cash-equity price/liquidity data;
9. official NSE corporate actions where needed for identity/share-change safety.

Full equity, total assets, borrowings, cash flow, receivables, inventory and working-capital facts are explicitly excluded from H019-v1. They may support a later post-2022 model but cannot be mixed into this historical test.

## Current-quarter XBRL convention

Across the 120-file deterministic audit, each available core fact above has exactly one finite value whose `contextRef` is `OneD`. This is the NSE filing convention used for the current reported quarter.

Some older XBRLs contain `OneD` facts without a corresponding declared `<context id="OneD">`, so requiring a standards-complete context object would reject valid official filings. H019 therefore freezes this source rule:

- select only exact concept names;
- select only `contextRef="OneD"` for the current-quarter value;
- require exactly one finite value for every required concept;
- require the expected units for INR and per-share facts;
- fail closed on missing, duplicated, malformed or non-finite facts;
- never use `FourD`, cumulative, segment or fuzzy-matched concepts as substitutes.

## Financial-company scope

The NSE legacy result metadata exposes a `bank` classification. H019-v1 will treat `bank == "N"` as the comparable non-financial universe and exclude banking/financial taxonomy codes from this first model. Their economics and accounting ratios require a separate hypothesis.

This is not a performance filter. It is an accounting-comparability rule fixed before H019 outcomes.

## Decision-window feasibility

Using listing metadata only, with no return outcomes, a strict eight-consecutive-quarter history and a latest reported quarter no more than 150 days old yields approximately:

- 978 non-financial symbols at 2020-12-31;
- 928 at 2021-06-30;
- 1,313 at 2021-12-31;
- 1,241 at 2022-06-30;
- 1,147 at 2022-12-31;
- 1,169 at 2023-06-30;
- 1,239 at 2023-12-31.

These are metadata-feasible counts before liquidity and exact-fact validation. They justify proceeding with seven semiannual design cohorts without choosing a minimum-universe gate from outcome data.

## Next gate

Before H019-v1 scores or pass/fail thresholds are frozen, the repository must construct an outcome-blind point-in-time factor frame and report exact eligible counts after:

- basis consistency;
- eight-quarter exact-fact parsing;
- non-financial classification;
- share-count validity;
- point-in-time liquidity;
- corporate-action safety for valuation.

Only then may selection count, score formula, historical holdout, random seed and promotion gates be frozen. No H019 future return may be opened during that coverage audit.
