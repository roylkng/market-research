from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError, cross_sectional_percentile, digest


@dataclass(frozen=True)
class ModelExample:
    symbol: str
    isin: str
    feature_session: str
    entry_session: str
    exit_session: str
    horizon_sessions: int
    features: dict[str, float | None]
    target_excess_return: float


@dataclass(frozen=True)
class RidgeModel:
    model_id: str
    feature_names: tuple[str, ...]
    feature_medians: tuple[float, ...]
    feature_means: tuple[float, ...]
    feature_scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    l2: float
    training_example_count: int
    training_last_exit_session: str
    model_sha256: str


def purge_training_examples(
    examples: list[ModelExample],
    *,
    validation_start_session: str,
) -> list[ModelExample]:
    """Keep only examples whose full label horizon matured before validation starts."""

    return sorted(
        [
            row
            for row in examples
            if row.exit_session < validation_start_session
            and row.feature_session < validation_start_session
        ],
        key=lambda row: (row.feature_session, row.symbol, row.isin),
    )


def _matrix(
    examples: list[ModelExample],
    feature_names: tuple[str, ...],
    *,
    medians: np.ndarray | None = None,
    means: np.ndarray | None = None,
    scales: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not examples:
        raise AlphaContractError("model examples cannot be empty")
    raw = np.empty((len(examples), len(feature_names)), dtype=float)
    for row_index, row in enumerate(examples):
        if not math.isfinite(row.target_excess_return):
            raise AlphaContractError("target excess return must be finite")
        unknown = set(row.features) - set(feature_names)
        if unknown:
            raise AlphaContractError(f"unexpected model features: {sorted(unknown)}")
        for col_index, name in enumerate(feature_names):
            value = row.features.get(name)
            raw[row_index, col_index] = np.nan if value is None else float(value)

    if medians is None:
        with np.errstate(all="ignore"):
            medians = np.nanmedian(raw, axis=0)
        if np.isnan(medians).any():
            missing = [
                feature_names[index]
                for index, value in enumerate(medians)
                if np.isnan(value)
            ]
            raise AlphaContractError(
                f"training features are entirely missing: {missing}"
            )
    filled = np.where(np.isnan(raw), medians, raw)

    if means is None:
        means = filled.mean(axis=0)
    if scales is None:
        scales = filled.std(axis=0)
        scales = np.where(scales == 0.0, 1.0, scales)
    normalized = (filled - means) / scales
    targets = np.asarray([row.target_excess_return for row in examples], dtype=float)
    return normalized, targets, medians, scales


def fit_ridge(
    examples: list[ModelExample],
    *,
    feature_names: list[str],
    l2: float = 1.0,
    model_id: str = "AE001-RIDGE-v1",
) -> RidgeModel:
    if l2 < 0 or not math.isfinite(l2):
        raise AlphaContractError("ridge l2 must be finite and non-negative")
    names = tuple(feature_names)
    if not names or len(names) != len(set(names)):
        raise AlphaContractError("feature_names must be non-empty and unique")

    matrix, targets, medians, scales = _matrix(examples, names)
    # _matrix already centered using the training means. Recompute them from filled inputs
    # so the transform can be serialized and reused exactly for OOS inference.
    raw = np.empty((len(examples), len(names)), dtype=float)
    for row_index, row in enumerate(examples):
        for col_index, name in enumerate(names):
            value = row.features.get(name)
            raw[row_index, col_index] = np.nan if value is None else float(value)
    filled = np.where(np.isnan(raw), medians, raw)
    means = filled.mean(axis=0)
    matrix = (filled - means) / scales

    target_mean = float(targets.mean())
    centered_target = targets - target_mean
    penalty = np.eye(len(names), dtype=float) * l2
    gram = matrix.T @ matrix + penalty
    rhs = matrix.T @ centered_target
    try:
        coefficients = np.linalg.solve(gram, rhs)
    except np.linalg.LinAlgError as exc:
        raise AlphaContractError("ridge system is singular") from exc

    payload = {
        "model_id": model_id,
        "feature_names": list(names),
        "feature_medians": medians.tolist(),
        "feature_means": means.tolist(),
        "feature_scales": scales.tolist(),
        "coefficients": coefficients.tolist(),
        "intercept": target_mean,
        "l2": l2,
        "training_example_count": len(examples),
        "training_last_exit_session": max(row.exit_session for row in examples),
    }
    return RidgeModel(
        model_id=model_id,
        feature_names=names,
        feature_medians=tuple(float(value) for value in medians),
        feature_means=tuple(float(value) for value in means),
        feature_scales=tuple(float(value) for value in scales),
        coefficients=tuple(float(value) for value in coefficients),
        intercept=target_mean,
        l2=l2,
        training_example_count=len(examples),
        training_last_exit_session=payload["training_last_exit_session"],
        model_sha256=digest(payload),
    )


def predict_ridge(
    model: RidgeModel,
    examples: list[ModelExample],
    *,
    prediction_role: str,
) -> list[dict[str, Any]]:
    if prediction_role not in {"DEVELOPMENT", "OOS"}:
        raise AlphaContractError("prediction_role must be DEVELOPMENT or OOS")
    if not examples:
        return []
    medians = np.asarray(model.feature_medians, dtype=float)
    means = np.asarray(model.feature_means, dtype=float)
    scales = np.asarray(model.feature_scales, dtype=float)
    coefficients = np.asarray(model.coefficients, dtype=float)

    raw = np.empty((len(examples), len(model.feature_names)), dtype=float)
    for row_index, row in enumerate(examples):
        for col_index, name in enumerate(model.feature_names):
            value = row.features.get(name)
            raw[row_index, col_index] = np.nan if value is None else float(value)
    filled = np.where(np.isnan(raw), medians, raw)
    normalized = (filled - means) / scales
    predictions = model.intercept + normalized @ coefficients

    return [
        {
            "model_id": model.model_id,
            "model_sha256": model.model_sha256,
            "symbol": row.symbol,
            "isin": row.isin,
            "feature_session": row.feature_session,
            "entry_session": row.entry_session,
            "exit_session": row.exit_session,
            "horizon_sessions": row.horizon_sessions,
            "prediction": float(predictions[index]),
            "target_excess_return": row.target_excess_return,
            "prediction_role": prediction_role,
            "oos_only": prediction_role == "OOS",
            "live_capital_allowed": False,
        }
        for index, row in enumerate(examples)
    ]


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    left_centered = [value - left_mean for value in left]
    right_centered = [value - right_mean for value in right]
    numerator = sum(a * b for a, b in zip(left_centered, right_centered, strict=True))
    left_scale = math.sqrt(sum(value * value for value in left_centered))
    right_scale = math.sqrt(sum(value * value for value in right_centered))
    if left_scale == 0 or right_scale == 0:
        return None
    return numerator / (left_scale * right_scale)


def evaluate_cross_sectional_predictions(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    by_session: dict[str, list[dict[str, Any]]] = {}
    for row in predictions:
        by_session.setdefault(str(row["feature_session"]), []).append(row)

    session_metrics = []
    prior_top: set[str] | None = None
    selection_churn_values = []
    for session in sorted(by_session):
        rows = by_session[session]
        if len(rows) < 5:
            continue
        pred_map = {
            f"{row['symbol']}|{row['isin']}": float(row["prediction"])
            for row in rows
        }
        target_map = {
            f"{row['symbol']}|{row['isin']}": float(row["target_excess_return"])
            for row in rows
        }
        pred_rank = cross_sectional_percentile(pred_map)
        target_rank = cross_sectional_percentile(target_map)
        keys = sorted(pred_map)
        ic = _pearson(
            [float(pred_rank[key]) for key in keys if pred_rank[key] is not None],
            [float(target_rank[key]) for key in keys if target_rank[key] is not None],
        )

        ordered = sorted(
            rows,
            key=lambda row: (
                -float(row["prediction"]),
                str(row["symbol"]),
                str(row["isin"]),
            ),
        )
        bucket = max(1, math.ceil(len(ordered) * 0.10))
        top = ordered[:bucket]
        bottom = ordered[-bucket:]
        top_mean = statistics.mean(float(row["target_excess_return"]) for row in top)
        bottom_mean = statistics.mean(float(row["target_excess_return"]) for row in bottom)
        top_ids = {f"{row['symbol']}|{row['isin']}" for row in top}
        if prior_top is not None:
            denominator = max(len(prior_top), len(top_ids), 1)
            selection_churn_values.append(1.0 - len(prior_top & top_ids) / denominator)
        prior_top = top_ids

        session_metrics.append(
            {
                "feature_session": session,
                "observation_count": len(rows),
                "rank_ic": ic,
                "top_decile_mean_excess": top_mean,
                "bottom_decile_mean_excess": bottom_mean,
                "top_minus_bottom_spread": top_mean - bottom_mean,
            }
        )

    rank_ics = [
        float(row["rank_ic"])
        for row in session_metrics
        if row["rank_ic"] is not None
    ]
    spreads = [float(row["top_minus_bottom_spread"]) for row in session_metrics]
    top_returns = [float(row["top_decile_mean_excess"]) for row in session_metrics]
    return {
        "schema_version": 1,
        "session_count": len(session_metrics),
        "prediction_count": len(predictions),
        "mean_rank_ic": statistics.mean(rank_ics) if rank_ics else None,
        "median_rank_ic": statistics.median(rank_ics) if rank_ics else None,
        "mean_top_decile_excess": statistics.mean(top_returns) if top_returns else None,
        "mean_top_minus_bottom_spread": statistics.mean(spreads) if spreads else None,
        "average_top_decile_selection_churn": (
            statistics.mean(selection_churn_values)
            if selection_churn_values
            else None
        ),
        "session_metrics": session_metrics,
        "live_capital_allowed": False,
    }
