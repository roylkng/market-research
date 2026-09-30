# AB001 OOS Alpha Library and Blender v1

Status: DEVELOPMENT BASELINE
Frozen initial specification: 2026-09-30
Live capital: DISABLED

## Objective

Create one canonical out-of-sample alpha library and a simple auditable blender
for MarketLab.

AB001 exists to prevent the project from becoming a collection of isolated
"good backtests". Every candidate alpha must enter the same OOS record format,
be compared against existing alphas, and prove incremental information.

## Canonical alpha record

Each OOS alpha record contains:

- alpha_id;
- alpha_version;
- model_sha256 or source_artifact_sha256;
- feature_session;
- symbol;
- ISIN;
- horizon_sessions;
- raw_prediction;
- normalized_score;
- prediction_role = OOS;
- target_excess_return when mature;
- entry_session and exit_session;
- outcome_status;
- live_capital_allowed = false.

The unique identity is:

    (alpha_id, feature_session, symbol, ISIN, horizon_sessions)

Duplicate records fail closed.

## Normalization

For every alpha and feature session independently:

1. preserve missing predictions as missing;
2. calculate tie-aware cross-sectional percentile among observed names;
3. convert to centered score:

       score = 2 * percentile - 1

Therefore every alpha enters the blender on a comparable [-1, 1] rank scale.

No future date contributes to current-session normalization.

## Standalone diagnostics

For every alpha/horizon:

- daily Spearman rank IC;
- mean and median rank IC;
- top-decile excess;
- bottom-decile excess;
- top-minus-bottom spread;
- long-only top-decile excess;
- top-decile selection churn;
- observation/session counts.

## Orthogonality diagnostics

For every alpha pair on overlapping OOS records:

- mean daily Spearman prediction correlation;
- median daily Spearman prediction correlation;
- correlation of daily top-minus-bottom spread series;
- overlapping sessions;
- overlapping stock-session records.

A candidate with high standalone IC but near-duplicate prediction/spread behavior
must not be treated as independent alpha.

## Incremental contribution

For a candidate alpha A against an existing set S:

1. build an equal-weight rank blend of S on common OOS rows;
2. build an equal-weight rank blend of S + A on the same rows;
3. compare daily rank IC and top-minus-bottom spread on identical sessions;
4. report paired Newey-West inference of the difference.

This is a diagnostic, not an automatic promotion decision.

## AB001-v1 dynamic blender

The first dynamic blender is deliberately simple and auditable.

For decision session D, each alpha's weight may use only OOS outcomes whose
entire label horizon had matured before D.

A historical record is eligible for efficacy only when:

    exit_session < D

Feature-session ordering alone is insufficient for multi-session labels.

For each alpha:

    efficacy = mean trailing daily rank IC

using up to the previous 60 completed OOS sessions, minimum 20.

Negative efficacy is floored to zero.

Correlation penalty:

    penalty_i = 1 / (1 + mean_j |corr(i,j)|)

where correlations use only trailing pre-D prediction records and require at
least 20 overlapping sessions.

Raw score:

    raw_weight_i = efficacy_i * penalty_i

Weights are normalized to sum to one and individually capped at 50%.

If fewer than two alphas have sufficient positive efficacy, AB001 falls back to
equal weight across all available alphas for that session and marks:

    weighting_status = INSUFFICIENT_TRAILING_EVIDENCE_EQUAL_WEIGHT_FALLBACK

No current-session target, partially matured label, or future outcome may enter
the weight calculation.

## Blend prediction

For each common stock identity on session D:

    blended_score = sum_i weight_i * normalized_score_i

The blend emits only scores/predictions. Outcomes are attached later.

## Trial discipline

Every alpha source entering AB001 must have:

- OOS-only prediction records;
- explicit horizon;
- immutable source/model hash;
- trial/source lineage.

In-sample or DEVELOPMENT predictions are rejected.

## v1 limitations

- efficacy uses mean rank IC only;
- no nonlinear meta-model;
- no regime conditioning;
- no Bayesian uncertainty weighting;
- no sector/size-neutral residualization yet;
- no portfolio-aware blend optimization.

These are challengers, not prerequisites.

## Promotion

AB001-v1 is sufficient for:

- canonical OOS alpha storage;
- redundancy/orthogonality diagnostics;
- simple dynamic rank blending;
- feeding one blended alpha into RM001/PO001 research.

Live capital remains disabled.
