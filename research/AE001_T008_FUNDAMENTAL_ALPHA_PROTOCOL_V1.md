# AE001 T008 Fundamental Filing Alpha Protocol v1

Status: FROZEN BEFORE RETURN OUTCOMES
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Test whether the six outcome-blind T008 filing-derived fundamental features
contain medium-horizon cross-sectional information about future NSE equity
excess returns.

T008 is historical-development evidence only.

The source/event panel was frozen before any stock return outcome was opened.

## Frozen source panel

Use only the successful T008-D004 combined panel:

- diagnostic: AE001-T008-D004-v1;
- workflow run: 36748060295;
- artifact ID: 11112604385;
- artifact name: ae001-t008-d004-36748060295;
- panel SHA-256:
  35ba8ea6bb87c9c9e39f79b6f9479114d96535cfefecffed4f713b1a362cb5c5;
- frozen U001 universe SHA-256:
  cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb;
- complete event rows: 369.

No alternative source panel may be substituted after return outcomes are opened.

## Frozen feature set

Exactly six D004 features:

1. revenue_yoy
2. pbt_change_to_prior_revenue
3. total_profit_change_to_prior_revenue
4. pbt_margin
5. pbt_margin_delta_yoy
6. total_profit_margin_delta_yoy

All six must be present and finite.

No feature is added, removed or repaired after outcome opening.

The D004 outcome-blind source diagnostic showed material outliers in several
ratio features. Therefore T008 does not feed raw ratios directly into the model.

## Point-in-time feature transform

For each chronological OOS fold and each feature separately:

1. use only eligible training events;
2. sort the training values;
3. transform every training and OOS value using the empirical training CDF;
4. ties use the midpoint rank:
   (count_less + 0.5 * count_equal) / n;
5. values below the training minimum map to 0;
6. values above the training maximum map to 1;
7. center the percentile:
   transformed = 2 * percentile - 1.

No OOS feature value affects the transform.

No winsorization threshold is estimated from OOS data.

No missing-value imputation is allowed because D004 admits complete rows only.

## Event decision timestamp

For every D004 row, the information timestamp is:

    target_exchange_published_at_utc

The timestamp must parse as timezone-aware UTC.

The target filing publication timestamp must be strictly later than the selected
baseline filing publication timestamp.

## Frozen execution rule

To avoid historical source-latency ambiguity and same-session execution claims,
T008 always enters on:

    the open of the first completed NSE trading session
    whose session date is strictly later than the filing publication date
    in Asia/Kolkata.

This rule applies even when the filing was published before the market open.

Same-calendar-day execution is prohibited.

The stock must be NSE CM / STK / EQ on the entry session.

Identity is exact symbol + ISIN from the entry-session official UDiFF row.

The same identity must remain observable through the exit session.

## Return labels

Primary horizon:

    20 completed NSE holding sessions

Secondary horizon:

    5 completed NSE holding sessions

The entry session counts as holding session 1.

For horizon h:

    stock_return = exit_close / entry_open - 1
    benchmark_return = Nifty500_exit_close / Nifty500_entry_open - 1
    excess_return = stock_return - benchmark_return

Primary target:

    20-session stock minus Nifty 500 excess return.

Secondary target:

    5-session stock minus Nifty 500 excess return.

No 60-session label is opened under T008-v1.

## Corporate-action and identity policy

Use the frozen historical corporate-action source contract already used by AE001.

For a return label, any share-changing corporate action strictly after the entry
session and on or before the exit session blocks that label.

Unresolved relevant corporate-action audit state fails closed.

A missing same-ISIN exit bar fails closed.

No adjusted-price reconstruction is introduced.

## Chronological OOS folds

T008 has exactly two OOS target-period folds.

### Fold 1

OOS target period:

    2026-03-31

Training target periods:

    2025-09-30
    2025-12-31

### Fold 2

OOS target period:

    2026-06-30

Training target periods:

    2025-09-30
    2025-12-31
    2026-03-31

No event from the OOS target period may enter that fold's training set.

## Label-maturity purge

For each fold and horizon separately:

