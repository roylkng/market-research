from __future__ import annotations

import copy
import math
import statistics
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001 import portfolio_risk
from marketlab.rm001_v2 import FACTOR_NAMES_V2, portfolio_risk_v2

PILOT_ID = "RM001-v2-P001-v1"
DECISION_SESSION = "2026-08-31"
MIN_V1_IDENTITY_OVERLAP = 0.99


def _verify_hash(
    payload: dict[str, Any],
    *,
    field: str,
    name: str,
) -> None:
    stored = str(payload.get(field) or "")
    unsigned = copy.deepcopy(payload)
    unsigned.pop(field, None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} hash mismatch")


def _control_positions(
    artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    _verify_hash(
        artifact,
        field="artifact_sha256",
        name="RM001-v2 P001 sealed I002 control",
    )
    if artifact.get("study_id") != "PO001-I002-v1":
        raise AlphaContractError("P001 control is not sealed I002")
    if artifact.get("decision_session") != DECISION_SESSION:
        raise AlphaContractError("P001 control decision session mismatch")
    if artifact.get("realized_outcome_opened") is not False:
        raise AlphaContractError("P001 control unexpectedly contains outcomes")
    portfolios = artifact.get("portfolios")
    if not isinstance(portfolios, dict):
        raise AlphaContractError("P001 control portfolios missing")
    portfolio = portfolios.get("full_po001_observable_cost_floor")
    if not isinstance(portfolio, dict):
        raise AlphaContractError("P001 observable-cost control missing")
    raw_positions = portfolio.get("positions")
    if not isinstance(raw_positions, list) or not raw_positions:
        raise AlphaContractError("P001 control positions missing")

    positions = []
    for row in raw_positions:
        weight = row.get("target_weight", row.get("weight"))
        if weight is None:
            raise AlphaContractError("P001 control position weight missing")
        parsed = float(weight)
        if parsed <= 1e-12:
            continue
        if not math.isfinite(parsed) or parsed < 0:
            raise AlphaContractError("P001 control weight invalid")
        positions.append(
            {
                "symbol": str(row["symbol"]),
                "isin": str(row["isin"]),
                "weight": parsed,
            }
        )
    if not positions:
        raise AlphaContractError("P001 control has no non-zero positions")
    return positions


def _risk_rows(
    state: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["symbol"]), str(row["isin"])): row
        for row in state["rows"]
    }


def _median_idio(
    rows: dict[tuple[str, str], dict[str, Any]],
    identities: set[tuple[str, str]],
) -> float:
    values = [
        float(rows[identity]["idiosyncratic_variance_daily"])
        for identity in identities
    ]
    if not values:
        raise AlphaContractError("P001 has no common idiosyncratic variances")
    return float(statistics.median(values))


def _factor_variances(state: dict[str, Any]) -> dict[str, float]:
    factors = [str(value) for value in state["factor_names"]]
    covariance = state["factor_covariance_daily"]
    if len(covariance) != len(factors):
        raise AlphaContractError("P001 covariance/factor dimension mismatch")
    return {
        factor: float(covariance[index][index])
        for index, factor in enumerate(factors)
    }


