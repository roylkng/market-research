from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001 import _portfolio_variance
from marketlab.po001_v3 import (
    _dynamic_risk_inputs,
    _verify_dynamic_risk_state,
)

STUDY_ID = "PO001-I005-v1"
EXPECTED_S001_REPORT_SHA256 = (
    "688c028a86e7ed0fb2fc981b014b153601569daa9f33c874f954dbb8980c2bbd"
)
EXPECTED_CONTROL_ARTIFACT_SHA256 = (
    "33d90bf35aefc4bb53050d99b95ccffc158cac4ece1196558fcb5b89a1bafd20"
)
EXPECTED_TREATMENT_ARTIFACT_SHA256 = (
    "068f3481a454416fa82daf471f33053d4f2d53e0f256e9f0cdb07f21c01384c7"
)
EXPECTED_CONTROL_RISK_SHA256 = (
    "b1d6898f1083d752ca7db6dc7509b8ef4a2aef0f1543f24fd8b30f07604d80c1"
)
EXPECTED_TREATMENT_RISK_SHA256 = (
    "32002ec101531c0e28fb551058c79f179fca53aafccf3c36ef07cb0159387441"
)

HORIZON_SESSIONS = 5
RISK_AVERSION = 5.0
OPTIMALITY_TOLERANCE = 1e-10

MATERIAL_WEIGHT_L1 = 0.05
MATERIAL_MAX_NAME_WEIGHT = 0.005
MATERIAL_ALPHA = 0.0001
MATERIAL_COST = 0.0001
MATERIAL_ANNUALIZED_VOLATILITY = 0.005


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


