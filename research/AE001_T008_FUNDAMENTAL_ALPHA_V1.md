# AE001 T008 Fundamental Growth / Profitability Incremental Alpha Trial v1

Status: FROZEN BEFORE RETURN OUTCOME MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Test whether the six point-in-time fundamental growth/profitability features
sealed by T008-D004 add out-of-sample medium-horizon cross-sectional information
beyond the existing CORE27 price/liquidity/delivery feature set.

T008 does not modify T003, T004, T005, T006 or T007.

## Frozen fundamental source panel

T008-D004 successful workflow run:

36748060295

Artifact:

ae001-t008-d004-36748060295

Artifact ID:

11112604385

Panel SHA-256:

35ba8ea6bb87c9c9e39f79b6f9479114d96535cfefecffed4f713b1a362cb5c5

Frozen event count:

369

Frozen target-period counts:

- 2025-09-30: 94
- 2025-12-31: 95
- 2026-03-31: 86
- 2026-06-30: 94

No D004 source row may be repaired, substituted or added after T008 outcome
materialization begins.

## Frozen universe

U001 snapshot:

research/prospective/universes/FY27-Q2-2026-09-06.json

Universe SHA-256:

cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb

D004 filing symbols are rebound to the exact symbol+ISIN identity in this frozen
universe.

## Historical market / CORE27 support window

Official market-support reconstruction:

2025-06-01 through 2026-09-30 inclusive.

Required sources:

- NSE cash UDiFF;
- Nifty 500;
- NSE share-changing corporate-action source;
- NSE Full Bhavcopy and Security Deliverable data used by CORE27.

Historical delivery publication timing remains unverified. Therefore T008 can
establish historical incremental information only, not prospective validation.

## Decision clock

Each D004 target filing retains its exact official
target_exchange_published_at_utc timestamp.

Decision cutoff:

18:30:00 Asia/Kolkata.

Each filing maps exactly once to the earliest completed NSE session whose 18:30
IST decision cutoff is greater than or equal to the official filing publication
timestamp.

Therefore:

- a filing published before/equal 18:30 IST on a completed trading session maps
  to that session;
- a filing published after 18:30 maps to the next completed trading session;
- a weekend/holiday filing maps to the next completed trading session.

No event may be backdated.

## Execution / labels

Entry:

next completed NSE session open after the mapped decision session.

Target:

stock return minus Nifty 500 return over the identical open-to-close interval.

Share-changing corporate actions between entry and exit fail closed.

Exact symbol+ISIN continuity is required at entry and exit.

### Primary horizon

20 completed NSE holding sessions.

The entry session counts as holding session 1.

### Secondary horizon

5 completed NSE holding sessions.

Secondary evidence cannot rescue a failed primary.

### Explicitly excluded horizons

1 session and 60 sessions are not T008 endpoints.

The one-session horizon is outside the frozen medium-horizon economic thesis.

The 60-session horizon is excluded because the latest D004 target period does
not provide a sufficiently mature, symmetric outcome window by the T008 freeze
date.

## Exact comparison

Base model:

CORE27 only.

Augmented model:

CORE27 + exact six T008 fundamentals = CORE33-FUND.

The six T008 features are:

1. revenue_yoy
2. pbt_change_to_prior_revenue
3. total_profit_change_to_prior_revenue
4. pbt_margin
5. pbt_margin_delta_yoy
6. total_profit_margin_delta_yoy

Base and augmented models use:

- identical event rows;
- identical labels;
- identical training and validation sets;
- identical purging;
- identical ridge family;
- identical l2.

Only the six frozen fundamental features differ.

## CORE27 transform

CORE27 uses the existing within-session tie-aware percentile transform over the
full action-safe, delivery-complete market cross-section for the mapped decision
session.

The event row then looks up the exact same-session symbol+ISIN CORE27 vector.

A filing event without a matching CORE27 row is excluded from BOTH models.

## Fundamental transform

Quarter-wide cross-sectional ranking is PROHIBITED because an early filing
would then see later filings from the same quarter.

For each fold and each of the six fundamental features, fit an empirical
distribution using the PURGED TRAINING EVENTS ONLY.

For a value x:

    percentile(x) =
        (count(training < x) + 0.5 * count(training == x))
        / count(training)

Training rows are transformed by their own training distribution.

Validation rows are transformed only by the frozen training distribution.

No validation or later-period value may alter a feature transform.

No winsorization or imputation is permitted.

## Model

Both base and augmented:

- ridge regression;
- l2 = 1.0;
- intercept enabled by existing MarketLab ridge implementation;
- no hyperparameter search;
- no nonlinear challenger;
- no feature selection after outcome opening.

