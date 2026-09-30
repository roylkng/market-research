from __future__ import annotations

from marketlab.alpha_fundamental import FEATURE_NAMES
from marketlab.alpha_fundamental_trial import (
    _cluster_bootstrap,
    _empirical_percentile,
    _event_metrics,
    _transform_fundamentals,
    map_publication_to_decision_session,
)
from marketlab.alpha_model import ModelExample


def _example(
    *,
    symbol: str,
    session: str,
    fundamental_value: float,
    base_value: float | None = 0.5,
) -> ModelExample:
    features = {"base_x": base_value}
    for index, feature in enumerate(FEATURE_NAMES):
        features[feature] = fundamental_value + index
    return ModelExample(
        symbol=symbol,
        isin=f"INE{symbol:0>9}"[-12:],
        feature_session=session,
        entry_session=session,
        exit_session=session,
        horizon_sessions=20,
        features=features,
        target_excess_return=fundamental_value / 100.0,
    )


def test_t008_publication_maps_to_1830_decision_cutoff():
    sessions = ["2026-07-31", "2026-08-03"]
    assert (
        map_publication_to_decision_session(
            "2026-07-31T12:59:59+00:00",
            sessions,
        )
        == "2026-07-31"
    )
    assert (
        map_publication_to_decision_session(
            "2026-07-31T13:00:01+00:00",
            sessions,
        )
        == "2026-08-03"
    )


def test_t008_empirical_percentile_is_training_only_and_tie_aware():
    training = [1.0, 2.0, 2.0, 4.0]
    assert _empirical_percentile(0.0, training) == 0.0
    assert _empirical_percentile(2.0, training) == 0.5
    assert _empirical_percentile(5.0, training) == 1.0


def test_t008_fundamental_transform_uses_only_training_distribution():
    training = [
        _example(
            symbol=f"T{index}",
            session=f"2026-01-{index + 1:02d}",
            fundamental_value=float(index),
            base_value=None if index == 0 else 0.5,
        )
        for index in range(6)
    ]
    validation = [
        _example(
            symbol="V1",
            session="2026-03-01",
            fundamental_value=1000.0,
        ),
        _example(
            symbol="V2",
            session="2026-03-02",
            fundamental_value=-1000.0,
        ),
    ]
    transformed_train, transformed_validation, diagnostics = (
        _transform_fundamentals(
            training,
            validation,
            base_feature_names=["base_x"],
        )
    )
    assert transformed_train[0].features["base_x"] is None
    assert transformed_validation[0].features["revenue_yoy"] == 1.0
    assert transformed_validation[1].features["revenue_yoy"] == 0.0
    assert diagnostics["revenue_yoy"]["training_min"] == 0.0
    assert diagnostics["revenue_yoy"]["training_max"] == 5.0


def test_t008_event_metrics_use_quintiles():
    rows = [
        {
            "feature_session": "2026-04-01",
            "symbol": f"S{index:02d}",
            "isin": f"INE{index:09d}",
            "prediction": float(index),
            "target_excess_return": float(index) / 100.0,
        }
        for index in range(10)
    ]
    report = _event_metrics(rows)
    assert report["event_count"] == 10
    assert report["quintile_count"] == 2
    assert report["rank_ic"] == 1.0
    assert report["top_minus_bottom_quintile_spread"] > 0.0


def test_t008_week_cluster_bootstrap_detects_strong_increment(monkeypatch):
    monkeypatch.setattr(
        "marketlab.alpha_fundamental_trial.BOOTSTRAP_REPETITIONS",
        200,
    )
    monkeypatch.setattr(
        "marketlab.alpha_fundamental_trial.MIN_VALID_BOOTSTRAPS",
        180,
    )
    folds = []
    for fold_index in range(2):
        rows = []
        for week in range(5):
            for item in range(4):
                value = week * 4 + item
                rows.append(
                    {
                        "feature_session": (
                            f"2026-0{4 + fold_index}-"
                            f"{1 + week * 7 + item:02d}"
                        ),
                        "decision_week": f"W{fold_index}-{week}",
                        "symbol": f"S{fold_index}{value:02d}",
                        "isin": f"INE{fold_index}{value:08d}",
                        "target_excess_return": value / 100.0,
                        "base_prediction": -float(value),
                        "augmented_prediction": float(value),
                    }
                )
        folds.append(rows)

    report = _cluster_bootstrap(folds)
    assert report["valid_repetitions"] >= 180
    assert report["rank_ic_delta"]["ci95_low"] > 0.0
    assert report["quintile_spread_delta"]["ci95_low"] > 0.0
