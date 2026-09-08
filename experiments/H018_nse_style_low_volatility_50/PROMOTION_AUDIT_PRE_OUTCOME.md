# H018 promotion audit, frozen before first H018 outcome

Recorded: 2026-09-08 while H018 workflow run 34242734569 was still executing its first historical challenge and before its first `challenge-summary.json` was available.

Status: **PROMOTION BLOCKERS PREDECLARED. H018-v1 GATES UNCHANGED. LIVE CAPITAL DISABLED.**

This audit does not modify H018-v1, its 2014-2016 challenge window, score, top-50 selection, execution convention, friction assumption, random seed, comparators, or pass/fail gates. It declares additional evidence required before any historical H018 pass may be interpreted as a company-selection strategy suitable for prospective promotion.

## Why this is necessary

H018 selects low-volatility companies from the project's broad point-in-time company-only universe rather than exact point-in-time Nifty 500 membership. Low volatility is mechanically correlated with company size, liquidity, sector composition, and mature-business characteristics. The frozen H018 matched-random test matches selection count but does not explicitly match liquidity or sector exposure. Consequently, a positive H018 result could partly reflect a liquidity/size/sector effect rather than volatility itself.

The project's objective is robust company selection, not merely finding a historical portfolio that beats Nifty 500. A successful H018-v1 challenge is therefore necessary but not sufficient for promotion.

## Additional promotion blockers

Before H018 may proceed beyond historical-candidate status, all of the following must be satisfied without changing H018-v1 selection rules:

1. **Liquidity-stratified random challenge**
   - For each H018 decision cohort, divide the eligible universe into deciles by the same point-in-time median prior-20-session traded value used for eligibility.
   - For every selected H018 company, random comparator draws must sample from the same cohort and liquidity decile.
   - Use a frozen independent random seed and at least 10,000 aggregate draws.
   - H018 equal-weight mean excess must retain a one-sided empirical p-value <= 0.05.

2. **Liquidity-adjusted cross-sectional regression diagnostic**
   - On each eligible cohort, regress realized company excess return on predecision `log(median_20d_traded_value)` and the frozen low-volatility score or volatility rank.
   - This is diagnostic rather than a replacement selection rule.
   - The low-volatility coefficient/rank relationship must retain the expected sign in at least four of five cohorts. No post-result variable transformations may be chosen.

3. **Sector concentration audit**
   - Obtain point-in-time sector/industry classification from a retained source that predates or is contemporaneous with each decision.
   - Report sector weights of H018 and the eligible cohort.
   - No claim of stock-specific alpha may be made until a sector-matched comparator is evaluated. If historical point-in-time sector data cannot be sourced, report the factor as a portfolio effect rather than company-specific alpha.

4. **Second disjoint historical challenge**
   - Freeze the window before its H018 outcomes are calculated.
   - Prefer an earlier period materially distinct from 2014-2016, because prior Indian evidence on the volatility effect is regime-dependent.
   - The second challenge must use the identical H018-v1 score and 50-company semiannual rule.
   - It must independently satisfy positive mean and median Nifty 500 excess, beat rate >= 55%, positive equal-weight excess in at least 4/5 cohorts, and matched-random p <= 0.05.

5. **Prospective paper validation**
   - No live capital based on historical success.
   - Freeze selections before future entry prices and outcomes exist.
   - Use the same company identity, signal, schedule and top-50 rule.
   - Retain exact source hashes and non-fill/lower-bound outcomes.
   - Apply an explicit prospective cost model and portfolio-level concentration constraints before promotion.

## External-evidence caution

NSE Indices publishes Nifty500 Low Volatility 50 as an explicit strategy index, but the official construction starts from Nifty 500 constituents and combines low-volatility score with free-float market capitalization for weights. H018 deliberately does not claim exact replication.

Published Indian evidence is not unanimous. A 2017 IIMB Management Review study using 493 BSE 500 companies from 2000-2013 reported no conventional low-volatility anomaly and found high-volatility stocks outperforming low-volatility stocks. A later IIMB Management Review study covering Nifty 500 companies during 2010-2020 reported that the volatility anomaly was more pronounced at medium-to-long horizons and especially at horizons of roughly three years or more. These conflicting findings strengthen the requirement for a second independent regime before promotion.

## Decision rule

If H018-v1 fails its original frozen challenge, retire H018-v1 without using this audit to rescue or modify it.

If H018-v1 passes, classify it only as **HISTORICAL_CANDIDATE_PENDING_CONFOUND_AND_SECOND_CHALLENGE**, not as a proven investment edge. The additional blockers above were frozen before the first H018 result and must be cleared without using them to tune the original score.
