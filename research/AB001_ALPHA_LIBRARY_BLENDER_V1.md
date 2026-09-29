# AB001 OOS Alpha Library and Blender v1

Status: DEVELOPMENT BASELINE
Frozen initial specification: 2026-09-29
Live capital: DISABLED

## Objective

Create a canonical library for independently generated out-of-sample alpha
predictions and combine multiple alpha streams without using future outcomes.

AB001 is upstream of PO001:

    OOS alpha streams -> AB001 -> calibrated expected excess return -> PO001

## Canonical prediction rule

AB001 accepts only prediction records explicitly marked OOS.

Each prediction identity is:

    alpha_id
    + horizon_sessions
    + feature_session
    + symbol
    + ISIN

Each record also binds:

- model/source artifact SHA-256;
- raw prediction value;
- prediction unit;
- decision timestamp when available.

Outcomes are never stored inside the prediction record.

## Outcome matching

Blend efficacy can use only completed outcomes with exact:

    horizon + feature_session + symbol + ISIN

For a blend decision on session D, an outcome is training-eligible only when:

    label_exit_session < D

This is the same purged chronology principle used elsewhere in AE001.

## Current-session common universe

All alphas participating in one blend must:

- have the same horizon;
- contain current-session OOS predictions;
- share at least 100 exact symbol+ISIN rows.

The blend uses the intersection of current eligible identities.

No missing alpha prediction is imputed.

## Cross-sectional normalization

Each alpha is converted within session to tie-aware percentiles and centered:

    standardized_score = 2 * percentile - 1

This removes arbitrary model scale before blending.

## Efficacy window

For each alpha:

- compute daily Spearman rank IC against matured excess-return outcomes;
- retain the latest 60 matured IC sessions before D;
- require at least 20 IC sessions.

Raw efficacy:

    max(mean_rank_ic, 0)

Alphas with non-positive trailing efficacy receive zero active weight.

## Orthogonality penalty

For each pair of eligible alphas, calculate the correlation of historical
standardized OOS predictions over the same matured training window.

For alpha i:

    redundancy_i = mean_j |corr(alpha_i, alpha_j)|

Frozen v1 effective score:

    efficacy_i / (1 + redundancy_i)

Active blend weight:

    effective_score_i / sum_j effective_score_j

If no alpha has positive effective score, AB001 does not emit an active blend.
It reports NO_POSITIVE_OOS_EFFICACY instead of forcing a portfolio signal.

Equal-weight current-session blending is always reported as a diagnostic
baseline but is not substituted for the active blend.

## Expected-return calibration

PO001 requires expected excess return, not an arbitrary rank score.

AB001 therefore calibrates the active blended standardized score using only
matured historical OOS observations from the same training window:

    target_excess_return = intercept + slope * blended_score + residual

Calibration is ordinary least squares.

Requirements:

- at least 20 distinct matured feature sessions;
- at least 2,000 matched stock-date observations;
- finite positive slope.

If calibration fails these gates, AB001 may report the blend score but does not
emit calibrated expected returns for PO001.

## Trial / overfitting boundary

AB001-v1 parameters are infrastructure defaults, not evidence that the blender
has alpha.

Any claim that AB001 improves returns versus an individual alpha requires a
separately frozen historical or prospective comparison.

No blend-weight parameter may be tuned from future T004 outcomes.

## Orthogonality diagnostics

AB001 reports:

- trailing mean IC per alpha;
- eligible IC session count;
- pairwise historical prediction correlation;
- redundancy penalty;
- active weights;
- equal-weight baseline score;
- calibration slope/intercept/R-squared;
- common-current-universe size.

## Non-goals

- no alpha discovery;
- no in-sample model predictions;
- no short portfolio construction;
- no transaction-cost optimization;
- no risk optimization;
- no live trading.

TC001, RM001 and PO001 remain separate layers.
