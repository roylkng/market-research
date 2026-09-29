# PO001 Long-Only Risk/Cost-Aware Portfolio Optimizer v1

Status: DEVELOPMENT BASELINE
Frozen initial specification: 2026-09-29
Live capital: DISABLED

## Objective

Convert an externally supplied cross-sectional expected-excess-return vector into
a long-only target portfolio using RM001 risk and TC001 cost inputs.

PO001 does not discover alpha. It consumes alpha.

AB001 is not yet implemented, so callers must identify the exact alpha source and
horizon in every optimization artifact.

## Clock alignment

Every optimization has a frozen holding horizon H in completed NSE sessions.

Inputs must use the same decision session:

- alpha = expected excess return over H sessions;
- RM001 covariance/idiosyncratic variance = daily risk as of decision session;
- PO001 scales daily variance by H under the v1 iid approximation;
- TC001 costs are expressed as fractions of portfolio NAV traded.

The iid risk scaling assumption is explicit and may be replaced only in a new
PO001 version.

## Decision variables

For each security i:

- target weight w_i >= 0;
- buy fraction b_i >= 0;
- sell fraction s_i >= 0.

Frozen accounting identity:

    w_i = current_weight_i + b_i - s_i

Cash is residual:

    cash = 1 - sum_i w_i

No leverage or short positions are allowed.

## Objective

PO001 minimizes the negative of:

    expected_alpha
    - risk_aversion * horizon_variance
    - immediate_transaction_cost
    - optional_terminal_liquidation_cost

where:

    expected_alpha = sum_i w_i * alpha_i

    horizon_variance =
        H * [ (w'B) F (B'w) + sum_i w_i^2 * idio_variance_i ]

    immediate_transaction_cost =
        sum_i b_i * buy_cost_i + s_i * sell_cost_i

If terminal_liquidation=true:

    terminal_liquidation_cost = sum_i w_i * sell_cost_i

This mode is suitable for fixed-horizon cohort research.

If terminal_liquidation=false, PO001 reports a rolling-target decision and does
not pretend that future exit cost has been modeled.

## Frozen constraints

v1 supports:

- long only;
- sum target weights <= maximum invested weight;
- per-name maximum weight;
- traded-notional budget:
      sum_i (b_i + s_i) <= max_traded_fraction_of_nav;
- factor exposure lower/upper bounds for factors available in RM001.

Initial default research constraints:

- maximum invested weight: 1.00;
- maximum name weight: 0.05;
- maximum traded fraction of NAV: 1.00.

There is no minimum number of holdings in v1 because a hard cardinality
constraint would make the problem mixed-integer. Diversification is controlled
through name caps and risk penalty.

## Deferred constraints

- sector constraints are unavailable until RM001 has a frozen PIT sector source;
- size constraints are unavailable until RM001 has a frozen PIT market-cap source;
- borrow/short constraints are out of scope.

## Cost inputs

PO001 receives per-security buy and sell cost bps from TC001 or another
explicitly identified cost artifact.

PO001 does not recalibrate TC001 impact coefficients from alpha outcomes.

## Solver

v1 uses scipy SLSQP over target, buy and sell variables.

A solution is accepted only if:

- optimizer reports success;
- all variable bounds hold within tolerance;
- accounting identities hold;
- invested weight and turnover constraints hold;
- factor bounds hold;
- recomputed objective is finite.

Otherwise PO001 fails closed.

## Required comparisons

Any paper study using PO001 must compare against:

- equal-weight eligible portfolio;
- alpha-proportional portfolio where defined;
- risk-aware portfolio without TC001 costs;
- full PO001 risk+cost portfolio.

PF001 remains an independent frozen baseline.

## Interpretation

PO001-v1 is portfolio-construction research only.

It does not establish:
- alpha validity;
- live execution quality;
- sector neutrality;
- size neutrality;
- live-capital readiness.
