from __future__ import annotations

import math
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001 import (
    BPS_PER_UNIT,
    DEFAULT_MAX_INVESTED_WEIGHT,
    DEFAULT_MAX_NAME_WEIGHT,
    DEFAULT_MAX_TRADED_FRACTION,
    FEASIBILITY_TOLERANCE,
    _finite_nonnegative,
    _portfolio_variance,
)
from marketlab.po001_v3 import (
    DEFAULT_IMPACT_COEFFICIENT,
    DEFAULT_MAX_PARTICIPATION,
    _dynamic_risk_inputs,
    _verify_dynamic_risk_state,
)

PO001_V4_MODEL_ID = "PO001-v4-DEVELOPMENT"

INNER_WEIGHT_TOLERANCE = 1e-13
INNER_MAX_SWEEPS = 20_000
OUTER_BUDGET_TOLERANCE = 1e-12
OUTER_MAX_BISECTION_ITERATIONS = 100
CANONICAL_ZERO_THRESHOLD = 5e-14
CANONICAL_DECIMAL_PLACES = 14
KKT_TOLERANCE = 1e-9


def _coordinate_minimum(
    *,
    quadratic_coefficient: float,
    sqrt_coefficient: float,
    constant_derivative: float,
    upper_bound: float,
) -> float:
    """Exact minimum of A*w + C*sqrt(w) + D derivative on [0, upper]."""

    if upper_bound <= 0:
        return 0.0
    a = max(0.0, float(quadratic_coefficient))
    c = max(0.0, float(sqrt_coefficient))
    d = float(constant_derivative)

    if d >= 0.0:
        return 0.0

    derivative_at_upper = a * upper_bound + c * math.sqrt(upper_bound) + d
    if derivative_at_upper <= 0.0:
        return upper_bound

    if a > 0.0:
        discriminant = c * c - 4.0 * a * d
        if discriminant < 0.0 and discriminant > -1e-18:
            discriminant = 0.0
        if discriminant < 0.0:
            raise AlphaContractError(
                "PO001-v4 coordinate discriminant became negative"
            )
        root = math.sqrt(discriminant)
        denominator = c + root
        if denominator <= 0.0:
            raise AlphaContractError(
                "PO001-v4 coordinate quadratic denominator is invalid"
            )
        # Stable positive root of A*z^2 + C*z + D = 0, z=sqrt(w).
        z = (-2.0 * d) / denominator
        value = z * z
    elif c > 0.0:
        z = -d / c
        value = z * z
    else:
        # Constant negative derivative across the interval.
        value = upper_bound

    return min(upper_bound, max(0.0, value))


def _solve_at_dual(
    *,
    alpha: np.ndarray,
    linear_cost: np.ndarray,
    impact_scale: np.ndarray,
    exposure_matrix: np.ndarray,
    factor_covariance: np.ndarray,
    idiosyncratic_variance: np.ndarray,
    upper_bounds: np.ndarray,
    risk_multiplier: float,
    budget_dual: float,
    initial: np.ndarray | None = None,
) -> tuple[np.ndarray, int]:
    n = len(alpha)
    weights = (
        np.zeros(n, dtype=float)
        if initial is None
        else np.clip(np.asarray(initial, dtype=float), 0.0, upper_bounds)
    )
    if weights.shape != (n,):
        raise AlphaContractError("PO001-v4 initial-weight shape mismatch")

    factor_exposure = weights @ exposure_matrix
    exposure_times_covariance = exposure_matrix @ factor_covariance

    for sweep in range(1, INNER_MAX_SWEEPS + 1):
        max_change = 0.0
        for index in range(n):
            old = float(weights[index])
            exposures = exposure_matrix[index]
            portfolio_without = factor_exposure - old * exposures

            factor_cross = float(
                exposure_times_covariance[index] @ portfolio_without
            )
            own_factor_variance = float(
                exposure_times_covariance[index] @ exposures
            )
            own_quadratic = own_factor_variance + float(
                idiosyncratic_variance[index]
            )
            if own_quadratic < -1e-14:
                raise AlphaContractError(
                    "PO001-v4 coordinate risk curvature is negative"
                )
            own_quadratic = max(0.0, own_quadratic)

            a = 2.0 * risk_multiplier * own_quadratic
            c = 3.0 * float(impact_scale[index])
            d = (
                -float(alpha[index])
                + float(linear_cost[index])
                + float(budget_dual)
                + 2.0 * risk_multiplier * factor_cross
            )
            new = _coordinate_minimum(
                quadratic_coefficient=a,
                sqrt_coefficient=c,
                constant_derivative=d,
                upper_bound=float(upper_bounds[index]),
            )

            change = new - old
            if change != 0.0:
                weights[index] = new
                factor_exposure = factor_exposure + change * exposures
                max_change = max(max_change, abs(change))

        if sweep >= 2 and max_change <= INNER_WEIGHT_TOLERANCE:
            return weights, sweep

    raise AlphaContractError(
        "PO001-v4 coordinate descent did not converge within frozen sweep cap"
    )


