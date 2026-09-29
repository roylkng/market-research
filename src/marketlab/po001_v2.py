from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001 import (
    BPS_PER_UNIT,
    DEFAULT_MAX_INVESTED_WEIGHT,
    DEFAULT_MAX_NAME_WEIGHT,
    DEFAULT_MAX_TRADED_FRACTION,
    FEASIBILITY_TOLERANCE,
    _finite_nonnegative,
    _portfolio_variance,
    _risk_inputs,
    _verify_risk_state,
)
from marketlab.rm001 import FACTOR_NAMES

PO001_V2_MODEL_ID = "PO001-v2-DEVELOPMENT"
DEFAULT_IMPACT_COEFFICIENT = 0.50
DEFAULT_MAX_PARTICIPATION = 0.10


def impact_cost_fraction(
    *,
    order_fraction_of_nav: float,
    portfolio_nav_inr: float,
    adv20_inr: float,
    daily_volatility_decimal: float,
    impact_coefficient: float,
) -> float:
    if order_fraction_of_nav < 0 or not math.isfinite(order_fraction_of_nav):
        raise AlphaContractError(
            "PO001-v2 order fraction must be finite and non-negative"
        )
    if order_fraction_of_nav == 0:
        return 0.0
    if portfolio_nav_inr <= 0 or not math.isfinite(portfolio_nav_inr):
        raise AlphaContractError("PO001-v2 portfolio NAV must be positive")
    if adv20_inr <= 0 or not math.isfinite(adv20_inr):
        raise AlphaContractError("PO001-v2 ADV20 must be positive")
    if (
        daily_volatility_decimal < 0
        or not math.isfinite(daily_volatility_decimal)
    ):
        raise AlphaContractError(
            "PO001-v2 daily volatility must be finite and non-negative"
        )
    if impact_coefficient < 0 or not math.isfinite(impact_coefficient):
        raise AlphaContractError(
            "PO001-v2 impact coefficient must be finite and non-negative"
        )
    return (
        impact_coefficient
        * daily_volatility_decimal
        * math.sqrt(portfolio_nav_inr / adv20_inr)
        * order_fraction_of_nav ** 1.5
    )


