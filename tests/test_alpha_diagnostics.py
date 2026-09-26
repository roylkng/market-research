import pytest

from marketlab.alpha_diagnostics import (
    leave_one_feature_out_ridge_walkforward,
    newey_west_mean_inference,
    report_time_series_inference,
    signed_single_feature_walkforward,
)
from marketlab.alpha_model import ModelExample


def _examples():
    rows = []
    for day in range(1, 13):
        feature_session = f"2026-01-{day:02d}"
        exit_session = f"2026-01-{day + 1:02d}"
        for index in range(20):
            signal = index / 19.0
            rows.append(
                ModelExample(
                    symbol=f"S{index:02d}",
                    isin=f"INE{index:09d}",
                    feature_session=feature_session,
                    entry_session=exit_session,
                    exit_session=exit_session,
                    horizon_sessions=1,
                    features={
                        "good": signal,
                        "inverse": signal,
                        "noise": float((index * 7 + day) % 20) / 19.0,
                    },
                    target_excess_return=(signal - 0.5) * 0.02,
                )
            )
    return rows


def test_signed_feature_direction_uses_training_only_and_can_reverse():
    rows = _examples()
    # Make the inverse feature truly inverse without changing the fixture structure.
    rows = [
        ModelExample(
            **{
                **row.__dict__,
                "features": {
                    **row.features,
                    "inverse": 1.0 - float(row.features["inverse"]),
                },
            }
        )
        for row in rows
    ]
    report = signed_single_feature_walkforward(
        rows,
        folds=[{"start": "2026-01-07", "end": "2026-01-09"}],
        feature_names=["good", "inverse", "noise"],
    )
    fold = report["folds"][0]
    directions = {
        row["feature"]: row["direction"]
        for row in fold["features"]
    }
    assert directions["good"] == 1
    assert directions["inverse"] == -1
    assert (
        report["best_single_feature_train_selected_oos"]["mean_rank_ic"]
        == pytest.approx(1.0)
    )


def test_leave_one_feature_out_ridge_runs_only_on_oos_fold():
    rows = _examples()
    report = leave_one_feature_out_ridge_walkforward(
        rows,
        folds=[{"start": "2026-01-07", "end": "2026-01-09"}],
        feature_names=["good", "inverse", "noise"],
        l2=1.0,
    )
    assert set(report["exclude_one_feature_oos"]) == {
        "good",
        "inverse",
        "noise",
    }
    assert all(
        value["session_count"] == 3
        for value in report["exclude_one_feature_oos"].values()
    )


def test_newey_west_inference_reports_positive_mean_signal():
    result = newey_west_mean_inference(
        [0.02, 0.01, 0.03, 0.02, 0.01, 0.04, 0.02],
        max_lag=2,
    )
    assert result["count"] == 7
    assert result["mean"] > 0
    assert result["standard_error"] > 0
    assert result["ci95_high"] > result["ci95_low"]


def test_report_time_series_inference_reads_session_metrics():
    report = {
        "session_metrics": [
            {
                "rank_ic": 0.1,
                "top_decile_mean_excess": 0.002,
                "top_minus_bottom_spread": 0.004,
            },
            {
                "rank_ic": 0.2,
                "top_decile_mean_excess": 0.001,
                "top_minus_bottom_spread": 0.003,
            },
            {
                "rank_ic": 0.15,
                "top_decile_mean_excess": 0.003,
                "top_minus_bottom_spread": 0.005,
            },
        ]
    }
    inference = report_time_series_inference(report, max_lag=1)
    assert set(inference["metrics"]) == {
        "rank_ic",
        "top_decile_excess",
        "top_minus_bottom_spread",
    }
