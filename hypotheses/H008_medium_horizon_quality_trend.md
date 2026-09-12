# H008 — Medium-horizon quality-growth-trend selection

## Status

**FROZEN DESIGN — 2026-09-08 before any 60-session target was computed in this continuation**

Live capital: **NO**

H008 changes both horizon and mechanism after H005-H007 showed that 20-session post-result selection is too noisy. It returns to the original company-selection objective: identify businesses where operating change and an already-forming market trend can compound over several months.

## Hypothesis

> After a result event, companies combining durable operating improvement, reasonable earnings quality, sustained pre-event relative strength, and one complete session of market confirmation will produce superior Nifty 500-relative returns over the next 60 sessions.

The mechanism is medium-horizon continuation, not a short earnings surprise trade.

## Chronology

No H008 60-session labels were inspected before this split was frozen.

- fit period: result publications 2025-10-01 through 2025-12-31;
- design-check period: publications 2026-01-01 through 2026-02-28;
- no March observations are expected from the result-season corpus and no dates are moved to manufacture observations;
- one-shot forward historical validation: publications 2026-04-01 through 2026-05-31, restricted to events whose full 60-session label is present in the already retained market-data window.

The project has previously inspected 20-session labels in these eras, so the April-May test is not represented as pristine untouched evidence about all possible horizons. The 60-session target itself has not been opened or used to choose this model, feature set, split or gate.

## Information set

H008 uses H005-B's point-in-time features plus only the following preregistered medium-horizon features, all ending before entry:

- prior 60-session stock return,
- prior 60-session stock return minus Nifty 500 return over the identical closes,
- sample volatility of the 60 one-session stock returns,
- current exact-quarter operating margin,
- current exact-quarter PAT margin.

No valuation, sector label, transcript, news, management, day-2 reaction or future-derived feature is permitted under H008-v1.

The H005 derived accounting, corporate-action, exact-session and first-complete-reaction conventions remain authoritative.

## Target and execution proxy

H008 uses H005-B timing. Exactly one full post-publication session is observed, then entry is the next eligible session open.

Primary target:

`excess_60d_pp = adjusted_stock_session60_close_return_from_entry_open_pct - nifty500_same_dates_open_to_close_return_pct`

The forward window contains exactly 60 market sessions including the entry session. Missing stock bars do not compress the horizon. The full session-60 date is required.

## Model

Primary and only H008-v1 model: `sklearn.linear_model.HuberRegressor` with fixed parameters:

- epsilon: 1.35,
- alpha: 1.0,
- max_iter: 500,
- tolerance: 1e-5.

Preprocessing is fit only on the training period:

1. continuous features clipped at training 1st/99th percentiles;
2. median imputation plus explicit missingness indicators;
3. standard scaling;
4. binary flags remain numeric 0/1 and are not winsorized.

There is no hyperparameter search or target transformation.

## Baselines

Matched top-10% signal counts:

- prior 60-session relative momentum,
- prior 20-session momentum,
- first-session tape composite frozen under H005,
- accounting-growth composite frozen under H005.

## Design-check gate

The model may proceed from the January-February design check to the April-May one-shot validation only if the design check has at least 100 evaluable events and its top-10% selection satisfies all of:

- median Nifty 500 60-session excess > +3.0 percentage points,
- mean excess > +3.0 percentage points,
- Nifty 500 beat rate > 55%,
- median raw stock 60-session return > 0,
- median excess exceeds matched prior-60-session relative momentum by at least 2.0 percentage points,
- median excess exceeds matched first-session tape by at least 2.0 percentage points.

If any condition fails, H008-v1 is rejected and the April-May 60-session validation target remains unopened.

## One-shot forward historical validation gate

If the design gate passes, refit once on the combined October 2025 through February 2026 fit+design data, freeze preprocessing and coefficients, and score April-May exactly once. At top 10%, require all of:

- at least 100 evaluable validation events,
- median Nifty 500 excess > +3.0 percentage points,
- mean excess > +3.0 percentage points,
- Nifty 500 beat rate > 55%,
- median raw return > 0,
- at least 35% of selections have excess >= +5 percentage points,
- median excess beats both matched prior-60 relative momentum and first-session tape,
- no single company contributes >20% of aggregate positive gross close-return P&L.

A historical pass remains `PAPER_ONLY_PENDING_PROSPECTIVE`. An online prospective ranking/allocation rule must be frozen before future outcomes for live-capital consideration.
