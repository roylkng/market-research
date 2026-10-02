from __future__ import annotations

import copy
import math
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001 import RM001_MODEL_ID, _q, portfolio_risk

CAL1_MODEL_ID = "RM001-v1-CAL1-DEVELOPMENT"
CALIBRATION_SCALE = 0.5670928922826751
CALIBRATION_DESIGN_SOURCE = "research/rm001-c001-result-v1.json"


def _verify_state_hash(state: dict[str, Any]) -> None:
    stored = str(state.get("state_sha256") or "")
    unsigned = copy.deepcopy(state)
    unsigned.pop("state_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError("RM001-CAL1 parent risk state hash mismatch")


def calibrate_v1_risk_state(
    raw_state: dict[str, Any],
    *,
    calibration_scale: float = CALIBRATION_SCALE,
) -> dict[str, Any]:
    """Scale an exact RM001-v1 state without changing exposure structure."""

    _verify_state_hash(raw_state)
    if raw_state.get("model_id") != RM001_MODEL_ID:
        raise AlphaContractError("RM001-CAL1 requires RM001-v1 parent state")
    if raw_state.get("live_capital_allowed") is not False:
        raise AlphaContractError("RM001-CAL1 parent cannot allow live capital")

    scale = float(calibration_scale)
    if not math.isfinite(scale) or scale <= 0.0:
        raise AlphaContractError(
            "RM001-CAL1 calibration scale must be finite and positive"
        )

    covariance = raw_state.get("factor_covariance_daily")
    rows = raw_state.get("rows")
    if not isinstance(covariance, list) or not covariance:
        raise AlphaContractError("RM001-CAL1 parent covariance is missing")
    if not isinstance(rows, list) or not rows:
        raise AlphaContractError("RM001-CAL1 parent rows are missing")

    calibrated_rows = []
    for row in rows:
        idio = float(row["idiosyncratic_variance_daily"])
        if not math.isfinite(idio) or idio < 0.0:
            raise AlphaContractError(
                "RM001-CAL1 parent idiosyncratic variance is invalid"
            )
        calibrated_rows.append(
            {
                "symbol": str(row["symbol"]),
                "isin": str(row["isin"]),
                "exposures": copy.deepcopy(row["exposures"]),
                "idiosyncratic_variance_daily": _q(idio * scale),
                "idiosyncratic_status": str(row["idiosyncratic_status"]),
            }
        )

    scaled_covariance = []
    for source_row in covariance:
        if not isinstance(source_row, list):
            raise AlphaContractError(
                "RM001-CAL1 covariance rows must be lists"
            )
        scaled_row = []
        for value in source_row:
            parsed = float(value)
            if not math.isfinite(parsed):
                raise AlphaContractError(
                    "RM001-CAL1 parent covariance contains nonfinite value"
                )
            scaled_row.append(_q(parsed * scale))
        scaled_covariance.append(scaled_row)

    fallback = float(raw_state["idiosyncratic_fallback_p75"])
    if not math.isfinite(fallback) or fallback < 0.0:
        raise AlphaContractError(
            "RM001-CAL1 parent idiosyncratic fallback is invalid"
        )

    calibrated: dict[str, Any] = {
        "schema_version": 1,
        "model_id": CAL1_MODEL_ID,
        "as_of_session": raw_state["as_of_session"],
        "factor_names": copy.deepcopy(raw_state["factor_names"]),
        "factor_covariance_window": raw_state[
            "factor_covariance_window"
        ],
        "factor_covariance_first_realized_session": raw_state[
            "factor_covariance_first_realized_session"
        ],
        "factor_covariance_last_realized_session": raw_state[
            "factor_covariance_last_realized_session"
        ],
        "factor_covariance_daily": scaled_covariance,
        "idiosyncratic_window": raw_state["idiosyncratic_window"],
        "minimum_idiosyncratic_observations": raw_state[
            "minimum_idiosyncratic_observations"
        ],
        "idiosyncratic_fallback_p75": _q(fallback * scale),
        "exposure_panel_sha256": raw_state["exposure_panel_sha256"],
        "factor_history_sha256": raw_state["factor_history_sha256"],
        "security_count": raw_state["security_count"],
        "rows": calibrated_rows,
        "deferred_factors": copy.deepcopy(raw_state["deferred_factors"]),
        "parent_model_id": RM001_MODEL_ID,
        "parent_risk_state_sha256": raw_state["state_sha256"],
        "calibration_type": "MULTIPLICATIVE_VARIANCE_SCALE",
        "calibration_scale": scale,
        "calibration_design_source": CALIBRATION_DESIGN_SOURCE,
        "historical_design_validation_claim_allowed": False,
        "live_capital_allowed": False,
    }
    calibrated["state_sha256"] = digest(calibrated)
    return calibrated


def portfolio_risk_cal1(
    calibrated_state: dict[str, Any],
    *,
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    if calibrated_state.get("model_id") != CAL1_MODEL_ID:
        raise AlphaContractError(
            "RM001-CAL1 portfolio risk requires calibrated state"
        )
    report = portfolio_risk(
        calibrated_state,
        positions=positions,
    )
    report["model_id"] = CAL1_MODEL_ID
    report["parent_model_id"] = RM001_MODEL_ID
    report["parent_risk_state_sha256"] = calibrated_state[
        "parent_risk_state_sha256"
    ]
    report["calibration_scale"] = calibrated_state[
        "calibration_scale"
    ]
    return report
