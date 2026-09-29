from __future__ import annotations

import math
import statistics
from dataclasses import asdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_model import (
    fit_ridge,
    project_examples,
    purge_training_examples,
)
from marketlab.alpha_multihorizon import build_action_safe_horizon_examples
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_t004_prospective import _score_model
from marketlab.po001 import (
    DEFAULT_MAX_INVESTED_WEIGHT,
    DEFAULT_MAX_NAME_WEIGHT,
    DEFAULT_MAX_TRADED_FRACTION,
    optimize_portfolio,
)
from marketlab.po001_i001 import (
    COST_REFERENCE_NOTIONAL_INR,
    RISK_AVERSION,
)
from marketlab.po001_v2 import (
    DEFAULT_IMPACT_COEFFICIENT,
    DEFAULT_MAX_PARTICIPATION,
    optimize_portfolio_v2,
)
from marketlab.tc001 import TC001Config, observable_side_cost

STUDY_ID = "PO001-I003-v1"
DECISION_SESSION = "2026-08-31"
HORIZON_SESSIONS = 5
VALIDATION_START_SESSION = "2026-07-01"
RIDGE_L2 = 1.0
MIN_COMMON_IDENTITIES = 500
NAV_SURFACES_INR = (1_000_000.0, 10_000_000.0, 100_000_000.0)
PRIMARY_NAV_INR = 10_000_000.0
RISK_EQUIVALENCE_TOLERANCE = 5e-15
ALPHA_PREDICTION_EQUIVALENCE_TOLERANCE = 1e-12

EXPECTED_MODEL_SHA256 = (
    "179ce84f40c1b6e461d2ff1f4104753381d3327b2dda35814b4a913547f91260"
)
EXPECTED_DELIVERY_PANEL_SHA256 = (
    "47ee538af6cfca16405632ce6396571455a548687b4ceabfd7999040a86f8b44"
)
EXPECTED_LEGACY_RISK_STATE_SHA256 = (
    "b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1"
)
EXPECTED_V1_OPTIMIZER_SHA256 = (
    "ad77db26c76e54921254aea9e49c30da8b1f044076b57961671229e93100154e"
)


def _verify_hash(
    payload: dict[str, Any],
    *,
    hash_field: str,
    name: str,
) -> None:
    stored = str(payload.get(hash_field) or "")
    unsigned = dict(payload)
    unsigned.pop(hash_field, None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} hash mismatch")


def _validate_i003_risk_inputs(
    legacy_risk_state: dict[str, Any],
    canonical_risk_state: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        legacy_risk_state,
        hash_field="state_sha256",
        name="I003 pinned I002 RM001 risk state",
    )
    _verify_hash(
        canonical_risk_state,
        hash_field="state_sha256",
        name="I003 canonical RM001 rebuild",
    )
    if (
        legacy_risk_state["state_sha256"]
        != EXPECTED_LEGACY_RISK_STATE_SHA256
    ):
        raise AlphaContractError(
            "I003 pinned risk state does not reproduce sealed I002"
        )

    invariant_fields = (
        "model_id",
        "as_of_session",
        "factor_names",
        "factor_covariance_window",
        "factor_covariance_first_realized_session",
        "factor_covariance_last_realized_session",
        "idiosyncratic_window",
        "minimum_idiosyncratic_observations",
        "security_count",
        "deferred_factors",
    )
    for field in invariant_fields:
        if legacy_risk_state.get(field) != canonical_risk_state.get(field):
            raise AlphaContractError(
                f"I003 RM001 economic invariant differs: {field}"
            )
    if str(legacy_risk_state.get("as_of_session") or "") != DECISION_SESSION:
        raise AlphaContractError("I003 pinned RM001 decision clock mismatch")

    legacy_rows = {
        (str(row["symbol"]), str(row["isin"])): row
        for row in legacy_risk_state["rows"]
    }
    canonical_rows = {
        (str(row["symbol"]), str(row["isin"])): row
        for row in canonical_risk_state["rows"]
    }
    if legacy_rows.keys() != canonical_rows.keys():
        raise AlphaContractError(
            "I003 legacy/canonical RM001 identity sets differ"
        )

    factor_names = [str(value) for value in legacy_risk_state["factor_names"]]
    max_exposure_diff = 0.0
    max_idio_diff = 0.0
    status_diff_count = 0
    for identity in sorted(legacy_rows):
        left = legacy_rows[identity]
        right = canonical_rows[identity]
        for factor in factor_names:
            max_exposure_diff = max(
                max_exposure_diff,
                abs(
                    float(left["exposures"][factor])
                    - float(right["exposures"][factor])
                ),
            )
        max_idio_diff = max(
            max_idio_diff,
            abs(
                float(left["idiosyncratic_variance_daily"])
                - float(right["idiosyncratic_variance_daily"])
            ),
        )
        status_diff_count += (
            left["idiosyncratic_status"]
            != right["idiosyncratic_status"]
        )

    max_covariance_diff = 0.0
    for left_row, right_row in zip(
        legacy_risk_state["factor_covariance_daily"],
        canonical_risk_state["factor_covariance_daily"],
        strict=True,
    ):
        for left, right in zip(left_row, right_row, strict=True):
            max_covariance_diff = max(
                max_covariance_diff,
                abs(float(left) - float(right)),
            )

    fallback_diff = abs(
        float(legacy_risk_state["idiosyncratic_fallback_p75"])
        - float(canonical_risk_state["idiosyncratic_fallback_p75"])
    )
    tol = RISK_EQUIVALENCE_TOLERANCE
    if max_exposure_diff > tol:
        raise AlphaContractError(
            "I003 canonical RM001 exposure drift exceeds frozen P5 tolerance"
        )
    if max_covariance_diff > tol:
        raise AlphaContractError(
            "I003 canonical RM001 covariance drift exceeds frozen P5 tolerance"
        )
    if max_idio_diff > tol:
        raise AlphaContractError(
            "I003 canonical RM001 idiosyncratic drift exceeds frozen P5 tolerance"
        )
    if fallback_diff > tol:
        raise AlphaContractError(
            "I003 canonical RM001 fallback drift exceeds frozen P5 tolerance"
        )
    if status_diff_count:
        raise AlphaContractError(
            "I003 canonical RM001 idiosyncratic statuses differ"
        )

    return {
        "pinned_risk_state_sha256": legacy_risk_state["state_sha256"],
        "fresh_canonical_risk_state_sha256": canonical_risk_state[
            "state_sha256"
        ],
        "tolerance": tol,
        "max_exposure_abs_diff": max_exposure_diff,
        "max_covariance_abs_diff": max_covariance_diff,
        "max_idiosyncratic_variance_abs_diff": max_idio_diff,
        "idiosyncratic_fallback_abs_diff": fallback_diff,
        "idiosyncratic_status_diff_count": status_diff_count,
        "economic_equivalence_passed": True,
    }


def _validate_pinned_alpha_model(model: dict[str, Any]) -> None:
    stored = str(model.get("model_sha256") or "")
    unsigned = dict(model)
    unsigned.pop("model_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError("I003 pinned alpha model hash mismatch")
    if stored != EXPECTED_MODEL_SHA256:
        raise AlphaContractError(
            "I003 pinned alpha model does not reproduce sealed I002"
        )
    if model.get("model_id") != "AE001-T003-H5-F2-AUGMENTED-RIDGE-I002":
        raise AlphaContractError("I003 pinned alpha model ID mismatch")
    if float(model.get("l2")) != RIDGE_L2:
        raise AlphaContractError("I003 pinned alpha ridge penalty mismatch")
    if int(model.get("training_example_count")) != 169825:
        raise AlphaContractError("I003 pinned alpha training count mismatch")
    if str(model.get("training_last_exit_session") or "") != "2026-06-30":
        raise AlphaContractError("I003 pinned alpha training boundary mismatch")


def _validate_alpha_diagnostic(
    pinned_model: dict[str, Any],
    diagnostic_model: Any,
    decision_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    diagnostic = asdict(diagnostic_model)
    structural_fields = (
        "model_id",
        "feature_names",
        "l2",
        "training_example_count",
        "training_last_exit_session",
    )
    for field in structural_fields:
        if pinned_model.get(field) != diagnostic.get(field):
            raise AlphaContractError(
                f"I003 diagnostic alpha structural invariant differs: {field}"
            )

    pinned_predictions = _score_model(pinned_model, decision_rows)
    diagnostic_predictions = _score_model(diagnostic, decision_rows)
    pinned_map = {
        (str(row["symbol"]), str(row["isin"])): float(row["prediction"])
        for row in pinned_predictions
    }
    diagnostic_map = {
        (str(row["symbol"]), str(row["isin"])): float(row["prediction"])
        for row in diagnostic_predictions
    }
    if pinned_map.keys() != diagnostic_map.keys():
        raise AlphaContractError(
            "I003 pinned/diagnostic alpha identity sets differ"
        )
    max_prediction_diff = max(
        abs(pinned_map[key] - diagnostic_map[key])
        for key in pinned_map
    )
    if max_prediction_diff > ALPHA_PREDICTION_EQUIVALENCE_TOLERANCE:
        raise AlphaContractError(
            "I003 diagnostic alpha drift exceeds frozen P5 tolerance"
        )

    bucket_size = max(1, math.ceil(len(pinned_map) * 0.10))
    pinned_order = sorted(
        pinned_map,
        key=lambda identity: (
            -pinned_map[identity],
            identity[0],
            identity[1],
        ),
    )
    diagnostic_order = sorted(
        diagnostic_map,
        key=lambda identity: (
            -diagnostic_map[identity],
            identity[0],
            identity[1],
        ),
    )
    pinned_top = set(pinned_order[:bucket_size])
    diagnostic_top = set(diagnostic_order[:bucket_size])
    symmetric_diff_count = len(pinned_top ^ diagnostic_top)
    if symmetric_diff_count:
        raise AlphaContractError(
            "I003 diagnostic alpha top-decile identity set differs"
        )

    return {
        "pinned_model_sha256": pinned_model["model_sha256"],
        "fresh_diagnostic_model_sha256": diagnostic_model.model_sha256,
        "prediction_tolerance": ALPHA_PREDICTION_EQUIVALENCE_TOLERANCE,
        "max_prediction_abs_diff": max_prediction_diff,
        "top_decile_count": bucket_size,
        "top_decile_symmetric_diff_count": symmetric_diff_count,
        "economic_equivalence_passed": True,
    }


def _execution_inputs(
    *,
    market_panel: dict[str, Any],
    delivery_feature_panel: dict[str, Any],
    identities: list[tuple[str, str]],
) -> dict[tuple[str, str], dict[str, float]]:
    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 20:
        raise AlphaContractError("I003 market panel has insufficient sessions")
    sessions = sorted(sessions, key=lambda row: str(row["session_date"]))
    if str(sessions[-1]["session_date"]) != DECISION_SESSION:
        raise AlphaContractError(
            "I003 market panel does not end on frozen decision session"
        )
    trailing = sessions[-20:]

    turnover_by_identity: dict[tuple[str, str], list[float]] = {
        identity: [] for identity in identities
    }
    wanted = set(identities)
    for session in trailing:
        seen: set[tuple[str, str]] = set()
        for raw in session.get("equities", []):
            identity = (str(raw["symbol"]), str(raw["isin"]))
            if identity not in wanted:
                continue
            if identity in seen:
                raise AlphaContractError(
                    f"I003 duplicate market identity in {session['session_date']}"
                )
            seen.add(identity)
            value = float(raw["turnover_inr"])
            if not math.isfinite(value) or value <= 0:
                raise AlphaContractError(
                    f"I003 invalid turnover for {identity}"
                )
            turnover_by_identity[identity].append(value)

    raw_decision_rows = {
        (str(row["symbol"]), str(row["isin"])): row
        for row in delivery_feature_panel.get("rows", [])
        if str(row.get("feature_session")) == DECISION_SESSION
    }
    result = {}
    for identity in identities:
        turnovers = turnover_by_identity.get(identity, [])
        if len(turnovers) != 20:
            raise AlphaContractError(
                f"I003 identity lacks 20 contiguous turnover observations: {identity}"
            )
        feature_row = raw_decision_rows.get(identity)
        if feature_row is None:
            raise AlphaContractError(
                f"I003 identity absent from decision feature panel: {identity}"
            )
        values = feature_row.get("values")
        if not isinstance(values, dict):
            raise AlphaContractError("I003 feature values must be an object")
        volatility = float(values.get("realized_vol_20"))
        if not math.isfinite(volatility) or volatility < 0:
            raise AlphaContractError(
                f"I003 invalid realized_vol_20 for {identity}"
            )
        result[identity] = {
            "adv20_inr": float(statistics.median(turnovers)),
            "daily_volatility_decimal": volatility,
        }
    return result


def _v2_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    rows = [
        row
        for row in artifact["rows"]
        if float(row["target_weight"]) > 1e-12
    ]
    hhi = sum(float(row["target_weight"]) ** 2 for row in rows)
    top = sorted(
        rows,
        key=lambda row: (
            -float(row["target_weight"]),
            -float(row["expected_excess_return"]),
            row["symbol"],
            row["isin"],
        ),
    )
    return {
        "optimizer_id": artifact["optimizer_id"],
        "artifact_sha256": artifact["artifact_sha256"],
        "portfolio_nav_inr": artifact["portfolio_nav_inr"],
        "holding_count": len(rows),
        "invested_weight": artifact["invested_weight"],
        "cash_weight": artifact["cash_weight"],
        "expected_5d_excess_return": artifact["expected_excess_return"],
        "annualized_volatility": math.sqrt(
            float(artifact["total_variance_daily"]) * 252.0
        ),
        "factor_variance_daily": artifact["factor_variance_daily"],
        "idiosyncratic_variance_daily": artifact[
            "idiosyncratic_variance_daily"
        ],
        "total_variance_daily": artifact["total_variance_daily"],
        "risk_penalty": artifact["risk_penalty"],
        "immediate_observable_cost_fraction": artifact[
            "immediate_observable_cost_fraction"
        ],
        "immediate_impact_cost_fraction": artifact[
            "immediate_impact_cost_fraction"
        ],
        "terminal_observable_cost_fraction": artifact[
            "terminal_observable_cost_fraction"
        ],
        "terminal_impact_cost_fraction": artifact[
            "terminal_impact_cost_fraction"
        ],
        "total_transaction_cost_fraction": artifact[
            "total_transaction_cost_fraction"
        ],
        "objective_utility": artifact["objective_utility"],
        "maximum_observed_participation": artifact[
            "maximum_observed_participation"
        ],
        "max_name_weight": (
            max(float(row["target_weight"]) for row in rows)
            if rows
            else 0.0
        ),
        "weight_hhi": hhi,
        "effective_number_of_names": (
            None if hhi <= 0 else 1.0 / hhi
        ),
        "portfolio_factor_exposures": artifact[
            "portfolio_factor_exposures"
        ],
        "solver": artifact["solver"],
        "top_holdings": [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "target_weight": row["target_weight"],
                "expected_excess_return": row[
                    "expected_excess_return"
                ],
                "adv20_inr": row["adv20_inr"],
                "daily_volatility_decimal": row[
                    "daily_volatility_decimal"
                ],
                "terminal_liquidation_participation": row[
                    "terminal_liquidation_participation"
                ],
            }
            for row in top[:25]
        ],
    }


def _v1_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    rows = [
        row
        for row in artifact["rows"]
        if float(row["target_weight"]) > 1e-12
    ]
    hhi = sum(float(row["target_weight"]) ** 2 for row in rows)
    return {
        "optimizer_id": artifact["optimizer_id"],
        "artifact_sha256": artifact["artifact_sha256"],
        "holding_count": len(rows),
        "invested_weight": artifact["invested_weight"],
        "cash_weight": artifact["cash_weight"],
        "expected_5d_excess_return": artifact["expected_excess_return"],
        "annualized_volatility": math.sqrt(
            float(artifact["total_variance_daily"]) * 252.0
        ),
        "total_variance_daily": artifact["total_variance_daily"],
        "risk_penalty": artifact["risk_penalty"],
        "immediate_transaction_cost_fraction": artifact[
            "immediate_transaction_cost_fraction"
        ],
        "terminal_liquidation_cost_fraction": artifact[
            "terminal_liquidation_cost_fraction"
        ],
        "objective_utility": artifact["objective_utility"],
        "max_name_weight": (
            max(float(row["target_weight"]) for row in rows)
            if rows
            else 0.0
        ),
        "weight_hhi": hhi,
        "effective_number_of_names": (
            None if hhi <= 0 else 1.0 / hhi
        ),
        "portfolio_factor_exposures": artifact[
            "portfolio_factor_exposures"
        ],
        "solver": artifact["solver"],
    }


def run_po001_i003(
    *,
    delivery_feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    risk_state: dict[str, Any],
    canonical_risk_state: dict[str, Any],
    pinned_alpha_model: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        delivery_feature_panel,
        hash_field="panel_sha256",
        name="I003 delivery feature panel",
    )
    _verify_hash(
        market_panel,
        hash_field="panel_sha256",
        name="I003 market panel",
    )
    _verify_hash(
        action_ledger,
        hash_field="ledger_sha256",
        name="I003 action ledger",
    )
    risk_equivalence = _validate_i003_risk_inputs(
        risk_state,
        canonical_risk_state,
    )
    _validate_pinned_alpha_model(pinned_alpha_model)
    if delivery_feature_panel["panel_sha256"] != EXPECTED_DELIVERY_PANEL_SHA256:
        raise AlphaContractError(
            "I003 delivery feature panel does not reproduce sealed I002"
        )

    ranked = (
        delivery_feature_panel
        if delivery_feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(delivery_feature_panel)
    )
    feature_names = [
        definition.name
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    definitions = ranked.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("I003 feature definitions are missing")
    if {str(row["name"]) for row in definitions} != set(feature_names):
        raise AlphaContractError(
            "I003 feature panel differs from frozen 27 features"
        )

    examples_by_horizon, exclusions = build_action_safe_horizon_examples(
        feature_panel=ranked,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizons=(HORIZON_SESSIONS,),
    )
    examples = project_examples(
        examples_by_horizon[HORIZON_SESSIONS],
        feature_names=feature_names,
    )
    training = purge_training_examples(
        examples,
        validation_start_session=VALIDATION_START_SESSION,
    )
    if len(training) < 100:
        raise AlphaContractError("I003 training set is too small")
    diagnostic_model = fit_ridge(
        training,
        feature_names=feature_names,
        l2=RIDGE_L2,
        model_id="AE001-T003-H5-F2-AUGMENTED-RIDGE-I002",
    )
    decision_rows = [
        row
        for row in ranked.get("rows", [])
        if str(row.get("feature_session")) == DECISION_SESSION
    ]
    if not decision_rows:
        raise AlphaContractError(
            "I003 delivery panel lacks decision session"
        )
    alpha_equivalence = _validate_alpha_diagnostic(
        pinned_alpha_model,
        diagnostic_model,
        decision_rows,
    )
    predictions = _score_model(pinned_alpha_model, decision_rows)
    alpha_all = {
        (str(row["symbol"]), str(row["isin"])): float(row["prediction"])
        for row in predictions
    }
    risk_identities = {
        (str(row["symbol"]), str(row["isin"]))
        for row in risk_state["rows"]
    }
    common = sorted(set(alpha_all) & risk_identities)
    if len(common) < MIN_COMMON_IDENTITIES:
        raise AlphaContractError(
            f"I003 common universe below minimum: {len(common)}"
        )
    execution = _execution_inputs(
        market_panel=market_panel,
        delivery_feature_panel=delivery_feature_panel,
        identities=common,
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

    def v1_rows() -> list[dict[str, Any]]:
        return [
            {
                "symbol": identity[0],
                "isin": identity[1],
                "expected_excess_return": alpha_all[identity],
                "current_weight": 0.0,
                "buy_cost_bps": buy_cost_bps,
                "sell_cost_bps": sell_cost_bps,
            }
            for identity in common
        ]

    baseline = optimize_portfolio(
        decision_session=DECISION_SESSION,
        horizon_sessions=HORIZON_SESSIONS,
        alpha_rows=v1_rows(),
        risk_state=risk_state,
        risk_aversion=RISK_AVERSION,
        max_name_weight=DEFAULT_MAX_NAME_WEIGHT,
        max_invested_weight=DEFAULT_MAX_INVESTED_WEIGHT,
        max_traded_fraction_of_nav=DEFAULT_MAX_TRADED_FRACTION,
        factor_bounds={},
        terminal_liquidation=True,
    )
    if baseline["artifact_sha256"] != EXPECTED_V1_OPTIMIZER_SHA256:
        raise AlphaContractError(
            "I003 PO001-v1 baseline does not reproduce sealed I002"
        )

    def v2_rows() -> list[dict[str, Any]]:
        return [
            {
                "symbol": identity[0],
                "isin": identity[1],
                "expected_excess_return": alpha_all[identity],
                "current_weight": 0.0,
                "buy_cost_bps": buy_cost_bps,
                "sell_cost_bps": sell_cost_bps,
                "adv20_inr": execution[identity]["adv20_inr"],
                "daily_volatility_decimal": execution[identity][
                    "daily_volatility_decimal"
                ],
            }
            for identity in common
        ]

    nav_results = {}
    for nav in NAV_SURFACES_INR:
        artifact = optimize_portfolio_v2(
            decision_session=DECISION_SESSION,
            horizon_sessions=HORIZON_SESSIONS,
            alpha_rows=v2_rows(),
            risk_state=risk_state,
            portfolio_nav_inr=nav,
            risk_aversion=RISK_AVERSION,
            impact_coefficient=DEFAULT_IMPACT_COEFFICIENT,
            max_participation=DEFAULT_MAX_PARTICIPATION,
            max_name_weight=DEFAULT_MAX_NAME_WEIGHT,
            max_invested_weight=DEFAULT_MAX_INVESTED_WEIGHT,
            max_traded_fraction_of_nav=DEFAULT_MAX_TRADED_FRACTION,
            factor_bounds={},
            terminal_liquidation=True,
        )
        nav_results[str(int(nav))] = _v2_summary(artifact)

    primary = nav_results[str(int(PRIMARY_NAV_INR))]
    adv_values = [execution[identity]["adv20_inr"] for identity in common]
    vol_values = [
        execution[identity]["daily_volatility_decimal"]
        for identity in common
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "evidence_class": "HISTORICAL_WALKFORWARD_OOS_COST_INTEGRATION",
        "decision_session": DECISION_SESSION,
        "horizon_sessions": HORIZON_SESSIONS,
        "realized_outcome_opened": False,
        "reproduction_gates": {
            "pinned_alpha_model_sha256": pinned_alpha_model["model_sha256"],
            "fresh_diagnostic_alpha_model_sha256": diagnostic_model.model_sha256,
            "alpha_model_resolution": "PIN_EXACT_SEALED_I002_MODEL_PER_P4",
            "alpha_numerical_equivalence": alpha_equivalence,
            "delivery_feature_panel_sha256": delivery_feature_panel[
                "panel_sha256"
            ],
            "legacy_i002_risk_state_sha256": risk_state["state_sha256"],
            "fresh_canonical_rm001_risk_state_sha256": canonical_risk_state[
                "state_sha256"
            ],
            "rm001_numerical_equivalence": risk_equivalence,
            "rm001_economic_equivalence_audit_run_id": 36579160593,
            "po001_equivalence_audit_run_id": 36579611661,
            "po001_equivalence_gate_passed": False,
            "resolution": "PIN_EXACT_SEALED_I002_RISK_STATE_PER_P3",
            "v1_optimizer_artifact_sha256": baseline["artifact_sha256"],
            "all_executable_reproduction_gates_matched": True,
        },
        "common_identity_count": len(common),
        "training_example_count": len(training),
        "training_last_exit_session": max(
            row.exit_session for row in training
        ),
        "training_exclusions": exclusions,
        "execution_input_distribution": {
            "adv20_inr_min": min(adv_values),
            "adv20_inr_median": float(statistics.median(adv_values)),
            "adv20_inr_max": max(adv_values),
            "volatility20_min": min(vol_values),
            "volatility20_median": float(statistics.median(vol_values)),
            "volatility20_max": max(vol_values),
        },
        "observable_cost_bps": {
            "buy": buy_cost_bps,
            "sell": sell_cost_bps,
        },
        "v1_observable_cost_baseline": _v1_summary(baseline),
        "v2_nav_surfaces": nav_results,
        "primary_nav_inr": PRIMARY_NAV_INR,
        "primary_v2": primary,
        "primary_delta_vs_v1": {
            "expected_5d_excess_return": (
                primary["expected_5d_excess_return"]
                - baseline["expected_excess_return"]
            ),
            "annualized_volatility": (
                primary["annualized_volatility"]
                - math.sqrt(
                    float(baseline["total_variance_daily"]) * 252.0
                )
            ),
            "invested_weight": (
                primary["invested_weight"] - baseline["invested_weight"]
            ),
            "holding_count": (
                primary["holding_count"]
                - _v1_summary(baseline)["holding_count"]
            ),
            "objective_utility": (
                primary["objective_utility"]
                - baseline["objective_utility"]
            ),
        },
        "impact_contract": {
            "impact_coefficient": DEFAULT_IMPACT_COEFFICIENT,
            "maximum_participation": DEFAULT_MAX_PARTICIPATION,
            "quoted_spread_included": False,
            "calibrated_to_nse_execution": False,
        },
        "interpretation_limits": {
            "no_realized_5d_outcome": True,
            "prospective_alpha_claim": False,
            "quoted_spread_source_frozen": False,
            "impact_model_calibrated": False,
            "sector_factor_available": False,
            "size_factor_available": False,
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
