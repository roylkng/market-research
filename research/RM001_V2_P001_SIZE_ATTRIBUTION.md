# RM001-v2 P001 Historical Size-Factor Attribution

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Materialize RM001-v2 on the established historical AE001 evidence plane and
measure the incremental risk attribution created by the newly validated SIZE
factor.

P001 is a risk-model diagnostic. It does not test alpha and opens no future
portfolio return outcome.

## Frozen source window

2025-09-01 through 2026-09-25.

## Frozen comparison date

2026-08-31.

This is the sealed I002/I003 portfolio decision date and permits direct
risk-attribution comparison without opening its subsequent five-session outcome.

## Models

Baseline:

    RM001-v1-DEVELOPMENT

Challenger:

    RM001-v2-DEVELOPMENT

All v1 definitions remain unchanged. v2 adds only total-market-cap SIZE.

## Size source

Daily NSE CM MII Security File validated by D007.

Formula:

    total_market_cap_inr = official_close * IssdCptl

Exposure:

    SIZE = 2 * same-session tie-aware percentile(total_market_cap_inr) - 1

## Frozen checks

P001 passes implementation integrity only if:

1. the full historical size panel rebuilds under D007 source gates;
2. RM001-v2 produces at least 60 realized factor-return sessions by 2026-08-31;
3. all persisted SIZE exposures are finite and within [-1, 1];
4. RM001-v2 current security count is at least 99.0% of the RM001-v1
   2026-08-31 security count;
5. the six-factor covariance matrix is finite and 6x6;
6. SIZE daily factor variance is finite and non-negative;
7. every non-zero position in the exact sealed I002 observable-cost portfolio has
   an exact symbol+ISIN row in the RM001-v2 state.

## Attribution outputs

For the common v1/v2 2026-08-31 risk universe:

- identity overlap;
- v1 and v2 idiosyncratic fallback p75;
- median observed idiosyncratic variance;
- change in median idiosyncratic variance;
- v1/v2 factor covariance diagonals.

For the exact sealed I002 observable-cost portfolio:

- v1 annualized volatility;
- v2 annualized volatility;
- v1/v2 factor variance;
- v1/v2 idiosyncratic variance;
- v2 SIZE exposure;
- v2 SIZE daily variance contribution;
- all common factor exposures.

## Interpretation

A lower v2 idiosyncratic variance is descriptive evidence that SIZE explains
cross-sectional common variation previously left in residuals. It is not an
alpha claim.

A higher or lower portfolio volatility is not itself a success/failure gate.

## Prospective boundary

Historical archived Security Files do not prove same-session availability by the
live EOD decision cutoff.

P001 cannot enable prospective SIZE use.

A separate source-timing protocol is required.

No live-capital implication.
