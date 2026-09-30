from __future__ import annotations

import copy
import math
import statistics
from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, cross_sectional_percentile, digest
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_model import evaluate_cross_sectional_predictions

AB001_MODEL_ID = "AB001-v1-DEVELOPMENT"
TRAILING_EFFICACY_SESSIONS = 60
MIN_EFFICACY_SESSIONS = 20
MIN_CORRELATION_SESSIONS = 20
MAX_ALPHA_WEIGHT = 0.50


def _finite(value: object, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(f"{field} must be numeric") from exc
    if not math.isfinite(parsed):
        raise AlphaContractError(f"{field} must be finite")
    return parsed


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    left_centered = [value - left_mean for value in left]
    right_centered = [value - right_mean for value in right]
    numerator = sum(
        a * b for a, b in zip(left_centered, right_centered, strict=True)
    )
    denominator = math.sqrt(
        sum(value * value for value in left_centered)
        * sum(value * value for value in right_centered)
    )
    if denominator == 0.0:
        return None
    return numerator / denominator


def _verify_source_sha(value: object) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise AlphaContractError("AB001 source SHA-256 must be 64 lowercase hex")
    return text


def normalize_oos_alpha_source(
    *,
    alpha_id: str,
    alpha_version: str,
    source_artifact_sha256: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert one OOS prediction stream into canonical AB001 records."""

    alpha = alpha_id.strip()
    version = alpha_version.strip()
    if not alpha or not version:
        raise AlphaContractError("AB001 alpha_id and alpha_version are required")
    source_sha = _verify_source_sha(source_artifact_sha256)
    if not predictions:
        raise AlphaContractError(f"{alpha}: OOS prediction stream cannot be empty")

    staged = []
    seen: set[tuple[str, str, str, int]] = set()
    by_session_horizon: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    for row in predictions:
        role = str(row.get("prediction_role") or "")
        if role != "OOS" or row.get("oos_only") is not True:
            raise AlphaContractError(
                f"{alpha}: AB001 accepts OOS-only prediction records"
            )
        session = str(row.get("feature_session") or "").strip()
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        try:
            horizon = int(row.get("horizon_sessions"))
        except (TypeError, ValueError) as exc:
            raise AlphaContractError(f"{alpha}: horizon is required") from exc
        if not session or not symbol or not isin or horizon < 1:
            raise AlphaContractError(
                f"{alpha}: session, symbol, ISIN and positive horizon are required"
            )
        identity = (session, symbol, isin, horizon)
        if identity in seen:
            raise AlphaContractError(
                f"{alpha}: duplicate OOS record {identity}"
            )
        seen.add(identity)
        prediction = _finite(row.get("prediction"), f"{alpha}.prediction")

        target_raw = row.get("target_excess_return")
        if target_raw is None:
            target = None
            outcome_status = "NOT_MATURE"
        else:
            target = _finite(
                target_raw,
                f"{alpha}.target_excess_return",
            )
            outcome_status = "COMPLETE"

        key = f"{symbol}|{isin}"
        by_session_horizon[(session, horizon)][key] = prediction
        staged.append(
            {
                "alpha_id": alpha,
                "alpha_version": version,
                "source_artifact_sha256": source_sha,
                "feature_session": session,
                "symbol": symbol,
                "isin": isin,
                "horizon_sessions": horizon,
                "raw_prediction": prediction,
                "target_excess_return": target,
                "outcome_status": outcome_status,
                "prediction_role": "OOS",
                "live_capital_allowed": False,
            }
        )

    normalized: dict[tuple[str, int, str], float | None] = {}
    for (session, horizon), values in by_session_horizon.items():
        percentiles = cross_sectional_percentile(values)
        for identity, percentile in percentiles.items():
            normalized[(session, horizon, identity)] = (
                None
                if percentile is None
                else 2.0 * float(percentile) - 1.0
            )

    records = []
    for row in staged:
        identity = f"{row['symbol']}|{row['isin']}"
        score = normalized[
            (row["feature_session"], row["horizon_sessions"], identity)
        ]
        if score is None:
            raise AlphaContractError(
                f"{alpha}: normalized OOS score unexpectedly missing"
            )
        record = {
            **row,
            "normalized_score": score,
        }
        record["record_sha256"] = digest(record)
        records.append(record)
    return sorted(
        records,
        key=lambda row: (
            row["feature_session"],
            row["horizon_sessions"],
            row["symbol"],
            row["isin"],
        ),
    )


def build_alpha_library(
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a hash-bound canonical multi-alpha OOS library."""

    if not sources:
        raise AlphaContractError("AB001 requires at least one alpha source")
    records = []
    alpha_metadata = []
    seen_alpha_ids: set[str] = set()
    for source in sources:
        alpha_id = str(source.get("alpha_id") or "").strip()
        if alpha_id in seen_alpha_ids:
            raise AlphaContractError(f"duplicate AB001 alpha source: {alpha_id}")
        seen_alpha_ids.add(alpha_id)
        normalized = normalize_oos_alpha_source(
            alpha_id=alpha_id,
            alpha_version=str(source.get("alpha_version") or ""),
            source_artifact_sha256=str(
                source.get("source_artifact_sha256") or ""
            ),
            predictions=list(source.get("predictions") or []),
        )
        records.extend(normalized)
        alpha_metadata.append(
            {
                "alpha_id": alpha_id,
                "alpha_version": normalized[0]["alpha_version"],
                "source_artifact_sha256": normalized[0][
                    "source_artifact_sha256"
                ],
                "record_count": len(normalized),
                "horizons": sorted(
                    {int(row["horizon_sessions"]) for row in normalized}
                ),
            }
        )

    library: dict[str, Any] = {
        "schema_version": 1,
        "model_id": AB001_MODEL_ID,
        "alpha_count": len(alpha_metadata),
        "record_count": len(records),
        "alphas": sorted(alpha_metadata, key=lambda row: row["alpha_id"]),
        "records": sorted(
            records,
            key=lambda row: (
                row["alpha_id"],
                row["feature_session"],
                row["horizon_sessions"],
                row["symbol"],
                row["isin"],
            ),
        ),
        "live_capital_allowed": False,
    }
    library["library_sha256"] = digest(library)
    validate_alpha_library(library)
    return library


def validate_alpha_library(library: dict[str, Any]) -> None:
    stored = str(library.get("library_sha256") or "")
    unsigned = copy.deepcopy(library)
    unsigned.pop("library_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError("AB001 library hash mismatch")
    if library.get("model_id") != AB001_MODEL_ID:
        raise AlphaContractError("unexpected AB001 model ID")
    if library.get("live_capital_allowed") is not False:
        raise AlphaContractError("AB001 cannot allow live capital")
    records = library.get("records")
    if not isinstance(records, list):
        raise AlphaContractError("AB001 records must be a list")
    if library.get("record_count") != len(records):
        raise AlphaContractError("AB001 record count mismatch")
    seen: set[tuple[str, str, str, str, int]] = set()
    for row in records:
        if row.get("prediction_role") != "OOS":
            raise AlphaContractError("AB001 library contains non-OOS prediction")
        key = (
            str(row["alpha_id"]),
            str(row["feature_session"]),
            str(row["symbol"]),
            str(row["isin"]),
            int(row["horizon_sessions"]),
        )
        if key in seen:
            raise AlphaContractError(f"duplicate AB001 canonical record: {key}")
        seen.add(key)
        score = _finite(row.get("normalized_score"), "normalized_score")
        if not -1.0 - 1e-12 <= score <= 1.0 + 1e-12:
            raise AlphaContractError("AB001 normalized score outside [-1, 1]")
        expected_hash = digest(
            {key: value for key, value in row.items() if key != "record_sha256"}
        )
        if row.get("record_sha256") != expected_hash:
            raise AlphaContractError("AB001 record hash mismatch")


def _mature_records(
    library: dict[str, Any],
    *,
    alpha_id: str,
    horizon_sessions: int,
    before_session: str | None = None,
    sessions: set[str] | None = None,
) -> list[dict[str, Any]]:
    validate_alpha_library(library)
    rows = []
    for row in library["records"]:
        if (
            row["alpha_id"] == alpha_id
            and int(row["horizon_sessions"]) == horizon_sessions
            and row["outcome_status"] == "COMPLETE"
            and row["target_excess_return"] is not None
        ):
            session = str(row["feature_session"])
            if before_session is not None and session >= before_session:
                continue
            if sessions is not None and session not in sessions:
                continue
            rows.append(row)
    return rows


def _prediction_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    return evaluate_cross_sectional_predictions(
        [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "feature_session": row["feature_session"],
                "prediction": row["normalized_score"],
                "target_excess_return": row["target_excess_return"],
            }
            for row in records
        ]
    )


def standalone_alpha_reports(
    library: dict[str, Any],
    *,
    horizon_sessions: int,
) -> dict[str, Any]:
    validate_alpha_library(library)
    reports = {}
    for alpha in sorted({row["alpha_id"] for row in library["records"]}):
        rows = _mature_records(
            library,
            alpha_id=alpha,
            horizon_sessions=horizon_sessions,
        )
        if rows:
            reports[alpha] = _prediction_report(rows)
    return reports


def _session_score_maps(
    library: dict[str, Any],
    *,
    alpha_id: str,
    horizon_sessions: int,
    before_session: str | None = None,
) -> dict[str, dict[tuple[str, str], float]]:
    maps: dict[str, dict[tuple[str, str], float]] = defaultdict(dict)
    for row in library["records"]:
        if row["alpha_id"] != alpha_id:
            continue
        if int(row["horizon_sessions"]) != horizon_sessions:
            continue
        session = str(row["feature_session"])
        if before_session is not None and session >= before_session:
            continue
        maps[session][(row["symbol"], row["isin"])] = float(
            row["normalized_score"]
        )
    return dict(maps)


def pairwise_alpha_diagnostics(
    library: dict[str, Any],
    *,
    horizon_sessions: int,
) -> list[dict[str, Any]]:
    """Measure OOS prediction and realized-spread overlap for every alpha pair."""

    validate_alpha_library(library)
    alpha_ids = sorted({row["alpha_id"] for row in library["records"]})
    standalone = standalone_alpha_reports(
        library,
        horizon_sessions=horizon_sessions,
    )
    results = []
    for left_index, left in enumerate(alpha_ids):
        left_maps = _session_score_maps(
            library,
            alpha_id=left,
            horizon_sessions=horizon_sessions,
        )
        for right in alpha_ids[left_index + 1 :]:
            right_maps = _session_score_maps(
                library,
                alpha_id=right,
                horizon_sessions=horizon_sessions,
            )
            common_sessions = sorted(set(left_maps) & set(right_maps))
            correlations = []
            overlap_records = 0
            for session in common_sessions:
                common_ids = sorted(
                    set(left_maps[session]) & set(right_maps[session])
                )
                if len(common_ids) < 5:
                    continue
                correlation = _pearson(
                    [left_maps[session][identity] for identity in common_ids],
                    [right_maps[session][identity] for identity in common_ids],
                )
                if correlation is not None:
                    correlations.append(correlation)
                    overlap_records += len(common_ids)

            left_report = standalone.get(left)
            right_report = standalone.get(right)
            spread_correlation = None
            common_spread_sessions = 0
            if left_report and right_report:
                left_spreads = {
                    str(row["feature_session"]): float(
                        row["top_minus_bottom_spread"]
                    )
                    for row in left_report["session_metrics"]
                }
                right_spreads = {
                    str(row["feature_session"]): float(
                        row["top_minus_bottom_spread"]
                    )
                    for row in right_report["session_metrics"]
                }
                common_spreads = sorted(
                    set(left_spreads) & set(right_spreads)
                )
                common_spread_sessions = len(common_spreads)
                if len(common_spreads) >= 2:
                    spread_correlation = _pearson(
                        [left_spreads[session] for session in common_spreads],
                        [right_spreads[session] for session in common_spreads],
                    )

            results.append(
                {
                    "left_alpha_id": left,
                    "right_alpha_id": right,
                    "horizon_sessions": horizon_sessions,
                    "prediction_correlation_session_count": len(correlations),
                    "prediction_overlap_record_count": overlap_records,
                    "mean_daily_spearman_prediction_correlation": (
                        statistics.mean(correlations)
                        if correlations
                        else None
                    ),
                    "median_daily_spearman_prediction_correlation": (
                        statistics.median(correlations)
                        if correlations
                        else None
                    ),
                    "spread_correlation_session_count": common_spread_sessions,
                    "daily_top_minus_bottom_spread_correlation": (
                        spread_correlation
                    ),
                }
            )
    return results


def _equal_weight_blend_records(
    library: dict[str, Any],
    *,
    alpha_ids: list[str],
    horizon_sessions: int,
) -> list[dict[str, Any]]:
    if not alpha_ids:
        raise AlphaContractError("AB001 blend requires at least one alpha")
    ids = sorted(set(alpha_ids))
    if len(ids) != len(alpha_ids):
        raise AlphaContractError("AB001 blend alpha IDs must be unique")

    by_alpha_session: dict[
        str, dict[str, dict[tuple[str, str], dict[str, Any]]]
    ] = defaultdict(lambda: defaultdict(dict))
    for row in library["records"]:
        if row["alpha_id"] not in ids:
            continue
        if int(row["horizon_sessions"]) != horizon_sessions:
            continue
        if row["outcome_status"] != "COMPLETE":
            continue
        by_alpha_session[row["alpha_id"]][str(row["feature_session"])][
            (row["symbol"], row["isin"])
        ] = row

    session_sets = [
        set(by_alpha_session[alpha]) for alpha in ids
    ]
    common_sessions = sorted(set.intersection(*session_sets)) if session_sets else []
    blended = []
    for session in common_sessions:
        identity_sets = [
            set(by_alpha_session[alpha][session])
            for alpha in ids
        ]
        common_ids = sorted(set.intersection(*identity_sets))
        for identity in common_ids:
            rows = [by_alpha_session[alpha][session][identity] for alpha in ids]
            targets = {float(row["target_excess_return"]) for row in rows}
            if len(targets) != 1:
                raise AlphaContractError(
                    "AB001 aligned alpha records disagree on target"
                )
            blended.append(
                {
                    "symbol": identity[0],
                    "isin": identity[1],
                    "feature_session": session,
                    "prediction": statistics.mean(
                        float(row["normalized_score"]) for row in rows
                    ),
                    "target_excess_return": targets.pop(),
                }
            )
    return blended


def incremental_alpha_contribution(
    library: dict[str, Any],
    *,
    existing_alpha_ids: list[str],
    candidate_alpha_id: str,
    horizon_sessions: int,
    newey_west_lag: int | None = None,
) -> dict[str, Any]:
    validate_alpha_library(library)
    if candidate_alpha_id in existing_alpha_ids:
        raise AlphaContractError("candidate alpha is already in existing set")
    baseline_predictions = _equal_weight_blend_records(
        library,
        alpha_ids=existing_alpha_ids,
        horizon_sessions=horizon_sessions,
    )
    challenger_predictions = _equal_weight_blend_records(
        library,
        alpha_ids=[*existing_alpha_ids, candidate_alpha_id],
        horizon_sessions=horizon_sessions,
    )
    challenger_sessions = {
        str(row["feature_session"]) for row in challenger_predictions
    }
    baseline_common = [
        row
        for row in baseline_predictions
        if str(row["feature_session"]) in challenger_sessions
    ]
    baseline_report = evaluate_cross_sectional_predictions(baseline_common)
    challenger_report = evaluate_cross_sectional_predictions(
        challenger_predictions
    )
    lag = (
        max(0, horizon_sessions - 1)
        if newey_west_lag is None
        else int(newey_west_lag)
    )
    inference = paired_report_difference_inference(
        challenger_report,
        baseline_report,
        max_lag=lag,
    )
    return {
        "schema_version": 1,
        "existing_alpha_ids": list(existing_alpha_ids),
        "candidate_alpha_id": candidate_alpha_id,
        "horizon_sessions": horizon_sessions,
        "baseline": baseline_report,
        "challenger": challenger_report,
        "challenger_minus_baseline_inference": inference,
        "live_capital_allowed": False,
    }


def _daily_rank_ic(
    records: list[dict[str, Any]],
) -> dict[str, float]:
    report = _prediction_report(records)
    return {
        str(row["feature_session"]): float(row["rank_ic"])
        for row in report["session_metrics"]
        if row["rank_ic"] is not None
    }


def _trailing_pair_correlation(
    library: dict[str, Any],
    *,
    left: str,
    right: str,
    horizon_sessions: int,
    before_session: str,
    lookback_sessions: int,
) -> tuple[float | None, int]:
    left_maps = _session_score_maps(
        library,
        alpha_id=left,
        horizon_sessions=horizon_sessions,
        before_session=before_session,
    )
    right_maps = _session_score_maps(
        library,
        alpha_id=right,
        horizon_sessions=horizon_sessions,
        before_session=before_session,
    )
    sessions = sorted(set(left_maps) & set(right_maps))[-lookback_sessions:]
    correlations = []
    for session in sessions:
        common = sorted(set(left_maps[session]) & set(right_maps[session]))
        if len(common) < 5:
            continue
        value = _pearson(
            [left_maps[session][identity] for identity in common],
            [right_maps[session][identity] for identity in common],
        )
        if value is not None:
            correlations.append(value)
    if len(correlations) < MIN_CORRELATION_SESSIONS:
        return None, len(correlations)
    return statistics.mean(correlations), len(correlations)


def _cap_and_normalize_weights(
    raw_weights: dict[str, float],
    *,
    cap: float,
) -> dict[str, float]:
    if not raw_weights:
        raise AlphaContractError("AB001 cannot normalize empty weights")
    if cap <= 0.0 or cap > 1.0:
        raise AlphaContractError("AB001 weight cap must be in (0, 1]")
    if len(raw_weights) * cap < 1.0 - 1e-12:
        raise AlphaContractError(
            "AB001 alpha count cannot satisfy frozen single-alpha weight cap"
        )

    remaining = 1.0
    active = dict(raw_weights)
    output: dict[str, float] = {}
    while active:
        total = sum(active.values())
        if total <= 0.0:
            equal = remaining / len(active)
            for alpha in active:
                output[alpha] = equal
            break
        provisional = {
            alpha: remaining * value / total
            for alpha, value in active.items()
        }
        capped = [
            alpha
            for alpha, weight in provisional.items()
            if weight > cap + 1e-15
        ]
        if not capped:
            output.update(provisional)
            break
        for alpha in sorted(capped):
            output[alpha] = cap
            remaining -= cap
            active.pop(alpha)

    total = sum(output.values())
    if total <= 0.0:
        raise AlphaContractError("AB001 normalized weights sum to zero")
    normalized = {alpha: weight / total for alpha, weight in output.items()}
    if max(normalized.values()) > cap + 1e-10:
        raise AlphaContractError("AB001 normalized blend violates weight cap")
    return normalized


def _weights_for_session(
    library: dict[str, Any],
    *,
    alpha_ids: list[str],
    horizon_sessions: int,
    session: str,
    lookback_sessions: int,
) -> tuple[dict[str, float], dict[str, Any]]:
    efficacy = {}
    evidence_counts = {}
    for alpha in alpha_ids:
        rows = _mature_records(
            library,
            alpha_id=alpha,
            horizon_sessions=horizon_sessions,
            before_session=session,
        )
        ic_by_session = _daily_rank_ic(rows) if rows else {}
        trailing_sessions = sorted(ic_by_session)[-lookback_sessions:]
        evidence_counts[alpha] = len(trailing_sessions)
        if len(trailing_sessions) >= MIN_EFFICACY_SESSIONS:
            value = statistics.mean(
                ic_by_session[item] for item in trailing_sessions
            )
            efficacy[alpha] = max(0.0, value)
        else:
            efficacy[alpha] = 0.0

    positive = [alpha for alpha in alpha_ids if efficacy[alpha] > 0.0]
    if len(positive) < 2:
        equal = 1.0 / len(alpha_ids)
        return (
            {alpha: equal for alpha in alpha_ids},
            {
                "weighting_status": (
                    "INSUFFICIENT_TRAILING_EVIDENCE_EQUAL_WEIGHT_FALLBACK"
                ),
                "efficacy": efficacy,
                "efficacy_session_count": evidence_counts,
                "correlation_penalties": {alpha: 1.0 for alpha in alpha_ids},
                "pairwise_correlation_evidence": {},
            },
        )

    penalties = {}
    pair_evidence = {}
    for alpha in alpha_ids:
        correlations = []
        for other in alpha_ids:
            if other == alpha:
                continue
            correlation, count = _trailing_pair_correlation(
                library,
                left=alpha,
                right=other,
                horizon_sessions=horizon_sessions,
                before_session=session,
                lookback_sessions=lookback_sessions,
            )
            pair_evidence[f"{alpha}|{other}"] = {
                "correlation": correlation,
                "session_count": count,
            }
            if correlation is not None:
                correlations.append(abs(correlation))
        penalties[alpha] = (
            1.0
            if not correlations
            else 1.0 / (1.0 + statistics.mean(correlations))
        )

    raw = {
        alpha: efficacy[alpha] * penalties[alpha]
        for alpha in alpha_ids
    }
    if sum(raw.values()) <= 0.0:
        equal = 1.0 / len(alpha_ids)
        return (
            {alpha: equal for alpha in alpha_ids},
            {
                "weighting_status": (
                    "INSUFFICIENT_TRAILING_EVIDENCE_EQUAL_WEIGHT_FALLBACK"
                ),
                "efficacy": efficacy,
                "efficacy_session_count": evidence_counts,
                "correlation_penalties": penalties,
                "pairwise_correlation_evidence": pair_evidence,
            },
        )

    weights = _cap_and_normalize_weights(raw, cap=MAX_ALPHA_WEIGHT)
    return (
        weights,
        {
            "weighting_status": "TRAILING_EFFICACY_CORRELATION_SHRUNK",
            "efficacy": efficacy,
            "efficacy_session_count": evidence_counts,
            "correlation_penalties": penalties,
            "pairwise_correlation_evidence": pair_evidence,
        },
    )


def dynamic_blend(
    library: dict[str, Any],
    *,
    alpha_ids: list[str],
    horizon_sessions: int,
    lookback_sessions: int = TRAILING_EFFICACY_SESSIONS,
) -> dict[str, Any]:
    """Create OOS blended scores using only evidence strictly before each session."""

    validate_alpha_library(library)
    ids = sorted(set(alpha_ids))
    if len(ids) < 2 or len(ids) != len(alpha_ids):
        raise AlphaContractError(
            "AB001 dynamic blender requires at least two unique alphas"
        )

    by_alpha_session: dict[
        str, dict[str, dict[tuple[str, str], dict[str, Any]]]
    ] = defaultdict(lambda: defaultdict(dict))
    for row in library["records"]:
        if row["alpha_id"] in ids and int(row["horizon_sessions"]) == horizon_sessions:
            by_alpha_session[row["alpha_id"]][str(row["feature_session"])][
                (row["symbol"], row["isin"])
            ] = row

    common_sessions = sorted(
        set.intersection(
            *(set(by_alpha_session[alpha]) for alpha in ids)
        )
    )
    blended = []
    weights_by_session = []
    for session in common_sessions:
        weights, diagnostics = _weights_for_session(
            library,
            alpha_ids=ids,
            horizon_sessions=horizon_sessions,
            session=session,
            lookback_sessions=lookback_sessions,
        )
        identity_sets = [
            set(by_alpha_session[alpha][session])
            for alpha in ids
        ]
        common_ids = sorted(set.intersection(*identity_sets))
        for identity in common_ids:
            rows = [
                by_alpha_session[alpha][session][identity]
                for alpha in ids
            ]
            targets = {
                row["target_excess_return"]
                for row in rows
                if row["target_excess_return"] is not None
            }
            if len(targets) > 1:
                raise AlphaContractError(
                    "AB001 dynamic blend aligned targets disagree"
                )
            target = next(iter(targets)) if targets else None
            blended.append(
                {
                    "symbol": identity[0],
                    "isin": identity[1],
                    "feature_session": session,
                    "horizon_sessions": horizon_sessions,
                    "prediction": sum(
                        weights[alpha]
                        * float(by_alpha_session[alpha][session][identity][
                            "normalized_score"
                        ])
                        for alpha in ids
                    ),
                    "target_excess_return": target,
                    "prediction_role": "OOS",
                    "oos_only": True,
                    "live_capital_allowed": False,
                }
            )
        weights_by_session.append(
            {
                "feature_session": session,
                "weights": weights,
                **diagnostics,
                "common_identity_count": len(common_ids),
            }
        )

    mature = [
        row for row in blended if row["target_excess_return"] is not None
    ]
    report = (
        evaluate_cross_sectional_predictions(mature)
        if mature
        else None
    )
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "model_id": AB001_MODEL_ID,
        "library_sha256": library["library_sha256"],
        "alpha_ids": ids,
        "horizon_sessions": horizon_sessions,
        "lookback_sessions": lookback_sessions,
        "minimum_efficacy_sessions": MIN_EFFICACY_SESSIONS,
        "minimum_correlation_sessions": MIN_CORRELATION_SESSIONS,
        "maximum_single_alpha_weight": MAX_ALPHA_WEIGHT,
        "weights_by_session": weights_by_session,
        "prediction_count": len(blended),
        "predictions": blended,
        "mature_oos_report": report,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact
