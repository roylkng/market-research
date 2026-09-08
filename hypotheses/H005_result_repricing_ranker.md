# H005 — Result-event repricing ranker

## Status

**FROZEN DESIGN — 2026-09-08**

Live capital: **NO**

H005 is a new hypothesis. It does not modify H004 after H004's historical failure.

## Motivation

H004-HR002 showed that requiring spectacular accounting growth before considering a stock is too restrictive. In the reconstructed 2025-10-01 through 2026-07-31 earnings-event set, most future +25%/20-session movers did not satisfy H004's earnings-inflection threshold. A broad result-event tape baseline had much higher recall but poor precision.

H005 therefore asks a different question:

> Among all sufficiently liquid companies reporting results, can a point-in-time ranker identify the subset most likely to undergo a large repricing during the next 20 sessions, using the result, earnings quality, the stock's pre-event state, and only the earliest observable market reaction?

The objective is not to prove that strong earnings outperform. It is to estimate **repricing probability**.

## Scientific separation

The H004-HR002 event window (2025-10-01 through 2026-07-31) is a **design/training set only** for H005 because its outcomes have already been inspected.

It may be used for:

- feature engineering,
- model fitting,
- cross-validation,
- calibration,
- failure analysis.

It may **not** be reported as H005 validation.

The first historical H005 validation set must be chronologically earlier and untouched during model design. Target validation window: result events from 2024-10-01 through 2025-06-30, subject to exact NSE filing/market-data reconstruction and adequate prior-year source coverage.

The 2026-08-31 through 2026-09-07 H004 design examples remain excluded from all validation claims.

## Universe

Primary:

- NSE main-board common equities in normal EQ series,
- median prior-20-session traded value >= ₹2 crore,
- at least 60 prior trading sessions,
- exact result publication timestamp/date retained,
- adequate forward price data for historical labels.

Secondary discovery tier may use >=₹25 lakh prior-20-session median traded value but is never pooled into primary statistics.

No nominal share-price threshold.

## Decision timing

Two frozen variants are evaluated independently:

### H005-A — information-only

Decision at the conservative result-event snapshot before using any post-publication stock reaction.

Allowed market-state features stop at the last price observable before publication.

### H005-B — early-recognition

Decision at the first daily 20:00 Asia/Kolkata snapshot after at least one full eligible trading session has occurred following publication.

This variant may use at most the first post-publication session of stock/volume reaction. It may not use day 2+ information.

H005-B exists because the H004 reconstruction showed that a broad result-event tape signal captured many movers that accounting thresholds missed. One early session is treated as confirmation/context, not as a requirement that momentum already be mature.

## Target

Primary binary label:

`explosive_20d_v1 = max(high over next 20 eligible sessions from executable entry) / entry_price - 1 >= 0.25`

Secondary:

- max +20% within 10 sessions,
- max +40% within 20 sessions,
- 5/10/20-session close return,
- Nifty 500 excess return,
- sector excess return,
- maximum adverse excursion before maximum favourable excursion,
- sessions to +25%.

## Frozen feature families

All features must be point-in-time and numeric or deterministically encoded. Missingness is retained explicitly; no future-derived imputation.

### 1. Continuous result change

- revenue YoY %,
- operating EBITDA/profit YoY %,
- PAT YoY %,
- operating-margin change in percentage points,
- loss-to-profit / profit-to-loss flags,
- current absolute PAT scale,
- current revenue scale.

No minimum growth threshold is required.

### 2. Earnings quality

- non-operating income / PBT,
- exceptional-item share where available,
- tax-effect diagnostics,
- operating-vs-reported profit divergence,
- tiny-base flag,
- negative-profit flag.

Quality variables are not hard exclusions except for invalid/unusable accounting rows.

### 3. Pre-event market state

- prior 1-session return,
- prior 5-session return,
- prior 20-session return,
- distance from prior 60-session high,
- prior-20-session volatility,
- median prior-20-session traded value,
- market-cap/liquidity bucket when point-in-time data are available.