def _solve_budgeted(
    *,
    alpha: np.ndarray,
    linear_cost: np.ndarray,
    impact_scale: np.ndarray,
    exposure_matrix: np.ndarray,
    factor_covariance: np.ndarray,
    idiosyncratic_variance: np.ndarray,
    upper_bounds: np.ndarray,
    risk_multiplier: float,
    budget: float,
) -> tuple[np.ndarray, float, int, int]:
    zero_dual_weights, zero_sweeps = _solve_at_dual(
        alpha=alpha,
        linear_cost=linear_cost,
        impact_scale=impact_scale,
        exposure_matrix=exposure_matrix,
        factor_covariance=factor_covariance,
        idiosyncratic_variance=idiosyncratic_variance,
        upper_bounds=upper_bounds,
        risk_multiplier=risk_multiplier,
        budget_dual=0.0,
    )
    if float(zero_dual_weights.sum()) <= budget + OUTER_BUDGET_TOLERANCE:
        return zero_dual_weights, 0.0, zero_sweeps, 0

    low = 0.0
    high = max(
        1e-12,
        float(np.max(alpha - linear_cost)),
    )
    high_weights = zero_dual_weights
    high_sweeps = 0
    while True:
        high_weights, high_sweeps = _solve_at_dual(
            alpha=alpha,
            linear_cost=linear_cost,
            impact_scale=impact_scale,
            exposure_matrix=exposure_matrix,
            factor_covariance=factor_covariance,
            idiosyncratic_variance=idiosyncratic_variance,
            upper_bounds=upper_bounds,
            risk_multiplier=risk_multiplier,
            budget_dual=high,
        )
        if float(high_weights.sum()) <= budget:
            break
        high *= 2.0
        if not math.isfinite(high) or high > 1e6:
            raise AlphaContractError(
                "PO001-v4 could not bracket invested-weight budget dual"
            )

    best_weights = high_weights
    best_dual = high
    total_sweeps = zero_sweeps + high_sweeps

    for outer in range(1, OUTER_MAX_BISECTION_ITERATIONS + 1):
        mid = (low + high) / 2.0
        weights, sweeps = _solve_at_dual(
            alpha=alpha,
            linear_cost=linear_cost,
            impact_scale=impact_scale,
            exposure_matrix=exposure_matrix,
            factor_covariance=factor_covariance,
            idiosyncratic_variance=idiosyncratic_variance,
            upper_bounds=upper_bounds,
            risk_multiplier=risk_multiplier,
            budget_dual=mid,
        )
        total_sweeps += sweeps
        invested = float(weights.sum())
        best_weights = weights
        best_dual = mid

        if abs(invested - budget) <= OUTER_BUDGET_TOLERANCE:
            return weights, mid, total_sweeps, outer

        if invested > budget:
            low = mid
        else:
            high = mid

    invested = float(best_weights.sum())
    if abs(invested - budget) > OUTER_BUDGET_TOLERANCE:
        raise AlphaContractError(
            "PO001-v4 budget dual bisection did not converge"
        )
    return (
        best_weights,
        best_dual,
        total_sweeps,
        OUTER_MAX_BISECTION_ITERATIONS,
    )


def _canonicalize_weights(
    weights: np.ndarray,
    *,
    upper_bounds: np.ndarray,
    budget: float,
) -> np.ndarray:
    canonical = np.asarray(weights, dtype=float).copy()
    canonical[np.abs(canonical) < CANONICAL_ZERO_THRESHOLD] = 0.0
    canonical = np.round(canonical, CANONICAL_DECIMAL_PLACES)

    if np.any(canonical < -1e-12):
        raise AlphaContractError("PO001-v4 canonical weights became negative")
    if np.any(canonical - upper_bounds > 1e-12):
        raise AlphaContractError(
            "PO001-v4 canonical weights violate upper bounds"
        )
    if float(canonical.sum()) > budget + 1e-12:
        raise AlphaContractError(
            "PO001-v4 canonical weights violate invested budget"
        )
    canonical = np.maximum(canonical, 0.0)
    return canonical


def _objective_terms(
    *,
    weights: np.ndarray,
    alpha: np.ndarray,
    buy_cost: np.ndarray,
    sell_cost: np.ndarray,
    impact_scale: np.ndarray,
    exposure_matrix: np.ndarray,
    factor_covariance: np.ndarray,
    idiosyncratic_variance: np.ndarray,
    horizon_sessions: int,
    risk_aversion: float,
    portfolio_nav_inr: float,
    adv: np.ndarray,
) -> dict[str, Any]:
    variance_daily, factor_var, idio_var, factor_exposure = (
        _portfolio_variance(
            weights,
            exposure_matrix,
            factor_covariance,
            idiosyncratic_variance,
        )
    )
    horizon_variance = float(horizon_sessions) * variance_daily
    expected_alpha = float(weights @ alpha)
    immediate_observable = float(weights @ buy_cost)
    terminal_observable = float(weights @ sell_cost)
    immediate_impact = float(
        np.sum(impact_scale * np.power(weights, 1.5))
    )
    terminal_impact = immediate_impact
    total_cost = (
        immediate_observable
        + terminal_observable
        + immediate_impact
        + terminal_impact
    )
    risk_penalty = float(risk_aversion) * horizon_variance
    utility = expected_alpha - risk_penalty - total_cost
    participation = weights * float(portfolio_nav_inr) / adv
    return {
        "expected_alpha": expected_alpha,
        "variance_daily": variance_daily,
        "factor_variance_daily": factor_var,
        "idiosyncratic_variance_daily": idio_var,
        "horizon_variance": horizon_variance,
        "risk_penalty": risk_penalty,
        "immediate_observable_cost": immediate_observable,
        "terminal_observable_cost": terminal_observable,
        "immediate_impact_cost": immediate_impact,
        "terminal_impact_cost": terminal_impact,
        "total_cost": total_cost,
        "utility": utility,
        "factor_exposure": factor_exposure,
        "participation": participation,
    }


def _kkt_violation(
    *,
    weights: np.ndarray,
    alpha: np.ndarray,
    linear_cost: np.ndarray,
    impact_scale: np.ndarray,
    exposure_matrix: np.ndarray,
    factor_covariance: np.ndarray,
    idiosyncratic_variance: np.ndarray,
    upper_bounds: np.ndarray,
    risk_multiplier: float,
    budget: float,
    budget_dual: float,
) -> dict[str, float]:
    factor_exposure = weights @ exposure_matrix
    risk_gradient = 2.0 * risk_multiplier * (
        exposure_matrix @ (factor_covariance @ factor_exposure)
        + weights * idiosyncratic_variance
    )
    gradient = (
        -alpha
        + linear_cost
        + 3.0 * impact_scale * np.sqrt(np.maximum(weights, 0.0))
        + risk_gradient
        + budget_dual
    )

    violations = []
    for index, weight in enumerate(weights):
        upper = float(upper_bounds[index])
        value = float(gradient[index])
        if weight <= 1e-13:
            violations.append(max(0.0, -value))
        elif upper - weight <= 1e-13:
            violations.append(max(0.0, value))
        else:
            violations.append(abs(value))

    invested = float(weights.sum())
    budget_slack = budget - invested
    complementarity = abs(budget_dual * max(0.0, budget_slack))

    return {
        "maximum_coordinate_kkt_violation": max(violations, default=0.0),
        "budget_feasibility_violation": max(0.0, -budget_slack),
        "budget_complementarity_violation": complementarity,
        "budget_slack": budget_slack,
    }


