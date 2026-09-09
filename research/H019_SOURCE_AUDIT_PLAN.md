# H019 source audit plan — long-horizon fundamental quality + inflection

Recorded: 2026-09-09

Status: **SOURCE FEASIBILITY ONLY. NO H019 SCORE OR RETURN OUTCOME MAY BE COMPUTED. LIVE CAPITAL DISABLED.**

## Objective

The project now needs an orthogonal long-horizon company-selection engine. H008/H009 showed that quarterly growth-change ranks can look strong in a design period and fail an untouched validation. H018-v1 was retired on its frozen coverage rule before any return outcome. H019 therefore must not be another short/medium-horizon price-factor variant or another four-line quarterly growth composite.

The intended mechanism is durable business quality plus measurable improvement in business economics, with explicit valuation discipline.

Before freezing an H019 signal, this audit asks only whether official NSE historical filings can support a point-in-time implementation with adequate coverage.

## Candidate information families to audit

The source audit should look for concepts sufficient to construct, without future information:

1. profitability / capital efficiency
   - profit after tax or profit attributable to owners,
   - EBIT / operating profit where available,
   - total assets,
   - shareholder equity / net worth,
   - current and non-current debt or borrowings;
2. cash conversion
   - cash flow from operating activities,
   - capital expenditure or cash purchase of property, plant and equipment when available;
3. growth and inflection
   - revenue from operations / total income,
   - operating profit,
   - EPS,
   - enough consecutive annual periods to calculate growth and variability;
4. valuation-enabling data
   - basic/diluted EPS and/or share-count concepts that can be paired with exact historical market prices.

No feature is yet frozen merely because a source concept exists. This is a data-contract audit only.

## Proposed historical source window

Probe annual NSE financial-result filings published from 2016-01-01 through 2020-12-31. The eventual H019 validation decisions are expected to fall in 2017-2019 if source coverage is adequate, leaving later years for future outcomes and/or a disjoint challenge.

This source window is not itself an H019 outcome window. No stock return, Nifty return, ranking, or selected-company outcome may be calculated during this audit.

## Point-in-time requirements

For every filing retained, preserve:

- symbol and company name,
- annual period end,
- publication timestamp,
- consolidated vs standalone basis,
- exact NSE-listed XBRL/iXBRL URL,
- SHA-256 and exact retained source bytes,
- listing response source hash.

Any eventual H019 decision may use only filings whose publication timestamp precedes that decision timestamp.

## Audit outputs

The audit should report:

- listing rows and unique company-year filings by calendar year;
- fraction with valid exchange-hosted XBRL/iXBRL source URLs;
- fetch success/failure by source host and format;
- local-name/tag coverage for candidate accounting concepts;
- number of companies with at least 2, 3, 4 and 5 consecutive annual filings available point-in-time;
- consolidated-vs-standalone availability;
- representative retained source hashes and parsing diagnostics.

Do not report returns, prices, future performance, candidate winners, or an H019 score.

## Decision rule

Only after this audit is complete may H019-v1 freeze a score. The score must be specified before any outcome window is opened. A plain NSE-style quality mechanism based on long-run profitability, leverage and earnings stability must be a frozen comparator so that H019 cannot claim generic quality exposure as a novel inflection edge.
