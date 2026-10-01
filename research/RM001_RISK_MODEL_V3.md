# RM001 Transparent + Statistical Residual Risk Model v3

Status: DEVELOPMENT CHALLENGER
Frozen initial specification: 2026-10-02
Live capital: DISABLED

## Objective

Extend RM001-v2 with a small statistical residual-risk layer so common
cross-sectional risk that is not captured by the transparent named factors can
be modeled without fabricating retrospective sector labels.

RM001-v1 and RM001-v2 remain immutable.

## Parent model

RM001-v2-DEVELOPMENT.

Named factors remain exactly:

1. MARKET_COMMON
2. BETA60_RELATIVE
3. MOMENTUM20
4. VOLATILITY60
5. LIQUIDITY
6. SIZE

RM001-v3 adds five statistical residual factors:

7. STAT_PC01
8. STAT_PC02
9. STAT_PC03
10. STAT_PC04
11. STAT_PC05

## Statistical source

The statistical layer is built only from the RM001-v2 realized residual-return
history.

No raw future stock return is accessed outside the already-realized RM001-v2
factor-history boundary.

For risk state as of decision session D:

- use only residual rows with realized_session <= D;
- use the latest 120 distinct realized sessions;
- current identity set comes from the RM001-v2 risk state for D.

## Complete-history universe

A current identity is statistically eligible only if it has one finite RM001-v2
residual for every one of the frozen 120 realized sessions.

No missing residual is imputed.

Frozen minimum complete-history current identities:

    500

If fewer than 500 current identities have a complete 120-session residual
history, RM001-v3 fails closed.

Current identities that are not statistically eligible remain in the v3 risk
state with:

- all STAT_PC exposures = 0;
- RM001-v2 idiosyncratic variance retained unchanged;
- status = V2_FALLBACK_NO_COMPLETE_STAT_HISTORY.

This is conservative because any omitted latent common component remains inside
their idiosyncratic risk.

## Residual PCA

Let R be the T x N matrix of RM001-v2 residual returns for the complete-history
universe, with:

    T = 120 realized sessions
    N >= 500 identities

For each identity column:

1. subtract its trailing-120 time-series mean;
2. do NOT volatility-standardize the column.

Reason:

RM001-v2 residuals are already in return units. The statistical risk model should
identify common covariance in the same units rather than give equal variance
weight to intrinsically low/high idiosyncratic names.

Compute deterministic SVD:

    R_centered = U S V'

Take the first K=5 components.

Frozen exposure convention:

    B_stat = V[:, :5]

Frozen statistical factor-return history:

    F_stat = U[:, :5] * S[:5]

Therefore:

    R_centered ~= F_stat * B_stat'

No arbitrary rescaling is applied.

## Deterministic sign convention

For each component:

1. find the current identity with the largest absolute loading;
2. ties break lexicographically by symbol then ISIN;
3. require that anchor loading to be positive;
4. if negative, multiply both the loading vector and factor-return series by -1.

## Degeneracy gate

The first five singular values must be finite, strictly positive and ordered.

For every adjacent pair among the first five:

    relative_gap =
        abs(s_i - s_{i+1}) / max(abs(s_i), abs(s_{i+1}))

Frozen minimum relative gap:

    1e-8

If a top-five pair is closer than this threshold, v3 fails closed because the
individual component basis is not numerically stable enough for persisted
exposures.

## Combined factor covariance

For the same latest 120 realized sessions, align:

- six RM001-v2 named factor returns;
- five statistical factor returns.

Build the 120 x 11 combined factor-return matrix.

Estimator:

- ordinary sample covariance;
- ddof = 1;
- no shrinkage in v3.

Cross-covariance between named and statistical factors is retained.

## Idiosyncratic variance

For statistically eligible identities:

    residual_after_stat =
        centered_v2_residual
        - F_stat * B_stat'

Idiosyncratic variance:

- sample variance of the 120 post-stat residuals;
- ddof = 1.

For non-eligible current identities:

- preserve exact RM001-v2 idiosyncratic variance and status;
- append the v3 status V2_FALLBACK_NO_COMPLETE_STAT_HISTORY.

No cross-sectional imputation is introduced by v3.

## Portfolio risk

For positions w:

    factor_variance = (w'B_v3) F_v3 (B_v3'w)
    idio_variance   = sum_i w_i^2 * sigma_i,v3^2

RM001-v3 reports:

- all eleven factor exposures;
- factor covariance;
- idiosyncratic variance;
- total variance;
- annualized volatility;
- factor variance contributions.

## Point-in-time invariants

- exact symbol + ISIN identity;
- all named-factor inputs inherited from hash-verified RM001-v2;
- no current sector labels;
- no future residual sessions;
- no missing residual imputation;
- statistical component basis frozen from trailing data only;
- live capital disabled.

## Interpretation

RM001-v3 is a statistical risk challenger, not an alpha model.

A reduction in residual/idiosyncratic variance is descriptive evidence that the
new PCs capture previously omitted common covariance.

Lower or higher total portfolio variance is not by itself a success criterion.

## Deferred structural factors

Sector / industry remains:

    POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN

The statistical layer does not claim semantic equivalence to industry sectors.

## Promotion

RM001-v3 may be used for:

- historical portfolio risk attribution;
- historical PO001 challenger studies;
- comparison against RM001-v2.

It may not be used for prospective portfolio construction until the RM001-v2 SIZE
source timing gate has independently passed and a separately frozen prospective
RM001-v3 protocol exists.

No live-capital implication.
