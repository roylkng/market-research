from __future__ import annotations

import copy
import math
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_t004_prospective import _score_model
from marketlab.po001 import (
    DEFAULT_MAX_INVESTED_WEIGHT,
    DEFAULT_MAX_NAME_WEIGHT,
    DEFAULT_MAX_TRADED_FRACTION,
)
from marketlab.po001_i001 import COST_REFERENCE_NOTIONAL_INR, RISK_AVERSION
from marketlab.po001_i003 import (
    DECISION_SESSION,
    HORIZON_SESSIONS,
    MIN_COMMON_IDENTITIES,
    _execution_inputs,
    _validate_pinned_alpha_model,
)
from marketlab.po001_v3 import (
    DEFAULT_IMPACT_COEFFICIENT,
    DEFAULT_MAX_PARTICIPATION,
    optimize_portfolio_v3,
)
from marketlab.tc001 import TC001Config, observable_side_cost

STUDY_ID = "PO001-I004-v1"
PORTFOLIO_NAV_INR = 10_000_000.0
LEGACY_I003_DELIVERY_FEATURE_PANEL_SHA256 = (
    "47ee538af6cfca16405632ce6396571455a548687b4ceabfd7999040a86f8b44"
)
EXPECTED_RAW_DELIVERY_PANEL_SHA256 = (
    "3d1755bad85a8cebcbc27effbe3a1a4c33a01ebdad47a0c9ea15a89febb6de96"
)
EXPECTED_DELIVERY_DEFINITION_PROJECTION_SHA256 = (
    "de753b2357df96308d999adb1636c18d2c0770cf3e9e5f631b9ba7cbb577bd7b"
)
EXPECTED_DELIVERY_SESSION_PROJECTION_SHA256 = (
    "9f5ce211cd75f2e921bbad383bbc7a7ce81ef1c22a91bb6dae85bc68454defa6"
)
EXPECTED_DELIVERY_ROW_PROJECTION_SHA256 = (
    "640694c8c5e44398281912b0d2d64551f63d21f9a76d33ebde577f5e3038a163"
)
EXPECTED_DELIVERY_FEATURE_ROW_COUNT = 234401
FEATURE_EQUIVALENCE_AUDIT_RUN_ID = 36967504413
EXPECTED_CONTROL_RISK_SHA256 = (
    "b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1"
)
EXPECTED_TREATMENT_RISK_SHA256 = (
    "32002ec101531c0e28fb551058c79f179fca53aafccf3c36ef07cb0159387441"
)
CONTROL_SCALAR_TOLERANCE = 1e-10
FROZEN_COMMON_IDENTITY_COUNT = 1307
FROZEN_CONTROL = {
    "holding_count": 47,
    "expected_5d_excess_return": 0.010268398328395899,
    "annualized_volatility": 0.12926327992563452,
    "total_transaction_cost_fraction": 0.00268388045086663,
    "immediate_impact_cost_fraction": 0.00022953422543330209,
    "terminal_impact_cost_fraction": 0.00022953422543330209,
    "maximum_observed_participation": 0.0036964433816679327,
    "objective_utility": 0.005926879431385127,
}


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


def _validate_i004_feature_panel(
    delivery_feature_panel: dict[str, Any],
) -> dict[str, Any]:
    raw_delivery_sha = str(
        delivery_feature_panel.get("delivery_panel_sha256") or ""
    )
    if raw_delivery_sha != EXPECTED_RAW_DELIVERY_PANEL_SHA256:
        raise AlphaContractError(
            "I004 raw delivery panel differs from frozen P1 source"
        )
    rows = delivery_feature_panel.get("rows")
    sessions = delivery_feature_panel.get("sessions")
    definitions = delivery_feature_panel.get("feature_definitions")
    if (
        not isinstance(rows, list)
        or not isinstance(sessions, list)
        or not isinstance(definitions, list)
    ):
        raise AlphaContractError(
            "I004 delivery feature panel is missing canonical projections"
        )
    if len(rows) != EXPECTED_DELIVERY_FEATURE_ROW_COUNT:
        raise AlphaContractError(
            f"I004 delivery feature row count changed: {len(rows)}"
        )
    row_projection = [
        {
            "feature_session": row["feature_session"],
            "symbol": row["symbol"],
            "isin": row["isin"],
            "values": row["values"],
        }
        for row in rows
    ]
    session_projection = [
        {
            "session_date": row["session_date"],
            "eligible_count": row["eligible_count"],
            "universe_sha256": row["universe_sha256"],
        }
        for row in sessions
    ]
    definition_sha = digest(definitions)
    session_sha = digest(session_projection)
    row_sha = digest(row_projection)
    if definition_sha != EXPECTED_DELIVERY_DEFINITION_PROJECTION_SHA256:
        raise AlphaContractError(
            "I004 delivery feature definitions differ from frozen P1"
        )
    if session_sha != EXPECTED_DELIVERY_SESSION_PROJECTION_SHA256:
        raise AlphaContractError(
            "I004 delivery session universe differs from frozen P1"
        )
    if row_sha != EXPECTED_DELIVERY_ROW_PROJECTION_SHA256:
        raise AlphaContractError(
            "I004 stock-date delivery feature values differ from frozen P1"
        )
    return {
        "legacy_i003_top_level_panel_sha256": (
            LEGACY_I003_DELIVERY_FEATURE_PANEL_SHA256
        ),
        "current_top_level_panel_sha256": delivery_feature_panel.get(
            "panel_sha256"
        ),
        "raw_delivery_panel_sha256": raw_delivery_sha,
        "definition_projection_sha256": definition_sha,
        "session_projection_sha256": session_sha,
        "row_projection_sha256": row_sha,
        "feature_row_count": len(rows),
        "equivalence_audit_run_id": FEATURE_EQUIVALENCE_AUDIT_RUN_ID,
        "economic_equivalence_passed": True,
    }


