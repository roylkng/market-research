# PO001-v2 Stock-Specific Impact Optimizer

Status: DEVELOPMENT BASELINE
Frozen initial specification: 2026-09-29
Live capital: DISABLED

## Objective

Extend PO001-v1 so transaction cost can influence cross-sectional portfolio
selection through stock-specific liquidity and volatility.

PO001-v1 remains unchanged.

## Inputs

All PO001-v1 alpha and RM001 risk inputs remain unchanged.

Additional per-security execution inputs:

- ADV20 = median NSE traded value over the latest 20 completed sessions,
  including the decision session;
- daily volatility = AE001 realized_vol_20 at the decision session;
- observable TC001 buy/sell charges;
- portfolio NAV in INR.

## Frozen impact model

TC001 square-root impact model:

    impact_bps_per_side =
        k * sigma_daily * 10,000 * sqrt(order_notional / ADV20)

Primary coefficient:

    k = 0.50

This is TC001's independently frozen BASE scenario. It is not calibrated from
alpha outcomes.

No bid-ask spread is fabricated in v2. A real spread source remains deferred.

## Portfolio-impact cost

For portfolio-weight order fraction x >= 0:

    order_notional = x * portfolio_NAV

    impact_cost_fraction_of_NAV =
        x * impact_bps / 10,000
        = k * sigma_daily * sqrt(portfolio_NAV / ADV20) * x^(3/2)

This convex cost enters directly into the optimizer objective.

For rebalances:

- buys use x = max(target-current, 0);
- sells use x = max(current-target, 0).

If terminal_liquidation=true, target weight is charged a future sell impact
using the same frozen current ADV20 and volatility inputs. This is a fixed-horizon
research approximation, not a forecast of future liquidity.

## Liquidity constraint

Maximum order participation per side:

    10% of ADV20

Therefore each target/buy/sell order must satisfy the frozen participation cap.

For current_weight=0 studies, this gives:

    target_weight <= 0.10 * ADV20 / portfolio_NAV

in addition to PO001's name cap.

## Objective

Maximize:

    expected_alpha
    - risk_aversion * horizon_variance
    - observable transaction costs
    - stock-specific square-root impact costs

The RM001 risk term is unchanged.

## Solver

SLSQP with analytical objective gradient and existing PO001 constraints.

PO001-v2 fails closed on:
- missing/invalid ADV20;
- missing/invalid volatility;
- participation above frozen cap;
- unsuccessful solver;
- infeasible constraints.

## Deferred execution terms

- actual quoted bid-ask spread;
- opening auction impact;
- intraday participation schedule;
- venue/order-type effects;
- broker-specific DP/brokerage schedules.

No proxy is silently substituted for these terms.

## Interpretation

PO001-v2 is a capacity-aware research optimizer.

It does not establish:
- calibrated NSE market impact;
- live execution quality;
- live-capital readiness.