- determine the earliest target_exchange_published_at_utc in the OOS period;
- a training event is eligible only when its label exit-session close occurred
  strictly before that earliest OOS publication timestamp.

For maturity comparison, a completed NSE cash session close is represented as
15:30:00 Asia/Kolkata on that session date.

This prevents a later-known training outcome from entering an earlier OOS model.

## Minimum sample gates

Primary 20-session analysis fails closed unless:

- each OOS period has at least 60 complete valid labels;
- combined primary OOS prediction count is at least 120;
- each training fold has at least 120 mature examples.

Secondary 5-session analysis uses the same OOS event set when its 5-session label
is valid.

The secondary horizon may not rescue a failed primary result.

## Frozen model

Primary model:

    ridge regression
    l2 = 1.0

Secondary model:

    ridge regression
    l2 = 1.0

Models are fit independently by horizon.

Inputs are the six training-CDF transformed features.

No hyperparameter search is performed.

No tree model, neural model or interaction term may be introduced under T008-v1.

## Fixed simple baseline

For diagnostics only, T008 also reports an equal-weight fundamental composite:

    mean of the six transformed feature values.

The composite uses the same training-only transforms.

The composite is not allowed to rescue a failed primary ridge endpoint.

## OOS evaluation

Predictions are grouped by frozen target period only after the OOS predictions
have been generated.

For each OOS target period:

### Rank IC

Spearman correlation between model prediction and realized excess return.

### Top-minus-bottom spread

Sort OOS events by model prediction.

Use top and bottom quartiles:

    bucket_size = ceil(n / 4)

Period spread:

    mean(top_quartile_excess_return)
    - mean(bottom_quartile_excess_return)

The primary aggregate metrics are the equal-weight mean of the two OOS-period
metrics, so the larger period cannot dominate.

## Frozen uncertainty estimate

Use a symbol-cluster bootstrap.

- seed: 8008;
- bootstrap replicates: 10,000;
- resampling unit: symbol;
- all OOS events for a sampled symbol move together;
- sampling is with replacement from the unique OOS symbol set;
- for each replicate, recompute both per-period metrics and their equal-period
  means.

Report percentile 95% confidence intervals for:

- mean OOS-period rank IC;
- mean OOS-period top-minus-bottom spread.

The bootstrap is inferential support only. The effect-size gates below remain
required.

## Primary 20-session success criteria

T008 primary is supported only if ALL are true:

1. Fold 1 rank IC > 0.
2. Fold 2 rank IC > 0.
3. Equal-period mean rank IC >= 0.03.
4. 95% symbol-bootstrap lower bound for mean rank IC > 0.
5. Fold 1 top-minus-bottom spread > 0.
6. Fold 2 top-minus-bottom spread > 0.
7. Equal-period mean top-minus-bottom spread >= 0.005
   (50 basis points over the 20-session horizon).
8. 95% symbol-bootstrap lower bound for mean spread > 0.
9. all minimum sample gates pass.

No single criterion may be dropped after outcomes are opened.

## Secondary 5-session interpretation

The secondary horizon reports the identical metric set.

It is supportive only.

It cannot rescue a failed primary 20-session result.

No independent promotion occurs from the secondary result.

## Multiple-testing accounting

T008-v1 counts as one new alpha-family trial in the AE001 trial ledger.

The primary claim is the joint eight-gate 20-session endpoint above.

The 5-session result and the equal-weight composite are diagnostics and do not
create separate success opportunities.

No parameter sweep is permitted under the same trial ID.

Any revised transform, horizon, feature subset, model class, threshold or split
requires a new trial ID.

## Promotion

If the primary endpoint passes:

- T008 may enter AB001 as a separately identifiable fundamental alpha family;
- AB001 must then test orthogonality versus existing price/delivery/futures
  alphas before portfolio use.

If the primary endpoint fails:

- T008-v1 is recorded as failed;
- the secondary horizon cannot rescue it;
- feature or transform changes require a new separately registered trial.

## Research boundaries

T008-v1 does not establish:

- prospective alpha;
- implementation cost;
- portfolio capacity;
- live-capital readiness.

Live capital remains disabled.