def run_rm001_v2_p001(
    *,
    v1_risk_state: dict[str, Any],
    v2_risk_state: dict[str, Any],
    sealed_i002_artifact: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        v1_risk_state,
        field="state_sha256",
        name="P001 RM001-v1 state",
    )
    _verify_hash(
        v2_risk_state,
        field="state_sha256",
        name="P001 RM001-v2 state",
    )
    if v1_risk_state.get("model_id") != "RM001-v1-DEVELOPMENT":
        raise AlphaContractError("P001 baseline must be RM001-v1")
    if v2_risk_state.get("model_id") != "RM001-v2-DEVELOPMENT":
        raise AlphaContractError("P001 challenger must be RM001-v2")
    if (
        v1_risk_state.get("as_of_session") != DECISION_SESSION
        or v2_risk_state.get("as_of_session") != DECISION_SESSION
    ):
        raise AlphaContractError("P001 risk-state decision session mismatch")
    if "SIZE" not in v2_risk_state.get("factor_names", []):
        raise AlphaContractError("P001 RM001-v2 state lacks SIZE")
    if len(v2_risk_state["factor_covariance_daily"]) != len(FACTOR_NAMES_V2):
        raise AlphaContractError("P001 RM001-v2 covariance is not 6x6")

    v1_rows = _risk_rows(v1_risk_state)
    v2_rows = _risk_rows(v2_risk_state)
    v1_ids = set(v1_rows)
    v2_ids = set(v2_rows)
    common = v1_ids & v2_ids
    overlap = 0.0 if not v1_ids else len(common) / len(v1_ids)
    if overlap < MIN_V1_IDENTITY_OVERLAP:
        raise AlphaContractError(
            f"P001 v2/v1 identity overlap below frozen gate: {overlap}"
        )

    for row in v2_rows.values():
        size = float(row["exposures"]["SIZE"])
        if not math.isfinite(size) or not -1.0 <= size <= 1.0:
            raise AlphaContractError("P001 SIZE exposure outside [-1, 1]")

    positions = _control_positions(sealed_i002_artifact)
    position_ids = {
        (str(row["symbol"]), str(row["isin"]))
        for row in positions
    }
    missing_v2 = sorted(position_ids - v2_ids)
    if missing_v2:
        raise AlphaContractError(
            f"P001 sealed I002 positions absent from RM001-v2: {missing_v2[:10]}"
        )

    v1_portfolio = portfolio_risk(v1_risk_state, positions=positions)
    v2_portfolio = portfolio_risk_v2(v2_risk_state, positions=positions)

    v1_median_idio = _median_idio(v1_rows, common)
    v2_median_idio = _median_idio(v2_rows, common)
    v1_factor_variances = _factor_variances(v1_risk_state)
    v2_factor_variances = _factor_variances(v2_risk_state)

    common_factor_exposure_delta = {}
    for factor in v1_risk_state["factor_names"]:
        common_factor_exposure_delta[factor] = (
            float(v2_portfolio["portfolio_factor_exposures"][factor])
            - float(v1_portfolio["portfolio_factor_exposures"][factor])
        )

    report: dict[str, Any] = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "evidence_class": "HISTORICAL_RISK_MODEL_ATTRIBUTION_NO_RETURN_OUTCOME",
        "decision_session": DECISION_SESSION,
        "v1_risk_state_sha256": v1_risk_state["state_sha256"],
        "v2_risk_state_sha256": v2_risk_state["state_sha256"],
        "sealed_i002_artifact_sha256": sealed_i002_artifact[
            "artifact_sha256"
        ],
        "identity_overlap": {
            "v1_security_count": len(v1_ids),
            "v2_security_count": len(v2_ids),
            "common_security_count": len(common),
            "v2_over_v1_fraction": overlap,
            "v1_only_count": len(v1_ids - v2_ids),
            "v2_only_count": len(v2_ids - v1_ids),
        },
        "idiosyncratic": {
            "v1_fallback_p75": float(
                v1_risk_state["idiosyncratic_fallback_p75"]
            ),
            "v2_fallback_p75": float(
                v2_risk_state["idiosyncratic_fallback_p75"]
            ),
            "v1_common_median_variance": v1_median_idio,
            "v2_common_median_variance": v2_median_idio,
            "median_variance_delta": v2_median_idio - v1_median_idio,
        },
        "factor_daily_variances": {
            "v1": v1_factor_variances,
            "v2": v2_factor_variances,
            "size": v2_factor_variances["SIZE"],
        },
        "sealed_i002_portfolio_risk": {
            "position_count": len(positions),
            "v1": v1_portfolio,
            "v2": v2_portfolio,
            "annualized_volatility_delta": (
                float(v2_portfolio["annualized_volatility"])
                - float(v1_portfolio["annualized_volatility"])
            ),
            "factor_variance_daily_delta": (
                float(v2_portfolio["factor_variance_daily"])
                - float(v1_portfolio["factor_variance_daily"])
            ),
            "idiosyncratic_variance_daily_delta": (
                float(v2_portfolio["idiosyncratic_variance_daily"])
                - float(v1_portfolio["idiosyncratic_variance_daily"])
            ),
            "size_exposure": float(
                v2_portfolio["portfolio_factor_exposures"]["SIZE"]
            ),
            "size_variance_contribution_daily": float(
                v2_portfolio["factor_variance_contributions_daily"]["SIZE"]
            ),
            "common_factor_exposure_delta": common_factor_exposure_delta,
        },
        "interpretation_limits": {
            "return_outcome_opened": False,
            "alpha_model_fit_performed": False,
            "prospective_size_source_timing_verified": False,
            "sector_factor_available": False,
            "free_float_size_available": False,
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
