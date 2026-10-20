# HG009 P026: why the original 300-company experiment cannot isolate AI alpha

**Audited on:** October 21, 2026. **First frozen HG009 paper reference open:** October 15, 2026.  
**Source:** original NSE Nifty Total Market constituent industry CSV for **October 16**, permanently archived under research/prospective/rm001-sc002/raw and pinned SHA-256 692caee1b8e4fd11912c71e1c2519c4070e9675f9a0a9e6d40294cdf032890fc. Source is an **index subset**, not every NSE-listed equity. Original Oct15 selected/control identities are unchanged.

## Failure mode of the initial experiment

The independently selected original 100-company HG009 cohort showed **negative observed October 15 H1 return** relative to both 100-company controls. The controls had only seven source historical traded-value matching bands. HG009 P005 had already documented large revenue, EPS, margin and accounting-regime imbalances. Market return differences from one trading day cannot be isolated as model skill.

The Oct16 official NSE constituent source has 755 original rows, 744 exact EQ symbol+ISIN rows. It matches the original HG009 identities:

| Exact industry-source join, frozen symbol+ISIN | Selected 100 | One-signal 100 | Zero-signal 100 |
|---|---:|---:|---:|
| Has source industry | 46 | 43 | 53 |
| Not in original 755-row index subset | 54 | 57 | 47 |
| Of those matched, Financial Services | 4 | 13 | 17 |

Thus **158/300 source identities cannot receive a sector label from this particular original index file**, and only **20 complete selected/one-signal/zero-signal same-industry triplets** can exist even with replacement prohibited. This 20 is a mathematical upper bound, not 20 economically risk-matched investment opportunities.

Crucially, the official Oct16 source is **later than the October 15 entry** and was not independently proven ready before original entry. Its classifications cannot be silently backfilled as frozen October 15 model features or used to reinterpret the predeclared cohort as sector balanced. The report labels *all* Oct16 industries post-entry forensic observations, including apparently stable industries.

## Higher-leverage next experiment

Do not add a nonlinear LLM ranking or optimize weights against H1/H5 losses.

1. **Official 300-issuer census, not only the 755-index subset.** Acquire original timestamped NSE/BSE macro sector, industry and basic-industry identities that cover all frozen NSE symbol+ISINs. NSE Indices has four-tier sector classifications. Use a complete, dated original source with actual retrieval UTC and SHA-256. Absence of a company from the Nifty Total Market index **is not** proof that its industry is unknown or low quality.
2. **Financial accounting segregation.** Use lending/insurance/holding-company source-backed profitability metrics separately from industrial CFO-minus-PPE. A one-to-one sector label must never be inferred from financial ticker names or free-form LLM guesses.
3. **As-of float/size and risk exposures.** Archive contemporaneous share float, enterprise/market capitalization, industry, prior momentum, realized volatility, balance-sheet leverage, and accounting quality. Require source observation before any **new** cohort entry.
4. **Freeze a genuinely new comparator.** Match sector AND size buckets, plus historical liquidity band, and document effective sample size and standardized differences. If source coverage is below 95% total or 90% within an arm, fail the *full 300 model* gate and preserve all unmatched identities and coverage reasons.
5. **Outcomes:** only future 60/120/252-session actual NSE price and corporate-action adjusted distributions, full issuer denominator and sector/style exposures, with real execution costs and paired independent-time uncertainty. Ignore sector model significance without repeated independent future cohort freezes and a multiplicity-aware gate.
6. **Do not count H5 as an independent new confirmation:** its October 15 first holding session was already examined when the October 21 P025 growth bucket adjustments were designed. It may be descriptively reported using the already frozen methodology, but cannot rescue H1.
7. If complete source and independent performance do not establish an edge, record **NO_SUPPORTED_ALPHA** and redirect resources to identifiable, source-backed fundamental value opportunities rather than tuning an unsuccessful signal screen.

NSE official background: [NSE Indices industry classification](https://www.nseindia.com/static/products-services/industry-classification), [Nifty Total Market index](https://www.nseindia.com/static/products-services/indices-nifty-total-market-index). These links describe the framework. The numeric report is derived solely from the *archived Oct16 original CSV* and the exact original 300-name HG009 manifest, not from the current webpage.

## Repeatability

Run:

    python scripts/materialize_hg009_p026_sector.py --check
    pytest -q tests/test_hg009_p026_sector_coverage.py

Output research/hg009/hg009-p026-postentry-sector-coverage-v1.json includes all **300** frozen names, exact industry matches or explicit nulls, per-arm financial-skew and industry overlap, signed original file hashes, and explicit rejection of any retrospective size/sector/risk model or investment advice. All live capital remains disabled.


## Independent publisher constraint

NSE Indices' official [industry-classification methodology](https://www.nseindia.com/static/products-services/industry-classification) explicitly bases classification primarily on **audited consolidated business-segment revenues**, with a four-tier sector hierarchy. Its industry-classification page also lists subscription contact details. Therefore a publicly downloadable 755-name index constituent subset must not be presented as a free full-exchange classifier for 2,319 NSE identities.

A technically honest open-source fallback is an original audited annual report, source-sealed segment-revenue extract, source-dated classification policy, analyst plus independent-agent review, and an explicit UNKNOWN if no reliable dominant-segment evidence exists. The policy must be frozen before **a subsequent independent cohort**, not reconstructed from later outcomes.

**Actual sealed source audit SHA:** 8309c178feeb1e0de8c30b62be08a5090ac8f394b832a4208fbf4f487a21f9bb. Retrospective sector matching from this October 16 index file does **not** resolve the earlier industry's missing-first-seen defect for the October 15 entry.
