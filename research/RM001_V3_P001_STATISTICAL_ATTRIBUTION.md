# RM001-v3 P001 Historical Statistical-Risk Attribution

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Materialize RM001-v3 on the established historical AE001/RM001 evidence plane
and measure the incremental risk attribution created by five statistical
residual factors relative to RM001-v2.

P001 is a risk-model diagnostic. It does not fit alpha and opens no future
portfolio return outcome.

## Frozen source window

2025-09-01 through 2026-09-25.

## Frozen comparison date

2026-08-31.

This is the sealed I002/I003 portfolio decision date.

## Models

Baseline:

    RM001-v2-DEVELOPMENT

Challenger:

    RM001-v3-DEVELOPMENT

RM001-v3 uses the exact frozen P1 clocks:

- 120 realized sessions to estimate the residual PCA basis;
- 60 realized sessions for combined factor covariance;
- 60 post-stat residual sessions for idiosyncratic variance.

## Statistical treatment

Add exactly five residual PCs:

- STAT_PC01
- STAT_PC02
- STAT_PC03
- STAT_PC04
- STAT_PC05

No sector proxy is introduced.

## Frozen implementation gates

P001 fails closed unless:

1. the historical market/action-safe/size source chain rebuilds;
2. the RM001-v2 parent state and factor history are hash-valid;
3. RM001-v3 has exactly eleven factors;
4. at least 500 current identities have complete 120-session residual history;
5. the first five singular values are finite, positive and pass the frozen
   relative-gap threshold;
6. the v3 security identity set is identical to the v2 current identity set;
7. the 11x11 factor covariance is finite;
8. every v3 idiosyncratic variance is finite and non-negative;
9. every exact sealed I002 portfolio position exists in both v2 and v3 states.

## Exact preserved portfolios

Use the exact sealed I002 integrated artifact already pinned at:

    research/po001-i003/inputs/i002-integrated-control-v1.json.gz

Attribute all four preserved portfolios:

- equal_weight_top_decile;
- positive_alpha_proportional_top_decile;
- risk_aware_zero_cost;
- full_po001_observable_cost_floor.

Weights are not re-optimized.

## Cross-sectional attribution

For the exact common current v2/v3 universe report:

- complete statistical-history identity count;
- fallback identity count;
- first-five singular values and relative gaps;
- explained residual variance ratio per PC and total;
- v2 median idiosyncratic variance;
- v3 median idiosyncratic variance;
- idiosyncratic median delta;
- v2/v3 idiosyncratic p25/p75;
- count of identities whose idiosyncratic variance falls/rises/is unchanged.

## Portfolio attribution

For each exact sealed I002 portfolio report:

- v2 annualized volatility;
- v3 annualized volatility;
- total-variance delta;
- factor-variance delta;
- idiosyncratic-variance delta;
- named-factor exposures;
- statistical-factor exposures;
- statistical-factor variance contributions;
- sum of statistical-factor contributions;
- total factor contributions.

## Scientific interpretation

A reduction in residual/idiosyncratic variance is descriptive evidence that the
statistical PCs capture common covariance omitted by named factors.

Lower total portfolio volatility is NOT a frozen success criterion.

Because factor covariance includes named/statistical cross-covariance,
individual factor contributions may be negative.

RM001-v3 does not claim that statistical PCs are semantic substitutes for
industry sectors.

## Prospective boundary

RM001-v3 cannot enter prospective portfolio construction until:

1. RM001-v2 SIZE source timing has independently passed its prospective gate;
2. a separately frozen prospective RM001-v3 protocol exists.

Sector remains unavailable until a valid point-in-time company classification
source is frozen.

No live-capital implication.
