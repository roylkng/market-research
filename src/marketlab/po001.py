from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001 import FACTOR_NAMES

PO001_MODEL_ID = "PO001-v1-DEVELOPMENT"
BPS_PER_UNIT = 10_000.0
DEFAULT_MAX_NAME_WEIGHT = 0.05
DEFAULT_MAX_INVESTED_WEIGHT = 1.0
DEFAULT_MAX_TRADED_FRACTION = 1.0
FEASIBILITY_TOLERANCE = 1e-7


def _verify_risk_state(risk_state: dict[str, Any]) -> None:
    stored = str(risk_state.get("state_sha256") or "")
    unsigned = copy.deepcopy(risk_state)
    unsigned.pop("state_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError("PO001 RM001 risk-state hash mismatch")
    if risk_state.get("live_capital_allowed") is not False:
        raise AlphaContractError("PO001 requires research-only RM001 state")
    if tuple(risk_state.get("factor_names") or ()) != FACTOR_NAMES:
        raise AlphaContractError("PO001 factor set differs from RM001-v1")


def _finite_nonnegative(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise AlphaContractError(f"PO001 {field} must be finite and non-negative")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(
            f"PO001 {field} must be finite and non-negative"
        ) from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise AlphaContractError(f"PO001 {field} must be finite and non-negative")
    return parsed


def _risk_inputs(
    risk_state: dict[str, Any],
    identities: list[tuple[str, str]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = {
        (str(row["symbol"]), str(row["isin"])): row
        for row in risk_state["rows"]
    }
    exposures = []
    idio = []
    for identity in identities:
        row = rows.get(identity)
        if row is None:
            raise AlphaContractError(
                f"PO001 identity absent from RM001 risk state: {identity}"
            )
        exposures.append(
            [float(row["exposures"][factor]) for factor in FACTOR_NAMES]
        )
        variance = float(row["idiosyncratic_variance_daily"])
        if not math.isfinite(variance) or variance < 0:
            raise AlphaContractError(
                f"PO001 invalid idiosyncratic variance: {identity}"
            )
        idio.append(variance)

    exposure_matrix = np.asarray(exposures, dtype=float)
    covariance = np.asarray(
        risk_state["factor_covariance_daily"],
        dtype=float,
    )
    if covariance.shape != (len(FACTOR_NAMES), len(FACTOR_NAMES)):
        raise AlphaContractError("PO001 RM001 covariance shape mismatch")
    if not np.isfinite(covariance).all():
        raise AlphaContractError("PO001 RM001 covariance contains nonfinite values")
    if not np.allclose(covariance, covariance.T, atol=1e-12):
        raise AlphaContractError("PO001 RM001 covariance is not symmetric")
    eigenvalues = np.linalg.eigvalsh(covariance)
    if float(eigenvalues.min()) < -1e-10:
        raise AlphaContractError("PO001 RM001 covariance is not positive semidefinite")
    return exposure_matrix, covariance, np.asarray(idio, dtype=float)


def _portfolio_variance(
    weights: np.ndarray,
    exposure_matrix: np.ndarray,
    factor_covariance: np.ndarray,
    idiosyncratic_variance: np.ndarray,
) -> tuple[float, float, float, np.ndarray]:
    factor_exposure = weights @ exposure_matrix
    factor_variance = float(
        factor_exposure @ factor_covariance @ factor_exposure
    )
    idio_variance = float(
        np.sum((weights**2) * idiosyncratic_variance)
    )
    total = factor_variance + idio_variance
    if not math.isfinite(total) or total < -1e-12:
        raise AlphaContractError("PO001 portfolio variance is invalid")
    return (
        max(0.0, total),
        max(0.0, factor_variance),
        max(0.0, idio_variance),
        factor_exposure,
    )


def optimize_portfolio(
    *,
    decision_session: str,
    horizon_sessions: int,
    alpha_rows: list[dict[str, Any]],
    risk_state: dict[str, Any],
    risk_aversion: float,
    max_name_weight: float = DEFAULT_MAX_NAME_WEIGHT,
    max_invested_weight: float = DEFAULT_MAX_INVESTED_WEIGHT,
    max_traded_fraction_of_nav: float = DEFAULT_MAX_TRADED_FRACTION,
    factor_bounds: dict[str, dict[str, float | None]] | None = None,
    terminal_liquidation: bool = True,
) -> dict[str, Any]:
    """Optimize one long-only target portfolio under RM001 risk and TC001 costs.

    alpha_rows define the complete optimizer universe. Existing holdings must be
    included even when their expected alpha is zero.
    """

    _verify_risk_state(risk_state)
    if str(risk_state.get("as_of_session") or "") != decision_session:
        raise AlphaContractError(
            "PO001 alpha decision session differs from RM001 as-of session"
        )
    if (
        isinstance(horizon_sessions, bool)
        or not isinstance(horizon_sessions, int)
        or horizon_sessions < 1
    ):
        raise AlphaContractError("PO001 horizon_sessions must be a positive integer")
    risk_aversion_value = _finite_nonnegative(risk_aversion, "risk_aversion")
    max_name = _finite_nonnegative(max_name_weight, "max_name_weight")
    max_invested = _finite_nonnegative(
        max_invested_weight,
        "max_invested_weight",
    )
    max_traded = _finite_nonnegative(
        max_traded_fraction_of_nav,
        "max_traded_fraction_of_nav",
    )
    if not 0 < max_name <= 1 or not 0 < max_invested <= 1:
        raise AlphaContractError("PO001 weight caps must be in (0, 1]")
    if max_traded > 2:
        raise AlphaContractError(
            "PO001 traded fraction cannot exceed 2x NAV in long-only v1"
        )
    if not alpha_rows:
        raise AlphaContractError("PO001 alpha universe cannot be empty")

    normalized = []
    seen: set[tuple[str, str]] = set()
    for raw in alpha_rows:
        symbol = str(raw.get("symbol") or "").strip().upper()
        isin = str(raw.get("isin") or "").strip()
        identity = (symbol, isin)
        if not symbol or not isin or identity in seen:
            raise AlphaContractError(
                "PO001 alpha rows require unique symbol+ISIN identities"
            )
        seen.add(identity)
        alpha = float(raw.get("expected_excess_return"))
        if not math.isfinite(alpha):
            raise AlphaContractError("PO001 expected alpha must be finite")
        current_weight = _finite_nonnegative(
            raw.get("current_weight", 0.0),
            f"{symbol}.current_weight",
        )
        row_max = _finite_nonnegative(
            raw.get("max_weight", max_name),
            f"{symbol}.max_weight",
        )
        row_max = min(row_max, max_name)
        buy_cost_bps = _finite_nonnegative(
            raw.get("buy_cost_bps"),
            f"{symbol}.buy_cost_bps",
        )
        sell_cost_bps = _finite_nonnegative(
            raw.get("sell_cost_bps"),
            f"{symbol}.sell_cost_bps",
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
            }
        )

    normalized.sort(key=lambda row: (row["symbol"], row["isin"]))
    identities = [
        (row["symbol"], row["isin"])
        for row in normalized
    ]
    current = np.asarray(
        [row["current_weight"] for row in normalized],
        dtype=float,
    )
    if float(current.sum()) > 1.0 + FEASIBILITY_TOLERANCE:
        raise AlphaContractError("PO001 current weights exceed 1")
    alpha = np.asarray(
        [row["expected_excess_return"] for row in normalized],
        dtype=float,
    )
    name_caps = np.asarray(
        [row["max_weight"] for row in normalized],
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

    exposure_matrix, factor_covariance, idio = _risk_inputs(
        risk_state,
        identities,
    )

    bounds = factor_bounds or {}
    unknown_factors = set(bounds) - set(FACTOR_NAMES)
    if unknown_factors:
        raise AlphaContractError(
            f"PO001 unknown factor bounds: {sorted(unknown_factors)}"
        )
    linear_rows = [np.ones(len(normalized), dtype=float)]
    lower = [-np.inf]
    upper = [max_invested]
    normalized_factor_bounds: dict[str, dict[str, float | None]] = {}
    for factor, spec in sorted(bounds.items()):
        if not isinstance(spec, dict):
            raise AlphaContractError("PO001 factor bound must be an object")
        low_raw = spec.get("min")
        high_raw = spec.get("max")
        low = -np.inf if low_raw is None else float(low_raw)
        high = np.inf if high_raw is None else float(high_raw)
        if (
            not (math.isfinite(low) or low == -np.inf)
            or not (math.isfinite(high) or high == np.inf)
            or low > high
        ):
            raise AlphaContractError(f"PO001 invalid factor bound for {factor}")
        factor_index = FACTOR_NAMES.index(factor)
        linear_rows.append(exposure_matrix[:, factor_index])
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
        immediate_cost = float(buys @ buy_cost + sells @ sell_cost)
        liquidation_cost = (
            float(weights @ sell_cost)
            if terminal_liquidation
            else 0.0
        )
        expected_alpha = float(weights @ alpha)
        risk_penalty = risk_aversion_value * horizon_variance
        utility = (
            expected_alpha
            - risk_penalty
            - immediate_cost
            - liquidation_cost
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
            "immediate_cost": immediate_cost,
            "terminal_liquidation_cost": liquidation_cost,
            "utility": utility,
            "factor_exposure": factor_exposure,
        }

    def objective(weights: np.ndarray) -> float:
        return -float(terms(weights)["utility"])

    def turnover_slack(weights: np.ndarray) -> float:
        return max_traded - float(np.abs(weights - current).sum())

    initial = np.minimum(current, name_caps)
    if float(initial.sum()) > max_invested:
        initial = initial * (max_invested / float(initial.sum()))

    result = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=Bounds(
            np.zeros(len(normalized), dtype=float),
            name_caps,
        ),
        constraints=[
            linear_constraint,
            {"type": "ineq", "fun": turnover_slack},
        ],
        options={
            "maxiter": 2000,
            "ftol": 1e-12,
            "disp": False,
        },
    )
    if not result.success:
        raise AlphaContractError(
            f"PO001 optimizer failed closed: {result.message}"
        )
    weights = np.asarray(result.x, dtype=float)
    if (
        np.any(weights < -FEASIBILITY_TOLERANCE)
        or np.any(weights - name_caps > FEASIBILITY_TOLERANCE)
    ):
        raise AlphaContractError("PO001 solution violates name bounds")

    metrics = terms(weights)
    if float(weights.sum()) > max_invested + FEASIBILITY_TOLERANCE:
        raise AlphaContractError("PO001 solution violates invested-weight cap")
    if metrics["traded_fraction"] > max_traded + FEASIBILITY_TOLERANCE:
        raise AlphaContractError("PO001 solution violates turnover budget")

    factor_exposure = metrics["factor_exposure"]
    for factor, spec in normalized_factor_bounds.items():
        value = float(factor_exposure[FACTOR_NAMES.index(factor)])
        low = spec["min"]
        high = spec["max"]
        if low is not None and value < low - FEASIBILITY_TOLERANCE:
            raise AlphaContractError(
                f"PO001 solution violates {factor} minimum"
            )
        if high is not None and value > high + FEASIBILITY_TOLERANCE:
            raise AlphaContractError(
                f"PO001 solution violates {factor} maximum"
            )
    if not math.isfinite(float(metrics["utility"])):
        raise AlphaContractError("PO001 solution utility is nonfinite")

    target_rows = []
    for index, row in enumerate(normalized):
        weight = float(weights[index])
        buy_fraction = float(metrics["buys"][index])
        sell_fraction = float(metrics["sells"][index])
        target_rows.append(
            {
                **row,
                "target_weight": weight,
                "buy_fraction_of_nav": buy_fraction,
                "sell_fraction_of_nav": sell_fraction,
            }
        )

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "optimizer_id": PO001_MODEL_ID,
        "decision_session": decision_session,
        "alpha_horizon_sessions": horizon_sessions,
        "alpha_unit": "DECIMAL_EXCESS_RETURN_OVER_HORIZON",
        "risk_state_sha256": risk_state["state_sha256"],
        "risk_scaling": "DAILY_VARIANCE_MULTIPLIED_BY_HORIZON_SESSIONS",
        "risk_aversion": risk_aversion_value,
        "max_name_weight": max_name,
        "max_invested_weight": max_invested,
        "max_traded_fraction_of_nav": max_traded,
        "terminal_liquidation": terminal_liquidation,
        "factor_bounds": normalized_factor_bounds,
        "rows": target_rows,
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
        "immediate_transaction_cost_fraction": metrics["immediate_cost"],
        "terminal_liquidation_cost_fraction": metrics[
            "terminal_liquidation_cost"
        ],
        "objective_utility": metrics["utility"],
        "portfolio_factor_exposures": {
            factor: float(factor_exposure[index])
            for index, factor in enumerate(FACTOR_NAMES)
        },
        "solver": {
            "method": "SLSQP",
            "iterations": int(result.nit),
            "message": str(result.message),
            "success": bool(result.success),
        },
        "deferred_constraints": {
            "SIZE": "RM001_PIT_MARKET_CAP_REQUIRED",
            "SECTOR": "RM001_PIT_SECTOR_REQUIRED",
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact
