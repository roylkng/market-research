# H004 experiment specification

## Status

FROZEN before broad historical replay and before any prospective scoring after 2026-09-08.

The recent explosive-mover study covering 2026-08-31 through 2026-09-07 is a **design set** only. It was used to identify failure modes and feature families. It is excluded from validation statistics.

## Unit of observation

One eligible company at one daily decision timestamp.

## Decision timestamp

Primary decision snapshot: 20:00 Asia/Kolkata on each trading day.

Information published after 20:00 is first eligible at the next decision snapshot. Intraday announcements are not traded intraday in the primary test; they are first eligible at the next session after the daily snapshot. This conservative convention prevents timestamp ambiguity.

## Universe

### Primary executable universe

- NSE main-board common equities in normal EQ-series trading,
- excludes SME, ETF, REIT, InvIT, preference-share and suspended securities,
- median prior-20-session traded value >= ₹2 crore,
- at least 60 prior sessions of price history.

### Secondary discovery universe

Same exclusions, but median prior-20-session traded value >= ₹25 lakh. Discovery-tier results are paper-only and never pooled with primary executable performance.

No nominal share-price cut-off is permitted.

## Pre-momentum eligibility

At Stage-1 decision time:

- prior 5-session return < 10%,
- prior 20-session return < 20%,
- previous trading-session return < 8%.

For a fresh public catalyst published after the prior close, only returns observable before that catalyst timestamp are used.

## Stage 1: information-driven watchlist

At least one anchor is required.

### A. Earnings-inflection anchor

Primary deterministic version:

- revenue YoY >= 20%,
- operating profit / EBITDA YoY >= 30%,
- PAT YoY >= 40%,
- and either operating margin improvement >= 1 percentage point or a loss-to-profit transition.

A company that meets three of the four numerical tests can still qualify only if a quantified management catalyst independently reaches catalyst grade 3 or 4.

### B. Turnaround anchor

All required:

- prior-year comparable period was loss-making or operating margin <= 3%,
- current loss narrows by >= 50% or current operating margin improves by >= 2 percentage points,
- revenue YoY >= 5%,
- no material deterioration in net debt / liquidity that plausibly explains the accounting improvement.

### C. Corporate-catalyst anchor

Catalysts are graded before any return inspection.

Grade 4 examples:

- announced change of control / strategic acquisition,
- regulatory approval that opens a material new market,
- order value >= 25% of trailing-12-month revenue,
- commercial commissioning or quantified capacity addition >= 25% of existing capacity,
- explicit management guidance increase >= 20% for a material financial/operating metric.

Grade 3 examples:

- order value 10% to <25% of trailing revenue,
- quantified network / capacity expansion of 10% to <25%,
- first commercial operation of a material new business,
- quantified new-product/customer ramp with a near-term financial horizon.

Grades 1–2 do not independently create a Stage-1 signal.

## Earnings-quality guardrails

The following are penalties / rejection diagnostics, not positive features:

- other income or exceptional gains >30% of PBT,
- PAT growth generated primarily by tax reversal, deconsolidation or asset sale,
- absolute quarterly PAT < ₹2 crore in the primary universe,
- rising promoter pledge / encumbrance,
- qualified audit opinion or unresolved auditor resignation,
- negative operating cash flow inconsistent with the claimed earnings inflection,
- management explicitly states the strong quarter is non-recurring or one-off.

The secondary discovery universe may retain tiny-profit companies, but they are labelled `SPECULATIVE_BASE_EFFECT` and evaluated separately.

## Context features

These cannot create a signal without an anchor:

- sector breadth / relative strength,
- documented FII/DII sector flow,
- valuation versus sector median and the company's own trailing history,
- net cash / leverage capacity,
- free-float / market-cap elasticity.

## Expectation-gap feature

For earnings events at least three sessions old, a strong information anchor receives an expectation-gap flag when the event-to-decision return remains <= 7% and the pre-momentum eligibility still holds.

This captures cases where the information changed but the stock has not yet materially repriced.

## Stage 2: early execution trigger

Stage 2 is evaluated only for companies already in Stage 1.

A trigger requires at least two of:

1. one-day return between +2% and +8%,
2. volume >= 2.0x prior-20-session median,
3. delivery ratio >= 1.5x prior-20-session median when delivery data is available,
4. stock return exceeds its sector index by >= 2 percentage points that day,
5. close is within 5% of the prior 60-session high after having been farther away at Stage 1.

Hard restrictions:

- an upper-circuit close cannot itself be the first valid executable trigger,
- prior 5-session return must remain <15% at trigger time,
- if offered liquidity is absent or one-sided circuit conditions prevent realistic execution, mark `NOT_EXECUTABLE`.

## Entry and outcome

Entry: first realistically executable price in the first 30 minutes of the next trading session after a valid Stage-2 trigger. If only daily data are available during historical reconstruction, next-session open is used and the observation is tagged `OPEN_PROXY`.

Primary label:

```text
explosive_20d_v1 = max(high over next 20 sessions) / entry_price - 1 >= 0.25
```

Secondary labels:

- `explosive_10d_20 = max_10d_return >= 20%`,
- `explosive_20d_40 = max_20d_return >= 40%`,
- 5/10/20-session close returns,
- Nifty 500 excess return,
- sector excess return,
- maximum adverse excursion before maximum favourable excursion.

## Evaluation hierarchy

Primary:

1. recall of future executable `explosive_20d_v1` movers,
2. precision of Stage-2 triggers,
3. median lead time before +25%.

Secondary:

- Stage-1 precision,
- executable rate,
- false positives,
- missed-mover taxonomy,
- return distribution and drawdown,
- winner concentration,
- sector stability,
- market-cap and liquidity-tier stability.

## Baselines

H004 must beat or add material recall versus:

- earnings-growth-only baseline derived from H001-style accounting features,
- momentum-only baseline using prior 5/20-session return and volume,
- catalyst-only baseline,
- sector-relative momentum baseline.

## Historical replay

Historical replay may be reconstructed for periods before 2026-09-08 but is not out-of-sample evidence.

The 2026-08-31 to 2026-09-07 design set is excluded entirely from headline replay metrics.

The first prospective cohort begins with the first decision snapshot after this specification is frozen.

## Success gate

No live capital. For a future research promotion, require all of:

- primary-universe explosive-mover recall >= 50%,
- Stage-2 precision >= 20%,
- median lead time >= 2 sessions,
- positive median 20-session excess return versus Nifty 500,
- no single company contributes >20% of aggregate positive P&L,
- results remain directionally positive across at least four distinct calendar quarters,
- materially better recall than the momentum-only baseline at comparable signal count.

Thresholds are frozen before replay and may not be optimized on the design set.
