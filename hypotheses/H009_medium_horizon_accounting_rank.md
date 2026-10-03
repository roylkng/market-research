# H009 — Medium-horizon accounting-change rank

## Status

**FROZEN FOR ONE-SHOT FORWARD HISTORICAL VALIDATION — 2026-09-08**

Live capital: **NO**

H009 is promoted from a baseline that was explicitly preregistered before H008's 60-session design-check outcomes were computed. The January-February result is therefore design evidence only. The April-May 2026 60-session outcomes remain unopened at H009 freeze time.

## Hypothesis

> The market may incorporate broad quarterly operating improvement over several months rather than within 20 sessions. A simple equal-weight cross-sectional rank of revenue growth, operating-profit growth, PAT growth and margin change may identify result-event companies with superior fixed 60-session Nifty 500-relative returns.

The purpose of H009 is to test the simplest mechanism suggested by H008. It does not add a learned model or new features.

## Signal

For each event, compute the four already-frozen point-in-time features:

1. revenue YoY %,
2. operating-profit YoY %,
3. PAT YoY %,
4. operating-margin change in percentage points.

Using only the combined October 2025 through February 2026 fit+design feature distribution, convert each feature to an empirical mid-CDF percentile. A missing value receives the training-period median before the percentile is computed. The H009 score is the unweighted arithmetic mean of the four feature percentiles.

There are no thresholds, fitted coefficients, nonlinear transforms, sector adjustments or hyperparameters. Equal weights are frozen. Event-ID breaks exact score ties.

## Timing and target

Use exactly H008/H005-B timing for comparability. Observe one complete post-publication session, then enter at the next eligible session open. The signal itself does not use the reaction session, but the entry timing is not moved earlier after seeing the design result.

Primary target:

`excess_60d_pp = adjusted_stock_session60_close_return_from_entry_open_pct - nifty500_same_dates_open_to_close_return_pct`

Exactly 60 market sessions including entry are required. Missing stock bars do not compress the horizon. Corporate-action and execution conventions remain those frozen in H005's derived-feature convention.

## One-shot validation cohort

The validation cohort is fixed before its 60-session outcomes are computed:

- result publication timestamp from 2026-04-01 00:00 through 2026-05-31 23:59:59 Asia/Kolkata;
- otherwise the same source-complete primary-liquidity and exact-session reconstruction rules;
- only observations whose full 60-session window exists in the already retained market-data corpus are evaluable;
- no replacement dates if coverage is poor.

## Primary operating point

Top 10% H009 score within the completed validation cohort, deterministic event-ID tie break. Top 5% and 20% may be reported only as diagnostics and cannot replace the primary gate.

## Frozen validation gate

H009 passes the one-shot forward historical validation only if all are true at top 10%:

- at least 100 total evaluable validation events;
- median Nifty 500 60-session excess > +3.0 percentage points;
- mean Nifty 500 excess > +3.0 percentage points;
- Nifty 500 beat rate > 55%;
- median raw stock 60-session return > 0;
- at least 35% of selections have excess >= +5 percentage points;
- H009 median excess exceeds matched top-10% prior-20-session momentum;
- H009 median excess exceeds matched top-10% first-session-tape composite;
- no single company contributes more than 20% of aggregate positive gross 60-session close-return P&L.

Diagnostics must include the unconditional cohort, prior-60 relative momentum and exact selected/missed rows. No gate may be changed after outcomes are opened.

## Evidence classification

A pass is `FORWARD_HISTORICAL_PROMISING`, not live validation. The project previously inspected shorter-horizon outcomes in the same era, so this historical period is not represented as pristine prospective evidence. A later prospective paper cohort with a predeclared online threshold and allocation rule is mandatory before live-capital consideration.
