import numpy as np
import pandas as pd
import pytest

from marketlab.h005 import H005Error, evaluate_h005_predictions, fit_h005


def _training_frame(rows: int = 160) -> pd.DataFrame:
    dates = pd.date_range("2025-10-01", periods=rows, freq="D")
    index = np.arange(rows)
    target = (index % 13 == 0) | (index % 29 == 0)
    signal = target.astype(float)
    return pd.DataFrame(
        {
            "decision_date": dates.astype(str),
            "explosive_20d_v1": target,
            "revenue_yoy_pct": 5 + signal * 45 + (index % 7),
            "operating_profit_yoy_pct": 2 + signal * 70 + (index % 11),
            "pat_yoy_pct": -5 + signal * 90 + (index % 9),
            "margin_change_pp": -1 + signal * 4 + (index % 3) * 0.2,
            "quarterly_pat_crore": 5 + (index % 30),
            "revenue_scale_log": 5 + (index % 20) / 20,
            "nonoperating_share_of_pbt": (index % 10) / 20,
            "prior_1d_return_pct": (index % 5) - 2,
            "prior_5d_return_pct": (index % 15) - 5,
            "prior_20d_return_pct": (index % 25) - 8,
            "distance_to_60d_high_pct": 20 - (index % 15),
            "prior_20d_volatility_pct": 2 + (index % 8) / 2,
            "median_20d_traded_value_log": 18 + (index % 5) / 10,
            "loss_to_profit": target & (index % 2 == 0),
            "profit_to_loss": False,
            "tiny_base": index % 31 == 0,
            "negative_pat": False,
            "quality_warning_nonoperating": index % 17 == 0,
            "reaction_1d_pct": signal * 4 + (index % 3) - 1,
            "reaction_volume_ratio_20d": 0.8 + signal * 2 + (index % 4) / 10,
            "reaction_traded_value_ratio_20d": 0.9 + signal * 1.7 + (index % 5) / 10,
            "reaction_range_pct": 2 + signal * 3 + (index % 4) / 5,
            "reaction_close_location": 0.4 + signal * 0.4,
            "reaction_nifty500_excess_pp": -1 + signal * 4 + (index % 3) / 4,
            "lead_sessions_to_25pct": np.where(target, 6, np.nan),
            "nifty500_excess_20d_pct": np.where(target, 15, -1),
        }
    )


def test_h005_b_fits_and_scores_deterministically() -> None:
    frame = _training_frame()
    model = fit_h005(frame, variant="H005-B")
    scores1 = model.predict_proba(frame)
    scores2 = model.predict_proba(frame)
    assert model.selected_c in {0.01, 0.1, 1.0, 10.0}
    assert len(scores1) == len(frame)
    assert np.allclose(scores1, scores2)
    evaluation = evaluate_h005_predictions(frame, scores1)
    assert evaluation.selected_count == 16
    assert evaluation.precision > evaluation.prevalence
    assert evaluation.prevalence_lift > 1


def test_h005_a_does_not_require_reaction_columns() -> None:
    frame = _training_frame().drop(
        columns=[
            "reaction_1d_pct",
            "reaction_volume_ratio_20d",
            "reaction_traded_value_ratio_20d",
            "reaction_range_pct",
            "reaction_close_location",
            "reaction_nifty500_excess_pp",
        ]
    )
    model = fit_h005(frame, variant="H005-A")
    assert model.variant == "H005-A"
    assert len(model.predict_proba(frame)) == len(frame)


def test_h005_drops_feature_over_40_percent_missing() -> None:
    frame = _training_frame()
    frame.loc[:80, "nonoperating_share_of_pbt"] = np.nan
    model = fit_h005(frame, variant="H005-B")
    assert "nonoperating_share_of_pbt" in model.dropped_high_missing_features
    assert "nonoperating_share_of_pbt" not in model.selected_features


def test_h005_rejects_one_class_training_data() -> None:
    frame = _training_frame()
    frame["explosive_20d_v1"] = False
    with pytest.raises(H005Error, match="both positive and negative"):
        fit_h005(frame, variant="H005-B")


def test_h005_rejects_unknown_variant() -> None:
    with pytest.raises(H005Error, match="H005-A or H005-B"):
        fit_h005(_training_frame(), variant="H005-C")
