from __future__ import annotations

import copy
import math
import statistics
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_t004 import validate_frozen_t004_models
from marketlab.alpha_t004_prospective import _score_model
from marketlab.po001 import (
    DEFAULT_MAX_INVESTED_WEIGHT,
    DEFAULT_MAX_NAME_WEIGHT,
    DEFAULT_MAX_TRADED_FRACTION,
    optimize_portfolio,
)
from marketlab.rm001 import portfolio_risk
from marketlab.tc001 import TC001Config, observable_side_cost

STUDY_ID = "PO001-I001-v1"
DECISION_SESSION = "2026-09-25"
HORIZON_SESSIONS = 5
RISK_AVERSION = 5.0
TOP_DECILE_SHARE = 0.10
COST_REFERENCE_NOTIONAL_INR = 1_000_000.0
MIN_COMMON_IDENTITIES = 500


def _verify_hash(
    payload: dict[str, Any],
    *,
    hash_field: str,
    name: str,
) -> None:
    stored = str(payload.get(hash_field) or "")
    unsigned = copy.deepcopy(payload)
    unsigned.pop(hash_field, None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} hash mismatch")


def _capped_proportional(
    values: list[tuple[tuple[str, str], float]],
    *,
    cap: float,
) -> dict[tuple[str, str], float]:
    positive = [(identity, value) for identity, value in values if value > 0.0]
    if not positive:
        raise AlphaContractError(
            "I001 alpha-proportional baseline has no positive alphas"
        )
    if len(positive) * cap < 1.0 - 1e-12:
        raise AlphaContractError(
            "I001 positive-alpha set cannot fully invest under name cap"
        )

    remaining_weight = 1.0
    active = dict(positive)
    weights: dict[tuple[str, str], float] = {}

    while active:
        total_alpha = sum(active.values())
        if total_alpha <= 0:
            raise AlphaContractError(
                "I001 proportional allocation has nonpositive alpha mass"
            )
        capped = []
        provisional = {
            identity: remaining_weight * value / total_alpha
            for identity, value in active.items()
        }
        for identity, weight in provisional.items():
            if weight > cap + 1e-15:
                weights[identity] = cap
                remaining_weight -= cap
                capped.append(identity)
        if not capped:
            for identity, weight in provisional.items():
                weights[identity] = weight
            remaining_weight = 0.0
            break
        for identity in capped:
            active.pop(identity)

    if abs(sum(weights.values()) - 1.0) > 1e-10:
        raise AlphaContractError(
            "I001 proportional baseline does not sum to one"
        )
    if any(weight > cap + 1e-10 for weight in weights.values()):
        raise AlphaContractError(
            "I001 proportional baseline violates name cap"
        )
    return weights


def _positions_from_weights(
    weights: dict[tuple[str, str], float],
) -> list[dict[str, Any]]:
    return [
        {
            "symbol": identity[0],
            "isin": identity[1],
            "weight": weight,
        }
        for identity, weight in sorted(weights.items())
        if weight > 1e-12
    ]


