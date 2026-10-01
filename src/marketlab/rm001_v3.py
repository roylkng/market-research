from __future__ import annotations

import copy
import math
from collections import defaultdict
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001 import ANNUALIZATION_SESSIONS, _q, _verify_hash
from marketlab.rm001_v2 import FACTOR_NAMES_V2, RM001_V2_MODEL_ID

RM001_V3_MODEL_ID = "RM001-v3-DEVELOPMENT"
STAT_FACTOR_NAMES = (
    "STAT_PC01",
    "STAT_PC02",
    "STAT_PC03",
    "STAT_PC04",
    "STAT_PC05",
)
FACTOR_NAMES_V3 = (*FACTOR_NAMES_V2, *STAT_FACTOR_NAMES)

DEFAULT_STATISTICAL_WINDOW = 120
DEFAULT_COMPONENT_COUNT = 5
DEFAULT_MIN_COMPLETE_CURRENT_IDENTITIES = 500
DEFAULT_MIN_SINGULAR_RELATIVE_GAP = 1e-8


def _history_hash(history: dict[str, Any]) -> None:
    _verify_hash(
        history,
        field="history_sha256",
        name="RM001-v3 parent factor history",
    )


def _risk_hash(state: dict[str, Any]) -> None:
    _verify_hash(
        state,
        field="state_sha256",
        name="RM001-v3 parent risk state",
    )


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row["symbol"]), str(row["isin"]))


def _relative_gaps(values: np.ndarray, count: int) -> list[float]:
    if count < 1:
        raise AlphaContractError("RM001-v3 component count must be positive")
    if len(values) < count:
        raise AlphaContractError(
            "RM001-v3 SVD returned fewer singular values than requested"
        )
    selected = values[:count]
    if not np.isfinite(selected).all() or np.any(selected <= 0):
        raise AlphaContractError(
            "RM001-v3 top singular values must be finite and positive"
        )
    if np.any(selected[:-1] < selected[1:]):
        raise AlphaContractError(
            "RM001-v3 singular values are not ordered descending"
        )
    gaps = []
    for left, right in zip(selected[:-1], selected[1:], strict=True):
        denominator = max(abs(float(left)), abs(float(right)))
        if denominator <= 0:
            raise AlphaContractError(
                "RM001-v3 singular-value gap denominator is zero"
            )
        gaps.append(abs(float(left) - float(right)) / denominator)
    return gaps


def _aligned_factor_rows(
    factor_history: dict[str, Any],
    *,
    as_of_session: str,
    statistical_window: int,
) -> tuple[list[str], dict[str, dict[str, float]]]:
    rows = [
        row
        for row in factor_history.get("factor_returns", [])
        if str(row.get("realized_session") or "") <= as_of_session
    ]
    rows.sort(key=lambda row: str(row["realized_session"]))
    if len(rows) < statistical_window:
        raise AlphaContractError(
            "RM001-v3 has insufficient realized factor-return history"
        )
    selected = rows[-statistical_window:]
    sessions = [str(row["realized_session"]) for row in selected]
    if len(set(sessions)) != len(sessions):
        raise AlphaContractError(
            "RM001-v3 realized factor sessions are not unique"
        )
    factor_by_session: dict[str, dict[str, float]] = {}
    for row in selected:
        session = str(row["realized_session"])
        values = row.get("factor_returns")
        if not isinstance(values, dict):
            raise AlphaContractError(
                "RM001-v3 parent factor-return row is malformed"
            )
        if set(values) != set(FACTOR_NAMES_V2):
            raise AlphaContractError(
                "RM001-v3 parent named factor set differs from RM001-v2"
            )
        parsed = {
            factor: float(values[factor])
            for factor in FACTOR_NAMES_V2
        }
        if not all(math.isfinite(value) for value in parsed.values()):
            raise AlphaContractError(
                "RM001-v3 named factor return is nonfinite"
            )
        factor_by_session[session] = parsed
    return sessions, factor_by_session


def _residual_history_for_current(
    factor_history: dict[str, Any],
    *,
    current_identities: set[tuple[str, str]],
    sessions: list[str],
) -> dict[tuple[str, str], dict[str, float]]:
    wanted_sessions = set(sessions)
    residuals: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in factor_history.get("residuals", []):
        session = str(row.get("realized_session") or "")
        if session not in wanted_sessions:
            continue
        identity = _identity(row)
        if identity not in current_identities:
            continue
        if session in residuals[identity]:
            raise AlphaContractError(
                f"RM001-v3 duplicate residual for {identity} on {session}"
            )
        value = float(row["residual_return"])
        if not math.isfinite(value):
            raise AlphaContractError(
                "RM001-v3 parent residual return is nonfinite"
            )
        residuals[identity][session] = value
    return residuals


def _canonicalize_stat_components(
    *,
    identities: list[tuple[str, str]],
    loadings: np.ndarray,
    factor_returns: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    if loadings.ndim != 2 or factor_returns.ndim != 2:
        raise AlphaContractError(
            "RM001-v3 statistical matrices must be two-dimensional"
        )
    if loadings.shape[1] != factor_returns.shape[1]:
        raise AlphaContractError(
            "RM001-v3 statistical component dimensions disagree"
        )
    canonical_loadings = np.array(loadings, dtype=float, copy=True)
    canonical_returns = np.array(factor_returns, dtype=float, copy=True)
    anchors = []
    for component in range(canonical_loadings.shape[1]):
        column = canonical_loadings[:, component]
        anchor_index = int(np.argmax(np.abs(column)))
        anchor_identity = identities[anchor_index]
        anchor_loading_before = float(column[anchor_index])
        flipped = anchor_loading_before < 0
        if flipped:
            canonical_loadings[:, component] *= -1.0
            canonical_returns[:, component] *= -1.0
        anchors.append(
            {
                "factor": STAT_FACTOR_NAMES[component],
                "symbol": anchor_identity[0],
                "isin": anchor_identity[1],
                "anchor_loading_before_sign_fix": _q(
                    anchor_loading_before
                ),
                "sign_flipped": flipped,
                "anchor_loading_after_sign_fix": _q(
                    canonical_loadings[anchor_index, component]
                ),
            }
        )
        if canonical_loadings[anchor_index, component] < 0:
            raise AlphaContractError(
                "RM001-v3 statistical sign anchor failed"
            )
    return canonical_loadings, canonical_returns, anchors


def build_rm001_v3_risk_state(
    *,
    v2_risk_state: dict[str, Any],
    v2_factor_history: dict[str, Any],
    statistical_window: int = DEFAULT_STATISTICAL_WINDOW,
    component_count: int = DEFAULT_COMPONENT_COUNT,
    minimum_complete_current_identities: int = (
        DEFAULT_MIN_COMPLETE_CURRENT_IDENTITIES
    ),
    minimum_singular_relative_gap: float = (
        DEFAULT_MIN_SINGULAR_RELATIVE_GAP
    ),
) -> dict[str, Any]:
    _risk_hash(v2_risk_state)
    _history_hash(v2_factor_history)
    if v2_risk_state.get("model_id") != RM001_V2_MODEL_ID:
        raise AlphaContractError(
            "RM001-v3 requires an RM001-v2 parent risk state"
        )
    if v2_factor_history.get("model_id") != RM001_V2_MODEL_ID:
        raise AlphaContractError(
            "RM001-v3 requires an RM001-v2 factor history"
        )
    if v2_factor_history.get("exposure_panel_sha256") != (
        v2_risk_state.get("exposure_panel_sha256")
    ):
        raise AlphaContractError(
            "RM001-v3 parent risk/history exposure binding mismatch"
        )
    if (
        isinstance(statistical_window, bool)
        or not isinstance(statistical_window, int)
        or statistical_window < 3
    ):
        raise AlphaContractError(
            "RM001-v3 statistical window must be an integer >= 3"
        )
    if (
        isinstance(component_count, bool)
        or not isinstance(component_count, int)
        or component_count < 1
        or component_count > len(STAT_FACTOR_NAMES)
    ):
        raise AlphaContractError(
            "RM001-v3 component count is outside frozen bounds"
        )
    if (
        isinstance(minimum_complete_current_identities, bool)
        or not isinstance(minimum_complete_current_identities, int)
        or minimum_complete_current_identities < component_count + 1
    ):
        raise AlphaContractError(
            "RM001-v3 minimum complete identity count is invalid"
        )
    if (
        not math.isfinite(minimum_singular_relative_gap)
        or minimum_singular_relative_gap <= 0
    ):
        raise AlphaContractError(
            "RM001-v3 singular-gap threshold must be positive"
        )

    as_of_session = str(v2_risk_state["as_of_session"])
    current_rows = v2_risk_state.get("rows")
    if not isinstance(current_rows, list) or not current_rows:
        raise AlphaContractError(
            "RM001-v3 parent risk state has no current rows"
        )
    current_by_identity = {
        _identity(row): row
        for row in current_rows
    }
    if len(current_by_identity) != len(current_rows):
        raise AlphaContractError(
            "RM001-v3 parent risk state has duplicate identities"
        )
    current_identities = set(current_by_identity)

    sessions, named_returns = _aligned_factor_rows(
        v2_factor_history,
        as_of_session=as_of_session,
        statistical_window=statistical_window,
    )
    residual_history = _residual_history_for_current(
        v2_factor_history,
        current_identities=current_identities,
        sessions=sessions,
    )

    complete_identities = sorted(
        identity
        for identity in current_identities
        if set(residual_history.get(identity, {})) == set(sessions)
    )
    if len(complete_identities) < minimum_complete_current_identities:
        raise AlphaContractError(
            "RM001-v3 complete residual-history universe is too small"
        )

    residual_matrix = np.asarray(
        [
            [
                residual_history[identity][session]
                for identity in complete_identities
            ]
            for session in sessions
        ],
        dtype=float,
    )
    if residual_matrix.shape != (
        statistical_window,
        len(complete_identities),
    ):
        raise AlphaContractError(
            "RM001-v3 residual matrix shape mismatch"
        )
    if not np.isfinite(residual_matrix).all():
        raise AlphaContractError(
            "RM001-v3 residual matrix contains nonfinite values"
        )

    column_means = residual_matrix.mean(axis=0)
    centered = residual_matrix - column_means
    u, singular_values, vt = np.linalg.svd(
        centered,
        full_matrices=False,
    )
    gaps = _relative_gaps(singular_values, component_count)
    if gaps and min(gaps) < minimum_singular_relative_gap:
        raise AlphaContractError(
            "RM001-v3 top statistical components are numerically degenerate"
        )

    raw_loadings = vt[:component_count, :].T
    raw_factor_returns = (
        u[:, :component_count]
        * singular_values[:component_count]
    )
    loadings, stat_returns, anchors = _canonicalize_stat_components(
        identities=complete_identities,
        loadings=raw_loadings,
        factor_returns=raw_factor_returns,
    )

    reconstructed = stat_returns @ loadings.T
    post_stat_residual = centered - reconstructed
    if not np.isfinite(post_stat_residual).all():
        raise AlphaContractError(
            "RM001-v3 post-stat residual matrix is nonfinite"
        )

    named_matrix = np.asarray(
        [
            [
                named_returns[session][factor]
                for factor in FACTOR_NAMES_V2
            ]
            for session in sessions
        ],
        dtype=float,
    )
    combined_returns = np.hstack(
        [named_matrix, stat_returns]
    )
    covariance = np.cov(
        combined_returns,
        rowvar=False,
        ddof=1,
    )
    expected_factor_count = len(FACTOR_NAMES_V2) + component_count
    if covariance.shape != (
        expected_factor_count,
        expected_factor_count,
    ):
        raise AlphaContractError(
            "RM001-v3 combined covariance shape mismatch"
        )
    if not np.isfinite(covariance).all():
        raise AlphaContractError(
            "RM001-v3 combined covariance contains nonfinite values"
        )

    loading_by_identity = {
        identity: loadings[index, :]
        for index, identity in enumerate(complete_identities)
    }
    idio_by_identity = {
        identity: _q(
            np.var(
                post_stat_residual[:, index],
                ddof=1,
            )
        )
        for index, identity in enumerate(complete_identities)
    }
    if any(
        (not math.isfinite(value) or value < 0)
        for value in idio_by_identity.values()
    ):
        raise AlphaContractError(
            "RM001-v3 statistical idiosyncratic variance is invalid"
        )

    rows = []
    fallback_count = 0
    for identity in sorted(current_identities):
        parent = current_by_identity[identity]
        parent_exposures = parent.get("exposures")
        if not isinstance(parent_exposures, dict):
            raise AlphaContractError(
                "RM001-v3 parent exposures are malformed"
            )
        if set(parent_exposures) != set(FACTOR_NAMES_V2):
            raise AlphaContractError(
                "RM001-v3 parent factor set differs from RM001-v2"
            )
        exposures = {
            factor: _q(parent_exposures[factor])
            for factor in FACTOR_NAMES_V2
        }
        if identity in loading_by_identity:
            vector = loading_by_identity[identity]
            for index in range(component_count):
                exposures[STAT_FACTOR_NAMES[index]] = _q(
                    vector[index]
                )
            idio_variance = idio_by_identity[identity]
            stat_status = "STAT_COMPLETE_120"
        else:
            fallback_count += 1
            for factor in STAT_FACTOR_NAMES[:component_count]:
                exposures[factor] = 0.0
            idio_variance = _q(
                parent["idiosyncratic_variance_daily"]
            )
            stat_status = "V2_FALLBACK_NO_COMPLETE_STAT_HISTORY"

        rows.append(
            {
                "symbol": identity[0],
                "isin": identity[1],
                "exposures": exposures,
                "idiosyncratic_variance_daily": idio_variance,
                "idiosyncratic_status": parent[
                    "idiosyncratic_status"
                ],
                "statistical_status": stat_status,
            }
        )

    total_variance = float(np.sum(centered * centered))
    explained = singular_values[:component_count] ** 2
    explained_ratio = (
        np.zeros(component_count, dtype=float)
        if total_variance <= 0
        else explained / total_variance
    )

    state: dict[str, Any] = {
        "schema_version": 1,
        "model_id": RM001_V3_MODEL_ID,
        "parent_model_id": RM001_V2_MODEL_ID,
        "as_of_session": as_of_session,
        "factor_names": [
            *FACTOR_NAMES_V2,
            *STAT_FACTOR_NAMES[:component_count],
        ],
        "named_factor_names": list(FACTOR_NAMES_V2),
        "statistical_factor_names": list(
            STAT_FACTOR_NAMES[:component_count]
        ),
        "statistical_window": statistical_window,
        "statistical_first_realized_session": sessions[0],
        "statistical_last_realized_session": sessions[-1],
        "statistical_component_count": component_count,
        "minimum_complete_current_identities": (
            minimum_complete_current_identities
        ),
        "complete_statistical_identity_count": len(
            complete_identities
        ),
        "fallback_identity_count": fallback_count,
        "singular_values": [
            _q(value)
            for value in singular_values[:component_count]
        ],
        "adjacent_singular_relative_gaps": [
            _q(value) for value in gaps
        ],
        "minimum_singular_relative_gap": (
            minimum_singular_relative_gap
        ),
        "statistical_explained_variance_ratio": [
            _q(value) for value in explained_ratio
        ],
        "statistical_sign_anchors": anchors,
        "factor_covariance_window": statistical_window,
        "factor_covariance_first_realized_session": sessions[0],
        "factor_covariance_last_realized_session": sessions[-1],
        "factor_covariance_daily": [
            [_q(value) for value in row]
            for row in covariance.tolist()
        ],
        "security_count": len(rows),
        "rows": rows,
        "parent_v2_risk_state_sha256": v2_risk_state[
            "state_sha256"
        ],
        "parent_v2_factor_history_sha256": v2_factor_history[
            "history_sha256"
        ],
        "exposure_panel_sha256": v2_risk_state[
            "exposure_panel_sha256"
        ],
        "deferred_factors": {
            "SECTOR": (
                "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN"
            )
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def portfolio_risk_v3(
    risk_state: dict[str, Any],
    *,
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    _verify_hash(
        risk_state,
        field="state_sha256",
        name="RM001-v3 risk state",
    )
    if risk_state.get("model_id") != RM001_V3_MODEL_ID:
        raise AlphaContractError(
            "unexpected RM001-v3 risk state"
        )
    if not positions:
        raise AlphaContractError(
            "RM001-v3 positions cannot be empty"
        )

    factor_names = tuple(
        str(value) for value in risk_state["factor_names"]
    )
    rows_by_identity = {
        _identity(row): row
        for row in risk_state["rows"]
    }

    weights = []
    exposures = []
    idio = []
    for position in positions:
        weight = float(position["weight"])
        if not math.isfinite(weight) or weight < 0:
            raise AlphaContractError(
                "RM001-v3 weights must be finite and non-negative"
            )
        identity = (
            str(position["symbol"]),
            str(position["isin"]),
        )
        row = rows_by_identity.get(identity)
        if row is None:
            raise AlphaContractError(
                f"RM001-v3 position absent from risk state: {identity}"
            )
        weights.append(weight)
        exposures.append(
            [
                float(row["exposures"][factor])
                for factor in factor_names
            ]
        )
        idio.append(
            float(row["idiosyncratic_variance_daily"])
        )

    weight_array = np.asarray(weights, dtype=float)
    if float(weight_array.sum()) > 1.0 + 1e-12:
        raise AlphaContractError(
            "RM001-v3 portfolio weights cannot exceed 1"
        )
    exposure_matrix = np.asarray(exposures, dtype=float)
    covariance = np.asarray(
        risk_state["factor_covariance_daily"],
        dtype=float,
    )
    if covariance.shape != (
        len(factor_names),
        len(factor_names),
    ):
        raise AlphaContractError(
            "RM001-v3 portfolio covariance shape mismatch"
        )

    portfolio_factor_exposure = (
        weight_array @ exposure_matrix
    )
    factor_variance = float(
        portfolio_factor_exposure
        @ covariance
        @ portfolio_factor_exposure
    )
    idio_variance = float(
        np.sum(
            (weight_array ** 2)
            * np.asarray(idio, dtype=float)
        )
    )
    total_variance = factor_variance + idio_variance
    if total_variance < -1e-14:
        raise AlphaContractError(
            "RM001-v3 produced negative portfolio variance"
        )
    total_variance = max(0.0, total_variance)

    covariance_times_exposure = (
        covariance @ portfolio_factor_exposure
    )
    contributions = {
        factor: float(
            portfolio_factor_exposure[index]
            * covariance_times_exposure[index]
        )
        for index, factor in enumerate(factor_names)
    }

    return {
        "schema_version": 1,
        "model_id": RM001_V3_MODEL_ID,
        "as_of_session": risk_state["as_of_session"],
        "risk_state_sha256": risk_state["state_sha256"],
        "position_count": len(positions),
        "invested_weight": float(weight_array.sum()),
        "cash_weight": 1.0 - float(weight_array.sum()),
        "portfolio_factor_exposures": {
            factor: float(
                portfolio_factor_exposure[index]
            )
            for index, factor in enumerate(factor_names)
        },
        "factor_variance_daily": factor_variance,
        "idiosyncratic_variance_daily": idio_variance,
        "total_variance_daily": total_variance,
        "annualized_volatility": math.sqrt(
            total_variance * ANNUALIZATION_SESSIONS
        ),
        "factor_variance_contributions_daily": contributions,
        "live_capital_allowed": False,
    }