def optimize_portfolio_v4(
    *,
    decision_session: str,
    horizon_sessions: int,
    alpha_rows: list[dict[str, Any]],
    risk_state: dict[str, Any],
    portfolio_nav_inr: float,
    risk_aversion: float,
    impact_coefficient: float = DEFAULT_IMPACT_COEFFICIENT,
    max_participation: float = DEFAULT_MAX_PARTICIPATION,
    max_name_weight: float = DEFAULT_MAX_NAME_WEIGHT,
    max_invested_weight: float = DEFAULT_MAX_INVESTED_WEIGHT,
    max_traded_fraction_of_nav: float = DEFAULT_MAX_TRADED_FRACTION,
    factor_bounds: dict[str, dict[str, float | None]] | None = None,
    terminal_liquidation: bool = True,
) -> dict[str, Any]:
    factor_names = _verify_dynamic_risk_state(risk_state)
    if str(risk_state.get("as_of_session") or "") != decision_session:
        raise AlphaContractError(
            "PO001-v4 alpha decision session differs from RM001 as-of session"
        )
    if not terminal_liquidation:
        raise AlphaContractError(
            "PO001-v4 v1 challenger requires terminal_liquidation=true"
        )
    if factor_bounds:
        raise AlphaContractError(
            "PO001-v4 v1 challenger does not support factor hard bounds"
        )
    if (
        isinstance(horizon_sessions, bool)
        or not isinstance(horizon_sessions, int)
        or horizon_sessions < 1
    ):
        raise AlphaContractError(
            "PO001-v4 horizon_sessions must be a positive integer"
        )
    if portfolio_nav_inr <= 0 or not math.isfinite(portfolio_nav_inr):
        raise AlphaContractError("PO001-v4 portfolio NAV must be positive")

    risk_aversion_value = _finite_nonnegative(
        risk_aversion,
        "risk_aversion",
    )
    impact_k = _finite_nonnegative(
        impact_coefficient,
        "impact_coefficient",
    )
    max_participation_value = _finite_nonnegative(
        max_participation,
        "max_participation",
    )
    max_name = _finite_nonnegative(max_name_weight, "max_name_weight")
    max_invested = _finite_nonnegative(
        max_invested_weight,
        "max_invested_weight",
    )
    max_traded = _finite_nonnegative(
        max_traded_fraction_of_nav,
        "max_traded_fraction_of_nav",
    )
    if not 0 < max_participation_value <= 1:
        raise AlphaContractError(
            "PO001-v4 max participation must be in (0, 1]"
        )
    if not 0 < max_name <= 1 or not 0 < max_invested <= 1:
        raise AlphaContractError("PO001-v4 weight caps must be in (0, 1]")
    if max_traded > 2:
        raise AlphaContractError(
            "PO001-v4 traded fraction cannot exceed 2x NAV"
        )
    if not alpha_rows:
        raise AlphaContractError("PO001-v4 alpha universe cannot be empty")

    normalized = []
    seen: set[tuple[str, str]] = set()
    for raw in alpha_rows:
        symbol = str(raw.get("symbol") or "").strip().upper()
        isin = str(raw.get("isin") or "").strip()
        identity = (symbol, isin)
        if not symbol or not isin or identity in seen:
            raise AlphaContractError(
                "PO001-v4 alpha rows require unique symbol+ISIN identities"
            )
        seen.add(identity)

        alpha = float(raw.get("expected_excess_return"))
        if not math.isfinite(alpha):
            raise AlphaContractError(
                "PO001-v4 expected alpha must be finite"
            )
        current_weight = _finite_nonnegative(
            raw.get("current_weight", 0.0),
            f"{symbol}.current_weight",
        )
        if current_weight > 1e-15:
            raise AlphaContractError(
                "PO001-v4 v1 challenger requires zero current weights"
            )
        row_max = min(
            _finite_nonnegative(
                raw.get("max_weight", max_name),
                f"{symbol}.max_weight",
            ),
            max_name,
        )
        buy_cost_bps = _finite_nonnegative(
            raw.get("buy_cost_bps"),
            f"{symbol}.buy_cost_bps",
        )
        sell_cost_bps = _finite_nonnegative(
            raw.get("sell_cost_bps"),
            f"{symbol}.sell_cost_bps",
        )
        adv20 = _finite_nonnegative(
            raw.get("adv20_inr"),
            f"{symbol}.adv20_inr",
        )
        volatility = _finite_nonnegative(
            raw.get("daily_volatility_decimal"),
            f"{symbol}.daily_volatility_decimal",
        )
        if adv20 <= 0:
            raise AlphaContractError(
                f"PO001-v4 {symbol}.adv20_inr must be positive"
            )
        normalized.append(
            {
                "symbol": symbol,
                "isin": isin,
                "expected_excess_return": alpha,
                "current_weight": 0.0,
                "max_weight": row_max,
                "buy_cost_bps": buy_cost_bps,
                "sell_cost_bps": sell_cost_bps,
                "adv20_inr": adv20,
                "daily_volatility_decimal": volatility,
            }
        )

    normalized.sort(key=lambda row: (row["symbol"], row["isin"]))
    identities = [(row["symbol"], row["isin"]) for row in normalized]

    alpha = np.asarray(
        [row["expected_excess_return"] for row in normalized],
        dtype=float,
    )
    buy_cost = np.asarray(
        [row["buy_cost_bps"] / BPS_PER_UNIT for row in normalized],
        dtype=float,
    )
    sell_cost = np.asarray(
        [row["sell_cost_bps"] / BPS_PER_UNIT for row in normalized],
        dtype=float,
    )
    linear_cost = buy_cost + sell_cost
    adv = np.asarray(
        [row["adv20_inr"] for row in normalized],
        dtype=float,
    )
    volatility = np.asarray(
        [row["daily_volatility_decimal"] for row in normalized],
        dtype=float,
    )
    impact_scale = (
        impact_k
        * volatility
        * np.sqrt(float(portfolio_nav_inr) / adv)
    )
    participation_weight_cap = (
        max_participation_value * adv / float(portfolio_nav_inr)
    )
    base_caps = np.asarray(
        [row["max_weight"] for row in normalized],
        dtype=float,
    )
    upper_bounds = np.minimum(base_caps, participation_weight_cap)

    exposure_matrix, factor_covariance, idio = _dynamic_risk_inputs(
        risk_state,
        identities,
        factor_names=factor_names,
    )
    risk_multiplier = risk_aversion_value * float(horizon_sessions)
    budget = min(max_invested, max_traded)

    weights, budget_dual, total_sweeps, outer_iterations = _solve_budgeted(
        alpha=alpha,
        linear_cost=linear_cost,
        impact_scale=impact_scale,
        exposure_matrix=exposure_matrix,
        factor_covariance=factor_covariance,
        idiosyncratic_variance=idio,
        upper_bounds=upper_bounds,
        risk_multiplier=risk_multiplier,
        budget=budget,
    )
    weights = _canonicalize_weights(
        weights,
        upper_bounds=upper_bounds,
        budget=budget,
    )

    metrics = _objective_terms(
        weights=weights,
        alpha=alpha,
        buy_cost=buy_cost,
        sell_cost=sell_cost,
        impact_scale=impact_scale,
        exposure_matrix=exposure_matrix,
        factor_covariance=factor_covariance,
        idiosyncratic_variance=idio,
        horizon_sessions=horizon_sessions,
        risk_aversion=risk_aversion_value,
        portfolio_nav_inr=portfolio_nav_inr,
        adv=adv,
    )
    diagnostics = _kkt_violation(
        weights=weights,
        alpha=alpha,
        linear_cost=linear_cost,
        impact_scale=impact_scale,
        exposure_matrix=exposure_matrix,
        factor_covariance=factor_covariance,
        idiosyncratic_variance=idio,
        upper_bounds=upper_bounds,
        risk_multiplier=risk_multiplier,
        budget=budget,
        budget_dual=budget_dual,
    )
    if (
        diagnostics["maximum_coordinate_kkt_violation"]
        > KKT_TOLERANCE
    ):
        raise AlphaContractError(
            "PO001-v4 solution fails frozen KKT tolerance"
        )
    max_participation_observed = float(
        np.max(metrics["participation"])
    )
    if max_participation_observed > (
        max_participation_value + FEASIBILITY_TOLERANCE
    ):
        raise AlphaContractError(
            "PO001-v4 solution violates participation cap"
        )

    rows = []
    for index, row in enumerate(normalized):
        weight = float(weights[index])
        rows.append(
            {
                **row,
                "target_weight": weight,
                "buy_fraction_of_nav": weight,
                "sell_fraction_of_nav": 0.0,
                "buy_participation": float(
                    metrics["participation"][index]
                ),
                "sell_participation": 0.0,
                "terminal_liquidation_participation": float(
                    metrics["participation"][index]
                ),
                "impact_scale": float(impact_scale[index]),
                "effective_max_weight": float(upper_bounds[index]),
            }
        )

    factor_exposure = metrics["factor_exposure"]
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "optimizer_id": PO001_V4_MODEL_ID,
        "decision_session": decision_session,
        "alpha_horizon_sessions": horizon_sessions,
        "alpha_unit": "DECIMAL_EXCESS_RETURN_OVER_HORIZON",
        "risk_state_sha256": risk_state["state_sha256"],
        "factor_names": list(factor_names),
        "portfolio_nav_inr": float(portfolio_nav_inr),
        "impact_model": {
            "model": "TC001_SQUARE_ROOT_PARTICIPATION_V1",
            "impact_coefficient": impact_k,
            "maximum_participation_per_side": max_participation_value,
            "adv20_estimator": (
                "MEDIAN_20_COMPLETED_SESSIONS_INCLUDING_DECISION"
            ),
            "daily_volatility_source": "AE001_REALIZED_VOL_20",
            "quoted_spread_included": False,
            "calibrated_to_nse_execution": False,
        },
        "risk_aversion": risk_aversion_value,
        "max_name_weight": max_name,
        "max_invested_weight": max_invested,
        "max_traded_fraction_of_nav": max_traded,
        "terminal_liquidation": True,
        "factor_bounds": {},
        "rows": rows,
        "invested_weight": float(weights.sum()),
        "cash_weight": 1.0 - float(weights.sum()),
        "traded_fraction_of_nav": float(weights.sum()),
        "expected_excess_return": metrics["expected_alpha"],
        "factor_variance_daily": metrics["factor_variance_daily"],
        "idiosyncratic_variance_daily": metrics[
            "idiosyncratic_variance_daily"
        ],
        "total_variance_daily": metrics["variance_daily"],
        "horizon_variance": metrics["horizon_variance"],
        "risk_penalty": metrics["risk_penalty"],
        "immediate_observable_cost_fraction": metrics[
            "immediate_observable_cost"
        ],
        "immediate_impact_cost_fraction": metrics[
            "immediate_impact_cost"
        ],
        "terminal_observable_cost_fraction": metrics[
            "terminal_observable_cost"
        ],
        "terminal_impact_cost_fraction": metrics[
            "terminal_impact_cost"
        ],
        "total_transaction_cost_fraction": metrics["total_cost"],
        "objective_utility": metrics["utility"],
        "maximum_observed_participation": max_participation_observed,
        "portfolio_factor_exposures": {
            factor: float(factor_exposure[index])
            for index, factor in enumerate(factor_names)
        },
        "solver": {
            "method": (
                "DETERMINISTIC_CYCLIC_COORDINATE_DESCENT_"
                "WITH_BUDGET_DUAL_BISECTION"
            ),
            "budget_dual": budget_dual,
            "total_coordinate_sweeps": total_sweeps,
            "outer_bisection_iterations": outer_iterations,
            "inner_weight_tolerance": INNER_WEIGHT_TOLERANCE,
            "outer_budget_tolerance": OUTER_BUDGET_TOLERANCE,
            "canonical_decimal_places": CANONICAL_DECIMAL_PLACES,
            "kkt": diagnostics,
            "success": True,
        },
        "deferred_execution_inputs": {
            "QUOTED_SPREAD": "POINT_IN_TIME_SOURCE_NOT_FROZEN",
            "OPEN_AUCTION_IMPACT": "NOT_MODELED",
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact
