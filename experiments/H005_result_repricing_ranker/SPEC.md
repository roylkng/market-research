# H005 experiment specification — result-event repricing ranker

Status: **FROZEN DESIGN**  
Frozen: 2026-09-08  
Live capital allowed: **NO**

This specification operationalizes `hypotheses/H005_result_repricing_ranker.md`.

## Design evidence already seen

H004-HR002 (2025-10-01 through 2026-07-31) is contaminated for H005 validation because its labels were inspected while designing H005. It is therefore training/design only.

Observed H004-HR002 facts that motivated H005:

- 2,182 primary evaluable result events,
- 77 future +25%/20-session movers,
- H004 Stage-1 recall ~10.4%,
- H004 Stage-2 precision ~4.9%,
- broad result-event tape baseline recall ~61%, but precision only ~3%,
- most H004 misses had no strict earnings-inflection anchor.

These figures may motivate the model but may not be reported as H005 validation.

## Required historical split

Training/design:

- result events 2025-10-01 through 2026-07-31.

Untouched validation target:

- result events 2024-10-01 through 2025-06-30.

If exact exchange-source coverage makes that target materially incomplete, the run must stop and declare `VALIDATION_COVERAGE_INSUFFICIENT`; the validation dates may not be silently moved after looking at returns.

## Observation identity

One company + result publication event. Duplicate revised filings are resolved point-in-time using the latest eligible original/revision known at the frozen decision timestamp; revisions published later cannot rewrite the earlier observation.

## Primary universe

- NSE EQ-series main-board common equity,
- median prior-20-session traded value >= ₹2 crore,
- >=60 prior sessions,
- valid result source and timestamp,
- valid forward market-data window for historical labels.

## Labels

Primary: executable maximum forward return >=25% within 20 sessions.

Entry conventions:

- H005-A: next eligible session open after information-only decision.
- H005-B: next eligible session open after the first complete post-publication session used for recognition features.
- upper-circuit/no-offer observations are flagged non-executable rather than assigned impossible fills.

## H005-A feature vector

Core numeric features:

`revenue_yoy_pct, operating_profit_yoy_pct, pat_yoy_pct, margin_change_pp, quarterly_pat_crore, revenue_scale_log, nonoperating_share_of_pbt, prior_1d_return_pct, prior_5d_return_pct, prior_20d_return_pct, distance_to_60d_high_pct, prior_20d_volatility_pct, median_20d_traded_value_log`

Core flags:

`loss_to_profit, profit_to_loss, tiny_base, negative_pat, quality_warning_nonoperating`

## H005-B additions

Only first eligible post-publication session:

`reaction_1d_pct, reaction_volume_ratio_20d, reaction_traded_value_ratio_20d, reaction_range_pct, reaction_close_location, reaction_nifty500_excess_pp`

Sector-relative first-session return is included only if a point-in-time sector mapping and exact historical sector benchmark are available for the entire validation protocol. Otherwise it is omitted from both training and validation.

## Missingness

- Missing values receive training-fitted median imputation.
- Each imputed feature gets an explicit missingness indicator.
- Features unavailable for >40% of training observations are removed before fitting and that removal is frozen before holdout scoring.
- No target-conditioned imputation.

## Preprocessing

Fit on training folds only:

1. 1st/99th percentile winsorization for continuous features,
2. median imputation,
3. missingness indicators,
4. standard scaling.

## Model

Primary: L2 logistic regression with balanced class weighting.

Candidate regularization strengths: `C=[0.01, 0.1, 1.0, 10.0]`.

Blocked chronological CV inside the training/design period. No random row shuffle because adjacent result cohorts share market regimes.

Selection metric:

1. highest mean average precision,
2. tie within 0.005 -> higher mean recall among top 10%,
3. remaining tie -> stronger regularization (smaller C).

After C is selected, refit once on all training/design rows and freeze coefficient vector + preprocessing parameters before opening validation labels.

## Ranking

Score every eligible event by predicted probability.

Predeclared buckets:

- top 5%,
- top 10% (primary),
- top 20%.

Percentiles are computed within each decision calendar quarter for headline stability analysis and globally for aggregate analysis. Primary gate uses global top 10%; quarter buckets are diagnostics.

## Baselines

At matched signal count:

- first-session tape composite,
- H004 strict earnings anchor,
- raw accounting-growth rank,
- pre-event price momentum rank,
- random prevalence.

The tape composite must be deterministically specified before validation scoring from training/design data only.

## Required outputs

- `training-summary.json`
- `frozen-model.json`
- `validation-coverage.json`
- `validation-predictions.csv`
- `validation-summary.json`
- `missed-movers.csv`
- `false-positives.csv`
- `RESULTS.md`

Every output must record source hashes or source artifact identifiers sufficient to reproduce the event/market dataset.

## Gate

Historical validation primary top-10%:

- explosive recall >=35%,
- precision >=10%,
- prevalence lift >=2.5x,
- median lead >=3 sessions,
- median Nifty500 20-session excess >0,
- tape comparison condition passes,
- max company contribution to positive P&L <=20%,
- quarter catastrophic-miss rule passes.

`PROMISING` historical classification additionally requires recall >=50% and precision >=15%.

Any historical pass remains `PAPER_ONLY_PENDING_PROSPECTIVE`.

## Audit rule

After the validation labels are opened, no feature, C-grid, preprocessing rule, timing rule, operating percentile, label definition, or success gate may change under H005-v1. A changed version becomes H005-v2 with a new untouched validation set or prospective-only evaluation.
