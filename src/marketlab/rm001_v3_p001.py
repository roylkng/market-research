from __future__ import annotations

import copy
import math
import statistics
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_v2 import FACTOR_NAMES_V2, portfolio_risk_v2
from marketlab.rm001_v3 import (
    RM001_V3_MODEL_ID,
    STAT_FACTOR_NAMES,
    portfolio_risk_v3,
)

PILOT_ID = "RM001-v3-P001-v1"
DECISION_SESSION = "2026-08-31"
PORTFOLIO_KEYS = (
    "equal_weight_top_decile",
    "positive_alpha_proportional_top_decile",
)
NAMED_EXPOSURE_TOLERANCE = 1e-12
MIN_COMPLETE_STATISTICAL_IDENTITIES = 500


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


def _rows(
    state: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    rows = {
        (str(row["symbol"]), str(row["isin"])): row
        for row in state.get("rows", [])
    }
    if len(rows) != len(state.get("rows", [])):
        raise AlphaContractError(
            "RM001-v3 P001 risk state has duplicate identities"
        )
    return rows


def _positions(
    artifact: dict[str, Any],
    *,
    portfolio_key: str,
) -> list[dict[str, Any]]:
    _verify_hash(
        artifact,
        field="artifact_sha256",
        name="RM001-v3 P001 sealed I002 artifact",
    )
    if artifact.get("study_id") != "PO001-I002-v1":
        raise AlphaContractError(
            "RM001-v3 P001 control is not sealed I002"
        )
    if artifact.get("decision_session") != DECISION_SESSION:
        raise AlphaContractError(
            "RM001-v3 P001 I002 decision session mismatch"
        )
    if artifact.get("realized_outcome_opened") is not False:
        raise AlphaContractError(
            "RM001-v3 P001 control unexpectedly opened outcomes"
        )
    portfolios = artifact.get("portfolios")
    if not isinstance(portfolios, dict):
        raise AlphaContractError(
            "RM001-v3 P001 control portfolios are missing"
        )
    portfolio = portfolios.get(portfolio_key)
    if not isinstance(portfolio, dict):
        raise AlphaContractError(
            f"RM001-v3 P001 portfolio missing: {portfolio_key}"
        )
    raw = portfolio.get("positions")
    if not isinstance(raw, list) or not raw:
        raise AlphaContractError(
            f"RM001-v3 P001 exact positions missing: {portfolio_key}"
        )
    positions = []
    for row in raw:
        weight = row.get("target_weight", row.get("weight"))
        if weight is None:
            raise AlphaContractError(
                "RM001-v3 P001 position weight is missing"
            )
        parsed = float(weight)
        if not math.isfinite(parsed) or parsed < 0:
            raise AlphaContractError(
                "RM001-v3 P001 position weight is invalid"
            )
        if parsed <= 1e-12:
            continue
        positions.append(
            {
                "symbol": str(row["symbol"]),
                "isin": str(row["isin"]),
                "weight": parsed,
            }
        )
    if not positions:
        raise AlphaContractError(
            f"RM001-v3 P001 no nonzero positions: {portfolio_key}"
        )
    return positions


def _median(values: list[float]) -> float:
    if not values:
        raise AlphaContractError(
            "RM001-v3 P001 has no values for median"
        )
    return float(statistics.median(values))


def _mean(values: list[float]) -> float:
    if not values:
        raise AlphaContractError(
            "RM001-v3 P001 has no values for mean"
        )
    return float(statistics.fmean(values))


def run_rm001_v3_p001(
    *,
    v2_risk_state: dict[str, Any],
    v3_risk_state: dict[str, Any],
    sealed_i002_artifact: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        v2_risk_state,
        field="state_sha256",
        name="RM001-v3 P001 v2 risk state",
    )
    _verify_hash(
        v3_risk_state,
        field="state_sha256",
        name="RM001-v3 P001 v3 risk state",
    )
    if v2_risk_state.get("model_id") != "RM001-v2-DEVELOPMENT":
        raise AlphaContractError(
            "RM001-v3 P001 baseline must be RM001-v2"
        )
    if v3_risk_state.get("model_id") != RM001_V3_MODEL_ID:
        raise AlphaContractError(
            "RM001-v3 P001 challenger must be RM001-v3"
        )
    if (
        str(v2_risk_state.get("as_of_session")) != DECISION_SESSION
        or str(v3_risk_state.get("as_of_session")) != DECISION_SESSION
    ):
        raise AlphaContractError(
            "RM001-v3 P001 as-of session mismatch"
        )
    if v3_risk_state.get("parent_v2_risk_state_sha256") != (
        v2_risk_state["state_sha256"]
    ):
        raise AlphaContractError(
            "RM001-v3 P001 parent v2 risk binding mismatch"
        )
    if int(v3_risk_state.get("statistical_component_count") or 0) != 5:
        raise AlphaContractError(
            "RM001-v3 P001 statistical factor count differs from frozen five"
        )
    if int(v3_risk_state.get("factor_covariance_window") or 0) != 60:
        raise AlphaContractError(
            "RM001-v3 P001 covariance clock differs from frozen 60"
        )
    if int(v3_risk_state.get("idiosyncratic_window") or 0) != 60:
        raise AlphaContractError(
            "RM001-v3 P001 idiosyncratic clock differs from frozen 60"
        )
    if int(
        v3_risk_state.get("complete_statistical_identity_count") or 0
    ) < MIN_COMPLETE_STATISTICAL_IDENTITIES:
        raise AlphaContractError(
            "RM001-v3 P001 complete statistical universe below frozen gate"
        )

    expected_factors = [*FACTOR_NAMES_V2, *STAT_FACTOR_NAMES]
    if list(v3_risk_state.get("factor_names") or []) != expected_factors:
        raise AlphaContractError(
            "RM001-v3 P001 factor ordering differs from frozen contract"
        )
    covariance = v3_risk_state.get("factor_covariance_daily")
    if (
        not isinstance(covariance, list)
        or len(covariance) != 11
        or any(
            not isinstance(row, list) or len(row) != 11
            for row in covariance
        )
    ):
        raise AlphaContractError(
            "RM001-v3 P001 covariance is not 11x11"
        )

    v2_rows = _rows(v2_risk_state)
    v3_rows = _rows(v3_risk_state)
    if set(v2_rows) != set(v3_rows):
        raise AlphaContractError(
            "RM001-v3 P001 v2/v3 current identity sets differ"
        )
    if len(v2_rows) != int(v3_risk_state["security_count"]):
        raise AlphaContractError(
            "RM001-v3 P001 security count mismatch"
        )

    complete = {
        identity
        for identity, row in v3_rows.items()
        if row.get("statistical_status") == "STAT_COMPLETE_120"
    }
    if len(complete) != int(
        v3_risk_state["complete_statistical_identity_count"]
    ):
        raise AlphaContractError(
            "RM001-v3 P001 complete-identity count mismatch"
        )

    for identity, row in v3_rows.items():
        exposures = row.get("exposures")
        if not isinstance(exposures, dict):
            raise AlphaContractError(
                "RM001-v3 P001 v3 exposures are malformed"
            )
        if set(exposures) != set(expected_factors):
            raise AlphaContractError(
                "RM001-v3 P001 v3 exposure factor set differs"
            )
        if not all(
            math.isfinite(float(exposures[factor]))
            for factor in expected_factors
        ):
            raise AlphaContractError(
                "RM001-v3 P001 v3 exposure is nonfinite"
            )
        if identity not in complete:
            v2_idio = float(
                v2_rows[identity]["idiosyncratic_variance_daily"]
            )
            v3_idio = float(row["idiosyncratic_variance_daily"])
            if abs(v2_idio - v3_idio) > 1e-15:
                raise AlphaContractError(
                    "RM001-v3 P001 fallback identity changed v2 idio"
                )
            if any(
                abs(float(exposures[factor])) > 1e-15
                for factor in STAT_FACTOR_NAMES
            ):
                raise AlphaContractError(
                    "RM001-v3 P001 fallback identity has statistical exposure"
                )

    v2_complete_idio = [
        float(v2_rows[identity]["idiosyncratic_variance_daily"])
        for identity in sorted(complete)
    ]
    v3_complete_idio = [
        float(v3_rows[identity]["idiosyncratic_variance_daily"])
        for identity in sorted(complete)
    ]

    portfolio_reports: dict[str, Any] = {}
    for portfolio_key in PORTFOLIO_KEYS:
        positions = _positions(
            sealed_i002_artifact,
            portfolio_key=portfolio_key,
        )
        position_ids = {
            (str(row["symbol"]), str(row["isin"]))
            for row in positions
        }
        missing = sorted(position_ids - set(v3_rows))
        if missing:
            raise AlphaContractError(
                f"RM001-v3 P001 portfolio identities missing from v3: "
                f"{portfolio_key}: {missing[:10]}"
            )
        v2_risk = portfolio_risk_v2(
            v2_risk_state,
            positions=positions,
        )
        v3_risk = portfolio_risk_v3(
            v3_risk_state,
            positions=positions,
        )

        named_exposure_delta = {}
        for factor in FACTOR_NAMES_V2:
            delta = (
                float(v3_risk["portfolio_factor_exposures"][factor])
                - float(v2_risk["portfolio_factor_exposures"][factor])
            )
            if abs(delta) > NAMED_EXPOSURE_TOLERANCE:
                raise AlphaContractError(
                    f"RM001-v3 P001 named exposure changed for {factor}"
                )
            named_exposure_delta[factor] = delta

        stat_contributions = {
            factor: float(
                v3_risk[
                    "factor_variance_contributions_daily"
                ][factor]
            )
            for factor in STAT_FACTOR_NAMES
        }
        portfolio_reports[portfolio_key] = {
            "position_count": len(positions),
            "v2": v2_risk,
            "v3": v3_risk,
            "total_variance_daily_delta": (
                float(v3_risk["total_variance_daily"])
                - float(v2_risk["total_variance_daily"])
            ),
            "factor_variance_daily_delta": (
                float(v3_risk["factor_variance_daily"])
                - float(v2_risk["factor_variance_daily"])
            ),
            "idiosyncratic_variance_daily_delta": (
                float(v3_risk["idiosyncratic_variance_daily"])
                - float(v2_risk["idiosyncratic_variance_daily"])
            ),
            "annualized_volatility_delta": (
                float(v3_risk["annualized_volatility"])
                - float(v2_risk["annualized_volatility"])
            ),
            "named_factor_exposure_delta": named_exposure_delta,
            "statistical_factor_exposures": {
                factor: float(
                    v3_risk["portfolio_factor_exposures"][factor]
                )
                for factor in STAT_FACTOR_NAMES
            },
            "statistical_factor_variance_contributions_daily": (
                stat_contributions
            ),
            "total_statistical_factor_variance_contribution_daily": (
                sum(stat_contributions.values())
            ),
        }

    explained = [
        float(value)
        for value in v3_risk_state[
            "statistical_explained_variance_ratio"
        ]
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "evidence_class": (
            "HISTORICAL_RISK_MODEL_ATTRIBUTION_NO_RETURN_OUTCOME"
        ),
        "decision_session": DECISION_SESSION,
        "v2_risk_state_sha256": v2_risk_state["state_sha256"],
        "v3_risk_state_sha256": v3_risk_state["state_sha256"],
        "sealed_i002_artifact_sha256": sealed_i002_artifact[
            "artifact_sha256"
        ],
        "identity": {
            "v2_security_count": len(v2_rows),
            "v3_security_count": len(v3_rows),
            "exact_identity_set_match": True,
            "complete_statistical_identity_count": len(complete),
            "complete_statistical_coverage": (
                len(complete) / len(v2_rows)
                if v2_rows
                else 0.0
            ),
            "fallback_identity_count": (
                len(v2_rows) - len(complete)
            ),
        },
        "statistical_basis": {
            "basis_window": int(
                v3_risk_state["statistical_basis_window"]
            ),
            "risk_estimation_window": int(
                v3_risk_state["risk_estimation_window"]
            ),
            "singular_values": v3_risk_state["singular_values"],
            "adjacent_singular_relative_gaps": v3_risk_state[
                "adjacent_singular_relative_gaps"
            ],
            "explained_variance_ratio": explained,
            "cumulative_explained_variance_ratio": sum(explained),
            "sign_anchors": v3_risk_state[
                "statistical_sign_anchors"
            ],
        },
        "complete_identity_idiosyncratic": {
            "v2_median_variance": _median(v2_complete_idio),
            "v3_median_variance": _median(v3_complete_idio),
            "median_variance_delta": (
                _median(v3_complete_idio)
                - _median(v2_complete_idio)
            ),
            "v2_mean_variance": _mean(v2_complete_idio),
            "v3_mean_variance": _mean(v3_complete_idio),
            "mean_variance_delta": (
                _mean(v3_complete_idio)
                - _mean(v2_complete_idio)
            ),
            "in_sample_reduction_is_promotion_gate": False,
        },
        "sealed_i002_portfolio_risk": portfolio_reports,
        "interpretation_limits": {
            "alpha_outcome_opened": False,
            "portfolio_return_outcome_opened": False,
            "in_sample_pca_reduction_is_not_oos_validation": True,
            "sector_semantics_claimed": False,
            "prospective_readiness_claimed": False,
            "oos_risk_calibration_required_next": True,
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