def optimize_portfolio_v2(
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
    _verify_risk_state(risk_state)
    if str(risk_state.get("as_of_session") or "") != decision_session:
        raise AlphaContractError(
            "PO001-v2 alpha decision session differs from RM001 as-of session"
        )
    if (
        isinstance(horizon_sessions, bool)
        or not isinstance(horizon_sessions, int)
        or horizon_sessions < 1
    ):
        raise AlphaContractError(
            "PO001-v2 horizon_sessions must be a positive integer"
        )
    if portfolio_nav_inr <= 0 or not math.isfinite(portfolio_nav_inr):
        raise AlphaContractError("PO001-v2 portfolio NAV must be positive")
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
            "PO001-v2 max participation must be in (0, 1]"
        )
    if not 0 < max_name <= 1 or not 0 < max_invested <= 1:
        raise AlphaContractError("PO001-v2 weight caps must be in (0, 1]")
    if max_traded > 2:
        raise AlphaContractError(
            "PO001-v2 traded fraction cannot exceed 2x NAV"
        )
    if not alpha_rows:
        raise AlphaContractError("PO001-v2 alpha universe cannot be empty")

    normalized = []
    seen: set[tuple[str, str]] = set()
    for raw in alpha_rows:
        symbol = str(raw.get("symbol") or "").strip().upper()
        isin = str(raw.get("isin") or "").strip()
        identity = (symbol, isin)
        if not symbol or not isin or identity in seen:
            raise AlphaContractError(
                "PO001-v2 alpha rows require unique symbol+ISIN identities"
            )
        seen.add(identity)
        alpha = float(raw.get("expected_excess_return"))
        if not math.isfinite(alpha):
            raise AlphaContractError("PO001-v2 expected alpha must be finite")
        current_weight = _finite_nonnegative(
            raw.get("current_weight", 0.0),
            f"{symbol}.current_weight",
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
                f"PO001-v2 {symbol}.adv20_inr must be positive"
            )
        normalized.append(
            {
                "symbol": symbol,
                "isin": isin,
                "expected_excess_return": alpha,
                "current_weight": current_weight,
                "max_weight": row_max,
                "buy_cost_bps": buy_cost_bps,
                "sell_cost_bps": sell_cost_bps,
                "adv20_inr": adv20,
                "daily_volatility_decimal": volatility,
            }
        )

    normalized.sort(key=lambda row: (row["symbol"], row["isin"]))
    identities = [(row["symbol"], row["isin"]) for row in normalized]
    current = np.asarray(
        [row["current_weight"] for row in normalized],
        dtype=float,
    )
    if float(current.sum()) > 1.0 + FEASIBILITY_TOLERANCE:
        raise AlphaContractError("PO001-v2 current weights exceed 1")

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
    adv = np.asarray([row["adv20_inr"] for row in normalized], dtype=float)
    volatility = np.asarray(
        [row["daily_volatility_decimal"] for row in normalized],
        dtype=float,
    )
    impact_scale = (
        impact_k * volatility * np.sqrt(float(portfolio_nav_inr) / adv)
    )
    participation_weight_cap = (
        max_participation_value * adv / float(portfolio_nav_inr)
    )
    base_caps = np.asarray(
        [row["max_weight"] for row in normalized],
        dtype=float,
    )
    lower_bounds = np.maximum(
        0.0,
        current - participation_weight_cap,
    )
    upper_bounds = np.minimum(
        base_caps,
        current + participation_weight_cap,
    )
    if terminal_liquidation:
        upper_bounds = np.minimum(
            upper_bounds,
            participation_weight_cap,
        )
    if np.any(lower_bounds - upper_bounds > FEASIBILITY_TOLERANCE):
        raise AlphaContractError(
            "PO001-v2 participation bounds are infeasible"
        )

    exposure_matrix, factor_covariance, idio = _risk_inputs(
        risk_state,
        identities,
    )

    factor_bounds_raw = factor_bounds or {}
    unknown_factors = set(factor_bounds_raw) - set(FACTOR_NAMES)
    if unknown_factors:
        raise AlphaContractError(
            f"PO001-v2 unknown factor bounds: {sorted(unknown_factors)}"
        )
    linear_rows = [np.ones(len(normalized), dtype=float)]
    lower = [-np.inf]
    upper = [max_invested]
    normalized_factor_bounds: dict[str, dict[str, float | None]] = {}
    for factor, spec in sorted(factor_bounds_raw.items()):
        if not isinstance(spec, dict):
            raise AlphaContractError(
                "PO001-v2 factor bound must be an object"
            )
        low_raw = spec.get("min")
        high_raw = spec.get("max")
        low = -np.inf if low_raw is None else float(low_raw)
        high = np.inf if high_raw is None else float(high_raw)
        if (
            not (math.isfinite(low) or low == -np.inf)
            or not (math.isfinite(high) or high == np.inf)
            or low > high
        ):
            raise AlphaContractError(
                f"PO001-v2 invalid factor bound for {factor}"
            )
        index = FACTOR_NAMES.index(factor)
        linear_rows.append(exposure_matrix[:, index])
        lower.append(low)
        upper.append(high)
        normalized_factor_bounds[factor] = {
            "min": None if low == -np.inf else low,
            "max": None if high == np.inf else high,
        }

    linear_constraint = LinearConstraint(
        np.vstack(linear_rows),
        np.asarray(lower, dtype=float),
        np.asarray(upper, dtype=float),
    )

    def impact_fraction(fractions: np.ndarray) -> float:
        return float(
            np.sum(impact_scale * np.power(fractions, 1.5))
        )

    def terms(weights: np.ndarray) -> dict[str, Any]:
        delta = weights - current
        buys = np.maximum(delta, 0.0)
        sells = np.maximum(-delta, 0.0)
        variance_daily, factor_var, idio_var, factor_exposure = (
            _portfolio_variance(
                weights,
                exposure_matrix,
                factor_covariance,
                idio,
            )
        )
        horizon_variance = float(horizon_sessions) * variance_daily
        immediate_observable = float(
            buys @ buy_cost + sells @ sell_cost
        )
        immediate_impact = (
            impact_fraction(buys) + impact_fraction(sells)
        )
        terminal_observable = (
            float(weights @ sell_cost)
            if terminal_liquidation
            else 0.0
        )
        terminal_impact = (
            impact_fraction(weights)
            if terminal_liquidation
            else 0.0
        )
        expected_alpha = float(weights @ alpha)
        risk_penalty = risk_aversion_value * horizon_variance
        total_cost = (
            immediate_observable
            + immediate_impact
            + terminal_observable
            + terminal_impact
        )
        utility = expected_alpha - risk_penalty - total_cost
        participation_buy = (
            buys * float(portfolio_nav_inr) / adv
        )
        participation_sell = (
            sells * float(portfolio_nav_inr) / adv
        )
        participation_terminal = (
            weights * float(portfolio_nav_inr) / adv
            if terminal_liquidation
            else np.zeros_like(weights)
        )
        return {
            "buys": buys,
            "sells": sells,
            "traded_fraction": float(np.abs(delta).sum()),
            "expected_alpha": expected_alpha,
            "variance_daily": variance_daily,
            "factor_variance_daily": factor_var,
            "idiosyncratic_variance_daily": idio_var,
            "horizon_variance": horizon_variance,
            "risk_penalty": risk_penalty,
            "immediate_observable_cost": immediate_observable,
            "immediate_impact_cost": immediate_impact,
            "terminal_observable_cost": terminal_observable,
            "terminal_impact_cost": terminal_impact,
            "total_cost": total_cost,
            "utility": utility,
            "factor_exposure": factor_exposure,
            "participation_buy": participation_buy,
            "participation_sell": participation_sell,
            "participation_terminal": participation_terminal,
        }

    def objective(weights: np.ndarray) -> float:
        return -float(terms(weights)["utility"])

    def objective_gradient(weights: np.ndarray) -> np.ndarray:
        delta = weights - current
        buys = np.maximum(delta, 0.0)
        sells = np.maximum(-delta, 0.0)

        observable_grad = np.where(
            delta > 0.0,
            buy_cost,
            np.where(delta < 0.0, -sell_cost, 0.0),
        )
        impact_grad = np.where(
            delta > 0.0,
            1.5 * impact_scale * np.sqrt(buys),
            np.where(
                delta < 0.0,
                -1.5 * impact_scale * np.sqrt(sells),
                0.0,
            ),
        )

        factor_exposure = weights @ exposure_matrix
        variance_gradient = 2.0 * (
            exposure_matrix @ (factor_covariance @ factor_exposure)
            + weights * idio
        )
        total_cost_grad = observable_grad + impact_grad
        if terminal_liquidation:
            total_cost_grad = (
                total_cost_grad
                + sell_cost
                + 1.5 * impact_scale * np.sqrt(np.maximum(weights, 0.0))
            )
        utility_gradient = (
            alpha
            - risk_aversion_value
            * float(horizon_sessions)
            * variance_gradient
            - total_cost_grad
        )
        return -utility_gradient

    def turnover_slack(weights: np.ndarray) -> float:
        return max_traded - float(np.abs(weights - current).sum())

    def turnover_slack_gradient(weights: np.ndarray) -> np.ndarray:
        return -np.sign(weights - current)

    initial = np.clip(current, lower_bounds, upper_bounds)
    if float(initial.sum()) > max_invested:
        initial = initial * (max_invested / float(initial.sum()))
        initial = np.clip(initial, lower_bounds, upper_bounds)

    result = minimize(
        objective,
        initial,
        method="SLSQP",
        jac=objective_gradient,
        bounds=Bounds(lower_bounds, upper_bounds),
        constraints=[
            linear_constraint,
            {
                "type": "ineq",
                "fun": turnover_slack,
                "jac": turnover_slack_gradient,
            },
        ],
        options={
            "maxiter": 2000,
            "ftol": 1e-12,
            "disp": False,
        },
    )
    if not result.success:
        raise AlphaContractError(
            f"PO001-v2 optimizer failed closed: {result.message}"
        )

    weights = np.asarray(result.x, dtype=float)
    if (
        np.any(weights < lower_bounds - FEASIBILITY_TOLERANCE)
        or np.any(weights > upper_bounds + FEASIBILITY_TOLERANCE)
    ):
        raise AlphaContractError(
            "PO001-v2 solution violates participation/name bounds"
        )
    metrics = terms(weights)
    if float(weights.sum()) > max_invested + FEASIBILITY_TOLERANCE:
        raise AlphaContractError(
            "PO001-v2 solution violates invested-weight cap"
        )
    if metrics["traded_fraction"] > max_traded + FEASIBILITY_TOLERANCE:
        raise AlphaContractError(
            "PO001-v2 solution violates turnover budget"
        )
    max_observed_participation = max(
        float(np.max(metrics["participation_buy"])),
        float(np.max(metrics["participation_sell"])),
        float(np.max(metrics["participation_terminal"])),
    )
    if max_observed_participation > (
        max_participation_value + FEASIBILITY_TOLERANCE
    ):
        raise AlphaContractError(
            "PO001-v2 solution violates participation cap"
        )

    factor_exposure = metrics["factor_exposure"]
    for factor, spec in normalized_factor_bounds.items():
        value = float(factor_exposure[FACTOR_NAMES.index(factor)])
        low = spec["min"]
        high = spec["max"]
        if low is not None and value < low - FEASIBILITY_TOLERANCE:
            raise AlphaContractError(
                f"PO001-v2 solution violates {factor} minimum"
            )
        if high is not None and value > high + FEASIBILITY_TOLERANCE:
            raise AlphaContractError(
                f"PO001-v2 solution violates {factor} maximum"
            )

    rows = []
    for index, row in enumerate(normalized):
        rows.append(
            {
                **row,
                "target_weight": float(weights[index]),
                "buy_fraction_of_nav": float(metrics["buys"][index]),
                "sell_fraction_of_nav": float(metrics["sells"][index]),
                "buy_participation": float(
                    metrics["participation_buy"][index]
                ),
                "sell_participation": float(
                    metrics["participation_sell"][index]
                ),
                "terminal_liquidation_participation": float(
                    metrics["participation_terminal"][index]
                ),
                "impact_scale": float(impact_scale[index]),
                "effective_max_weight": float(upper_bounds[index]),
            }
        )

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "optimizer_id": PO001_V2_MODEL_ID,
        "decision_session": decision_session,
        "alpha_horizon_sessions": horizon_sessions,
        "alpha_unit": "DECIMAL_EXCESS_RETURN_OVER_HORIZON",
        "risk_state_sha256": risk_state["state_sha256"],
        "portfolio_nav_inr": float(portfolio_nav_inr),
        "impact_model": {
            "model": "TC001_SQUARE_ROOT_PARTICIPATION_V1",
            "impact_coefficient": impact_k,
            "maximum_participation_per_side": max_participation_value,
            "adv20_estimator": "MEDIAN_20_COMPLETED_SESSIONS_INCLUDING_DECISION",
            "daily_volatility_source": "AE001_REALIZED_VOL_20",
            "quoted_spread_included": False,
            "calibrated_to_nse_execution": False,
        },
        "risk_aversion": risk_aversion_value,
        "max_name_weight": max_name,
        "max_invested_weight": max_invested,
        "max_traded_fraction_of_nav": max_traded,
        "terminal_liquidation": terminal_liquidation,
        "factor_bounds": normalized_factor_bounds,
        "rows": rows,
        "invested_weight": float(weights.sum()),
        "cash_weight": 1.0 - float(weights.sum()),
        "traded_fraction_of_nav": metrics["traded_fraction"],
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
        "maximum_observed_participation": max_observed_participation,
        "portfolio_factor_exposures": {
            factor: float(factor_exposure[index])
            for index, factor in enumerate(FACTOR_NAMES)
        },
        "solver": {
            "method": "SLSQP",
            "objective_gradient": "ANALYTIC_V2_WITH_SQRT_IMPACT",
            "turnover_constraint_gradient": "SUBGRADIENT_SIGN_V1",
            "iterations": int(result.nit),
            "message": str(result.message),
            "success": bool(result.success),
        },
        "deferred_execution_inputs": {
            "QUOTED_SPREAD": "POINT_IN_TIME_SOURCE_NOT_FROZEN",
            "OPEN_AUCTION_IMPACT": "NOT_MODELED",
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact
