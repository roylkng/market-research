# H018 — NSE-style company-only Low Volatility 50

Frozen: 2026-09-08 before any H018 score or return was calculated.

Status: **FROZEN INDEPENDENT HISTORICAL CHALLENGE. LIVE CAPITAL DISABLED.**

## External mechanism anchor

H017 failed as a 50/50 momentum + low-volatility composite, while its preregistered low-volatility-only comparator was the strongest factor in that window. H018 does not change H017's weight. It starts a new standalone hypothesis anchored to NSE Indices' published low-volatility strategy methodology.

NSE Indices states that Nifty500 Low Volatility 50 selects 50 stocks based on low volatility, where volatility is the standard deviation of daily lognormal price returns over the previous one year, and the index is reconstituted semiannually.

Frozen external reference:

- https://www.niftyindices.com/indices/equity/strategy-indices/nifty500-low--volatility-50

H018 adapts the factor to the project's point-in-time company-only universe because point-in-time historical Nifty 500 membership and free-float weights are not available in the retained source harness. It is therefore NSE-style, not an exact index replication.

## First challenge window

Five untouched semiannual decisions:

- November 2014,
- May 2015,
- November 2015,
- May 2016,
- November 2016.

Use the final retained common NSE session of each decision month. Source history begins no later than November 2013 and extends through the May 2017 exit of the last cohort.

No H005-H017 full-market company-selection experiment used this period before this freeze.

## Point-in-time company universe

At decision `t`:

- NSE cash-market `EQ` series,
- 12-character ISIN beginning `INE`,
- one candidate per decision-day ISIN, lexicographically smallest symbol on duplicate identity,
- complete common-session company bars for at least the previous one year through `t`,
- finite positive OHLC,
- median traded value over the 20 common sessions ending at `t` >= INR 2 crore,
- no structural corporate action effective during the one-year signal lookback,
- future bars, future suspensions/delistings and future corporate actions may not affect selection eligibility,
- at least 300 eligible companies at every decision.

Post-selection execution failures remain in the denominator under the H015/H016 conservative policy.

## Frozen score

For each eligible company, calculate daily log returns across the retained one-year lookback ending at the decision session.

`vol_1y = sample_std(daily_log_returns) * sqrt(252)`

Require finite `vol_1y > 0`.

`low_vol_score = 1 / vol_1y`

Rank descending by `low_vol_score`, tie by symbol.

Select exactly the top **50 companies** at every decision. There is no percentile threshold, fitted model or optimized parameter.

## Semiannual execution

- freeze the complete 50-company list before inspecting next-session data,
- enter at next common NSE session open,
- exit at close of the final retained common NSE session exactly six calendar months after the decision month,
- benchmark against Nifty 500 over the same entry-open to exit-close interval,
- no-fill cash slots remain selected and are never replaced,
- future resolved split/bonus/consolidation factors are applied only in the outcome layer,
- unresolved future structural action or missing deterministic filled-position exit receives frozen -100% lower-bound stock return,
- report gross metrics and fixed 0.50% filled-position friction-adjusted metrics.

## Frozen comparators

Use identical point-in-time eligible company universes, count=50 and post-selection outcome policy:

1. H016 dual-horizon normalized momentum,
2. raw 12-month momentum,
3. full eligible company cohort,
4. fixed-seed matched random selections, seed `1818`, 10,000 aggregate draws.

## Independent challenge gates

All must pass:

- all five cohorts evaluable,
- exactly 250 selected company observations,
- fill rate >=98%,
- lower-bound outcome rate <=2%,
- mean selected-company Nifty 500 excess >+2 pp,
- median selected-company Nifty 500 excess >0,
- selected-company Nifty 500 beat rate >=55%,
- at least 4 of 5 cohorts have positive equal-weight Nifty 500 excess,
- mean H018 excess >= full eligible company cohort mean excess +2 pp,
- one-sided fixed-seed matched-random empirical p-value for mean excess <=0.05,
- no single corporate-equity ISIN contributes >15% of aggregate positive gross selected return,
- no two consecutive cohorts both have non-positive equal-weight excess,
- mean selected-company excess after frozen 0.50% friction >+1.5 pp.

The momentum comparators are diagnostics, not requirements for every finite sample.

If all gates pass, H018 becomes `HISTORICALLY_ROBUST_PENDING_SECOND_CHALLENGE`. Live capital remains disabled until a disjoint second historical challenge and prospective paper validation both succeed.

## Audit rule

After the first H018 score or outcome is calculated, no universe rule, volatility estimator, fixed count, schedule, execution convention, friction assumption, comparator or gate may change under H018-v1.