def _validate_risk_state(
    risk_state: dict[str, Any],
    *,
    expected_sha256: str,
    expected_model_id: str,
    name: str,
) -> None:
    _verify_hash(risk_state, hash_field="state_sha256", name=name)
    if risk_state["state_sha256"] != expected_sha256:
        raise AlphaContractError(f"{name} does not match frozen SHA")
    if risk_state.get("model_id") != expected_model_id:
        raise AlphaContractError(f"{name} model ID mismatch")
    if str(risk_state.get("as_of_session") or "") != DECISION_SESSION:
        raise AlphaContractError(f"{name} decision session mismatch")
    if risk_state.get("live_capital_allowed") is not False:
        raise AlphaContractError(f"{name} must remain research-only")


def _summarize(artifact: dict[str, Any]) -> dict[str, Any]:
    active = [
        row
        for row in artifact["rows"]
        if float(row["target_weight"]) > 1e-12
    ]
    hhi = sum(float(row["target_weight"]) ** 2 for row in active)
    return {
        "optimizer_id": artifact["optimizer_id"],
        "artifact_sha256": artifact["artifact_sha256"],
        "factor_names": list(
            artifact["portfolio_factor_exposures"].keys()
        ),
        "holding_count": len(active),
        "invested_weight": float(artifact["invested_weight"]),
        "cash_weight": float(artifact["cash_weight"]),
        "expected_5d_excess_return": float(
            artifact["expected_excess_return"]
        ),
        "annualized_volatility": math.sqrt(
            float(artifact["total_variance_daily"]) * 252.0
        ),
        "factor_variance_daily": float(
            artifact["factor_variance_daily"]
        ),
        "idiosyncratic_variance_daily": float(
            artifact["idiosyncratic_variance_daily"]
        ),
        "total_variance_daily": float(
            artifact["total_variance_daily"]
        ),
        "risk_penalty": float(artifact["risk_penalty"]),
        "immediate_observable_cost_fraction": float(
            artifact["immediate_observable_cost_fraction"]
        ),
        "immediate_impact_cost_fraction": float(
            artifact["immediate_impact_cost_fraction"]
        ),
        "terminal_observable_cost_fraction": float(
            artifact["terminal_observable_cost_fraction"]
        ),
        "terminal_impact_cost_fraction": float(
            artifact["terminal_impact_cost_fraction"]
        ),
        "total_transaction_cost_fraction": float(
            artifact["total_transaction_cost_fraction"]
        ),
        "maximum_observed_participation": float(
            artifact["maximum_observed_participation"]
        ),
        "objective_utility": float(artifact["objective_utility"]),
        "portfolio_factor_exposures": {
            str(key): float(value)
            for key, value in artifact[
                "portfolio_factor_exposures"
            ].items()
        },
        "weight_hhi": hhi,
        "effective_number_of_names": (
            None if hhi <= 0.0 else 1.0 / hhi
        ),
    }


def _validate_control_reproduction(summary: dict[str, Any]) -> None:
    if summary["holding_count"] != FROZEN_CONTROL["holding_count"]:
        raise AlphaContractError(
            "I004 control holding count does not reproduce I003"
        )
    for field in (
        "expected_5d_excess_return",
        "annualized_volatility",
        "total_transaction_cost_fraction",
        "immediate_impact_cost_fraction",
        "terminal_impact_cost_fraction",
        "maximum_observed_participation",
        "objective_utility",
    ):
        difference = abs(
            float(summary[field]) - float(FROZEN_CONTROL[field])
        )
        if difference > CONTROL_SCALAR_TOLERANCE:
            raise AlphaContractError(
                f"I004 control does not reproduce I003: {field} "
                f"diff={difference}"
            )


