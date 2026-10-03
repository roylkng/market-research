# H013 — Regime-aware risk-adjusted 120/5 momentum

Frozen: 2026-09-08 before any H013 score was calculated.

Status: **FROZEN HISTORICAL CHALLENGE. LIVE CAPITAL DISABLED.**

## Motivation

H011 and H012 both showed positive equal-weight cohort means but weak median-stock performance and sub-50% beat rates. That pattern is consistent with raw momentum selecting volatile right-tail names rather than broad persistent trends. H013 tests a narrower mechanism: scale the 120-session momentum-with-5-session-skip signal by its own realized volatility, without changing the market regime rule or using earnings data.

This is a new hypothesis, not a threshold edit to H011 or H012.

## Challenge windows

H013 is tested on both retained disjoint full-market windows already available from official NSE sources:

1. older window: monthly decisions 2024-12 through 2025-06,
2. later window: monthly decisions 2025-10 through 2026-05.

No H013 risk-adjusted score or H013 cohort return has been calculated before this freeze. These are historical challenges, not prospective validation.

## Universe and regime

Use exactly the same source, complete-bar, INR 2 crore prior-20-session median traded-value, corporate-action, entry-tradability, minimum-200-stock universe and Nifty 500 regime rules frozen for H011/H012.

A cohort is ACTIVE only when Nifty 500 close is above its 120-session simple moving average and Nifty 500 prior-60-session return is positive.

## Primary score

For each eligible stock:

- raw momentum: `r120_skip5 = close[t-5] / close[t-125] - 1`.
- compute 120 common-session daily log returns from close[t-125] through close[t-5].
- realized volatility: sample standard deviation of those daily log returns multiplied by `sqrt(120)`.
- primary score: `risk_adjusted_momentum = r120_skip5 / realized_volatility`.

Reject a stock if the volatility denominator is non-finite or <=0. There is no winsorization and no fitted parameter.

Rank descending by primary score, tie by symbol, and select exactly the top 10% with minimum 20 names.

## Execution

Same as H011/H012:

- next common session open entry,
- 60th holding-session close exit,
- equal-weight arithmetic cohort means,
- Nifty 500 same-date benchmark,
- gross returns only.

## Frozen comparators

At matched selected count per active cohort:

1. raw H011 120/5 momentum,
2. prior-60 momentum,
3. prior-20 momentum,
4. full eligible cohort,
5. fixed-seed matched random selection, seed `113`, 10,000 aggregate draws per challenge window.

## Frozen gates

H013 must pass **both** challenge windows separately and the combined sample.

Per-window gates:

- at least 3 active cohorts,
- at least 250 selected observations,
- mean selected-stock Nifty 500 excess > +2 pp,
- median selected-stock excess > 0,
- selected-stock beat rate >=52%,
- at least two-thirds of active cohorts have positive equal-weight excess,
- H013 mean excess >= raw 120/5 momentum mean excess,
- H013 mean excess >= prior-60 momentum mean excess,
- H013 mean excess >= full eligible cohort mean excess +2 pp,
- one-sided fixed-seed matched-random empirical p-value for mean excess <=0.05,
- no single symbol contributes >15% of aggregate positive gross selected return.

Combined gates:

- >=600 selected observations,
- combined mean Nifty 500 excess > +2 pp,
- combined median selected-stock excess >0,
- combined selected-stock beat rate >=55%,
- no challenge window has negative mean selected-stock excess.

`PROMISING` additionally requires >=60% combined beat rate and >=+4 pp combined mean excess.

## Audit rule

After any H013 result is calculated, the signal, volatility estimator, windows, regime rules, top-decile operating point, execution convention, comparators and gates cannot change under H013-v1. Failure retires H013-v1.
