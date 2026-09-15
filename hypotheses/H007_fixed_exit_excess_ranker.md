# H007 — Fixed-exit market-relative result-event ranker

## Status

**FROZEN DESIGN — 2026-09-08**

Live capital: **NO**

H007 is a new hypothesis. H005 and H006 are retained as failed maximum-excursion classifiers. The historical holdout remains unopened.

## Motivation

H005 and H006 showed a structural mismatch between the label and the investment objective. A stock can touch +25% intraday during the next 20 sessions and still finish the fixed holding period with a negative market-relative return. Both models therefore selected groups with negative median Nifty 500 excess even when they captured some maximum-excursion movers.

H007 changes the target rather than tuning those failed classifiers.

## Hypothesis

> Among sufficiently liquid result events, can the frozen H005-B point-in-time information set rank stocks by the market-relative return actually realized at a fixed 20-session close, rather than by an untradeable future maximum?

## Information set

Exactly the source-complete H005-B features are allowed. No additional news, sector, valuation, transcript, management, day-2 reaction or LLM-derived features may be introduced under H007-v1.

Entry and corporate-action conventions are exactly those frozen in `experiments/H005_result_repricing_ranker/DERIVED_FEATURE_CONVENTIONS.md`.

## Target

Primary continuous target:

`excess_20d_pp = stock_adjusted_session20_close_return_from_entry_open_pct - nifty500_same_dates_open_to_close_return_pct`

The entry is H005-B's next eligible session open after observing exactly one complete post-publication reaction session. The exit is the adjusted close of session 20. This is an OHLC execution proxy, not a claim about intraday fills or transaction costs.

Secondary diagnostics:

- raw stock 20-session close return,
- beat-Nifty-500 rate,
- fraction with excess >= +5 percentage points,
- fraction with raw return >= +10%,
- maximum excursion and drawdown only as diagnostics, not training targets.

## Model

Primary and only H007-v1 model: `sklearn.ensemble.HistGradientBoostingRegressor` with fixed parameters:

- loss: absolute error,
- learning rate: 0.05,
- max iterations: 200,
- max leaf nodes: 15,
- min samples leaf: 40,
- L2 regularization: 10.0,
- max bins: 63,
- early stopping: disabled,
- random state: 23.

Continuous features are clipped to each training fold's 1st/99th percentiles. Binary flags remain binary. Missing values remain missing and are handled natively. There is no hyperparameter search, target winsorization, sample weighting or probability calibration.

## Ranking and design gate

The primary operating point is the global retrospective top 10% of out-of-fold predicted excess return, with deterministic event-ID tie breaking. Top 5% and 20% are diagnostics.

H007 may consume the untouched historical holdout only if the source-complete design diagnostics satisfy all of:

- top-10% median Nifty 500 excess > +2.0 percentage points,
- top-10% mean Nifty 500 excess > +2.0 percentage points,
- top-10% Nifty 500 beat rate > 55%,
- top-10% median raw stock return > 0,
- top-10% median excess exceeds matched-count prior-20-session momentum by at least 1.0 percentage point,
- top-10% median excess exceeds matched-count first-session-tape rank by at least 1.0 percentage point,
- at least two reporting-quarter cohorts with at least 30 selected observations have positive median excess.

Failure of any condition rejects H007-v1 without opening the holdout.

## Frozen historical validation gate

If H007 reaches the untouched 2024-10-01 through 2025-06-30 holdout, the model and preprocessing are frozen before labels are opened. The top-10% holdout selection must satisfy all of:

- median Nifty 500 excess > +2.0 percentage points,
- mean Nifty 500 excess > +2.0 percentage points,
- Nifty 500 beat rate > 55%,
- median raw stock return > 0,
- excess >= +5 percentage points for at least 35% of selected observations,
- matched-count median excess exceeds both momentum and first-session-tape baselines,
- no single company contributes more than 20% of aggregate positive gross close-return P&L,
- no holdout calendar quarter with at least 20 selections has a median excess below -2 percentage points.

Historical success remains `PAPER_ONLY_PENDING_PROSPECTIVE`. A future prospective cohort with a predeclared online threshold/allocation rule is required before any live-capital consideration.
