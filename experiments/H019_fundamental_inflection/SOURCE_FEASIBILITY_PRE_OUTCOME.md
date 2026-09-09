# H019 fundamental-inflection source feasibility

Status: **SOURCE FEASIBILITY ONLY. NO RETURN OUTCOMES. NO SCORE FROZEN YET.**

H019 is the orthogonal successor to retired H018-v1. Its intended research question is whether point-in-time fundamental quality plus improving business economics can identify companies with superior medium/long-horizon returns, rather than merely reproducing momentum, low volatility, or an earnings-event classifier.

Before freezing H019-v1, the project must establish what accounting primitives are reproducibly available from official historical NSE financial-result filings.

## Source-feasibility window

Probe official NSE financial-result listings and exchange-hosted XBRL documents across 2017-01-01 through 2023-12-31.

This window is for source-schema discovery only. No stock-return label, future price, excess return, or selected-company outcome may be calculated or opened.

## Required metadata audit

For quarterly and annual result listings, retain exact response bytes and report by calendar year:

- listing rows;
- distinct NSE symbols;
- rows with exact publication/broadcast timestamp;
- rows with period/quarter end;
- rows with exchange-hosted XBRL URL;
- consolidated versus standalone availability where exposed.

## XBRL schema audit

Use a deterministic URL-hash sample, independent of company performance, and fetch only from the official NSE archive hosts already allowed by the repository.

For each valid sampled XBRL document, inspect concept/tag names only and record whether the schema appears to expose primitives needed for potential H019 factors, including:

- revenue / operating revenue;
- operating profit or operating expense primitives;
- profit after tax / net profit;
- equity / net worth;
- assets;
- borrowings / debt;
- cash flow from operating activities;
- EPS;
- receivables;
- inventory;
- current assets / current liabilities where available.

Do not choose a final score from sample values. The purpose is only to determine what can be defined consistently and point-in-time.

## External baselines already fixed conceptually

Any eventual H019-v1 must include independent baselines that prevent a false novelty claim:

1. an NSE-style quality baseline built from profitability, leverage and earnings stability where the source data permits;
2. a quality + value baseline where valuation primitives can be constructed point-in-time;
3. the broad eligible company cohort;
4. matched random portfolios using predecision observables such as liquidity and business scale.

The eventual inflection score must add predictive value beyond these baselines. Otherwise H019 will be classified as rediscovery of known quality/value factor exposure.

## Outcome lock

This feasibility phase must not create or read any H019 selection or return-outcome artifact. Any eventual decision dates, factor weights, thresholds, holdout windows, random seeds, and pass/fail gates will be frozen only after this source audit is complete and before H019 outcomes are calculated.
