# PO001-v3 Factor-Dynamic Capacity-Aware Portfolio Optimizer

Status: DEVELOPMENT CHALLENGER
Frozen initial specification: 2026-10-02
Live capital: DISABLED

## Objective

Extend PO001-v2 so the optimizer can consume a hash-verified RM001 risk state
with any frozen factor set, including RM001-v2 SIZE and RM001-v3 statistical
residual factors.

PO001-v1 and PO001-v2 remain immutable.

## Treatment

The only structural change from PO001-v2 is the risk-factor dimension.

PO001-v3 reads:

    factor_names = risk_state.factor_names

and requires:

- non-empty unique factor names;
- every security row has exactly that exposure set;
- covariance dimension matches the factor count;
- covariance is finite, symmetric and positive semidefinite.

The objective, transaction-cost model, square-root impact model, participation
cap, name cap, invested-weight cap, turnover budget, terminal-liquidation
convention and SLSQP implementation remain PO001-v2 semantics.

## Frozen execution model

Unchanged from PO001-v2:

- TC001 observable buy/sell costs;
- square-root impact coefficient k = 0.50 by default;
- maximum participation per side = 10% ADV20;
- ADV20 = median traded value over latest 20 completed sessions including D;
- volatility input = AE001 realized_vol_20;
- no fabricated quoted spread;
- terminal liquidation charged using current frozen liquidity inputs.

## Risk-model compatibility

Supported research states must satisfy the generic risk contract.

Initial intended models:

- RM001-v1, five factors;
- RM001-v2, six factors including SIZE;
- RM001-v3, eleven factors including five statistical PCs.

PO001-v3 does not reinterpret factor semantics.

Factor bounds may reference only names present in the supplied risk state.

## Backward-equivalence gate

Before PO001-v3 may be used as an RM001-v3 portfolio challenger, unit tests must
show that for an RM001-v1 state and identical alpha/execution inputs:

- PO001-v3 and PO001-v2 target weights agree within 1e-10;
- expected alpha agrees within 1e-12;
- total variance agrees within 1e-12;
- transaction costs agree within 1e-12;
- objective utility agrees within 1e-12.

This is an implementation equivalence gate, not an outcome test.

## Research boundary

PO001-v3 may be used for historical-development and separately frozen
prospective paper-portfolio studies.

It does not authorize:

- live capital;
- leverage;
- unmodeled sector constraints;
- model-specific risk-factor tuning after outcomes;
- use of a risk model whose prospective source gates have not passed.

## Next gate

After implementation equivalence passes, freeze a separate I004 historical
integration study in which:

- alpha, NAV, execution costs and capacity are held fixed;
- control risk = exact I003-compatible RM001-v1 state;
- treatment risk = sealed RM001-v3 P001 state;
- no post-decision return outcome is opened.

Only that study may assess the effect of the richer risk model on optimized
weights.
