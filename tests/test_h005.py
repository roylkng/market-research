"""Synthetic invariant tests. None of these scores are market evidence."""
import copy
import json

import numpy as np
import pandas as pd
import pytest

from marketlab.h005 import (
    H005_A_FEATURES,
    H005_B_EXTRA_FEATURES,
    H005_FLAG_FEATURES,
    H005Error,
    _chronological_folds,
    _select_candidate,
    _top_fraction_mask,
    evaluate_h005_predictions,
    fit_h005,
    predict_frozen_h005,
)


def _training_frame(rows: int = 160) -> pd.DataFrame:
    dates = pd.bdate_range("2025-10-01", periods=rows)
    index = np.arange(rows)
    target = (index % 13 == 0) | (index % 29 == 0)
    signal = target.astype(float)
    return pd.DataFrame({
        "event_id": [f"E{i:04d}" for i in index],
        "decision_date": dates.astype(str),
        # Synthetic business days, not an exchange calendar or sourced return window.
        "label_end_date": (dates + pd.offsets.BDay(20)).astype(str),
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
    })


@pytest.fixture(scope="module")
def fitted():
    return fit_h005(_training_frame())


def test_h005_b_fits_and_scores_deterministically(fitted):
    frame = _training_frame()
    a, b = fitted.predict_proba(frame), fitted.predict_proba(frame)
    assert fitted.selected_c in {0.01, 0.1, 1.0, 10.0}
    assert np.allclose(a, b)
    evaluation = evaluate_h005_predictions(frame, a)
    assert evaluation.selected_count == 16
    assert evaluation.precision > evaluation.prevalence
    assert not evaluation.live_capital_allowed
    assert evaluation.evidence_classification == "RETROSPECTIVE_RANKING_DIAGNOSTIC_ONLY"


def test_h005_a_does_not_require_reaction_columns():
    frame = _training_frame().drop(columns=list(H005_B_EXTRA_FEATURES))
    model = fit_h005(frame, variant=" H005-a ")
    assert model.variant == "H005-A"
    assert len(model.predict_proba(frame)) == len(frame)


def test_h005_drops_feature_over_40_percent_missing():
    frame = _training_frame()
    frame.loc[:80, "nonoperating_share_of_pbt"] = np.nan
    model = fit_h005(frame)
    assert "nonoperating_share_of_pbt" in model.dropped_high_missing_features
    assert "nonoperating_share_of_pbt" not in model.selected_features


def test_h005_retains_feature_at_exactly_40_percent_missing():
    frame = _training_frame()
    frame.loc[96:, "nonoperating_share_of_pbt"] = np.nan
    assert "nonoperating_share_of_pbt" in fit_h005(frame).selected_features


def test_h005_rejects_one_class_training_data():
    frame = _training_frame()
    frame["explosive_20d_v1"] = False
    with pytest.raises(H005Error, match="both positive and negative"):
        fit_h005(frame)


def test_h005_rejects_unknown_variant():
    with pytest.raises(H005Error, match="H005-A or H005-B"):
        fit_h005(_training_frame(), variant="H005-C")


@pytest.mark.parametrize("column", ["label_end_date", "event_id", "decision_date"])
def test_missing_identity_or_label_maturity_fails_closed(column):
    with pytest.raises(H005Error, match=column):
        fit_h005(_training_frame().drop(columns=column))


def test_grouped_folds_never_split_dates_or_use_unmatured_labels():
    frame = _training_frame()
    frame["decision_date"] = np.repeat(pd.bdate_range("2025-10-01", periods=80).astype(str), 2)
    frame["label_end_date"] = (
        pd.to_datetime(frame.decision_date) + pd.offsets.BDay(20)
    ).astype(str)
    for train, valid in _chronological_folds(frame):
        first = pd.to_datetime(frame.iloc[valid].decision_date).min()
        assert (pd.to_datetime(frame.iloc[train].label_end_date) < first).all()
        assert not set(frame.iloc[train].decision_date) & set(frame.iloc[valid].decision_date)
        for day in frame.iloc[valid].decision_date.unique():
            assert set(np.flatnonzero(frame.decision_date.eq(day))) <= set(valid)


def test_equal_label_end_at_validation_boundary_is_purged():
    frame = _training_frame()
    first = _chronological_folds(frame)[0][1][0]
    frame.loc[0, "label_end_date"] = frame.loc[first, "decision_date"]
    assert 0 not in _chronological_folds(frame)[0][0]


def test_late_outlier_does_not_change_earlier_fold_preprocessing(fitted):
    frame = _training_frame()
    frame.loc[159, "revenue_yoy_pct"] = 1e9
    changed = fit_h005(frame)
    assert fitted.summary.fold_audit[0] == changed.summary.fold_audit[0]
    for before, after in zip(fitted.summary.candidate_audit, changed.summary.candidate_audit):
        assert before["fold_average_precision"][0] == after["fold_average_precision"][0]
    assert changed.upper_bounds["revenue_yoy_pct"] >= fitted.upper_bounds["revenue_yoy_pct"]


def test_late_missingness_cannot_choose_earlier_fold_features(fitted):
    frame = _training_frame()
    frame.loc[80:, "nonoperating_share_of_pbt"] = np.nan
    model = fit_h005(frame)
    assert model.summary.fold_audit[0] == fitted.summary.fold_audit[0]
    assert "nonoperating_share_of_pbt" in model.summary.fold_audit[0]["selected_features"]
    assert "nonoperating_share_of_pbt" in model.dropped_high_missing_features


def test_binary_flags_are_never_winsorized(fitted):
    assert not set(H005_FLAG_FEATURES) & set(fitted.lower_bounds)
    assert not set(H005_FLAG_FEATURES) & set(fitted.upper_bounds)