def _weights(artifact: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {
        (str(row["symbol"]), str(row["isin"])): float(
            row["target_weight"]
        )
        for row in artifact["rows"]
    }


def _weight_changes(
    control: dict[str, Any],
    treatment: dict[str, Any],
) -> dict[str, Any]:
    left = _weights(control)
    right = _weights(treatment)
    if left.keys() != right.keys():
        raise AlphaContractError(
            "I004 control/treatment optimizer identity sets differ"
        )
    changes = [
        {
            "symbol": identity[0],
            "isin": identity[1],
            "control_weight": left[identity],
            "treatment_weight": right[identity],
            "delta_weight": right[identity] - left[identity],
        }
        for identity in sorted(left)
    ]
    l1 = sum(abs(row["delta_weight"]) for row in changes)
    maximum = max(
        (abs(row["delta_weight"]) for row in changes),
        default=0.0,
    )
    increased = sorted(
        changes,
        key=lambda row: (
            -float(row["delta_weight"]),
            row["symbol"],
            row["isin"],
        ),
    )
    decreased = sorted(
        changes,
        key=lambda row: (
            float(row["delta_weight"]),
            row["symbol"],
            row["isin"],
        ),
    )
    return {
        "weight_l1_change": l1,
        "maximum_absolute_weight_change": maximum,
        "changed_identity_count_gt_1bp": sum(
            abs(row["delta_weight"]) > 0.0001 for row in changes
        ),
        "top_weight_increases": increased[:20],
        "top_weight_decreases": decreased[:20],
    }


def run_po001_i004(
    *,
    delivery_feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    pinned_alpha_model: dict[str, Any],
    control_risk_state: dict[str, Any],
    treatment_risk_state: dict[str, Any],
) -> dict[str, Any]:
    _validate_pinned_alpha_model(pinned_alpha_model)
    _validate_risk_state(
        control_risk_state,
        expected_sha256=EXPECTED_CONTROL_RISK_SHA256,
        expected_model_id="RM001-v1-DEVELOPMENT",
        name="I004 control RM001-v1 state",
    )
    _validate_risk_state(
        treatment_risk_state,
        expected_sha256=EXPECTED_TREATMENT_RISK_SHA256,
        expected_model_id="RM001-v3-DEVELOPMENT",
        name="I004 treatment RM001-v3 state",
    )
    feature_equivalence = _validate_i004_feature_panel(
        delivery_feature_panel
    )

    ranked = (
        delivery_feature_panel
        if delivery_feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(delivery_feature_panel)
    )
    decision_rows = [
        row
        for row in ranked.get("rows", [])
        if str(row.get("feature_session")) == DECISION_SESSION
    ]
    if not decision_rows:
        raise AlphaContractError(
            "I004 delivery feature panel lacks decision session"
        )
    predictions = _score_model(pinned_alpha_model, decision_rows)
    alpha_all = {
        (str(row["symbol"]), str(row["isin"])): float(row["prediction"])
        for row in predictions
    }

    control_ids = {
        (str(row["symbol"]), str(row["isin"]))
        for row in control_risk_state["rows"]
    }
    treatment_ids = {
        (str(row["symbol"]), str(row["isin"]))
        for row in treatment_risk_state["rows"]
    }
    if control_ids != treatment_ids:
        raise AlphaContractError(
            "I004 RM001-v1/v3 security identity sets differ"
        )
    common = sorted(set(alpha_all) & control_ids)
    if len(common) < MIN_COMMON_IDENTITIES:
        raise AlphaContractError(
            f"I004 common universe below minimum: {len(common)}"
        )
    if len(common) != FROZEN_COMMON_IDENTITY_COUNT:
        raise AlphaContractError(
            f"I004 frozen common identity count changed: {len(common)}"
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

    alpha_rows = [
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

    kwargs = {
        "decision_session": DECISION_SESSION,
        "horizon_sessions": HORIZON_SESSIONS,
        "alpha_rows": alpha_rows,
        "portfolio_nav_inr": PORTFOLIO_NAV_INR,
        "risk_aversion": RISK_AVERSION,
        "impact_coefficient": DEFAULT_IMPACT_COEFFICIENT,
        "max_participation": DEFAULT_MAX_PARTICIPATION,
        "max_name_weight": DEFAULT_MAX_NAME_WEIGHT,
        "max_invested_weight": DEFAULT_MAX_INVESTED_WEIGHT,
        "max_traded_fraction_of_nav": DEFAULT_MAX_TRADED_FRACTION,
        "factor_bounds": {},
        "terminal_liquidation": True,
    }
    control = optimize_portfolio_v3(
        risk_state=control_risk_state,
        **kwargs,
    )
    control_summary = _summarize(control)
    _validate_control_reproduction(control_summary)

    treatment = optimize_portfolio_v3(
        risk_state=treatment_risk_state,
        **kwargs,
    )
    treatment_summary = _summarize(treatment)
    weight_changes = _weight_changes(control, treatment)

    common_factor_names = [
        factor
        for factor in control_summary["factor_names"]
        if factor in treatment_summary["factor_names"]
    ]
    common_factor_exposure_changes = {
        factor: (
            treatment_summary["portfolio_factor_exposures"][factor]
            - control_summary["portfolio_factor_exposures"][factor]
        )
        for factor in common_factor_names
    }
    new_factor_exposures = {
        factor: treatment_summary["portfolio_factor_exposures"][factor]
        for factor in treatment_summary["factor_names"]
        if factor not in control_summary["factor_names"]
    }

    report: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "evidence_class": "HISTORICAL_OOS_RISK_TREATMENT_INTEGRATION",
        "decision_session": DECISION_SESSION,
        "horizon_sessions": HORIZON_SESSIONS,
        "portfolio_nav_inr": PORTFOLIO_NAV_INR,
        "realized_outcome_opened": False,
        "alpha_model_sha256": pinned_alpha_model["model_sha256"],
        "delivery_feature_panel_sha256": delivery_feature_panel[
            "panel_sha256"
        ],
        "delivery_feature_economic_equivalence": feature_equivalence,
        "control_risk_state_sha256": control_risk_state["state_sha256"],
        "treatment_risk_state_sha256": treatment_risk_state["state_sha256"],
        "common_identity_count": len(common),
        "execution_contract": {
            "impact_coefficient": DEFAULT_IMPACT_COEFFICIENT,
            "max_participation": DEFAULT_MAX_PARTICIPATION,
            "observable_buy_cost_bps": buy_cost_bps,
            "observable_sell_cost_bps": sell_cost_bps,
            "max_name_weight": DEFAULT_MAX_NAME_WEIGHT,
            "max_invested_weight": DEFAULT_MAX_INVESTED_WEIGHT,
            "max_traded_fraction_of_nav": DEFAULT_MAX_TRADED_FRACTION,
            "risk_aversion": RISK_AVERSION,
            "terminal_liquidation": True,
            "factor_bounds": {},
        },
        "control_reproduction_passed": True,
        "control_rm001_v1": control_summary,
        "treatment_rm001_v3": treatment_summary,
        "treatment_minus_control": {
            "holding_count": (
                treatment_summary["holding_count"]
                - control_summary["holding_count"]
            ),
            "invested_weight": (
                treatment_summary["invested_weight"]
                - control_summary["invested_weight"]
            ),
            "expected_5d_excess_return": (
                treatment_summary["expected_5d_excess_return"]
                - control_summary["expected_5d_excess_return"]
            ),
            "annualized_volatility": (
                treatment_summary["annualized_volatility"]
                - control_summary["annualized_volatility"]
            ),
            "factor_variance_daily": (
                treatment_summary["factor_variance_daily"]
                - control_summary["factor_variance_daily"]
            ),
            "idiosyncratic_variance_daily": (
                treatment_summary["idiosyncratic_variance_daily"]
                - control_summary["idiosyncratic_variance_daily"]
            ),
            "total_variance_daily": (
                treatment_summary["total_variance_daily"]
                - control_summary["total_variance_daily"]
            ),
            "risk_penalty": (
                treatment_summary["risk_penalty"]
                - control_summary["risk_penalty"]
            ),
            "total_transaction_cost_fraction": (
                treatment_summary["total_transaction_cost_fraction"]
                - control_summary["total_transaction_cost_fraction"]
            ),
            "objective_utility": (
                treatment_summary["objective_utility"]
                - control_summary["objective_utility"]
            ),
            "weight_hhi": (
                treatment_summary["weight_hhi"]
                - control_summary["weight_hhi"]
            ),
            "effective_number_of_names": (
                treatment_summary["effective_number_of_names"]
                - control_summary["effective_number_of_names"]
            ),
        },
        "weight_changes": weight_changes,
        "common_factor_exposure_changes": common_factor_exposure_changes,
        "new_factor_exposures": new_factor_exposures,
        "interpretation_limits": {
            "no_realized_post_decision_outcome": True,
            "alpha_changed": False,
            "execution_inputs_changed": False,
            "optimizer_parameters_changed": False,
            "only_changed_input": "RISK_STATE",
            "rm001_v3_prospective_claim": False,
            "live_capital_allowed": False,
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
