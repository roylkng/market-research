from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_v2 import (
    FACTOR_NAMES_V2,
    RM001_V2_MODEL_ID,
    portfolio_risk_v2,
)
from marketlab.rm001_v3 import (
    FACTOR_NAMES_V3,
    RM001_V3_MODEL_ID,
    STAT_FACTOR_NAMES,
    portfolio_risk_v3,
)

PILOT_ID = "RM001-v3-P001-v1"
DECISION_SESSION = "2026-08-31"
PRESERVED_PORTFOLIO_KEYS = (
    "equal_weight_top_decile",
    "positive_alpha_proportional_top_decile",
)


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


def _rows_by_identity(
    state: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    rows = state.get("rows")
    if not isinstance(rows, list) or not rows:
        raise AlphaContractError("RM001-v3 P001 risk state has no rows")
    mapped = {
        (str(row["symbol"]), str(row["isin"])): row
        for row in rows
    }
    if len(mapped) != len(rows):
        raise AlphaContractError(
            "RM001-v3 P001 risk state has duplicate identities"
        )
    return mapped


def _control_positions(
    artifact: dict[str, Any],
    *,
    portfolio_key: str,
) -> list[dict[str, Any]]:
    _verify_hash(
        artifact,
        field="artifact_sha256",
        name="RM001-v3 P001 sealed I002 control",
    )
    if artifact.get("study_id") != "PO001-I002-v1":
        raise AlphaContractError("RM001-v3 P001 control is not sealed I002")
    if artifact.get("decision_session") != DECISION_SESSION:
        raise AlphaContractError(
            "RM001-v3 P001 control decision session mismatch"
        )
    if artifact.get("realized_outcome_opened") is not False:
        raise AlphaContractError(
            "RM001-v3 P001 control unexpectedly contains outcomes"
        )
    portfolios = artifact.get("portfolios")
    if not isinstance(portfolios, dict):
        raise AlphaContractError(
            "RM001-v3 P001 control portfolios are missing"
        )
    portfolio = portfolios.get(portfolio_key)
    if not isinstance(portfolio, dict):
        raise AlphaContractError(
            f"RM001-v3 P001 control portfolio missing: {portfolio_key}"
        )
    raw_positions = portfolio.get("positions")
    if not isinstance(raw_positions, list) or not raw_positions:
        raise AlphaContractError(
            f"RM001-v3 P001 control positions missing: {portfolio_key}"
        )

    positions = []
    seen: set[tuple[str, str]] = set()
    for row in raw_positions:
        identity = (str(row["symbol"]), str(row["isin"]))
        if identity in seen:
            raise AlphaContractError(
                f"RM001-v3 P001 duplicate control identity: {identity}"
            )
        seen.add(identity)
        weight_raw = row.get("target_weight", row.get("weight"))
        if weight_raw is None:
            raise AlphaContractError(
                "RM001-v3 P001 control position weight is missing"
            )
        weight = float(weight_raw)
        if not math.isfinite(weight) or weight < 0:
            raise AlphaContractError(
                "RM001-v3 P001 control weight is invalid"
            )
        if weight <= 1e-12:
            continue
        positions.append(
            {
                "symbol": identity[0],
                "isin": identity[1],
                "weight": weight,
            }
        )
    if not positions:
        raise AlphaContractError(
            f"RM001-v3 P001 control has no non-zero positions: {portfolio_key}"
        )
    return positions


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        raise AlphaContractError(
            "RM001-v3 P001 idiosyncratic distribution is empty"
        )
    array = np.asarray(values, dtype=float)
    if not np.isfinite(array).all() or np.any(array < 0):
        raise AlphaContractError(
            "RM001-v3 P001 idiosyncratic distribution is invalid"
        )
    return {
        "p25": float(np.percentile(array, 25)),
        "median": float(np.percentile(array, 50)),
        "p75": float(np.percentile(array, 75)),
    }


def _factor_variances(state: dict[str, Any]) -> dict[str, float]:
    names = [str(value) for value in state["factor_names"]]
    covariance = np.asarray(
        state["factor_covariance_daily"],
        dtype=float,
    )
    if covariance.shape != (len(names), len(names)):
        raise AlphaContractError(
            "RM001-v3 P001 covariance/factor shape mismatch"
        )
    if not np.isfinite(covariance).all():
        raise AlphaContractError(
            "RM001-v3 P001 covariance contains nonfinite values"
        )
    return {
        factor: float(covariance[index, index])
        for index, factor in enumerate(names)
    }


def _portfolio_attribution(
    *,
    v2_state: dict[str, Any],
    v3_state: dict[str, Any],
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    v2 = portfolio_risk_v2(v2_state, positions=positions)
    v3 = portfolio_risk_v3(v3_state, positions=positions)

    common_named_delta = {
        factor: (
            float(v3["portfolio_factor_exposures"][factor])
            - float(v2["portfolio_factor_exposures"][factor])
        )
        for factor in FACTOR_NAMES_V2
    }
    stat_exposures = {
        factor: float(v3["portfolio_factor_exposures"][factor])
        for factor in STAT_FACTOR_NAMES
    }
    stat_contributions = {
        factor: float(
            v3["factor_variance_contributions_daily"][factor]
        )
        for factor in STAT_FACTOR_NAMES
    }
    contribution_sum = sum(
        float(value)
        for value in v3[
            "factor_variance_contributions_daily"
        ].values()
    )
    if abs(
        contribution_sum - float(v3["factor_variance_daily"])
    ) > 1e-12:
        raise AlphaContractError(
            "RM001-v3 P001 factor contributions do not sum to factor variance"
        )

    return {
        "position_count": len(positions),
        "v2": v2,
        "v3": v3,
        "annualized_volatility_delta": (
            float(v3["annualized_volatility"])
            - float(v2["annualized_volatility"])
        ),
        "total_variance_daily_delta": (
            float(v3["total_variance_daily"])
            - float(v2["total_variance_daily"])
        ),
        "factor_variance_daily_delta": (
            float(v3["factor_variance_daily"])
            - float(v2["factor_variance_daily"])
        ),
        "idiosyncratic_variance_daily_delta": (
            float(v3["idiosyncratic_variance_daily"])
            - float(v2["idiosyncratic_variance_daily"])
        ),
        "named_factor_exposure_delta": common_named_delta,
        "statistical_factor_exposures": stat_exposures,
        "statistical_factor_variance_contributions_daily": (
            stat_contributions
        ),
        "statistical_factor_contribution_sum_daily": sum(
            stat_contributions.values()
        ),
        "v3_factor_contribution_sum_daily": contribution_sum,
    }


def run_rm001_v3_p001(
    *,
    v2_risk_state: dict[str, Any],
    v2_factor_history: dict[str, Any],
    v3_risk_state: dict[str, Any],
    sealed_i002_artifact: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        v2_risk_state,
        field="state_sha256",
        name="RM001-v3 P001 parent v2 risk state",
    )
    _verify_hash(
        v2_factor_history,
        field="history_sha256",
        name="RM001-v3 P001 parent v2 factor history",
    )
    _verify_hash(
        v3_risk_state,
        field="state_sha256",
        name="RM001-v3 P001 v3 risk state",
    )

    if v2_risk_state.get("model_id") != RM001_V2_MODEL_ID:
        raise AlphaContractError(
            "RM001-v3 P001 baseline must be RM001-v2"
        )
    if v2_factor_history.get("model_id") != RM001_V2_MODEL_ID:
        raise AlphaContractError(
            "RM001-v3 P001 parent history must be RM001-v2"
        )
    if v3_risk_state.get("model_id") != RM001_V3_MODEL_ID:
        raise AlphaContractError(
            "RM001-v3 P001 challenger must be RM001-v3"
        )
    if (
        v2_risk_state.get("as_of_session") != DECISION_SESSION
        or v3_risk_state.get("as_of_session") != DECISION_SESSION
    ):
        raise AlphaContractError(
            "RM001-v3 P001 risk-state decision session mismatch"
        )
    if v3_risk_state.get("parent_v2_risk_state_sha256") != (
        v2_risk_state["state_sha256"]
    ):
        raise AlphaContractError(
            "RM001-v3 P001 v3 parent risk binding mismatch"
        )
    if v3_risk_state.get("parent_v2_factor_history_sha256") != (
        v2_factor_history["history_sha256"]
    ):
        raise AlphaContractError(
            "RM001-v3 P001 v3 parent history binding mismatch"
        )

    if tuple(v2_risk_state.get("factor_names", ())) != FACTOR_NAMES_V2:
        raise AlphaContractError(
            "RM001-v3 P001 parent factor set differs from v2"
        )
    if tuple(v3_risk_state.get("factor_names", ())) != FACTOR_NAMES_V3:
        raise AlphaContractError(
            "RM001-v3 P001 challenger factor set differs from frozen v3"
        )
    if int(v3_risk_state.get("statistical_window") or 0) != 120:
        raise AlphaContractError(
            "RM001-v3 P001 statistical basis window differs from frozen v3"
        )
    if int(v3_risk_state.get("risk_estimation_window") or 0) != 60:
        raise AlphaContractError(
            "RM001-v3 P001 risk-estimation window differs from P1"
        )
    if int(v3_risk_state.get("statistical_component_count") or 0) != 5:
        raise AlphaContractError(
            "RM001-v3 P001 component count differs from frozen v3"
        )
    if int(v3_risk_state.get("complete_statistical_identity_count") or 0) < 500:
        raise AlphaContractError(
            "RM001-v3 P001 complete-history universe below frozen minimum"
        )

    singular_values = [
        float(value) for value in v3_risk_state["singular_values"]
    ]
    gaps = [
        float(value)
        for value in v3_risk_state[
            "adjacent_singular_relative_gaps"
        ]
    ]
    if len(singular_values) != 5 or len(gaps) != 4:
        raise AlphaContractError(
            "RM001-v3 P001 singular diagnostics have wrong dimensions"
        )
    if (
        not all(math.isfinite(value) and value > 0 for value in singular_values)
        or min(gaps) < 1e-8
    ):
        raise AlphaContractError(
            "RM001-v3 P001 singular diagnostics fail frozen gate"
        )

    v2_rows = _rows_by_identity(v2_risk_state)
    v3_rows = _rows_by_identity(v3_risk_state)
    if set(v2_rows) != set(v3_rows):
        raise AlphaContractError(
            "RM001-v3 P001 current identity set differs from RM001-v2"
        )
    common = sorted(v2_rows)

    v2_idio = [
        float(v2_rows[identity]["idiosyncratic_variance_daily"])
        for identity in common
    ]
    v3_idio = [
        float(v3_rows[identity]["idiosyncratic_variance_daily"])
        for identity in common
    ]
    if any(
        not math.isfinite(value) or value < 0
        for value in [*v2_idio, *v3_idio]
    ):
        raise AlphaContractError(
            "RM001-v3 P001 idiosyncratic variance is invalid"
        )

    down = sum(
        new < old - 1e-15
        for old, new in zip(v2_idio, v3_idio, strict=True)
    )
    up = sum(
        new > old + 1e-15
        for old, new in zip(v2_idio, v3_idio, strict=True)
    )
    unchanged = len(common) - down - up

    portfolio_attribution = {}
    for key in PRESERVED_PORTFOLIO_KEYS:
        positions = _control_positions(
            sealed_i002_artifact,
            portfolio_key=key,
        )
        position_ids = {
            (str(row["symbol"]), str(row["isin"]))
            for row in positions
        }
        missing = sorted(position_ids - set(v2_rows))
        if missing:
            raise AlphaContractError(
                f"RM001-v3 P001 I002 positions absent from risk state "
                f"for {key}: {missing[:10]}"
            )
        portfolio_attribution[key] = _portfolio_attribution(
            v2_state=v2_risk_state,
            v3_state=v3_risk_state,
            positions=positions,
        )

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
        "v2_factor_history_sha256": v2_factor_history["history_sha256"],
        "v3_risk_state_sha256": v3_risk_state["state_sha256"],
        "sealed_i002_artifact_sha256": sealed_i002_artifact[
            "artifact_sha256"
        ],
        "identity": {
            "v2_security_count": len(v2_rows),
            "v3_security_count": len(v3_rows),
            "identity_sets_equal": True,
            "complete_statistical_identity_count": int(
                v3_risk_state["complete_statistical_identity_count"]
            ),
            "fallback_identity_count": int(
                v3_risk_state["fallback_identity_count"]
            ),
        },
        "statistical_basis": {
            "singular_values": singular_values,
            "adjacent_singular_relative_gaps": gaps,
            "explained_variance_ratio": explained,
            "explained_variance_ratio_total": sum(explained),
            "sign_anchors": v3_risk_state["statistical_sign_anchors"],
        },
        "idiosyncratic": {
            "v2": _percentiles(v2_idio),
            "v3": _percentiles(v3_idio),
            "median_variance_delta": (
                _percentiles(v3_idio)["median"]
                - _percentiles(v2_idio)["median"]
            ),
            "identity_count_lower_in_v3": down,
            "identity_count_higher_in_v3": up,
            "identity_count_unchanged": unchanged,
        },
        "factor_daily_variances": {
            "v2": _factor_variances(v2_risk_state),
            "v3": _factor_variances(v3_risk_state),
        },
        "sealed_i002_portfolio_risk": portfolio_attribution,
        "control_resolution": {
            "protocol_amendment": "RM001-v3-P001-P2",
            "unavailable_portfolios": [
                "risk_aware_zero_cost",
                "full_po001_observable_cost_floor",
            ],
            "reason": (
                "SEALED_I002_COMPACT_OPTIMIZER_SUMMARIES_DID_NOT_PERSIST_"
                "FULL_TARGET_WEIGHT_VECTORS"
            ),
            "exact_preserved_portfolios_used": list(
                PRESERVED_PORTFOLIO_KEYS
            ),
        },
        "interpretation_limits": {
            "return_outcome_opened": False,
            "alpha_model_fit_performed": False,
            "portfolio_reoptimized": False,
            "prospective_v3_allowed": False,
            "prospective_size_source_timing_verified": False,
            "sector_factor_available": False,
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