def _validate_s001_report(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _verify_hash(
        report,
        hash_field="report_sha256",
        name="I005 pinned S001 report",
    )
    if report["report_sha256"] != EXPECTED_S001_REPORT_SHA256:
        raise AlphaContractError("I005 pinned S001 report SHA mismatch")
    if report.get("study_id") != "PO001-S001-v1":
        raise AlphaContractError("I005 pinned report study ID mismatch")
    if report.get("realized_outcome_opened") is not False:
        raise AlphaContractError("I005 pinned report unexpectedly opened outcome")
    if report.get("control_risk_state_sha256") != EXPECTED_CONTROL_RISK_SHA256:
        raise AlphaContractError("I005 S001 control risk provenance mismatch")
    if report.get("treatment_risk_state_sha256") != EXPECTED_TREATMENT_RISK_SHA256:
        raise AlphaContractError("I005 S001 treatment risk provenance mismatch")

    control = report["control_rm001_v1"]["artifact"]
    treatment = report["treatment_rm001_v3"]["artifact"]
    _verify_hash(
        control,
        hash_field="artifact_sha256",
        name="I005 control optimizer artifact",
    )
    _verify_hash(
        treatment,
        hash_field="artifact_sha256",
        name="I005 treatment optimizer artifact",
    )
    if control["artifact_sha256"] != EXPECTED_CONTROL_ARTIFACT_SHA256:
        raise AlphaContractError("I005 control optimizer artifact mismatch")
    if treatment["artifact_sha256"] != EXPECTED_TREATMENT_ARTIFACT_SHA256:
        raise AlphaContractError("I005 treatment optimizer artifact mismatch")
    if control.get("optimizer_id") != "PO001-v4-DEVELOPMENT":
        raise AlphaContractError("I005 control optimizer ID mismatch")
    if treatment.get("optimizer_id") != "PO001-v4-DEVELOPMENT":
        raise AlphaContractError("I005 treatment optimizer ID mismatch")
    return control, treatment


def _validate_risk(
    risk_state: dict[str, Any],
    *,
    expected_sha: str,
    expected_model_id: str,
    name: str,
) -> tuple[str, ...]:
    factor_names = _verify_dynamic_risk_state(risk_state)
    if risk_state["state_sha256"] != expected_sha:
        raise AlphaContractError(f"{name} frozen SHA mismatch")
    if risk_state.get("model_id") != expected_model_id:
        raise AlphaContractError(f"{name} model ID mismatch")
    if str(risk_state.get("as_of_session") or "") != "2026-08-31":
        raise AlphaContractError(f"{name} decision session mismatch")
    return factor_names


def _row_map(artifact: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = artifact.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("I005 optimizer rows must be a list")
    mapped = {
        (str(row["symbol"]), str(row["isin"])): row
        for row in rows
    }
    if len(mapped) != len(rows):
        raise AlphaContractError("I005 optimizer rows contain duplicate identities")
    return mapped


def _validate_common_economic_inputs(
    control: dict[str, Any],
    treatment: dict[str, Any],
) -> list[tuple[str, str]]:
    left = _row_map(control)
    right = _row_map(treatment)
    if left.keys() != right.keys():
        raise AlphaContractError("I005 control/treatment identity sets differ")

    fields = (
        "expected_excess_return",
        "current_weight",
        "max_weight",
        "buy_cost_bps",
        "sell_cost_bps",
        "adv20_inr",
        "daily_volatility_decimal",
        "effective_max_weight",
    )
    for identity in left:
        for field in fields:
            if float(left[identity][field]) != float(right[identity][field]):
                raise AlphaContractError(
                    f"I005 economic input differs for {identity}: {field}"
                )
    return sorted(left)


def _weights(
    artifact: dict[str, Any],
    identities: list[tuple[str, str]],
) -> np.ndarray:
    mapped = _row_map(artifact)
    values = np.asarray(
        [float(mapped[identity]["target_weight"]) for identity in identities],
        dtype=float,
    )
    if not np.isfinite(values).all() or np.any(values < -1e-14):
        raise AlphaContractError("I005 portfolio weights are invalid")
    return np.maximum(values, 0.0)


def _evaluate_under_risk(
    artifact: dict[str, Any],
    *,
    risk_state: dict[str, Any],
    identities: list[tuple[str, str]],
    factor_names: tuple[str, ...],
) -> dict[str, Any]:
    weights = _weights(artifact, identities)
    exposure_matrix, covariance, idio = _dynamic_risk_inputs(
        risk_state,
        identities,
        factor_names=factor_names,
    )
    total, factor, idio_var, factor_exposure = _portfolio_variance(
        weights,
        exposure_matrix,
        covariance,
        idio,
    )
    expected_alpha = float(artifact["expected_excess_return"])
    cost = float(artifact["total_transaction_cost_fraction"])
    risk_penalty = RISK_AVERSION * HORIZON_SESSIONS * total
    utility = expected_alpha - risk_penalty - cost
    return {
        "factor_names": list(factor_names),
        "factor_variance_daily": factor,
        "idiosyncratic_variance_daily": idio_var,
        "total_variance_daily": total,
        "annualized_volatility": math.sqrt(total * 252.0),
        "risk_penalty": risk_penalty,
        "expected_5d_excess_return": expected_alpha,
        "total_transaction_cost_fraction": cost,
        "utility": utility,
        "portfolio_factor_exposures": {
            factor_name: float(factor_exposure[index])
            for index, factor_name in enumerate(factor_names)
        },
    }


def _weight_changes(
    control: dict[str, Any],
    treatment: dict[str, Any],
    identities: list[tuple[str, str]],
) -> dict[str, Any]:
    left = _row_map(control)
    right = _row_map(treatment)
    changes = [
        {
            "symbol": identity[0],
            "isin": identity[1],
            "control_weight": float(left[identity]["target_weight"]),
            "treatment_weight": float(right[identity]["target_weight"]),
            "delta_weight": (
                float(right[identity]["target_weight"])
                - float(left[identity]["target_weight"])
            ),
        }
        for identity in identities
    ]
    l1 = sum(abs(row["delta_weight"]) for row in changes)
    maximum = max(
        (abs(row["delta_weight"]) for row in changes),
        default=0.0,
    )
    active_control = [
        row for row in changes if row["control_weight"] > 1e-12
    ]
    active_treatment = [
        row for row in changes if row["treatment_weight"] > 1e-12
    ]
    hhi_control = sum(row["control_weight"] ** 2 for row in active_control)
    hhi_treatment = sum(
        row["treatment_weight"] ** 2 for row in active_treatment
    )
    increases = sorted(
        changes,
        key=lambda row: (
            -row["delta_weight"],
            row["symbol"],
            row["isin"],
        ),
    )
    decreases = sorted(
        changes,
        key=lambda row: (
            row["delta_weight"],
            row["symbol"],
            row["isin"],
        ),
    )
    return {
        "weight_l1_change": l1,
        "maximum_absolute_weight_change": maximum,
        "control_holding_count": len(active_control),
        "treatment_holding_count": len(active_treatment),
        "holding_count_change": len(active_treatment) - len(active_control),
        "control_weight_hhi": hhi_control,
        "treatment_weight_hhi": hhi_treatment,
        "control_effective_names": (
            None if hhi_control <= 0 else 1.0 / hhi_control
        ),
        "treatment_effective_names": (
            None if hhi_treatment <= 0 else 1.0 / hhi_treatment
        ),
        "top_weight_increases": increases[:20],
        "top_weight_decreases": decreases[:20],
    }


def _risk_delta(
    treatment_eval: dict[str, Any],
    control_eval: dict[str, Any],
) -> dict[str, float]:
    fields = (
        "factor_variance_daily",
        "idiosyncratic_variance_daily",
        "total_variance_daily",
        "annualized_volatility",
        "risk_penalty",
        "utility",
    )
    return {
        field: float(treatment_eval[field]) - float(control_eval[field])
        for field in fields
    }


def run_po001_i005(
    *,
    s001_report: dict[str, Any],
    control_risk_state: dict[str, Any],
    treatment_risk_state: dict[str, Any],
) -> dict[str, Any]:
    control, treatment = _validate_s001_report(s001_report)
    control_factors = _validate_risk(
        control_risk_state,
        expected_sha=EXPECTED_CONTROL_RISK_SHA256,
        expected_model_id="RM001-v1-DEVELOPMENT",
        name="I005 control RM001-v1",
    )
    treatment_factors = _validate_risk(
        treatment_risk_state,
        expected_sha=EXPECTED_TREATMENT_RISK_SHA256,
        expected_model_id="RM001-v3-DEVELOPMENT",
        name="I005 treatment RM001-v3",
    )
    identities = _validate_common_economic_inputs(control, treatment)

    control_under_v1 = _evaluate_under_risk(
        control,
        risk_state=control_risk_state,
        identities=identities,
        factor_names=control_factors,
    )
    treatment_under_v1 = _evaluate_under_risk(
        treatment,
        risk_state=control_risk_state,
        identities=identities,
        factor_names=control_factors,
    )
    control_under_v3 = _evaluate_under_risk(
        control,
        risk_state=treatment_risk_state,
        identities=identities,
        factor_names=treatment_factors,
    )
    treatment_under_v3 = _evaluate_under_risk(
        treatment,
        risk_state=treatment_risk_state,
        identities=identities,
        factor_names=treatment_factors,
    )

    v1_optimality = (
        control_under_v1["utility"]
        >= treatment_under_v1["utility"] - OPTIMALITY_TOLERANCE
    )
    v3_optimality = (
        treatment_under_v3["utility"]
        >= control_under_v3["utility"] - OPTIMALITY_TOLERANCE
    )

    weights = _weight_changes(control, treatment, identities)
    expected_alpha_delta = (
        float(treatment["expected_excess_return"])
        - float(control["expected_excess_return"])
    )
    cost_delta = (
        float(treatment["total_transaction_cost_fraction"])
        - float(control["total_transaction_cost_fraction"])
    )
    v1_delta = _risk_delta(treatment_under_v1, control_under_v1)
    v3_delta = _risk_delta(treatment_under_v3, control_under_v3)

    flags = {
        "reallocation_material": (
            weights["weight_l1_change"] >= MATERIAL_WEIGHT_L1
            or weights["maximum_absolute_weight_change"]
            >= MATERIAL_MAX_NAME_WEIGHT
        ),
        "alpha_material": abs(expected_alpha_delta) >= MATERIAL_ALPHA,
        "cost_material": abs(cost_delta) >= MATERIAL_COST,
        "rm001_v1_risk_material": (
            abs(v1_delta["annualized_volatility"])
            >= MATERIAL_ANNUALIZED_VOLATILITY
        ),
        "rm001_v3_risk_material": (
            abs(v3_delta["annualized_volatility"])
            >= MATERIAL_ANNUALIZED_VOLATILITY
        ),
    }

    if not (v1_optimality and v3_optimality):
        classification = "IMPLEMENTATION_SANITY_CHECK_FAILED"
    elif any(flags.values()):
        classification = "MATERIAL_RISK_MODEL_PORTFOLIO_EFFECT"
    else:
        classification = "LIMITED_RISK_MODEL_PORTFOLIO_EFFECT"

    report: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "status": classification,
        "evidence_class": "HISTORICAL_OOS_STABLE_RISK_TREATMENT_INTEGRATION",
        "decision_session": "2026-08-31",
        "horizon_sessions": HORIZON_SESSIONS,
        "realized_outcome_opened": False,
        "source": {
            "s001_report_sha256": s001_report["report_sha256"],
            "control_optimizer_artifact_sha256": control[
                "artifact_sha256"
            ],
            "treatment_optimizer_artifact_sha256": treatment[
                "artifact_sha256"
            ],
            "control_risk_state_sha256": control_risk_state[
                "state_sha256"
            ],
            "treatment_risk_state_sha256": treatment_risk_state[
                "state_sha256"
            ],
        },
        "common_identity_count": len(identities),
        "common_metrics": {
            "control_expected_5d_excess_return": float(
                control["expected_excess_return"]
            ),
            "treatment_expected_5d_excess_return": float(
                treatment["expected_excess_return"]
            ),
            "expected_5d_excess_return_delta": expected_alpha_delta,
            "control_total_transaction_cost_fraction": float(
                control["total_transaction_cost_fraction"]
            ),
            "treatment_total_transaction_cost_fraction": float(
                treatment["total_transaction_cost_fraction"]
            ),
            "total_transaction_cost_fraction_delta": cost_delta,
        },
        "weight_changes": weights,
        "rm001_v1_common_map": {
            "control": control_under_v1,
            "treatment": treatment_under_v1,
            "treatment_minus_control": v1_delta,
            "control_optimality_sanity_passed": v1_optimality,
        },
        "rm001_v3_common_map": {
            "control": control_under_v3,
            "treatment": treatment_under_v3,
            "treatment_minus_control": v3_delta,
            "treatment_optimality_sanity_passed": v3_optimality,
        },
        "materiality_flags": flags,
        "materiality_thresholds": {
            "weight_l1": MATERIAL_WEIGHT_L1,
            "max_name_weight": MATERIAL_MAX_NAME_WEIGHT,
            "expected_5d_excess_return": MATERIAL_ALPHA,
            "total_transaction_cost_fraction": MATERIAL_COST,
            "annualized_volatility": MATERIAL_ANNUALIZED_VOLATILITY,
        },
        "interpretation_limits": {
            "risk_forecast_superiority_claim_allowed": False,
            "realized_return_opened": False,
            "live_capital_allowed": False,
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
