# H017 — NSE-style momentum + low-volatility company selection

Frozen: 2026-09-08 before any H017 score or return was calculated.

Status: **FROZEN INDEPENDENT HISTORICAL CHALLENGE. LIVE CAPITAL DISABLED.**

## External mechanism anchor

H017 is a new multi-factor hypothesis. It does not alter H016's frozen 6/12-month momentum weights.

NSE Indices' published multi-factor methodology treats:

- momentum as volatility-adjusted multi-horizon trend,
- low volatility as the inverse of the standard deviation of previous one-year daily price returns,
- factor-level z-scores as percentile scores,
- multiple factors by a weighted average of factor percentile scores.

NSE Indices also publishes several indices explicitly designed to counter single-factor cyclicality through multi-factor selection.

Frozen external references:

- https://www.niftyindices.com/Methodology/NIFTY_Multi-Factor_Indices_Methodology.pdf
- https://www.niftyindices.com/Methodology/Method_NIFTY_Equity_Indices.pdf
- https://www.niftyindices.com/indices/equity/strategy-indices/nifty500-low--volatility-50

There is no claim that H017 replicates a named NSE index. H017 applies the published factor-combination framework to the project's point-in-time company-only universe.

## First challenge window

Five semiannual decisions:

- November 2017,
- May 2018,
- November 2018,
- May 2019,
- November 2019.

Each decision uses the final retained common NSE trading session of the month. Official source history starts no later than November 2016 and extends through the final May 2020 exit.

No H005-H016 company-selection experiment used this period for full-market portfolio outcomes before this freeze. The last cohort deliberately spans the February-March 2020 COVID shock, providing a severe regime challenge.

## Point-in-time company universe

Identical integrity contract to H016:

- NSE `EQ` series,
- 12-character ISIN beginning `INE`,
- one candidate per decision-day ISIN, lexicographically smallest symbol on duplicate identity,
- complete common-session price history from the 12-month anchor through decision,
- at least one year of usable price history,
- median prior-20-session traded value >= INR 2 crore,
- no structural corporate action effective between the 12-month anchor and decision,
- future bars and future actions never affect selection eligibility,
- at least 300 eligible companies per decision.

Post-selection no-fill, future-action and missing-exit handling remains conservative and identical to H016/H015 point-in-time policy.

## Momentum factor

Use H016 unchanged:

- 6-month and 12-month calendar-month-end price returns,
- divide each by annualized sample standard deviation of one-year daily log returns,
- cross-sectional z-score `MR6` and `MR12`,
- `momentum_z = 0.5 * Z12 + 0.5 * Z6`.

No H016 weight is changed.

Convert `momentum_z` into a cross-sectional mid-percentile, where the lowest score approaches 0 and highest approaches 1, with ties receiving their midpoint percentile.

## Low-volatility factor

For the same one-year volatility already calculated for H016:

`low_vol_raw = 1 / vol_1y`

Cross-sectionally z-score `low_vol_raw`, then convert that z-score into the same deterministic mid-percentile. Since z-scoring is monotonic, percentile ordering is equivalent to ranking inverse volatility, but both values are retained for audit.

## Composite score

`H017_score = 0.50 * momentum_percentile + 0.50 * low_vol_percentile`

The 50/50 factor weighting is frozen before outcomes and is not optimized.

Rank descending by H017 score, tie by symbol. Select exactly `ceil(10% * eligible_count)`, minimum 30 names.

## Execution

Identical semiannual execution to H016:

- next common NSE session open after decision,
- exit at close of the final common NSE session exactly six calendar months after the decision month,
- Nifty 500 same entry-open to exit-close benchmark,
- selected list frozen before inspecting entry/future bars,
- no-fill cash slots remain in denominator,
- unresolved future structural outcomes receive frozen -100% lower-bound stock return,
- 0.50% round-trip friction diagnostic on filled positions.

## Frozen comparators

At matched selected count and identical point-in-time/outcome policy:

1. H016 dual-horizon momentum factor alone,
2. low-volatility factor alone,
3. raw 12-month momentum,
4. full eligible company cohort,
5. deterministic random matched selections, seed `1717`, 10,000 aggregate draws.

## Independent challenge gates

All must pass:

- all 5 frozen cohorts evaluable,
- >=300 selected company observations,
- fill rate >=98%,
- lower-bound outcome rate <=2%,
- mean selected-company Nifty 500 excess > +2 pp,
- median selected-company Nifty 500 excess >0,
- selected-company Nifty 500 beat rate >=55%,
- at least 4 of 5 cohorts have positive equal-weight excess,
- mean H017 excess >= full eligible company cohort mean excess +2 pp,
- one-sided fixed-seed matched-random p-value for mean excess <=0.05,
- no single corporate-equity ISIN contributes >15% of aggregate positive gross selected return,
- no two consecutive cohorts both have non-positive equal-weight excess,
- mean selected-company excess after frozen 0.50% friction > +1.5 pp.

The H016 momentum-only and low-volatility-only comparators are reported. They are not required individually to underperform in every finite window because H017's primary claim is robust company selection versus the market/full cohort and random selection.

If all gates pass, H017 becomes `HISTORICALLY_ROBUST_PENDING_SECOND_CHALLENGE`. It still cannot enable live capital. A disjoint second historical challenge and prospective paper test remain mandatory.

## Audit rule

After the first H017 score or outcome is calculated, no universe rule, factor definition, factor weight, percentile convention, top-decile operating point, schedule, execution rule, friction assumption or success gate may change under H017-v1.
