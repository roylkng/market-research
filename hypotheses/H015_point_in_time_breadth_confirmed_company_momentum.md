# H015 — Point-in-time breadth-confirmed company momentum

Frozen: 2026-09-08 before any H015 score or outcome was calculated in the 2023-01 through 2024-03 challenge period.

Status: **FROZEN INDEPENDENT HISTORICAL CHALLENGE. LIVE CAPITAL DISABLED.**

## Why H015 exists

H011-H014 exposed two independent problems:

1. raw `EQ` series admitted ETF/unit securities, so a supposed company-selection edge could actually be repeated commodity exposure,
2. historical eligibility required future holding-window bars and future corporate-action information, allowing survivorship/future-tradability leakage into the ranked universe.

H015 starts from a new point-in-time contract. H011-H014 windows are design evidence only. Their outcomes cannot validate H015.

The H014 design diagnostics also showed that Nifty 500 trend alone can remain positive while breadth narrows sharply. H015 therefore requires company breadth confirmation in addition to the broad-index trend rule.

## First challenge period

Monthly decisions from **2023-01 through 2024-03**, using the final retained common NSE trading session of each calendar month.

Official market source history begins no later than 2022-06-01 to support the 125-session lookback and extends through at least 2024-06-30 for the 60-session exits.

No H015 company-only monthly ranking or H015 return from this period has been calculated before this freeze.

## Point-in-time company universe

At decision session `t`, selection eligibility may inspect data only through `t`.

A candidate must satisfy:

- NSE cash-market `EQ` series stock bar at `t`,
- 12-character ISIN beginning with `INE`,
- one candidate per decision-day ISIN, tie by lexicographically smallest symbol,
- complete stock bars on every common session from `t-125` through `t`,
- finite positive OHLC,
- median traded value over `t-19 ... t` >= INR 2 crore,
- no unresolved structural corporate action effective in `t-125 ... t`.

Source-backed split, bonus or consolidation actions already effective by `t` may either be correctly adjusted into a common share basis or conservatively exclude the affected security. This choice must be implemented deterministically before H015 outcome inspection and reported. Future actions after `t` may **not** affect selection eligibility.

Selection may not inspect:

- whether a next-session bar exists,
- whether an exit-session bar exists,
- whether the company later suspends/delists,
- future corporate actions,
- future returns or benchmark outcomes.

At least 200 eligible company equities are required for an active cohort.

## Market regime

The broad-index conditions remain:

1. Nifty 500 close at `t` > simple mean of Nifty 500 closes over `t-119 ... t`,
2. Nifty 500 close at `t` / close at `t-60` - 1 > 0.

## Breadth confirmation

Breadth is calculated only from the point-in-time eligible company list at `t`.

For every eligible company:

- `mom60_now = close[t] / close[t-60] - 1`,
- `mom60_20_sessions_ago = close[t-20] / close[t-80] - 1`.

Define:

- `breadth_now = fraction(mom60_now > 0)`,
- `breadth_20_sessions_ago = fraction(mom60_20_sessions_ago > 0)`,
- `breadth_change_20 = breadth_now - breadth_20_sessions_ago`.

Breadth confirms the cohort when either:

- `breadth_now >= 0.55`, or
- `breadth_change_20 >= 0.10`.

A cohort is `ACTIVE` only when both broad-index conditions and the breadth-confirmation condition pass. Otherwise it is `REGIME_OFF` and selects no companies.

These breadth thresholds were motivated by H014 design diagnostics. They are therefore fixed before the independent 2023-2024 challenge and cannot be tuned from that challenge.

## Company score

Unchanged risk-adjusted medium-horizon trend mechanism:

- `raw120_skip5 = close[t-5] / close[t-125] - 1`,
- daily log returns from `t-125` through `t-5`,
- `vol120 = sample_std(daily_log_returns) * sqrt(120)`,
- `score = raw120_skip5 / vol120`.

Reject only if the volatility denominator is non-finite or <=0. Rank descending, tie by symbol. Select exactly `ceil(10% * eligible_count)`, minimum 20 names.

There is no fitted model and no optimized coefficient.

## Selection / execution separation

The complete selected list is frozen before inspecting `t+1` or any later market data.

### Entry

Target entry is the next common NSE session open.

- If a valid tradable bar exists, paper entry occurs at that open.
- If the security has no usable next-session bar or only a non-tradable flat/no-offer proxy, the candidate remains in the selected denominator and its portfolio slot stays in cash for the entire frozen horizon: stock return = 0. This is reported as `NO_FILL`.

A no-fill can never be removed and replaced by the next-ranked company.

### Exit

Target exit is the close of the 60th holding session, with entry session counted as holding session 1.

- Source-backed split/bonus/consolidation share changes after selection are applied in the outcome layer only.
- Future rights, merger, demerger, delisting or other structural events that cannot be valued deterministically from retained source evidence remain in the denominator and receive the conservative primary lower-bound stock return of **-100%**.
- A filled position with no usable exact exit-session bar and no deterministically resolved terminal value also receives primary lower-bound stock return **-100%**.

Report unresolved/lower-bound outcomes separately. They are never pre-selection exclusions.

## Benchmark and friction

Benchmark return is Nifty 500 from the target entry-session open to the target exit-session close.

Primary historical diagnostics are gross. Also report a fixed 0.50% round-trip friction deduction on filled stock positions. `NO_FILL` cash slots incur no trade friction.

## Frozen comparators

Use the identical point-in-time company universe, active months, selected count and post-selection outcome policy:

1. raw 120/5 momentum,
2. prior-60 momentum,
3. prior-20 momentum,
4. full eligible company cohort,
5. deterministic random matched selections with seed `1515` and 10,000 draws.

## Independent challenge gates

All must pass:

- >=5 ACTIVE monthly cohorts,
- >=500 selected company observations,
- next-session fill rate >=98%,
- unresolved/lower-bound outcome rate <=2%,
- gross mean selected-stock Nifty 500 excess > +2 pp,
- gross median selected-stock excess > 0,
- gross selected-stock beat rate >=52%,
- >=2/3 of active cohorts have positive equal-weight gross excess,
- H015 mean excess >= raw 120/5 comparator mean excess,
- H015 mean excess >= prior-60 comparator mean excess,
- H015 mean excess >= full eligible company cohort mean excess +2 pp,
- fixed-seed matched-random one-sided empirical p-value for mean excess <=0.05,
- no single corporate-equity ISIN contributes >15% of aggregate positive gross selected return,
- no calendar quarter containing >=2 active cohorts has non-positive median active-cohort excess.

Cost sanity gate:

- mean selected-stock excess after the frozen 0.50% friction deduction > +1.5 pp.

If every gate passes, H015 is classified `HISTORICALLY_ROBUST_PENDING_PROSPECTIVE`. Live capital remains disabled and a fresh prospective paper clock begins.

## Audit rule

After the first H015 2023-2024 outcome is calculated, no company-identity rule, point-in-time eligibility rule, breadth threshold, signal definition, regime rule, operating percentile, execution fallback, horizon, comparator, friction assumption or success gate may change under H015-v1.