## Chronological folds

Validation is by TARGET PERIOD, not arbitrary event-date slicing.

### Fold 1

Validation target period:

2026-03-31

Candidate training target periods:

- 2025-09-30
- 2025-12-31

### Fold 2

Validation target period:

2026-06-30

Candidate training target periods:

- 2025-09-30
- 2025-12-31
- 2026-03-31

For each horizon independently:

1. construct valid labeled events;
2. identify the earliest mapped decision session in the validation target
   period;
3. retain a candidate training event only if its label exit session is strictly
   before that earliest validation decision session.

This purges overlapping forward labels.

Minimum purged training events per fold:

100.

Minimum valid validation events per fold:

60.

Failure of either threshold fails T008 closed. Thresholds may not be lowered
after outcomes open.

## Event-level evaluation

T008 filings are sparse events, not a daily whole-market prediction panel.
Daily cross-sectional metrics that require many stocks per calendar session are
therefore not used.

For each validation fold/model:

### Rank IC

Spearman correlation between model prediction and realized excess return across
all valid validation events in that target period.

### Top-minus-bottom spread

Top and bottom QUINTILES by model prediction within the validation target
period.

Bucket size:

ceil(validation_event_count * 0.20).

Spread:

mean excess return of top quintile minus mean excess return of bottom quintile.

Ties are resolved deterministically by symbol then ISIN after prediction score.

## Incremental metrics

For each fold:

delta_rank_ic =
    augmented_rank_ic - base_rank_ic

delta_quintile_spread =
    augmented_top_minus_bottom - base_top_minus_bottom

Pooled metrics use validation-event-count weighting across the two frozen folds.

Raw prediction scales from separately trained folds are never pooled directly.

## Cluster-bootstrap inference

Inference unit:

decision calendar week within each validation target period.

Week definition:

Monday-start ISO calendar week of the mapped decision session.

Bootstrap:

- seed = 20260930;
- repetitions = 10,000;
- resample decision-week clusters WITH replacement separately inside each fold;
- include every event in each sampled cluster;
- recompute fold base/augmented metrics;
- recompute validation-event-count-weighted pooled deltas.

A bootstrap replicate is valid only when both base and augmented rank IC and
quintile spread are defined in both folds.

At least 9,500 valid bootstrap replicates are required.

95% confidence interval:

2.5th and 97.5th percentiles of valid bootstrap pooled deltas.

No alternative bootstrap seed, grouping or confidence interval may be selected
after outcomes are opened.

## Primary H20 success criteria

T008 primary support requires ALL of:

1. fold-1 delta_rank_ic > 0;
2. fold-2 delta_rank_ic > 0;
3. fold-1 delta_quintile_spread > 0;
4. fold-2 delta_quintile_spread > 0;
5. pooled weighted delta_rank_ic > 0;
6. 95% cluster-bootstrap lower bound for pooled delta_rank_ic > 0;
7. pooled weighted delta_quintile_spread > 0;
8. 95% cluster-bootstrap lower bound for pooled delta_quintile_spread > 0.

Intersection rule.

Failure of any condition means the primary endpoint is unsupported.

## Secondary H5 interpretation

Run the identical two folds, transforms, models, event metrics and
cluster-bootstrap procedure at five sessions.

Secondary support is reported using the same eight-condition intersection rule.

Secondary H5 cannot rescue a failed H20 primary.

## Additional diagnostics

Report, but do not use for success:

- base and augmented fold event counts;
- base and augmented fold rank IC;
- top/bottom quintile mean returns;
- average augmented-minus-base prediction change;
- ridge coefficients;
- fundamental empirical-transform training ranges;
- exclusions by reason;
- decision-session distribution;
- target-period accounting-basis counts.

No post-outcome feature ablation, sign search or taxonomy change is part of
T008-v1.

## Trial accounting

T008 must be registered in:

research/ae001/trial-ledger.json

before the first return label is materialized.

Failed source/pre-model runs remain evidence but are not T008 outcome openings
when model fitting and outcome metrics never begin.

## Interpretation

If supported, T008 establishes historical-development incremental information
for the frozen six fundamental filing features beyond CORE27 at the frozen
medium horizon.

It does NOT establish:

- prospective information content;
- fundamental causality;
- sector-neutral alpha;
- size-neutral alpha;
- calibrated trading profitability;
- live-capital readiness.

If historically supported, the next allowed steps are:

1. separately frozen prospective T008 confirmation using future filings only;
2. AB001 orthogonality analysis against T003/T005/H024 and other supported
   families.

Live capital remains disabled.
