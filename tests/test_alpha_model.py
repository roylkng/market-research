import math

import pytest

from marketlab.alpha_model import (
    ModelExample,
    evaluate_cross_sectional_predictions,
    fit_ridge,
    predict_ridge,
    purge_training_examples,
    ridge_model_from_record,
    score_ridge_values,
)


def _example(index, session, exit_session, target):
    return ModelExample(
        symbol=f"S{index:03d}",
        isin=f"INE{index:09d}",
        feature_session=session,
        entry_session=session,
        exit_session=exit_session,
        horizon_sessions=20,
        features={
            "signal": float(index),
            "noise": float(index % 3),
        },
        target_excess_return=target,
    )


def test_purge_training_examples_requires_label_to_mature_before_validation():
    rows = [
        _example(1, "2026-01-01", "2026-01-20", 0.01),
        _example(2, "2026-01-02", "2026-02-05", 0.02),
    ]
    retained = purge_training_examples(
        rows,
        validation_start_session="2026-02-01",
    )
    assert [row.symbol for row in retained] == ["S001"]


def test_ridge_learns_simple_monotonic_cross_section():
    train = [
        _example(index, "2026-01-01", "2026-01-20", index / 1000.0)
        for index in range(1, 50)
    ]
    model = fit_ridge(
        train,
        feature_names=["signal", "noise"],
        l2=0.1,
    )
    predictions = predict_ridge(model, train, prediction_role="DEVELOPMENT")
    assert predictions[-1]["prediction"] > predictions[0]["prediction"]
    assert model.training_example_count == 49
    assert len(model.model_sha256) == 64


def test_ridge_imputes_missing_using_training_only_statistics():
    train = [
        ModelExample(
            symbol=f"S{index}",
            isin=f"INE{index:09d}",
            feature_session="2026-01-01",
            entry_session="2026-01-02",
            exit_session="2026-01-20",
            horizon_sessions=20,
            features={"signal": None if index == 1 else float(index)},
            target_excess_return=float(index) / 100.0,
        )
        for index in range(1, 10)
    ]
    model = fit_ridge(train, feature_names=["signal"])
    predictions = predict_ridge(model, train, prediction_role="DEVELOPMENT")
    assert all(math.isfinite(row["prediction"]) for row in predictions)


def test_cross_sectional_evaluator_reports_positive_rank_ic_and_spread():
    predictions = []
    for session_index in range(3):
        session = f"2026-01-{session_index + 1:02d}"
        for index in range(20):
            predictions.append(
                {
                    "symbol": f"S{index:03d}",
                    "isin": f"INE{index:09d}",
                    "feature_session": session,
                    "prediction": float(index),
                    "target_excess_return": float(index) / 1000.0,
                }
            )
    report = evaluate_cross_sectional_predictions(predictions)
    assert report["session_count"] == 3
    assert report["mean_rank_ic"] == pytest.approx(1.0)
    assert report["mean_top_minus_bottom_spread"] > 0
    assert report["average_top_decile_selection_churn"] == pytest.approx(0.0)



def test_label_free_ridge_scoring_matches_development_prediction():
    train = [
        _example(index, "2026-01-01", "2026-01-20", index / 1000.0)
        for index in range(1, 20)
    ]
    model = fit_ridge(train, feature_names=["signal", "noise"], l2=0.5)
    record = {
        "model_id": model.model_id,
        "feature_names": list(model.feature_names),
        "feature_medians": list(model.feature_medians),
        "feature_means": list(model.feature_means),
        "feature_scales": list(model.feature_scales),
        "coefficients": list(model.coefficients),
        "intercept": model.intercept,
        "l2": model.l2,
        "training_example_count": model.training_example_count,
        "training_last_exit_session": model.training_last_exit_session,
        "model_sha256": model.model_sha256,
    }
    loaded = ridge_model_from_record(record)
    scored = score_ridge_values(
        loaded,
        [row.features for row in train],
    )
    development = predict_ridge(
        model,
        train,
        prediction_role="DEVELOPMENT",
    )
    assert scored == pytest.approx(
        [row["prediction"] for row in development]
    )


def test_serialized_ridge_hash_fails_closed():
    train = [
        _example(index, "2026-01-01", "2026-01-20", index / 1000.0)
        for index in range(1, 10)
    ]
    model = fit_ridge(train, feature_names=["signal", "noise"])
    record = {
        "model_id": model.model_id,
        "feature_names": list(model.feature_names),
        "feature_medians": list(model.feature_medians),
        "feature_means": list(model.feature_means),
        "feature_scales": list(model.feature_scales),
        "coefficients": list(model.coefficients),
        "intercept": model.intercept + 1.0,
        "l2": model.l2,
        "training_example_count": model.training_example_count,
        "training_last_exit_session": model.training_last_exit_session,
        "model_sha256": model.model_sha256,
    }
    with pytest.raises(ValueError, match="hash mismatch"):
        ridge_model_from_record(record)
