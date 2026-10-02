from __future__ import annotations

import itertools
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
from marketlab.po001_i004 import (
    EXPECTED_CONTROL_RISK_SHA256,
    EXPECTED_TREATMENT_RISK_SHA256,
    FROZEN_COMMON_IDENTITY_COUNT,
    PORTFOLIO_NAV_INR,
    _summarize,
    _validate_i004_feature_panel,
    _validate_risk_state,
)
from marketlab.po001_v3 import (
    DEFAULT_IMPACT_COEFFICIENT,
    DEFAULT_MAX_PARTICIPATION,
)
from marketlab.po001_v4 import optimize_portfolio_v4
from marketlab.tc001 import TC001Config, observable_side_cost

STUDY_ID = "PO001-S001-v1"


def run_po001_s001_replica(
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
        name="S001 control RM001-v1 state",
    )
    _validate_risk_state(
        treatment_risk_state,
        expected_sha256=EXPECTED_TREATMENT_RISK_SHA256,
        expected_model_id="RM001-v3-DEVELOPMENT",
        name="S001 treatment RM001-v3 state",
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
            "S001 delivery feature panel lacks decision session"
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
            "S001 RM001-v1/v3 security identity sets differ"
        )
    common = sorted(set(alpha_all) & control_ids)
    if len(common) < MIN_COMMON_IDENTITIES:
        raise AlphaContractError(
            f"S001 common universe below minimum: {len(common)}"
        )
    if len(common) != FROZEN_COMMON_IDENTITY_COUNT:
        raise AlphaContractError(
            f"S001 frozen common identity count changed: {len(common)}"
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

    control = optimize_portfolio_v4(
        risk_state=control_risk_state,
        **kwargs,
    )
    treatment = optimize_portfolio_v4(
        risk_state=treatment_risk_state,
        **kwargs,
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "evidence_class": "HISTORICAL_OOS_NUMERICAL_SOLVER_STABILITY",
        "decision_session": DECISION_SESSION,
        "horizon_sessions": HORIZON_SESSIONS,
        "portfolio_nav_inr": PORTFOLIO_NAV_INR,
        "realized_outcome_opened": False,
        "alpha_model_sha256": pinned_alpha_model["model_sha256"],
        "control_risk_state_sha256": control_risk_state["state_sha256"],
        "treatment_risk_state_sha256": treatment_risk_state["state_sha256"],
        "delivery_feature_economic_equivalence": feature_equivalence,
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
        "control_rm001_v1": {
            "summary": _summarize(control),
            "artifact": control,
        },
        "treatment_rm001_v3": {
            "summary": _summarize(treatment),
            "artifact": treatment,
        },
        "interpretation_limits": {
            "numerical_stability_test_only": True,
            "realized_outcome_opened": False,
            "alpha_changed": False,
            "risk_changed_relative_to_i004": False,
            "execution_changed_relative_to_i004": False,
            "solver_only_changed_component": "PO001_V4",
            "live_capital_allowed": False,
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report



S001_SCALAR_LIMITS = {
    "expected_5d_excess_return": 1e-10,
    "annualized_volatility": 1e-9,
    "total_variance_daily": 1e-12,
    "risk_penalty": 1e-11,
    "total_transaction_cost_fraction": 1e-10,
    "objective_utility": 1e-10,
}
S001_MAX_WEIGHT_ABS_DIFF = 1e-10
S001_MAX_WEIGHT_L1_DIFF = 1e-8
S001_REPLICA_COUNT = 3


def _s001_weights(
    artifact: dict[str, Any],
) -> dict[tuple[str, str], float]:
    return {
        (str(row["symbol"]), str(row["isin"])): float(row["target_weight"])
        for row in artifact["rows"]
    }


def _s001_portfolio_stats(
    reports: list[dict[str, Any]],
    *,
    key: str,
) -> dict[str, Any]:
    artifacts = [report[key]["artifact"] for report in reports]
    identity_maps = [_s001_weights(artifact) for artifact in artifacts]
    identities = identity_maps[0].keys()
    if any(mapping.keys() != identities for mapping in identity_maps[1:]):
        raise AlphaContractError(
            f"S001 {key} identity sets differ across replicas"
        )

    max_abs = 0.0
    max_l1 = 0.0
    for left, right in itertools.combinations(identity_maps, 2):
        differences = [
            abs(left[identity] - right[identity])
            for identity in identities
        ]
        max_abs = max(max_abs, max(differences, default=0.0))
        max_l1 = max(max_l1, sum(differences))

    scalar_ranges: dict[str, float] = {}
    for field in S001_SCALAR_LIMITS:
        if field == "annualized_volatility":
            values = [
                (float(artifact["total_variance_daily"]) * 252.0) ** 0.5
                for artifact in artifacts
            ]
        else:
            source_field = (
                "expected_excess_return"
                if field == "expected_5d_excess_return"
                else field
            )
            values = [
                float(artifact[source_field]) for artifact in artifacts
            ]
        scalar_ranges[field] = max(values) - min(values)

    kkt_values = [
        float(
            artifact["solver"]["kkt"][
                "maximum_coordinate_kkt_violation"
            ]
        )
        for artifact in artifacts
    ]
    scalar_pass = all(
        scalar_ranges[field] <= limit
        for field, limit in S001_SCALAR_LIMITS.items()
    )
    weight_pass = (
        max_abs <= S001_MAX_WEIGHT_ABS_DIFF
        and max_l1 <= S001_MAX_WEIGHT_L1_DIFF
    )
    kkt_pass = max(kkt_values) <= 1e-9

    return {
        "artifact_sha256_values": [
            artifact["artifact_sha256"] for artifact in artifacts
        ],
        "all_artifact_hashes_identical": (
            len(
                {
                    artifact["artifact_sha256"]
                    for artifact in artifacts
                }
            )
            == 1
        ),
        "scalar_ranges": scalar_ranges,
        "scalar_limits": S001_SCALAR_LIMITS,
        "economic_scalar_stability_passed": scalar_pass,
        "max_pairwise_absolute_weight_diff": max_abs,
        "max_pairwise_l1_weight_diff": max_l1,
        "weight_stability_passed": weight_pass,
        "maximum_kkt_violation": max(kkt_values),
        "kkt_tolerance": 1e-9,
        "kkt_passed": kkt_pass,
        "passed": scalar_pass and weight_pass and kkt_pass,
    }


def evaluate_po001_s001_reports(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(reports) != S001_REPLICA_COUNT:
        raise AlphaContractError(
            f"S001 requires exactly {S001_REPLICA_COUNT} replicas"
        )
    if any(
        report.get("study_id") != STUDY_ID
        for report in reports
    ):
        raise AlphaContractError("unexpected S001 replica study id")
    if any(
        report.get("realized_outcome_opened") is not False
        for report in reports
    ):
        raise AlphaContractError(
            "S001 replica unexpectedly opened outcome"
        )

    invariant_fields = (
        "alpha_model_sha256",
        "control_risk_state_sha256",
        "treatment_risk_state_sha256",
        "common_identity_count",
        "execution_contract",
    )
    for field in invariant_fields:
        first = reports[0][field]
        if any(report[field] != first for report in reports[1:]):
            raise AlphaContractError(
                f"S001 replica invariant differs: {field}"
            )

    control = _s001_portfolio_stats(
        reports,
        key="control_rm001_v1",
    )
    treatment = _s001_portfolio_stats(
        reports,
        key="treatment_rm001_v3",
    )
    passed = control["passed"] and treatment["passed"]
    result: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "status": (
            "NUMERICAL_STABILITY_ESTABLISHED"
            if passed
            else "PO001_V4_NUMERICAL_STABILITY_NOT_ESTABLISHED"
        ),
        "replica_count": len(reports),
        "source_report_sha256_values": [
            report["report_sha256"] for report in reports
        ],
        "control_rm001_v1": control,
        "treatment_rm001_v3": treatment,
        "promotion": {
            "po001_v4_numerical_stability_established": passed,
            "rm001_v3_portfolio_revisit_allowed": passed,
            "live_capital_allowed": False,
        },
        "realized_outcome_opened": False,
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return result