def _portfolio_summary(
    *,
    name: str,
    weights: dict[tuple[str, str], float],
    alpha_by_identity: dict[tuple[str, str], float],
    risk_state: dict[str, Any],
    buy_cost_bps: float,
    sell_cost_bps: float,
    risk_aversion: float,
) -> dict[str, Any]:
    positions = _positions_from_weights(weights)
    risk = portfolio_risk(risk_state, positions=positions)
    invested = sum(weights.values())
    expected_alpha = sum(
        weight * alpha_by_identity[identity]
        for identity, weight in weights.items()
    )
    immediate_cost = invested * buy_cost_bps / 10_000.0
    terminal_cost = invested * sell_cost_bps / 10_000.0
    horizon_variance = risk["total_variance_daily"] * HORIZON_SESSIONS
    risk_penalty = risk_aversion * horizon_variance
    utility = (
        expected_alpha
        - risk_penalty
        - immediate_cost
        - terminal_cost
    )
    weight_values = [weight for weight in weights.values() if weight > 1e-12]
    hhi = sum(weight * weight for weight in weight_values)
    top = sorted(
        (
            {
                "symbol": identity[0],
                "isin": identity[1],
                "weight": weight,
                "expected_excess_return": alpha_by_identity[identity],
            }
            for identity, weight in weights.items()
            if weight > 1e-12
        ),
        key=lambda row: (
            -float(row["weight"]),
            -float(row["expected_excess_return"]),
            row["symbol"],
            row["isin"],
        ),
    )
    return {
        "name": name,
        "holding_count": len(weight_values),
        "invested_weight": invested,
        "cash_weight": 1.0 - invested,
        "expected_5d_excess_return": expected_alpha,
        "factor_variance_daily": risk["factor_variance_daily"],
        "idiosyncratic_variance_daily": risk[
            "idiosyncratic_variance_daily"
        ],
        "total_variance_daily": risk["total_variance_daily"],
        "annualized_volatility": risk["annualized_volatility"],
        "portfolio_factor_exposures": risk[
            "portfolio_factor_exposures"
        ],
        "buy_cost_fraction": immediate_cost,
        "terminal_sell_cost_fraction": terminal_cost,
        "total_round_trip_cost_fraction": immediate_cost + terminal_cost,
        "risk_penalty_at_i001_lambda": risk_penalty,
        "utility_at_i001_lambda": utility,
        "max_name_weight": max(weight_values) if weight_values else 0.0,
        "weight_hhi": hhi,
        "effective_number_of_names": (
            None if hhi <= 0 else 1.0 / hhi
        ),
        "top_holdings": top[:25],
        "positions": top,
    }


def _optimizer_summary(
    *,
    name: str,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    weights = [
        float(row["target_weight"])
        for row in artifact["rows"]
        if float(row["target_weight"]) > 1e-12
    ]
    hhi = sum(weight * weight for weight in weights)
    top = sorted(
        (
            row
            for row in artifact["rows"]
            if float(row["target_weight"]) > 1e-12
        ),
        key=lambda row: (
            -float(row["target_weight"]),
            -float(row["expected_excess_return"]),
            row["symbol"],
            row["isin"],
        ),
    )
    return {
        "name": name,
        "holding_count": len(weights),
        "invested_weight": artifact["invested_weight"],
        "cash_weight": artifact["cash_weight"],
        "expected_5d_excess_return": artifact["expected_excess_return"],
        "factor_variance_daily": artifact["factor_variance_daily"],
        "idiosyncratic_variance_daily": artifact[
            "idiosyncratic_variance_daily"
        ],
        "total_variance_daily": artifact["total_variance_daily"],
        "annualized_volatility": math.sqrt(
            float(artifact["total_variance_daily"]) * 252.0
        ),
        "portfolio_factor_exposures": artifact[
            "portfolio_factor_exposures"
        ],
        "buy_cost_fraction": artifact[
            "immediate_transaction_cost_fraction"
        ],
        "terminal_sell_cost_fraction": artifact[
            "terminal_liquidation_cost_fraction"
        ],
        "total_round_trip_cost_fraction": (
            float(artifact["immediate_transaction_cost_fraction"])
            + float(artifact["terminal_liquidation_cost_fraction"])
        ),
        "risk_penalty_at_i001_lambda": artifact["risk_penalty"],
        "utility_at_i001_lambda": artifact["objective_utility"],
        "max_name_weight": max(weights) if weights else 0.0,
        "weight_hhi": hhi,
        "effective_number_of_names": (
            None if hhi <= 0 else 1.0 / hhi
        ),
        "top_holdings": [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "target_weight": row["target_weight"],
                "expected_excess_return": row[
                    "expected_excess_return"
                ],
            }
            for row in top[:25]
        ],
        "optimizer_artifact_sha256": artifact["artifact_sha256"],
        "solver": artifact["solver"],
    }