def test_zero_positive_cv_blocks_are_retained():
    frame = _training_frame()
    frame.loc[96:127, "explosive_20d_v1"] = False
    model = fit_h005(frame)
    assert len(model.summary.fold_average_precision) == 4
    assert model.summary.fold_average_precision[2] == 0.0
    assert model.summary.fold_top_decile_recall[2] == 0.0


def test_ap_ties_use_frozen_point_005_tolerance_then_recall_then_c():
    candidates = [(0.501, 0.30, 1.0, (), ()), (0.497, 0.40, 10.0, (), ()),
                  (0.497, 0.40, 0.01, (), ()), (0.490, 0.90, 0.1, (), ())]
    assert _select_candidate(candidates)[2] == 0.01


def test_unseen_prediction_missingness_has_an_explicit_indicator(fitted):
    frame = _training_frame().iloc[:3].copy()
    frame.loc[0, "revenue_yoy_pct"] = np.nan
    payload = fitted.to_dict()
    assert len(payload["missing_indicator_features"]) == len(fitted.selected_features)
    assert len(payload["coefficients"]) == 2 * len(fitted.selected_features)
    assert np.isfinite(fitted.predict_proba(frame)).all()


def test_string_and_boolean_flags_score_identically(fitted):
    frame = _training_frame()
    expected = fitted.predict_proba(frame)
    for flag in H005_FLAG_FEATURES:
        frame[flag] = frame[flag].astype("string")
    assert np.allclose(expected, fitted.predict_proba(frame))


def test_json_export_reproduces_scores_and_is_tamper_evident(fitted):
    payload = json.loads(json.dumps(fitted.to_dict(), allow_nan=False))
    frame = _training_frame()
    frame.loc[0, "revenue_yoy_pct"] = np.nan
    assert np.allclose(fitted.predict_proba(frame), predict_frozen_h005(frame, payload), atol=1e-12)
    damaged = copy.deepcopy(payload)
    damaged["coefficients"][0] += 0.1
    with pytest.raises(H005Error, match="checksum"):
        predict_frozen_h005(frame, damaged)


def test_fit_is_row_order_invariant(fitted):
    frame = _training_frame()
    shuffled = fit_h005(frame.sample(frac=1, random_state=123))
    assert shuffled.summary.training_frame_sha256 == fitted.summary.training_frame_sha256
    assert np.allclose(shuffled.predict_proba(frame), fitted.predict_proba(frame))


def test_ties_are_broken_by_event_identity_not_csv_order():
    frame = _training_frame().iloc[:10]
    scores = np.full(10, 0.5)
    expected = evaluate_h005_predictions(frame, scores)
    actual = evaluate_h005_predictions(frame.iloc[::-1], scores)
    assert actual == expected
    assert expected.hits == 1


@pytest.mark.parametrize("fraction", [0, -0.1, 1.1, np.nan, np.inf, True])
def test_bad_top_fraction_rejected(fraction):
    with pytest.raises(H005Error, match="top_fraction"):
        _top_fraction_mask(np.array([0.1]), fraction)


@pytest.mark.parametrize("scores", [[np.nan], [np.inf], [-0.1], [1.1], [[0.5]]])
def test_bad_scores_rejected(scores):
    with pytest.raises(H005Error):
        evaluate_h005_predictions(_training_frame().iloc[:1], np.array(scores))


@pytest.mark.parametrize("target", [False, True])
def test_single_class_evaluation_does_not_crash(target):
    frame = _training_frame()
    frame["explosive_20d_v1"] = target
    result = evaluate_h005_predictions(frame, np.full(len(frame), 0.5))
    assert result.selected_count == 16
    if target:
        assert result.precision == 1 and result.recall == 0.1
    else:
        assert result.precision == 0 and result.recall is None
        assert result.prevalence_lift is None
    json.dumps(result.to_dict(), allow_nan=False)


def test_empty_evaluation_is_explicit_and_json_safe():
    result = evaluate_h005_predictions(_training_frame().iloc[:0], np.array([]))
    assert result.evidence_classification == "NO_OBSERVATIONS"
    assert result.recall is None and result.precision is None
    json.dumps(result.to_dict(), allow_nan=False)


def test_partial_forward_coverage_does_not_produce_a_median():
    frame = _training_frame().iloc[:10].copy()
    frame.loc[0, "nifty500_excess_20d_pct"] = np.nan
    result = evaluate_h005_predictions(frame, np.full(10, 0.5))
    assert result.median_nifty500_excess_20d_pct is None


@pytest.mark.parametrize("value", [np.inf, -np.inf, "not-a-number"])
def test_malformed_or_infinite_features_rejected(fitted, value):
    frame = _training_frame().iloc[:2].copy()
    frame["revenue_yoy_pct"] = frame["revenue_yoy_pct"].astype(object)
    frame.loc[0, "revenue_yoy_pct"] = value
    with pytest.raises(H005Error):
        fitted.predict_proba(frame)


def test_duplicate_event_identity_rejected():
    frame = _training_frame()
    frame.loc[1, "event_id"] = frame.loc[0, "event_id"]
    with pytest.raises(H005Error, match="event_id"):
        fit_h005(frame)


def test_label_end_before_decision_rejected():
    frame = _training_frame()
    frame.loc[0, "label_end_date"] = "2020-01-01"
    with pytest.raises(H005Error, match="cannot precede"):
        fit_h005(frame)


def test_insufficient_mature_training_labels_fail_closed():
    frame = _training_frame()
    frame["label_end_date"] = "2030-01-01"
    with pytest.raises(H005Error, match="fewer than two"):
        fit_h005(frame)


def test_no_continuous_feature_was_added_to_frozen_protocol(fitted):
    assert set(fitted.selected_features) <= set(H005_A_FEATURES + H005_B_EXTRA_FEATURES)
