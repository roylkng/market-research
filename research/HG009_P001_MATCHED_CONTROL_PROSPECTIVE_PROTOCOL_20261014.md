# HG009-P001: prospective comparator design for the 100-company discovery experiment

**Frozen:** October 14, 2026, before the first planned Oct 15 NSE entry session.  
**Class:** source-locked, observational three-arm research comparison, not an approved confirmatory alpha or investment strategy.  
**Live capital:** prohibited. **Return observations opened:** none.

## The scientific gap

HG009-D001 preserved an authentic historical 2,319-company source and selected 100 names without future return data. That is necessary for an honest experiment, but **not sufficient** to infer outperformance. U001's Nifty200 top-100 nonfinancials is a separate earnings panel, not the HG009 comparator. Nifty 500 price index is a useful market reference, but does not control industry, liquidity, volatility or size.

The 100 HG009 participants include 28 original triple-lane cases and 72 hash-sampled two-lane cases. Historical source band counts: L1 >=₹10cr/day 51, L2 ₹5-10cr 12, L3 ₹2-5cr 17, L4 ₹1-2cr 7, L5 ₹20L-1cr 7, L6 below ₹20L 4, and two with insufficient historical observations. No earlier selection is altered.

## Three frozen arms, 300 unique symbols + ISINs

- **100 selected:** original HG009 28 triple-lane plus 72 two-lane names.
- **100 one-lane comparisons:** exactly the same numbers per original source liquidity band, sampled from outside-U001 NSE companies with one frozen earnings, asset or event lane and no governance/asset caution.
- **100 zero-lane comparisons:** identical band quotas, drawn from companies with no active opportunity lane and with the same outside-U001/clean-caution restrictions.

Control inclusion is deterministically sorted by SHA-256 over the immutable original HG001 source SHA, HG009-P001 experiment ID, arm, original liquidity band, NSE symbol and ISIN. There is no subsequent price comparison, sector guess, subjective name preference or iterative seed optimization.

**Limitations are material.** Exact matching is **ONLY historical turnover band plus coarse existing-U001/caution restrictions**, not current bid/ask order capacity, sector, float-adjusted market cap, company size, leverage, accounting standards or market-factor beta. The one- and zero-lane controls are a sanity check, **not randomized treatment assignment**. Hashing a fixed source makes selection reproducible, not automatically statistically exchangeable. A high post-entry selected-arm return cannot be attributed to LLM discovery without controlling confounders and replication across independent future cohorts.

## Outcome observation, separately controlled

Research participation is frozen before opening Oct 15, 2026. The first planned paper anchor is **official NSE EQ open on Oct 15** for every predeclared identity, regardless of whether original quote bytes become available only after close. This is not a claim of executed fills. A source unavailable at entry remains explicitly missing, not dropped or replaced by a same-name different ISIN, BE-series price, today's quote, or synthetic fill.

An independently implemented market-observation pipeline must retain real acquisition UTC timestamps and the official original NSE market UDiFF + Nifty 500 price-index bytes and hashes. Index comparison is price-only, **not** Nifty500 TRI. Require exact NSE trading calendar for 1, 5, 20 and 60 market-session holding windows, with the entry session counted as session one and official exit close. No calendar dates substituted for missed market sessions. Exchange's unresolved November 8 Muhurat session must be resolved from official original timing sources before any horizon crosses that date.

Any dividends, split/bonus/rights, merger/demerger or changes in shares/ISIN during the window need source-backed handling before stock returns may be called economically equivalent. Report every blocked company, percentage of missing source rows and denominator. No survivorship conditioning.

**Descriptive pilot endpoint:** report 20-market-session gross NSE open-to-close stock-price return distributions (median, means and tails) for each frozen 100-name arm, and differences of arm medians/means after identical observation/corporate-action gates. Show Nifty 500 price-index excess separately. Publish coverage and suspension/delisting counts even if this makes the selected arm look worse. Inferences remain descriptive until sector/size/risk conditioning and multiple **outcome-independent future cohort freezes** are implemented. Avoid small-sample significance claims from a single cross section.

## Evidence and promotion gates

1. Original HG001 router SHA, selected HG009 SHA and new control manifest SHA all verify.
2. Exactly 300 unique symbol+ISIN identities, no duplicate/overlap, 100 per arm, matched original band quotas, no original 28 removed.
3. Original source timestamps and publication readiness preserved, real raw exchange bytes kept.
4. Before choosing an investable stock: company filings → normalized free cash flow → diluted share/debt/minority bridge → 3-scenario probability with uncertainty and red-team → cost/impact/capacity → independent prospective outcomes.
5. No price target, calibrated probability, statistical win claim or actual capital authorization until separately verified.

**Reproduce:** python scripts/materialize_hg009_controls.py --check; pytest -q tests/test_hg009_controls.py. The manifest is research/hg009/hg009-p001-matched-300-company-controls-v1.json. Its input source remains the immutable October 5 2,319-NSE-identity router committed under HG009-D001.

## Published pre-entry reproducibility receipt

The first control freezer completed on October 14 before the planned next trading-session entry, and the canonical three-arm JSON manifest has SHA-256 **8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8**. The three arms contain exactly 100, 100, and 100 unique symbol+ISIN pairs. The source was the original HG001 SHA **79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff** and the selected HG009 SHA **e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5**. Both identities and the matching rules must remain unchanged after opening future prices.

This receipt is **not** an outcome. The initial Oct 15 NSE entry can be counted as predeclared only if this source manifest is present on the canonical remote branch before the market opens. A later merge cannot retroactively repair that temporal condition.