def run_po001_i001(
    *,
    delivery_feature_panel: dict[str, Any],
    risk_state: dict[str, Any],
    frozen_models: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        delivery_feature_panel,
        hash_field="panel_sha256",
        name="I001 delivery feature panel",
    )
    _verify_hash(
        risk_state,
        hash_field="state_sha256",
        name="I001 RM001 risk state",
    )
    validate_frozen_t004_models(frozen_models)
    if str(risk_state.get("as_of_session") or "") != DECISION_SESSION:
        raise AlphaContractError(
            "I001 RM001 state does not match frozen decision session"
        )

    ranked = (
        delivery_feature_panel
        if delivery_feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(delivery_feature_panel)
    )
    session_rows = [
        row
        for row in ranked.get("rows", [])
        if str(row.get("feature_session")) == DECISION_SESSION
    ]
    if not session_rows:
        raise AlphaContractError(
            "I001 delivery feature panel lacks decision session"
        )
    augmented_names = [
        str(name)
        for name in frozen_models["augmented_feature_names"]
    ]
    definitions = ranked.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("I001 feature definitions are missing")
    if {str(row["name"]) for row in definitions} != set(augmented_names):
        raise AlphaContractError(
            "I001 delivery feature set differs from frozen T004 model"
        )

    predictions = _score_model(
        frozen_models["augmented_model"],
        session_rows,
    )
    prediction_by_identity = {
        (str(row["symbol"]), str(row["isin"])): float(row["prediction"])
        for row in predictions
    }
    risk_identities = {
        (str(row["symbol"]), str(row["isin"]))
        for row in risk_state["rows"]
    }
    common = sorted(set(prediction_by_identity) & risk_identities)
    if len(common) < MIN_COMMON_IDENTITIES:
        raise AlphaContractError(
            f"I001 common universe below minimum: {len(common)}"
        )
    alpha_by_identity = {
        identity: prediction_by_identity[identity]
        for identity in common
    }

    ordered = sorted(
        common,
        key=lambda identity: (
            -alpha_by_identity[identity],
            identity[0],
            identity[1],
        ),
    )
    bucket_size = max(1, math.ceil(len(ordered) * TOP_DECILE_SHARE))
    top_decile = ordered[:bucket_size]
    equal_weights = {
        identity: 1.0 / len(top_decile)
        for identity in top_decile
    }
    if max(equal_weights.values()) > DEFAULT_MAX_NAME_WEIGHT + 1e-12:
        raise AlphaContractError(
            "I001 equal-weight top decile violates PO001 name cap"
        )

    proportional_weights = _capped_proportional(
        [
            (identity, alpha_by_identity[identity])
            for identity in top_decile
        ],
        cap=DEFAULT_MAX_NAME_WEIGHT,
    )

    buy = observable_side_cost(
        side="BUY",
        notional_inr=COST_REFERENCE_NOTIONAL_INR,
        config=TC001Config(),
    )
    sell = observable_side_cost(
        side="SELL",
        notional_inr=COST_REFERENCE_NOTIONAL_INR,
        config=TC001Config(),
    )
    buy_cost_bps = float(buy["total_bps"])
    sell_cost_bps = float(sell["total_bps"])

    baseline_equal = _portfolio_summary(
        name="EQUAL_WEIGHT_TOP_DECILE",
        weights=equal_weights,
        alpha_by_identity=alpha_by_identity,
        risk_state=risk_state,
        buy_cost_bps=buy_cost_bps,
        sell_cost_bps=sell_cost_bps,
        risk_aversion=RISK_AVERSION,
    )
    baseline_proportional = _portfolio_summary(
        name="POSITIVE_ALPHA_PROPORTIONAL_TOP_DECILE",
        weights=proportional_weights,
        alpha_by_identity=alpha_by_identity,
        risk_state=risk_state,
        buy_cost_bps=buy_cost_bps,
        sell_cost_bps=sell_cost_bps,
        risk_aversion=RISK_AVERSION,
    )

    def alpha_rows(*, with_cost: bool) -> list[dict[str, Any]]:
        return [
            {
                "symbol": identity[0],
                "isin": identity[1],
                "expected_excess_return": alpha_by_identity[identity],
                "current_weight": 0.0,
                "buy_cost_bps": buy_cost_bps if with_cost else 0.0,
                "sell_cost_bps": sell_cost_bps if with_cost else 0.0,
            }
            for identity in common
        ]

    risk_aware = optimize_portfolio(
        decision_session=DECISION_SESSION,
        horizon_sessions=HORIZON_SESSIONS,
        alpha_rows=alpha_rows(with_cost=False),
        risk_state=risk_state,
        risk_aversion=RISK_AVERSION,
        max_name_weight=DEFAULT_MAX_NAME_WEIGHT,
        max_invested_weight=DEFAULT_MAX_INVESTED_WEIGHT,
        max_traded_fraction_of_nav=DEFAULT_MAX_TRADED_FRACTION,
        factor_bounds={},
        terminal_liquidation=True,
    )
    full = optimize_portfolio(
        decision_session=DECISION_SESSION,
        horizon_sessions=HORIZON_SESSIONS,
        alpha_rows=alpha_rows(with_cost=True),
        risk_state=risk_state,
        risk_aversion=RISK_AVERSION,
        max_name_weight=DEFAULT_MAX_NAME_WEIGHT,
        max_invested_weight=DEFAULT_MAX_INVESTED_WEIGHT,
        max_traded_fraction_of_nav=DEFAULT_MAX_TRADED_FRACTION,
        factor_bounds={},
        terminal_liquidation=True,
    )

    alphas = [alpha_by_identity[identity] for identity in common]
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT_INTEGRATION",
        "decision_session": DECISION_SESSION,
        "horizon_sessions": HORIZON_SESSIONS,
        "realized_outcome_opened": False,
        "alpha_source": {
            "model_id": frozen_models["augmented_model"]["model_id"],
            "model_sha256": frozen_models["augmented_model"]["model_sha256"],
            "frozen_model_artifact_sha256": frozen_models["artifact_sha256"],
            "delivery_feature_panel_sha256": delivery_feature_panel[
                "panel_sha256"
            ],
            "ranked_delivery_feature_panel_sha256": ranked["panel_sha256"],
        },
        "risk_source": {
            "model_id": risk_state["model_id"],
            "risk_state_sha256": risk_state["state_sha256"],
            "as_of_session": risk_state["as_of_session"],
            "deferred_factors": risk_state["deferred_factors"],
        },
        "cost_source": {
            "model_id": "TC001-v1-DEVELOPMENT",
            "surface": "OBSERVABLE_DELIVERY_EQUITY_COST_FLOOR",
            "reference_notional_inr": COST_REFERENCE_NOTIONAL_INR,
            "buy_cost_bps": buy_cost_bps,
            "sell_cost_bps": sell_cost_bps,
            "spread_included": False,
            "market_impact_included": False,
        },
        "frozen_parameters": {
            "risk_aversion": RISK_AVERSION,
            "max_name_weight": DEFAULT_MAX_NAME_WEIGHT,
            "max_invested_weight": DEFAULT_MAX_INVESTED_WEIGHT,
            "max_traded_fraction_of_nav": DEFAULT_MAX_TRADED_FRACTION,
            "terminal_liquidation": True,
            "factor_bounds": {},
        },
        "common_identity_count": len(common),
        "top_decile_count": len(top_decile),
        "alpha_distribution": {
            "min": min(alphas),
            "median": float(statistics.median(alphas)),
            "max": max(alphas),
            "positive_count": sum(value > 0.0 for value in alphas),
        },
        "portfolios": {
            "equal_weight_top_decile": baseline_equal,
            "positive_alpha_proportional_top_decile": (
                baseline_proportional
            ),
            "risk_aware_zero_cost": _optimizer_summary(
                name="RISK_AWARE_ZERO_COST",
                artifact=risk_aware,
            ),
            "full_po001_observable_cost_floor": _optimizer_summary(
                name="FULL_PO001_OBSERVABLE_COST_FLOOR",
                artifact=full,
            ),
        },
        "interpretation_limits": {
            "no_realized_5d_outcome": True,
            "tc001_spread_included": False,
            "tc001_market_impact_included": False,
            "sector_factor_available": False,
            "size_factor_available": False,
            "prospective_alpha_claim": False,
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact
