from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np
from scipy import stats

from marketlab.alpha import AlphaContractError
from marketlab.alpha_model import (
    ModelExample,
    evaluate_cross_sectional_predictions,
    fit_ridge,
    predict_ridge,
    purge_training_examples,
)


def feature_predictions(
    examples: list[ModelExample],
    *,
    feature_name: str,
    direction: int,
    model_id: str,
    prediction_role: str,
) -> list[dict[str, Any]]:
    if direction not in {-1, 1}:
        raise AlphaContractError("feature direction must be -1 or 1")
    if prediction_role not in {"DEVELOPMENT", "OOS"}:
        raise AlphaContractError("prediction_role must be DEVELOPMENT or OOS")
    rows = []
    for example in examples:
        value = example.features.get(feature_name)
        if value is None:
            continue
        rows.append(
            {
                "model_id": model_id,
                "symbol": example.symbol,
                "isin": example.isin,
                "feature_session": example.feature_session,
                "entry_session": example.entry_session,
                "exit_session": example.exit_session,
                "horizon_sessions": example.horizon_sessions,
                "prediction": direction * float(value),
                "target_excess_return": example.target_excess_return,
                "prediction_role": prediction_role,
                "oos_only": prediction_role == "OOS",
                "live_capital_allowed": False,
            }
        )
    return rows


def learn_feature_direction(
    training: list[ModelExample],
    *,
    feature_name: str,
) -> tuple[int, dict[str, Any]]:
    positive = feature_predictions(
        training,
        feature_name=feature_name,
        direction=1,
        model_id=f"TRAIN-SIGN-{feature_name}",
        prediction_role="DEVELOPMENT",
    )
    report = evaluate_cross_sectional_predictions(positive)
    mean_ic = report.get("mean_rank_ic")
    if mean_ic is None:
        raise AlphaContractError(
            f"{feature_name}: cannot learn direction without training rank IC"
        )
    direction = 1 if float(mean_ic) >= 0.0 else -1
    return direction, report


def _fold_examples(
    examples: list[ModelExample],
    *,
    start: str,
    end: str,
) -> tuple[list[ModelExample], list[ModelExample]]:
    train = purge_training_examples(
        examples,
        validation_start_session=start,
    )
    validation = [
        row for row in examples if start <= row.feature_session <= end
    ]
    if len(train) < 100:
        raise AlphaContractError("fewer than 100 purged training examples")
    if not validation:
        raise AlphaContractError("validation fold is empty")
    return train, validation


def signed_single_feature_walkforward(
    examples: list[ModelExample],
    *,
    folds: list[dict[str, str]],
    feature_names: list[str],
) -> dict[str, Any]:
    if not feature_names:
        raise AlphaContractError("single-feature diagnostics require features")

    oos_by_feature: dict[str, list[dict[str, Any]]] = {
        feature: [] for feature in feature_names
    }
    selected_predictions: list[dict[str, Any]] = []
    fold_reports = []

    prior_end: str | None = None
    for fold_index, fold in enumerate(folds, start=1):
        start = str(fold.get("start") or "")
        end = str(fold.get("end") or "")
        if not start or not end or start > end:
            raise AlphaContractError("invalid diagnostic fold")
        if prior_end is not None and start <= prior_end:
            raise AlphaContractError("diagnostic folds must be ordered and non-overlapping")
        prior_end = end

        train, validation = _fold_examples(examples, start=start, end=end)
        learned = []
        for feature in feature_names:
            direction, train_report = learn_feature_direction(
                train,
                feature_name=feature,
            )
            train_ic = float(train_report["mean_rank_ic"])
            oos = feature_predictions(
                validation,
                feature_name=feature,
                direction=direction,
                model_id=f"AE001-SIGNED-{feature}-F{fold_index:02d}",
                prediction_role="OOS",
            )
            oos_by_feature[feature].extend(oos)
            learned.append(
                {
                    "feature": feature,
                    "direction": direction,
                    "training_mean_rank_ic_raw_direction": train_ic,
                    "training_signed_rank_ic": abs(train_ic),
                    "oos": evaluate_cross_sectional_predictions(oos),
                }
            )

        learned.sort(
            key=lambda row: (
                -float(row["training_signed_rank_ic"]),
                str(row["feature"]),
            )
        )
        selected = learned[0]
        selected_oos = feature_predictions(
            validation,
            feature_name=str(selected["feature"]),
            direction=int(selected["direction"]),
            model_id=f"AE001-BEST-SINGLE-TRAIN-SELECTED-F{fold_index:02d}",
            prediction_role="OOS",
        )
        selected_predictions.extend(selected_oos)
        fold_reports.append(
            {
                "fold": fold_index,
                "start": start,
                "end": end,
                "training_example_count": len(train),
                "validation_example_count": len(validation),
                "selected_feature": selected["feature"],
                "selected_direction": selected["direction"],
                "selected_training_signed_rank_ic": selected[
                    "training_signed_rank_ic"
                ],
                "features": learned,
            }
        )

    per_feature = {
        feature: evaluate_cross_sectional_predictions(rows)
        for feature, rows in sorted(oos_by_feature.items())
    }
    return {
        "schema_version": 1,
        "selection_rule": (
            "SIGN_EACH_FEATURE_FROM_PURGED_TRAINING_MEAN_RANK_IC; "
            "BEST_SINGLE_FEATURE_PER_FOLD_SELECTED_BY_TRAINING_SIGNED_RANK_IC"
        ),
        "folds": fold_reports,
        "per_feature_oos": per_feature,
        "best_single_feature_train_selected_oos": (
            evaluate_cross_sectional_predictions(selected_predictions)
        ),
        "live_capital_allowed": False,
    }


def leave_one_feature_out_ridge_walkforward(
    examples: list[ModelExample],
    *,
    folds: list[dict[str, str]],
    feature_names: list[str],
    l2: float,
) -> dict[str, Any]:
    if len(feature_names) < 2:
        raise AlphaContractError("ridge ablation requires at least two features")

    predictions: dict[str, list[dict[str, Any]]] = {
        feature: [] for feature in feature_names
    }
    fold_reports = []

    prior_end: str | None = None
    for fold_index, fold in enumerate(folds, start=1):
        start = str(fold.get("start") or "")
        end = str(fold.get("end") or "")
        if not start or not end or start > end:
            raise AlphaContractError("invalid ablation fold")
        if prior_end is not None and start <= prior_end:
            raise AlphaContractError("ablation folds must be ordered and non-overlapping")
        prior_end = end
        train, validation = _fold_examples(examples, start=start, end=end)

        fold_rows = []
        for excluded in feature_names:
            selected = [feature for feature in feature_names if feature != excluded]
            model = fit_ridge(
                train,
                feature_names=selected,
                l2=l2,
                model_id=f"AE001-RIDGE-LOO-{excluded}-F{fold_index:02d}",
            )
            oos = predict_ridge(
                model,
                validation,
                prediction_role="OOS",
            )
            predictions[excluded].extend(oos)
            fold_rows.append(
                {
                    "excluded_feature": excluded,
                    "model_sha256": model.model_sha256,
                    "oos": evaluate_cross_sectional_predictions(oos),
                }
            )
        fold_reports.append(
            {
                "fold": fold_index,
                "start": start,
                "end": end,
                "models": fold_rows,
            }
        )

    return {
        "schema_version": 1,
        "l2": l2,
        "folds": fold_reports,
        "exclude_one_feature_oos": {
            feature: evaluate_cross_sectional_predictions(rows)
            for feature, rows in sorted(predictions.items())
        },
        "live_capital_allowed": False,
    }


def newey_west_mean_inference(
    values: list[float],
    *,
    max_lag: int = 5,
) -> dict[str, float | int | None]:
    clean = np.asarray(
        [float(value) for value in values if math.isfinite(float(value))],
        dtype=float,
    )
    n = int(clean.size)
    if n < 3:
        return {
            "count": n,
            "mean": float(clean.mean()) if n else None,
            "newey_west_lag": max_lag,
            "standard_error": None,
            "t_stat": None,
            "p_value_two_sided": None,
            "ci95_low": None,
            "ci95_high": None,
        }
    if max_lag < 0:
        raise AlphaContractError("Newey-West lag cannot be negative")
    lag = min(max_lag, n - 1)
    mean = float(clean.mean())
    centered = clean - mean
    gamma0 = float(centered @ centered) / n
    long_run_variance = gamma0
    for offset in range(1, lag + 1):
        gamma = float(centered[offset:] @ centered[:-offset]) / n
        weight = 1.0 - offset / (lag + 1.0)
        long_run_variance += 2.0 * weight * gamma
    long_run_variance = max(long_run_variance, 0.0)
    standard_error = math.sqrt(long_run_variance / n)
    if standard_error == 0.0:
        t_stat = None
        p_value = None
        low = high = mean
    else:
        t_stat = mean / standard_error
        p_value = float(2.0 * stats.t.sf(abs(t_stat), df=n - 1))
        critical = float(stats.t.ppf(0.975, df=n - 1))
        low = mean - critical * standard_error
        high = mean + critical * standard_error
    return {
        "count": n,
        "mean": mean,
        "newey_west_lag": lag,
        "standard_error": standard_error,
        "t_stat": t_stat,
        "p_value_two_sided": p_value,
        "ci95_low": low,
        "ci95_high": high,
    }


def report_time_series_inference(
    report: dict[str, Any],
    *,
    max_lag: int = 5,
) -> dict[str, Any]:
    rows = report.get("session_metrics")
    if not isinstance(rows, list):
        raise AlphaContractError("prediction report lacks session_metrics")

    fields = {
        "rank_ic": "rank_ic",
        "top_decile_excess": "top_decile_mean_excess",
        "top_minus_bottom_spread": "top_minus_bottom_spread",
    }
    result = {}
    for name, field in fields.items():
        values = [
            float(row[field])
            for row in rows
            if row.get(field) is not None
        ]
        result[name] = newey_west_mean_inference(
            values,
            max_lag=max_lag,
        )
    return {
        "schema_version": 1,
        "method": "NEWEY_WEST_BARTLETT_MEAN_INFERENCE_V1",
        "metrics": result,
    }


def summarize_ablation_delta(
    full_ridge_report: dict[str, Any],
    ablation_report: dict[str, Any],
) -> list[dict[str, Any]]:
    full_ic = full_ridge_report.get("mean_rank_ic")
    full_spread = full_ridge_report.get("mean_top_minus_bottom_spread")
    if full_ic is None or full_spread is None:
        raise AlphaContractError("full ridge report is incomplete")
    rows = []
    for feature, report in ablation_report["exclude_one_feature_oos"].items():
        ic = report.get("mean_rank_ic")
        spread = report.get("mean_top_minus_bottom_spread")
        rows.append(
            {
                "excluded_feature": feature,
                "ablation_mean_rank_ic": ic,
                "delta_full_minus_ablation_rank_ic": (
                    None if ic is None else float(full_ic) - float(ic)
                ),
                "ablation_top_minus_bottom_spread": spread,
                "delta_full_minus_ablation_spread": (
                    None
                    if spread is None
                    else float(full_spread) - float(spread)
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -float(row["delta_full_minus_ablation_rank_ic"] or 0.0),
            row["excluded_feature"],
        ),
    )
