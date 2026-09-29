# RM001 Transparent Equity Risk Model v1

Status: DEVELOPMENT BASELINE
Frozen initial specification: 2026-09-29
Live capital: DISABLED

## Objective

Provide a point-in-time daily covariance and exposure model for AE001/PO001 so
portfolio construction can distinguish stock-selection alpha from common risk.

RM001-v1 is deliberately transparent. It does not use future returns to create
current exposures.

## Factor set

Frozen v1 factors:

1. MARKET_COMMON
   - exposure = 1 for every stock.

2. BETA60_RELATIVE
   - trailing 60 completed close-to-close stock returns versus Nifty 500;
   - ordinary covariance / benchmark variance;
   - exposure = beta - 1.

3. MOMENTUM20
   - AE001 momentum_20 within-session percentile;
   - centered to [-1, 1] as 2 * percentile - 1.

4. VOLATILITY60
   - AE001 realized_vol_60 within-session percentile;
   - centered to [-1, 1].

5. LIQUIDITY
   - AE001 turnover_inr within-session percentile;
   - centered to [-1, 1].

## Deferred factors

### Size

DEFERRED_POINT_IN_TIME_SOURCE_NOT_FROZEN.

Turnover is not a substitute for market capitalization.

### Sector / industry

DEFERRED_POINT_IN_TIME_SOURCE_NOT_FROZEN.

Current industry labels must not be projected backward. A separately frozen
historical company-level classification source is required before sector factors
enter RM001.

## Realized factor returns

For exposure session D, exposures use information available through D.

The realized response is the exact same-identity close-to-close stock return from
D to the next completed NSE session.

Share-changing corporate actions in the response interval fail closed for that
stock observation.

For each realized session, RM001 estimates factor returns using equal-weight
cross-sectional ordinary least squares:

    stock_return = X_D * factor_return + residual

No return winsorization is applied in v1.

A realized factor-return cross-section requires at least 100 valid stocks and a
full-rank design matrix.

## Factor covariance

Risk state as of D uses the latest 60 completed factor-return observations whose
realized session is <= D.

Estimator:

- ordinary sample covariance;
- ddof = 1;
- no future observations;
- no covariance shrinkage in v1.

Shrinkage may be added only as a separately versioned challenger.

## Idiosyncratic risk

For each current identity:

- trailing up to 60 realized residual returns;
- minimum 20 observations;
- sample variance with ddof = 1.

If a current eligible identity has fewer than 20 residual observations, v1 uses
the cross-sectional 75th percentile of observed idiosyncratic variances and
marks the row as CONSERVATIVE_IMPUTATION_P75.

## Portfolio risk

For long-only research weights w:

    factor_variance = (w'B) F (B'w)
    idio_variance   = sum_i w_i^2 * sigma_i^2
    total_variance  = factor_variance + idio_variance

RM001 reports daily variance and annualized volatility using 252 sessions.

Factor contribution is reported as:

    exposure_k * (F * exposure)_k

Contributions may be negative when factor covariance provides diversification.


## Canonical numerical serialization

Persisted RM001 floating-point values are rounded to 15 decimal places before
they enter canonical artifacts and hashes.

Purpose:

- remove machine-level BLAS/NumPy floating-point noise from evidence hashes;
- make identical source/model rebuilds content-stable;
- preserve economically meaningful precision.

This is an artifact-serialization rule, not a factor, estimator or tuning
parameter. Factor definitions, OLS estimation, covariance windows and
idiosyncratic-risk rules are unchanged.

## Point-in-time invariants

- exact symbol + ISIN identity;
- action-safe feature panel required;
- no random splits;
- no future factor returns in current risk state;
- current sector labels are not used retrospectively;
- missing size exposure is not fabricated;
- live capital disabled.

## Promotion

RM001-v1 is sufficient for:
- alpha risk attribution;
- risk-aware paper optimization research;
- factor-exposure diagnostics.

It is not sufficient for:
- live portfolio optimization;
- sector-neutral optimization;
- size-neutral optimization;
- production VaR.

Those require separately frozen PIT size/sector sources and validation.
