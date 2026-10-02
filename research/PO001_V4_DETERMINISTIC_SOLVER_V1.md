# PO001-v4 Deterministic Cash-Start Convex Solver Challenger

Status: DEVELOPMENT CHALLENGER
Frozen initial specification: 2026-10-02
Live capital: DISABLED

## Objective

Replace the numerically unstable broad-universe SLSQP solve identified by
PO001-I004 with a deterministic solver for the SAME frozen economic objective.

PO001-v1/v2/v3 remain immutable.

v4 is initially limited to the exact portfolio class needed by I003/I004:

- long only;
- current weights = zero;
- terminal liquidation = true;
- no factor hard bounds;
- invested-weight cap;
- turnover cap;
- per-name cap;
- TC001 observable buy/sell costs;
- TC001 square-root impact;
- stock-specific ADV20 participation caps;
- arbitrary hash-verified RM001 factor dimension.

This narrower domain is deliberate. Rebalancing and factor-bound support require
a later separately frozen extension.

## Mathematical problem

For weights w >= 0, minimize:

    - alpha' w
    + lambda * H * [ (B'w)' F (B'w) + sum_i idio_i * w_i^2 ]
    + sum_i (buy_cost_i + sell_cost_i) * w_i
    + 2 * sum_i impact_scale_i * w_i^(3/2)

subject to:

    0 <= w_i <= u_i

    sum_i w_i <= budget

where:

    H = alpha horizon in sessions

    impact_scale_i
        = k * sigma_i * sqrt(NAV / ADV20_i)

    u_i
        = min(
            name_cap_i,
            max_participation * ADV20_i / NAV
          )

    budget
        = min(max_invested_weight, max_traded_fraction_of_nav)

The factor-risk, observable-cost, impact and participation semantics are exactly
PO001-v3 semantics for current_weight=0 and terminal_liquidation=true.

## Convexity

The objective is convex when minimized:

- factor covariance is PSD;
- idiosyncratic variance is non-negative;
- w^(3/2) is convex for w >= 0;
- all constraints are convex.

If positive idiosyncratic variance exists, the practical broad-universe problem
is strongly convex enough to have a unique economic solution.

## Solver

### Inner solve

Cyclic coordinate descent in deterministic symbol+ISIN order.

Maintain portfolio factor exposure:

    p = B' w

For coordinate i, hold all other weights fixed.

The derivative in w_i is:

    A_i * w_i
    + C_i * sqrt(w_i)
    + D_i

where:

    A_i
      = 2 * lambda * H
        * ( b_i' F b_i + idio_i )

    C_i
      = 3 * impact_scale_i

    D_i
      = -alpha_i
        + buy_cost_i
        + sell_cost_i
        + nu
        + 2 * lambda * H * b_i' F p_without_i

and nu >= 0 is the multiplier on the aggregate invested-weight budget.

Let z = sqrt(w_i). The exact unconstrained coordinate minimum solves:

    A_i z^2 + C_i z + D_i = 0

then clips w_i = z^2 to [0, u_i].

Special cases A_i=0 and/or C_i=0 fail closed unless their linear optimum is
unambiguous.

### Outer budget solve

1. Solve at nu=0.
2. If sum(w) <= budget, the invested-weight constraint is inactive.
3. Otherwise deterministically bracket nu by doubling.
4. Use fixed-order bisection on nu.
5. At every nu, solve the inner coordinate problem to convergence.

## Frozen convergence

Inner coordinate sweep stops only when:

    max_i |delta w_i| <= 1e-13

and at least two full sweeps have executed.

Maximum inner sweeps:

    20,000

Outer bisection stops when:

    |sum(w) - budget| <= 1e-12

or after:

    100 bisection iterations

If convergence is not reached, fail closed.

## Canonical weights

After convergence:

- weights with absolute value < 5e-14 become exactly zero;
- remaining weights are rounded to 14 decimal places;
- feasibility is rechecked;
- objective and risk/cost metrics are recomputed from canonical weights.

No post-hoc renormalization is permitted.

If canonical rounding violates a constraint by >1e-12, fail closed.

## KKT diagnostics

Report:

- budget multiplier nu;
- invested-budget slack;
- maximum coordinate KKT violation;
- maximum bound violation;
- maximum participation;
- inner sweep count;
- outer bisection count.

Frozen KKT promotion tolerance:

    max coordinate KKT violation <= 1e-9

## Backward economic equivalence

On small synthetic problems, v4 must match PO001-v3 to:

- maximum weight absolute difference <= 1e-8;
- expected alpha <= 1e-10;
- total variance <= 1e-12;
- total transaction cost <= 1e-10;
- objective utility <= 1e-10.

This is an implementation check only.

## S001 exact I004 reproducibility study

A separately gated solver study will reuse the exact frozen I004 control and
treatment problems.

No realized return is opened.

Run the exact v4 control and treatment problems independently on three runners.

Frozen reproducibility gates:

### Economic scalars

max-minus-min across three replicas:

- expected 5D excess return <= 1e-10;
- annualized volatility <= 1e-9;
- total daily variance <= 1e-12;
- risk penalty <= 1e-11;
- total transaction cost <= 1e-10;
- objective utility <= 1e-10.

### Weights

Across every runner pair:

- max absolute name-weight difference <= 1e-10;
- L1 weight difference <= 1e-8.

### KKT

Every replica:

- maximum coordinate KKT violation <= 1e-9.

If any gate fails:

    PO001_V4_NUMERICAL_STABILITY_NOT_ESTABLISHED

## Interpretation

S001 tests numerical reproducibility only.

It may not claim:

- better realized returns;
- superior risk forecasts;
- calibrated impact;
- live-capital readiness.

Only after S001 passes may a separately frozen portfolio study revisit the
RM001-v3 treatment using PO001-v4.

## Prohibited

- no realized post-decision return;
- no changing I004 alpha/risk/execution inputs;
- no parameter tuning using I004 portfolio result;
- no lowering stability gates after observing S001;
- no live capital.
