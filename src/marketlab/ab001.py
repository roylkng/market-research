from __future__ import annotations

import copy
import math
import re
import statistics
from collections import defaultdict
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, cross_sectional_percentile, digest

AB001_LIBRARY_ID = "AB001-ALPHA-LIBRARY-v1"
AB001_BLENDER_ID = "AB001-v1-DEVELOPMENT"
EFFICACY_LOOKBACK_SESSIONS = 60
MIN_EFFICACY_SESSIONS = 20
MIN_IC_CROSS_SECTION = 100
MIN_CURRENT_COMMON_STOCKS = 100
MIN_CALIBRATION_SESSIONS = 20
MIN_CALIBRATION_ROWS = 2_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _library_hash(library: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(library)
    unsigned.pop("library_sha256", None)
    return digest(unsigned)


def new_alpha_library() -> dict[str, Any]:
    library: dict[str, Any] = {
        "schema_version": 1,
        "library_id": AB001_LIBRARY_ID,
        "record_count": 0,
        "records": [],
        "outcomes_embedded": False,
        "live_capital_allowed": False,
    }
    library["library_sha256"] = _library_hash(library)
    return library


def validate_alpha_library(library: dict[str, Any]) -> None:
    if library.get("library_id") != AB001_LIBRARY_ID:
        raise AlphaContractError("unexpected AB001 alpha library id")
    if library.get("outcomes_embedded") is not False:
        raise AlphaContractError("AB001 prediction library cannot contain outcomes")
    if library.get("live_capital_allowed") is not False:
        raise AlphaContractError("AB001 alpha library cannot allow live capital")
    records = library.get("records")
    if not isinstance(records, list):
        raise AlphaContractError("AB001 alpha records must be a list")
    if library.get("record_count") != len(records):
        raise AlphaContractError("AB001 alpha record count mismatch")
    seen: set[tuple[str, int, str, str, str]] = set()
    for row in records:
        if not isinstance(row, dict):
            raise AlphaContractError("AB001 alpha record must be an object")
        if row.get("prediction_role") != "OOS":
            raise AlphaContractError("AB001 accepts OOS predictions only")
        forbidden = {
            "target_excess_return",
            "outcome",
            "label",
            "label_exit_session",
        } & set(row)
        if forbidden:
            raise AlphaContractError(
                f"AB001 alpha record embeds outcome fields: {sorted(forbidden)}"
            )
        alpha_id = str(row.get("alpha_id") or "").strip()
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        feature_session = str(row.get("feature_session") or "").strip()
        horizon = row.get("horizon_sessions")
        if (
            not alpha_id
            or not symbol
            or not isin
            or not feature_session
            or isinstance(horizon, bool)
            or not isinstance(horizon, int)
            or horizon < 1
        ):
            raise AlphaContractError("AB001 alpha identity is malformed")
        prediction = float(row.get("prediction"))
        if not math.isfinite(prediction):
            raise AlphaContractError("AB001 prediction must be finite")
        for field in ("model_sha256", "source_artifact_sha256"):
            value = str(row.get(field) or "").strip().lower()
            if not _SHA256.fullmatch(value):
                raise AlphaContractError(f"AB001 {field} must be SHA-256 hex")
        identity = (alpha_id, horizon, feature_session, symbol, isin)
        if identity in seen:
            raise AlphaContractError(f"duplicate AB001 alpha identity: {identity}")
        seen.add(identity)
    if str(library.get("library_sha256") or "") != _library_hash(library):
        raise AlphaContractError("AB001 alpha library hash mismatch")


def append_alpha_predictions(
    library: dict[str, Any],
    *,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    validate_alpha_library(library)
    if not records:
        raise AlphaContractError("AB001 append requires prediction records")
    updated = copy.deepcopy(library)
    updated.pop("library_sha256", None)
    for raw in records:
        row = {
            **raw,
            "symbol": str(raw.get("symbol") or "").strip().upper(),
            "isin": str(raw.get("isin") or "").strip(),
            "alpha_id": str(raw.get("alpha_id") or "").strip(),
            "prediction_role": str(raw.get("prediction_role") or "").strip(),
            "prediction": float(raw.get("prediction")),
        }
        updated["records"].append(row)
    updated["records"].sort(
        key=lambda row: (
            str(row["feature_session"]),
            int(row["horizon_sessions"]),
            str(row["alpha_id"]),
            str(row["symbol"]),
            str(row["isin"]),
        )
    )
    updated["record_count"] = len(updated["records"])
    updated["library_sha256"] = _library_hash(updated)
    validate_alpha_library(updated)
    return updated


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    x = np.asarray(left, dtype=float)
    y = np.asarray(right, dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise AlphaContractError("AB001 correlation contains nonfinite values")
    x = x - x.mean()
    y = y - y.mean()
    denominator = float(np.sqrt((x @ x) * (y @ y)))
    if denominator <= 1e-16:
        return None
    return float((x @ y) / denominator)


def _centered_ranks(values: dict[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    encoded = {
        f"{symbol}|{isin}": value
        for (symbol, isin), value in values.items()
    }
    ranked = cross_sectional_percentile(encoded)
    result = {}
    for identity in values:
        key = f"{identity[0]}|{identity[1]}"
        percentile = ranked[key]
        if percentile is None:
            raise AlphaContractError("AB001 percentile unexpectedly missing")
        result[identity] = 2.0 * float(percentile) - 1.0
    return result


def _prediction_maps(
    library: dict[str, Any],
    *,
    horizon_sessions: int,
    alpha_ids: list[str],
) -> dict[str, dict[tuple[str, str, str], float]]:
    wanted = set(alpha_ids)
    maps = {alpha_id: {} for alpha_id in alpha_ids}
    for row in library["records"]:
        if (
            row["alpha_id"] not in wanted
            or int(row["horizon_sessions"]) != horizon_sessions
        ):
            continue
        maps[row["alpha_id"]][
            (
                str(row["feature_session"]),
                str(row["symbol"]),
                str(row["isin"]),
            )
        ] = float(row["prediction"])
    return maps


def _outcome_index(
    outcomes: list[dict[str, Any]],
    *,
    horizon_sessions: int,
    decision_session: str,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    index = {}
    for row in outcomes:
        if int(row.get("horizon_sessions") or 0) != horizon_sessions:
            continue
        if str(row.get("status") or "COMPLETE") != "COMPLETE":
            continue
        feature_session = str(row.get("feature_session") or "")
        exit_session = str(row.get("label_exit_session") or "")
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        if not feature_session or not exit_session or not symbol or not isin:
            raise AlphaContractError("AB001 outcome identity is malformed")
        if exit_session >= decision_session:
            continue
        target = float(row.get("target_excess_return"))
        if not math.isfinite(target):
            raise AlphaContractError("AB001 outcome target must be finite")
        key = (feature_session, symbol, isin)
        if key in index:
            raise AlphaContractError(f"duplicate AB001 matured outcome: {key}")
        index[key] = {
            **row,
            "target_excess_return": target,
        }
    return index


def _daily_ic(
    predictions: dict[tuple[str, str, str], float],
    outcomes: dict[tuple[str, str, str], dict[str, Any]],
    *,
    decision_session: str,
) -> list[dict[str, Any]]:
    by_session: dict[str, list[tuple[tuple[str, str], float, float]]] = defaultdict(list)
    for key, prediction in predictions.items():
        feature_session, symbol, isin = key
        if feature_session >= decision_session:
            continue
        outcome = outcomes.get(key)
        if outcome is None:
            continue
        by_session[feature_session].append(
            ((symbol, isin), prediction, float(outcome["target_excess_return"]))
        )

    result = []
    for session in sorted(by_session):
        rows = by_session[session]
        if len(rows) < MIN_IC_CROSS_SECTION:
            continue
        pred_values = {identity: pred for identity, pred, _ in rows}
        target_values = {identity: target for identity, _, target in rows}
        pred_rank = _centered_ranks(pred_values)
        target_rank = _centered_ranks(target_values)
        identities = sorted(pred_values)
        ic = _pearson(
            [pred_rank[identity] for identity in identities],
            [target_rank[identity] for identity in identities],
        )
        if ic is None:
            continue
        result.append(
            {
                "feature_session": session,
                "rank_ic": ic,
                "observation_count": len(rows),
            }
        )
    return result


def _pair_prediction_correlation(
    left: dict[tuple[str, str, str], float],
    right: dict[tuple[str, str, str], float],
    outcomes: dict[tuple[str, str, str], dict[str, Any]],
    *,
    allowed_sessions: set[str],
) -> float | None:
    left_scores = []
    right_scores = []
    for session in sorted(allowed_sessions):
        identities = sorted(
            {
                (symbol, isin)
                for feature_session, symbol, isin in outcomes
                if feature_session == session
                and (feature_session, symbol, isin) in left
                and (feature_session, symbol, isin) in right
            }
        )
        if len(identities) < MIN_IC_CROSS_SECTION:
            continue
        left_rank = _centered_ranks(
            {
                identity: left[(session, identity[0], identity[1])]
                for identity in identities
            }
        )
        right_rank = _centered_ranks(
            {
                identity: right[(session, identity[0], identity[1])]
                for identity in identities
            }
        )
        left_scores.extend(left_rank[identity] for identity in identities)
        right_scores.extend(right_rank[identity] for identity in identities)
    return _pearson(left_scores, right_scores)


def _calibrate_blend(
    *,
    active_alpha_ids: list[str],
    weights: dict[str, float],
    prediction_maps: dict[str, dict[tuple[str, str, str], float]],
    outcomes: dict[tuple[str, str, str], dict[str, Any]],
    allowed_sessions: list[str],
) -> dict[str, Any]:
    blend_scores = []
    targets = []
    used_sessions = 0
    for session in allowed_sessions:
        identities = sorted(
            {
                (symbol, isin)
                for feature_session, symbol, isin in outcomes
                if feature_session == session
                and all(
                    (session, symbol, isin) in prediction_maps[alpha_id]
                    for alpha_id in active_alpha_ids
                )
            }
        )
        if len(identities) < MIN_IC_CROSS_SECTION:
            continue
        standardized = {}
        for alpha_id in active_alpha_ids:
            standardized[alpha_id] = _centered_ranks(
                {
                    identity: prediction_maps[alpha_id][
                        (session, identity[0], identity[1])
                    ]
                    for identity in identities
                }
            )
        used_sessions += 1
        for identity in identities:
            score = sum(
                weights[alpha_id] * standardized[alpha_id][identity]
                for alpha_id in active_alpha_ids
            )
            blend_scores.append(score)
            targets.append(
                float(
                    outcomes[(session, identity[0], identity[1])][
                        "target_excess_return"
                    ]
                )
            )

    if (
        used_sessions < MIN_CALIBRATION_SESSIONS
        or len(blend_scores) < MIN_CALIBRATION_ROWS
    ):
        return {
            "status": "INSUFFICIENT_MATURED_CALIBRATION_DATA",
            "session_count": used_sessions,
            "observation_count": len(blend_scores),
        }

    x = np.asarray(blend_scores, dtype=float)
    y = np.asarray(targets, dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    intercept = float(coefficients[0])
    slope = float(coefficients[1])
    fitted = design @ coefficients
    residual = y - fitted
    total = float(((y - y.mean()) ** 2).sum())
    r_squared = (
        None
        if total <= 1e-16
        else 1.0 - float((residual**2).sum()) / total
    )
    if not math.isfinite(slope) or slope <= 0:
        return {
            "status": "NONPOSITIVE_CALIBRATION_SLOPE",
            "session_count": used_sessions,
            "observation_count": len(x),
            "intercept": intercept,
            "slope": slope,
            "r_squared": r_squared,
        }
    return {
        "status": "READY",
        "session_count": used_sessions,
        "observation_count": len(x),
        "intercept": intercept,
        "slope": slope,
        "r_squared": r_squared,
    }


def blend_oos_alphas(
    *,
    library: dict[str, Any],
    outcomes: list[dict[str, Any]],
    decision_session: str,
    horizon_sessions: int,
    alpha_ids: list[str],
) -> dict[str, Any]:
    validate_alpha_library(library)
    if (
        isinstance(horizon_sessions, bool)
        or not isinstance(horizon_sessions, int)
        or horizon_sessions < 1
    ):
        raise AlphaContractError("AB001 horizon must be a positive integer")
    normalized_alpha_ids = [value.strip() for value in alpha_ids if value.strip()]
    if (
        not normalized_alpha_ids
        or len(normalized_alpha_ids) != len(set(normalized_alpha_ids))
    ):
        raise AlphaContractError("AB001 alpha_ids must be non-empty and unique")

    prediction_maps = _prediction_maps(
        library,
        horizon_sessions=horizon_sessions,
        alpha_ids=normalized_alpha_ids,
    )
    matured_outcomes = _outcome_index(
        outcomes,
        horizon_sessions=horizon_sessions,
        decision_session=decision_session,
    )

    diagnostics = {}
    eligible = []
    ic_sessions_by_alpha: dict[str, list[str]] = {}
    for alpha_id in normalized_alpha_ids:
        current_count = sum(
            1
            for session, _, _ in prediction_maps[alpha_id]
            if session == decision_session
        )
        ic_rows = _daily_ic(
            prediction_maps[alpha_id],
            matured_outcomes,
            decision_session=decision_session,
        )[-EFFICACY_LOOKBACK_SESSIONS:]
        mean_ic = (
            statistics.mean(row["rank_ic"] for row in ic_rows)
            if ic_rows
            else None
        )
        diagnostics[alpha_id] = {
            "current_prediction_count": current_count,
            "matured_ic_session_count": len(ic_rows),
            "trailing_mean_rank_ic": mean_ic,
        }
        ic_sessions_by_alpha[alpha_id] = [
            str(row["feature_session"]) for row in ic_rows
        ]
        if (
            current_count > 0
            and len(ic_rows) >= MIN_EFFICACY_SESSIONS
        ):
            eligible.append(alpha_id)

    if not eligible:
        artifact = {
            "schema_version": 1,
            "blender_id": AB001_BLENDER_ID,
            "decision_session": decision_session,
            "horizon_sessions": horizon_sessions,
            "status": "NO_ELIGIBLE_ALPHA_HISTORY",
            "alpha_diagnostics": diagnostics,
            "library_sha256": library["library_sha256"],
            "live_capital_allowed": False,
        }
        artifact["artifact_sha256"] = digest(artifact)
        return artifact

    correlations: dict[str, dict[str, float | None]] = {
        alpha_id: {} for alpha_id in eligible
    }
    for left_index, left_id in enumerate(eligible):
        for right_id in eligible[left_index:]:
            if left_id == right_id:
                corr = 1.0
            else:
                common_sessions = sorted(
                    set(ic_sessions_by_alpha[left_id])
                    & set(ic_sessions_by_alpha[right_id])
                )[-EFFICACY_LOOKBACK_SESSIONS:]
                corr = _pair_prediction_correlation(
                    prediction_maps[left_id],
                    prediction_maps[right_id],
                    matured_outcomes,
                    allowed_sessions=set(common_sessions),
                )
            correlations[left_id][right_id] = corr
            correlations[right_id][left_id] = corr

    effective_scores = {}
    for alpha_id in eligible:
        mean_ic = float(diagnostics[alpha_id]["trailing_mean_rank_ic"])
        raw = max(mean_ic, 0.0)
        peer_corr = [
            abs(float(correlations[alpha_id][peer]))
            for peer in eligible
            if peer != alpha_id
            and correlations[alpha_id][peer] is not None
        ]
        redundancy = statistics.mean(peer_corr) if peer_corr else 0.0
        effective = raw / (1.0 + redundancy)
        diagnostics[alpha_id].update(
            {
                "positive_efficacy_score": raw,
                "mean_abs_prediction_correlation": redundancy,
                "effective_score": effective,
            }
        )
        effective_scores[alpha_id] = effective

    active = [
        alpha_id
        for alpha_id in eligible
        if effective_scores[alpha_id] > 0
    ]
    if not active:
        artifact = {
            "schema_version": 1,
            "blender_id": AB001_BLENDER_ID,
            "decision_session": decision_session,
            "horizon_sessions": horizon_sessions,
            "status": "NO_POSITIVE_OOS_EFFICACY",
            "eligible_alpha_ids": eligible,
            "alpha_diagnostics": diagnostics,
            "prediction_correlations": correlations,
            "library_sha256": library["library_sha256"],
            "live_capital_allowed": False,
        }
        artifact["artifact_sha256"] = digest(artifact)
        return artifact

    score_sum = sum(effective_scores[alpha_id] for alpha_id in active)
    weights = {
        alpha_id: effective_scores[alpha_id] / score_sum
        for alpha_id in active
    }

    current_identity_sets = []
    for alpha_id in active:
        current_identity_sets.append(
            {
                (symbol, isin)
                for session, symbol, isin in prediction_maps[alpha_id]
                if session == decision_session
            }
        )
    common_current = set.intersection(*current_identity_sets)
    if len(common_current) < MIN_CURRENT_COMMON_STOCKS:
        raise AlphaContractError(
            f"AB001 current common universe below frozen minimum: {len(common_current)}"
        )
    identities = sorted(common_current)
    current_standardized = {}
    for alpha_id in active:
        current_standardized[alpha_id] = _centered_ranks(
            {
                identity: prediction_maps[alpha_id][
                    (decision_session, identity[0], identity[1])
                ]
                for identity in identities
            }
        )

    current_rows = []
    for identity in identities:
        active_score = sum(
            weights[alpha_id] * current_standardized[alpha_id][identity]
            for alpha_id in active
        )
        equal_score = statistics.mean(
            current_standardized[alpha_id][identity]
            for alpha_id in active
        )
        current_rows.append(
            {
                "symbol": identity[0],
                "isin": identity[1],
                "blended_score": active_score,
                "equal_weight_score": equal_score,
            }
        )

    common_training_sessions = sorted(
        set.intersection(
            *[
                set(ic_sessions_by_alpha[alpha_id])
                for alpha_id in active
            ]
        )
    )[-EFFICACY_LOOKBACK_SESSIONS:]
    calibration = _calibrate_blend(
        active_alpha_ids=active,
        weights=weights,
        prediction_maps=prediction_maps,
        outcomes=matured_outcomes,
        allowed_sessions=common_training_sessions,
    )
    if calibration.get("status") == "READY":
        for row in current_rows:
            row["expected_excess_return"] = (
                float(calibration["intercept"])
                + float(calibration["slope"]) * float(row["blended_score"])
            )
    else:
        for row in current_rows:
            row["expected_excess_return"] = None

    artifact = {
        "schema_version": 1,
        "blender_id": AB001_BLENDER_ID,
        "decision_session": decision_session,
        "horizon_sessions": horizon_sessions,
        "status": (
            "READY_FOR_PO001"
            if calibration.get("status") == "READY"
            else "BLEND_SCORE_ONLY"
        ),
        "library_sha256": library["library_sha256"],
        "candidate_alpha_ids": normalized_alpha_ids,
        "eligible_alpha_ids": eligible,
        "active_alpha_ids": active,
        "active_weights": weights,
        "alpha_diagnostics": diagnostics,
        "prediction_correlations": correlations,
        "common_current_stock_count": len(current_rows),
        "calibration": calibration,
        "rows": current_rows,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact
