# H006 — Nonlinear result-event repricing interactions

## Status

**FROZEN DESIGN — 2026-09-08**

Live capital: **NO**

H006 is a new hypothesis created after H005-v1 failed its source-complete design gate. H005's untouched 2024-10-01 through 2025-06-30 holdout remains unopened.

## Hypothesis

The weak but nonzero discrimination of H005-B may be caused by nonlinear interactions rather than an absence of signal. Large post-result repricings may concentrate when early reaction, volatility, company scale, profitability transitions and accounting changes occur jointly. A low-capacity nonlinear tree ensemble may capture those interactions without adding any new information source.

H006 therefore asks:

> Using exactly the frozen H005-B point-in-time feature vector and exactly one complete post-publication session, can a fixed low-capacity nonlinear model materially concentrate future +25%/20-session movers and positive market-relative outcomes better than H005-B and the simple baselines?

## Information set

H006 uses exactly the H005-B source and feature contract frozen before this hypothesis:

- continuous result changes and profitability transitions,
- earnings-quality diagnostics,
- pre-event price state and liquidity,
- exactly the first complete post-publication session reaction,
- no day-2-or-later information,
- no news, transcript, valuation, sector, management or LLM-derived feature additions.

No new feature may be added after the H006 design result is observed.

## Model

Primary and only H006-v1 model: `sklearn.ensemble.HistGradientBoostingClassifier` with:

- loss: log loss,
- learning rate: 0.05,
- max iterations: 200,
- max leaf nodes: 15,
- min samples leaf: 40,
- L2 regularization: 10.0,
- max bins: 63,
- early stopping: disabled,
- random state: 19,
- balanced sample weights fitted from each training fold only.

Continuous features are clipped to the training fold's 1st/99th percentiles. Binary flags remain binary and unclipped. Missing values remain missing and are handled natively by the histogram model. No standardization, imputation, probability calibration or hyperparameter search is permitted under H006-v1.

## Evaluation

The design period is the same source-complete H005 training/design period. Purged chronological folds and label-end maturity rules are identical to H005. The primary operating bucket is the global retrospective top 10% of out-of-fold H006 scores, with deterministic event-ID tie breaking. Top 5% and 20% are diagnostics only.

H006 is allowed to consume the untouched historical holdout only if its source-complete design diagnostics satisfy all of:

- top-10% recall >= 25%,
- top-10% precision >= 12%,
- prevalence lift >= 2.0x,
- median Nifty 500 20-session excess among selected events > 0,
- both recall and precision exceed source-complete H005-B at the matched top-10% count.

If any design-continuation condition fails, H006-v1 is rejected without opening the holdout.

If H006 reaches the holdout, the frozen historical validation gate remains demanding:

- recall >= 35%,
- precision >= 10%,
- prevalence lift >= 2.5x,
- median lead to +25% >= 3 sessions,
- median Nifty 500 20-session excess > 0,
- matched-count first-session-tape comparison passes,
- no single company contributes >20% of aggregate positive gross close-return P&L,
- no validation calendar quarter has both zero hits and at least five true explosive movers.

Historical success remains paper-only. It cannot authorize live capital without a later prospective cohort frozen before outcomes exist.
