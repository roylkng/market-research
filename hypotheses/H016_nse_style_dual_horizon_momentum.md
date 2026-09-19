# H016 — NSE-style dual-horizon normalized momentum for company selection

Frozen: 2026-09-08 before any H016 score or return was calculated.

Status: **FROZEN INDEPENDENT HISTORICAL CHALLENGE. LIVE CAPITAL DISABLED.**

## External mechanism anchor

H016 is not derived by tuning H015's failed 2023-2024 residuals. Its signal construction is anchored to the published NSE Indices momentum methodology used for indices such as Nifty200 Momentum 30 and Nifty500 Momentum 50.

NSE Indices defines momentum using:

- 12-month price return divided by annualized one-year daily-return volatility,
- 6-month price return divided by the same volatility,
- cross-sectional z-score of each momentum ratio,
- 50% weight to the 12-month momentum z-score and 50% to the 6-month momentum z-score,
- a monotonic normalized momentum score derived from that weighted z-score,
- semiannual reconstitution.

Published methodology references frozen before this experiment:

- https://www.niftyindices.com/indices/equity/strategy-indices/nifty500--momentum--50
- https://www.niftyindices.com/Methodology/Method_NIFTY_Equity_Indices.pdf

H016 adapts the published score to the project's source-audited company-only universe because historical point-in-time Nifty 500 membership and free-float market-cap weights are not available in the retained harness. It is therefore **NSE-style**, not a claim of exact Nifty500 Momentum 50 index replication.

## First challenge window

Use five semiannual decision dates, each the last retained common NSE session of the specified month:

- November 2020,
- May 2021,
- November 2021,
- May 2022,
- November 2022.

Required official market source history starts no later than November 2019. The last portfolio exits at the final common trading session of May 2023.

No H005-H015 experiment calculated full-market company-selection returns for this period. This is H016's first independent historical challenge.

## Point-in-time company universe

At each decision `t`, eligibility uses only source data available through `t`:

- NSE cash-market `EQ` series,
- 12-character ISIN beginning with `INE`,
- one candidate per decision-day ISIN, keeping lexicographically smallest symbol if duplicate symbols map to one ISIN,
- at least one full year of retained common-session price history required by the H016 score,
- a valid bar on every common session from the 12-month price anchor through `t`,
- finite positive OHLC,
- median traded value over the 20 common sessions ending at `t` >= INR 2 crore,
- no structural corporate action effective from the 12-month price anchor through `t`; the experiment conservatively excludes such names from selection rather than attempting historical share-basis reconstruction,
- at least 300 eligible company equities at each decision.

Future stock bars, future suspensions/delistings and future corporate actions may not affect selection eligibility.

## Frozen score

Let `P0` be the decision-session close.

Let `P6` be the close on the final retained common NSE session of the calendar month exactly 6 months before the decision month.

Let `P12` be the close on the final retained common NSE session of the calendar month exactly 12 months before the decision month.

Use all daily log returns from `P12` through `P0` to estimate one-year volatility:

`vol_1y = sample_std(daily_log_returns) * sqrt(252)`

Require finite `vol_1y > 0`.

For each eligible company:

- `R6 = P0 / P6 - 1`
- `R12 = P0 / P12 - 1`
- `MR6 = R6 / vol_1y`
- `MR12 = R12 / vol_1y`

Within the decision-date eligible universe:

- `Z6 = (MR6 - mean(MR6)) / sample_std(MR6)`
- `Z12 = (MR12 - mean(MR12)) / sample_std(MR12)`
- `weighted_z = 0.5 * Z12 + 0.5 * Z6`

The published normalized transformation is monotonic in `weighted_z`, but H016 records it explicitly:

- if `weighted_z >= 0`, `normalized_momentum = 1 + weighted_z`
- otherwise `normalized_momentum = 1 / (1 - weighted_z)`

Rank descending by `normalized_momentum`, tie by symbol.

Select exactly `ceil(10% * eligible_count)`, minimum 30 names.

No fitted parameter, regime threshold, breadth threshold or model search is used.

## Semiannual paper execution

For each frozen selected list:

- target entry: next common NSE session open after decision,
- target exit: close on the final retained common NSE session of the calendar month exactly 6 months after the decision month,
- Nifty 500 benchmark: same entry-session open to same target exit-session close.

The complete selected list is frozen before inspecting entry or future bars.

### Post-selection failures

Use the point-in-time integrity policy established after H015:

- missing/nontradable next-session entry remains in the selected denominator as a cash slot with stock return 0 and is never replaced,
- source-backed future split/bonus/consolidation factors may be applied only in the outcome layer,
- a filled position with unresolved future structural action or no deterministically usable target exit receives a conservative primary lower-bound stock return of -100%,
- execution failures and lower-bound outcomes remain in the denominator.

Gross stock return and Nifty 500 excess are primary. Also report a fixed 0.50% round-trip friction deduction on filled positions. Cash no-fill slots incur no friction.

## Frozen comparators

Use identical point-in-time eligible companies, selected count and outcome policy:

1. raw 6-month price return,
2. raw 12-month price return,
3. 6-month volatility-adjusted momentum ratio `MR6`,
4. 12-month volatility-adjusted momentum ratio `MR12`,
5. full eligible company cohort,
6. deterministic matched-random selections using seed `1616` and 10,000 aggregate draws.

Comparators are diagnostics and cannot redefine H016 after the result.

## Independent challenge gates

All must pass:

- all 5 frozen semiannual cohorts are evaluable,
- >=300 selected company observations total,
- next-session fill rate >=98%,
- conservative lower-bound outcome rate <=2%,
- mean selected-company Nifty 500 excess > +2.0 percentage points,
- median selected-company Nifty 500 excess > 0,
- selected-company Nifty 500 beat rate >=55%,
- at least 4 of 5 cohorts have positive equal-weight gross Nifty 500 excess,
- mean H016 excess >= full eligible company cohort mean excess +2.0 percentage points,
- one-sided fixed-seed matched-random empirical p-value for mean excess <=0.05,
- no single corporate-equity ISIN contributes >15% of aggregate positive gross selected return,
- no two consecutive H016 cohorts both have non-positive equal-weight excess,
- mean selected-company Nifty 500 excess after frozen 0.50% friction > +1.5 percentage points.

The single-horizon comparators are reported but are not required to underperform H016 in every finite sample. H016's claim is a robust company-selection edge versus the market/full eligible cohort and random selection, not that the combination must dominate each component in every historical window.

If every gate passes, H016 is classified `HISTORICALLY_ROBUST_PENDING_SECOND_CHALLENGE`. It still cannot enable live capital. A second disjoint historical robustness window and then prospective paper validation remain mandatory.

## Audit rule

After the first H016 score or outcome is calculated, the universe rule, source convention, 6/12-month anchors, volatility estimator, cross-sectional z-score construction, 50/50 weighting, top-decile operating point, semiannual schedule, execution policy, friction assumption and gates cannot change under H016-v1.
