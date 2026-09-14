# H021 StockAnalysis target-aware parser result v1

Recorded: 2026-09-14
Status: **FROZEN 5-NAME LIVE PARSER PASS. FULL-U001 AUTOMATION NOT YET AUTHORIZED.**
Live capital: disabled
Return outcomes opened: no

## Purpose

Validate a deterministic parser for the public StockAnalysis NSE forecast pages before using it for prospective H021 acquisition.

The parser must extract the exact fiscal-period label and period-ending date already frozen for each symbol in the immutable 2026-09-11 H021 anchor. It is not allowed to choose the latest visible estimate column or silently roll to a different fiscal horizon.

It must also preserve the provider financial currency explicitly rather than infer it from NSE listing currency, company domicile, or EPS magnitude.

## Frozen live cohort

Configuration: `research/prospective/h021/stockanalysis-parser-probe-v1.json`

Symbols:

- RELIANCE
- INFY
- TCS
- M&M
- NESTLEIND

The probe consumes only source pages plus the immutable Sep 11 H021 anchor. It does not consume prices, returns, H013, H019, H020, PF001, valuation or future outcomes.

## First live run: deliberate failure

GitHub Actions run `34822017242` produced 4/5 parser success and correctly failed final enforcement.

The exact failure was INFY. Its forecast page contained the correct FY2027 / 2027-03-31 EPS table but did not expose the reporting currency in the same visible page text. The immutable H021 anchor identifies INFY EPS currency as USD.

The parser was **not** relaxed to infer USD from the small EPS value, NSE listing currency, or company identity.

Instead, the source contract was strengthened to use the public StockAnalysis financials page as an explicit second source for financial/reporting currency when the forecast page does not expose it. A forecast/financials currency disagreement fails closed.

## Corrected live run

Final retained run: GitHub Actions `34822518214`, attempt 1.

Anchored evidence: `reports/h021-stockanalysis-parser-probe/run-34822518214-attempt-1.json`

Result:

- parser rows: 5/5
- EPS-currency semantic matches to immutable Sep 11 anchor: 5/5
- exact frozen fiscal period/period endpoint: 5/5
- robots verification: passed
- unit/parser invariant tests: passed
- final workflow enforcement: passed

### Parsed current observations

| Symbol | Frozen target | EPS | EPS currency | Analyst count | Revenue growth | Currency source |
|---|---|---:|---|---:|---:|---|
| RELIANCE | FY2027 / 2027-03-31 | 63.97 | INR | 24 | 11.95% | forecast page |
| INFY | FY2027 / 2027-03-31 | 0.86 | USD | 50 | 9.07% | financials page |
| TCS | FY2027 / 2027-03-31 | 155.08 | INR | 41 | 8.97% | forecast page |
| M&M | FY2027 / 2027-03-31 | 137.07 | INR | 35 | -17.25% | forecast page |
| NESTLEIND | FY2027 / 2027-03-31 | 21.53 | INR | 35 | 16.22% | forecast page |

The retained report stores response URL, HTTP status, byte length and SHA-256 for both forecast and financials pages. Raw provider HTML is not committed.

## Parser invariants

The parser now fails when:

- the `NSE:<symbol>` page identity does not match;
- the S&P Global Market Intelligence forecast-provider marker is absent;
- there is not exactly one recognizable annual forecast table;
- the frozen fiscal-period label plus exact period-ending date does not identify exactly one column;
- target EPS is unavailable or unparsable;
- financial/reporting currency is unavailable from both public pages;
- forecast and financials pages disagree on financial currency;
- the financials page identity does not match the forecast symbol.

The parser retains which public URL supplied the EPS currency.

## Decision

The parser is sufficiently validated to proceed to a broader **source-only full-U001 dry run**.

It is **not yet authorized for unattended weekly 100-name production capture**. Five names prove the parsing mechanism and important currency edge case, but they do not establish full-universe coverage, symbol URL compatibility, provider-page availability or layout consistency across all frozen U001 names.

The next gate must freeze the full 100-name target set before running it, execute at low rate in deterministic shards, retain only source hashes/parsed fields/errors, and report all failures without substitution or fallback repair.

Only after that broader dry run should automated primary-field acquisition be considered for the Friday H021 capture process.
