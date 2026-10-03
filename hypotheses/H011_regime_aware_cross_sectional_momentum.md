# H011 — Regime-aware cross-sectional momentum

Frozen: 2026-09-08 before any H011 cohort return was calculated.

Status: **FROZEN HISTORICAL CHALLENGE. LIVE CAPITAL DISABLED.**

## Why this is a new hypothesis

H010 rejected the claim that conditioning result events on strong prior-60-session relative momentum is regime-stable. The next question removes the result-event gate entirely. H011 asks whether medium-horizon cross-sectional momentum works across the full sufficiently liquid NSE EQ universe only while the broad market is in a supportive trend regime.

This is not a tuning variant of H010. It changes the sampling mechanism from result events to fixed monthly market-wide rebalances and makes market regime an explicit predeclared condition.

## First historical challenge window

Monthly decisions from **2025-10-01 through 2026-05-31**. The exact decision is the last retained common NSE trading session of each calendar month. Required price history begins before this window and 60-session exits may extend through 2026-08-31.

This window has been used in other project research, so success is not prospective evidence. However, no H011 monthly full-market cohort returns were calculated before this freeze. If it passes, H011 still requires a prospective paper phase.

## Universe at each decision

- NSE cash-market `EQ` series stocks present in the retained official UDiFF bhavcopy.
- Complete bars on every common trading session needed by the frozen 125-session signal lookback, prior-20 liquidity window, entry and 60-session holding window.
- Median traded value over the 20 common sessions ending at the decision >= INR 2 crore.
- Positive finite OHLC and turnover data.
- No unresolved share-basis corporate action from the start of the signal lookback through the exit. If a split, bonus, consolidation, rights issue, demerger or other structural action cannot be transformed from retained source evidence without judgment, reject the stock for that cohort.
- Flat/no-trade entry bars are rejected.

No nominal share-price, market-cap, sector, earnings, valuation or analyst filter.

## Regime rule

The cohort is **ACTIVE** only when both are true on the decision session:

1. Nifty 500 close > simple mean of the previous 120 common-session Nifty 500 closes including the decision close.
2. Nifty 500 close / Nifty 500 close 60 common sessions earlier - 1 > 0.

Otherwise the cohort is `REGIME_OFF` and produces no stock selections. Regime-off months are reported but excluded from active-stock selection statistics. They cannot be retrospectively re-enabled.

## Signal

For every eligible stock in an active cohort:

`momentum_120_skip5 = close[t-5] / close[t-125] - 1`

where `t` is the monthly decision session and positions are indexed on the common NSE session calendar.

Rank descending within the cohort. Break equal scores by symbol. Select exactly `ceil(10% * eligible_count)`, with a minimum of 20 names required for an active cohort. If fewer than 200 eligible stocks exist, the cohort fails coverage and produces no selection.

There is no fitted model and no hyperparameter search.

## Execution and outcome

- Entry: next common session open after the monthly decision.
- Exit: close of the 60th holding session, with the entry session counted as holding session 1.
- Stock return: `exit_close / entry_open - 1`.
- Nifty 500 benchmark: same entry-session open to same exit-session close.
- Excess return: stock return minus Nifty 500 return.
- Cohort stock return and excess: equal-weight arithmetic mean across selected stocks.

Transaction costs, taxes and slippage are not included in the first gross edge test. A historical pass therefore remains paper-only.

## Frozen comparators

At exactly the H011 selected count for every active cohort:

1. prior-20-session stock return rank,
2. prior-60-session stock return rank,
3. deterministic random matched selections using seed `111` and 10,000 draws per aggregate significance test,
4. the full eligible cohort.

No comparator may be used to redefine H011 after results are viewed.

## Frozen first-challenge gates

All must pass:

- at least 4 active monthly cohorts,
- at least 200 selected stock-observations total,
- median active-cohort Nifty 500 excess > +2.0 percentage points,
- mean selected-stock Nifty 500 excess > +2.0 percentage points,
- median selected-stock Nifty 500 excess > 0,
- selected-stock Nifty 500 beat rate >= 55%,
- at least 75% of active cohorts have positive equal-weight excess,
- H011 mean selected-stock excess >= prior-20 comparator mean excess + 1.0 percentage point,
- H011 mean selected-stock excess >= prior-60 comparator mean excess,
- H011 mean selected-stock excess >= full eligible cohort mean excess + 2.0 percentage points,
- one-sided fixed-seed matched-random empirical p-value for mean excess <= 0.05,
- no single symbol contributes >15% of aggregate positive gross selected-stock P&L,
- no calendar quarter containing >=2 active cohorts has non-positive median active-cohort excess.

A stronger `PROMISING` designation additionally requires median active-cohort excess >= +4 pp and selected-stock beat rate >=60%.

## Audit rule

After the first H011 cohort outcome is calculated, the regime thresholds, 120/5 signal window, top-decile operating point, liquidity floor, execution convention, 60-session horizon, comparators and gates cannot change under H011-v1.

Failure retires H011-v1. Any subsequent momentum rule is a new hypothesis.
