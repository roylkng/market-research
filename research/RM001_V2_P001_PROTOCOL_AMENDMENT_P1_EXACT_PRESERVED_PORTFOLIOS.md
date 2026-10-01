# RM001-v2 P001 Protocol Amendment P1: Exact Preserved I002 Portfolios

Frozen: 2026-10-01
Status: FROZEN AFTER FAIL-CLOSED MATERIALIZATION, BEFORE ANY P001 ATTRIBUTION RESULT
Live capital: DISABLED

## Trigger

The first P001 materialization attempt, workflow run 36858895001, successfully
completed:

- the full historical market rebuild;
- the action-safe feature rebuild;
- all 266 D007-bound Security File sessions;
- the RM001-v2 six-factor risk state as of 2026-08-31.

It failed closed before producing a P001 attribution report because the sealed
I002 study artifact does not contain the full position vector of the
`full_po001_observable_cost_floor` optimized portfolio.

The I002 artifact retained only that optimizer's compact summary and top
holdings. The full 39-name target-weight vector was never persisted.

No P001 attribution result was emitted before this amendment.

## Evidence constraint

An optimizer artifact SHA cannot be inverted to recover target weights.

A fresh PO001-v1 re-solve cannot be described as the exact sealed I002
portfolio. Prior I003 work already established numerical solver sensitivity on
locally flat PO001-v1 solution surfaces.

Therefore P001 must not reconstruct or approximate the missing optimized
positions and label them exact.

## Exact preserved I002 portfolios

The sealed I002 study artifact does retain complete position vectors for:

1. `equal_weight_top_decile`
2. `positive_alpha_proportional_top_decile`

Those portfolio position lists were produced before RM001-v2 existed and are
immutable historical controls.

P001-P1 changes the portfolio attribution target from the unavailable optimized
portfolio to BOTH exact preserved baseline portfolios.

## Required attribution outputs

For each exact preserved portfolio:

- RM001-v1 annualized volatility;
- RM001-v2 annualized volatility;
- v1/v2 factor variance;
- v1/v2 idiosyncratic variance;
- RM001-v2 SIZE exposure;
- RM001-v2 SIZE daily variance contribution;
- common-factor exposure deltas.

Universe-level v1/v2 identity overlap, idiosyncratic fallback, median residual
variance and factor covariance diagnostics remain unchanged.

## Interpretation

This amendment does not change RM001-v2 or the SIZE factor.

It narrows P001 to claims that can be supported by immutable evidence.

P001 may conclude how SIZE changes risk attribution for the exact sealed I002
baseline portfolios.

P001 may NOT claim attribution for the unavailable full optimized I002 weight
vector.

## Outcome boundary

No return outcome is opened.

No alpha model is fitted.

No prospective SIZE claim is created.

Live capital remains disabled.