Pre-existing momentum is **not** a hard reject. The model learns whether modest prior movement helps or hurts repricing probability.

### 4. H005-B first-session recognition only

- first eligible post-publication session return,
- first-session volume / prior-20-session median,
- first-session traded-value / prior-20-session median,
- first-session intraday range when available,
- first-session close location within daily range,
- first-session relative return versus Nifty 500,
- first-session relative return versus sector benchmark when available.

No second-session or later reaction may enter H005-B.

### 5. Event context, only when reconstructable point-in-time

- H002-style seasonal EPS surprise where exact pre-filing expectation exists,
- quantified guidance/corporate catalyst flags from filings/transcripts,
- balance-sheet capacity/leverage,
- valuation relative to sector/company history,
- sector/regime features.

These are challenger additions. The core model must be evaluated without them first so unavailable semantic/context data cannot silently determine the result.

## Frozen model protocol

Primary model: **regularized logistic regression** predicting `explosive_20d_v1`.

Why:

- rare-event sample is modest,
- coefficients are auditable,
- continuous features can be standardized using training data only,
- regularization limits unstable threshold hunting,
- probability/rank output directly supports recall-at-signal-count evaluation.

Training protocol:

- class weights: inverse-frequency balanced,
- continuous features winsorized to training-set 1st/99th percentiles only,
- median imputation fitted on training set only plus explicit missing indicators,
- standardization fitted on training set only,
- L2 regularization,
- regularization strength chosen only within training data using blocked chronological cross-validation,
- candidate C values fixed at `[0.01, 0.1, 1.0, 10.0]`,
- optimization metric: average precision, with recall-at-top-decile as recorded secondary model-selection metric.

No tree/boosting/neural challenger may replace the primary model after viewing holdout returns. Any later nonlinear model is H006 or a separately frozen H005 challenger before its own untouched validation.

## Ranking / signal counts

The primary output is a probability ranking, not an arbitrary probability cutoff.

Predeclared evaluation buckets:

- top 5% of eligible result events,
- top 10%,
- top 20%.

Primary operating point: **top 10%**.

This keeps signal count stable and makes comparison to baselines fair.

## Baselines

1. result-event first-session tape ranker,
2. H004 strict earnings-inflection Stage 1,
3. raw earnings-growth composite,
4. pre-event momentum-only ranker,
5. random ranking prevalence baseline.

Baseline signal counts must be matched to H005's top-10% operating point where applicable.

## Historical validation success gate

On the untouched historical validation window, H005-B top-10% must satisfy all of:

- recall of executable future +25%/20-session movers >= 35%,
- precision >= 10%,
- lift over unconditional explosive-mover prevalence >= 2.5x,
- median lead time to +25% >= 3 sessions,
- median 20-session Nifty 500 excess return > 0,
- recall exceeds first-session-tape baseline at matched signal count OR precision is >=2x the tape baseline while retaining at least 90% of its recall,
- no single company contributes >20% of aggregate positive P&L,
- no validation calendar quarter has both zero hits and >=5 true explosive movers.

A stronger `PROMISING` classification requires validation recall >=50% and precision >=15% without failing any other gate.

H005-A is reported independently; it is especially valuable if it achieves meaningful lift without any post-result reaction, but H005-B is the primary tradability hypothesis.

## Prospective requirement

Even if historical validation passes, live capital remains disabled.

Promotion requires a prospective paper cohort after freeze. Historical reconstruction cannot create out-of-sample evidence for dates whose outcomes were already inspected during design.

## Prohibited actions

- do not tune H004 thresholds and rename the result H005,
- do not inspect validation outcomes while changing H005 features/model protocol,
- do not choose a different model because it performs better on the holdout,
- do not remove false positives post hoc,
- do not count non-executable upper-circuit entries as hits,
- do not use day-2-or-later tape features in H005-B,
- do not use current reconstructed knowledge that was unavailable at the historical decision timestamp.
