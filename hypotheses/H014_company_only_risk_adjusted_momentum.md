# H014 — Company-only regime-aware risk-adjusted momentum

Frozen: 2026-09-08 before any company-only H014 cohort result was calculated.

Status: **FROZEN. LIVE CAPITAL DISABLED.**

## Motivation

H013's signal passed its numerical historical gates but its implementation admitted ETF units because NSE `EQ` series alone was not sufficient to establish operating-company common equity. That invalidated H013 as a company-selection proof.

H014 keeps the already frozen H013 signal and regime mechanism but changes the universe contract explicitly. This is a new hypothesis. No H013 result may be relabelled as H014 evidence.

## Company-only identity contract

A selected security must satisfy all of:

- NSE cash-market `EQ` series,
- retained stock-instrument daily bar under the project's official NSE market-data contract,
- nonempty 12-character ISIN beginning with `INE`,
- one candidate security per corporate-equity ISIN at each decision. If more than one symbol maps to the same eligible ISIN, keep only the lexicographically smallest symbol before ranking,
- complete required common-session bars,
- median prior-20-session traded value >= INR 2 crore,
- unresolved structural corporate actions excluded,
- flat/no-trade entry bars excluded.

ISINs beginning with mutual-fund/unit prefixes such as `INF` are excluded. REIT/InvIT or other non-company securities that do not satisfy the full common-equity contract are excluded rather than guessed.

No sector, earnings, valuation, market-cap or nominal-price filter.

## Signal and regime

Unchanged from H013:

`risk_adjusted_momentum = (close[t-5] / close[t-125] - 1) / (sample_std(120 daily log returns) * sqrt(120))`

Cohort is active only when both:

- Nifty 500 close > 120-session SMA including the decision close,
- Nifty 500 prior-60-session return > 0.

Rank descending, tie by symbol, select exact top 10%, minimum 20 names and minimum 200 eligible company equities.

## Execution

- monthly decision at final retained common NSE session,
- next common-session open entry,
- 60th holding-session close exit,
- Nifty 500 same-date benchmark,
- equal-weight gross cohort diagnostics.

## Historical challenge windows

Run the corrected company-only implementation on both source-audited windows without changing any threshold:

1. older challenge: 2024-12 through 2025-06 decisions,
2. later challenge: 2025-10 through 2026-05 decisions.

Per-window gates are the same as H013:

- >=3 active cohorts,
- >=250 selected observations,
- mean selected-stock Nifty 500 excess > +2 pp,
- median selected-stock excess >0,
- selected-stock beat rate >=52%,
- >=2/3 active cohorts positive equal-weight excess,
- H014 mean excess >= raw 120/5 comparator,
- H014 mean excess >= prior-60 comparator,
- H014 mean excess >= full eligible company-equity cohort +2 pp,
- fixed-seed matched-random p <=0.05,
- max single-company positive-return contribution <=15%.

Combined gates:

- >=600 selected observations,
- mean excess > +2 pp,
- median excess >0,
- beat rate >=55%,
- neither window has negative mean excess.

## Independent robustness

If the corrected two-window gates pass, H014 must also pass an earlier 2023-01 through 2024-03 monthly challenge using official legacy NSE bhavcopies, the identical signal and regime rule, and the same company-only ISIN contract. The already frozen H013 independent-robustness numerical gates are reused, with fixed random seed `1414`.

## Prospective requirement

Even a historical and independent-robustness pass remains paper-only. H014 must start a fresh prospective clock because H013 prospective evidence, if any, would use a contaminated universe.

## Audit rule

After any H014 result is calculated, the company-identity rule, signal, regime thresholds, liquidity floor, top-decile operating point, execution convention, 60-session horizon and gates cannot change under H014-v1. Failure creates a new hypothesis rather than a patch.
