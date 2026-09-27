import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_delivery_trial import run_delivery_incremental_trial
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    append_trial_event,
    new_trial_ledger,
)


def _trial_ledger():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T003",
        recorded_at_utc="2026-09-27T08:10:00+00:00",
        payload={"status": "FROZEN_BEFORE_DELIVERY_OUTCOME_RUN"},
    )
    return append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T003",
        recorded_at_utc="2026-09-27T08:20:00+00:00",
        payload={
            "protocol_id": "AE001-T003-P1",
            "ridge_l2": 1.0,
            "feature_count_base": 18,
            "feature_count_delivery": 9,
            "feature_count_augmented": 27,
            "folds": {
                "1": [["2026-04-01", "2026-06-30"]],
                "5": [["2026-04-01", "2026-06-30"]],
                "20": [["2026-04-01", "2026-06-30"]],
            },
        },
    )


def _metric(mean_ic):
    return {
        "schema_version": 1,
        "session_count": 3,
        "prediction_count": 30,
        "mean_rank_ic": mean_ic,
        "median_rank_ic": mean_ic,
        "mean_top_decile_excess": mean_ic / 10,
        "mean_top_minus_bottom_spread": mean_ic / 5,
        "average_top_decile_selection_churn": 0.2,
        "session_metrics": [
            {
                "feature_session": f"2026-04-0{index}",
                "observation_count": 10,
                "rank_ic": mean_ic,
                "top_decile_mean_excess": mean_ic / 10,
                "bottom_decile_mean_excess": -mean_ic / 10,
                "top_minus_bottom_spread": mean_ic / 5,
            }
            for index in range(1, 4)
        ],
        "live_capital_allowed": False,
    }


def _feature_panel():
    definitions = [
        {
            "name": definition.name,
            "family": definition.family,
            "version": definition.version,
            "description": definition.description,
            "lookback_sessions": definition.lookback_sessions,
            "availability_lag_sessions": definition.availability_lag_sessions,
        }
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    return {
        "panel_sha256": "f" * 64,
        "feature_definitions": definitions,
    }


def test_delivery_trial_compares_same_rows_with_frozen_feature_sets(monkeypatch):
    calls = []

    def fake_one_day(**kwargs):
        calls.append(("1d", tuple(kwargs["feature_names"])))
        score = 0.06 if len(kwargs["feature_names"]) == 27 else 0.04
        return {"ridge": _metric(score), "report_sha256": "r" * 64}

    def fake_multi(**kwargs):
        calls.append(("multi", tuple(kwargs["feature_names"])))
        score = 0.03 if len(kwargs["feature_names"]) == 27 else 0.02
        return {
            "horizons": {
                "5": {"ridge": _metric(score)},
                "20": {"ridge": _metric(score / 2)},
            }
        }

    monkeypatch.setattr(
        "marketlab.alpha_delivery_trial.run_ridge_walkforward",
        fake_one_day,
    )
    monkeypatch.setattr(
        "marketlab.alpha_delivery_trial.run_action_safe_horizon_walkforward",
        fake_multi,
    )
    fold = [{"start": "2026-04-01", "end": "2026-06-30"}]
    report = run_delivery_incremental_trial(
        market_panel={"panel_sha256": "m" * 64},
        feature_panel=_feature_panel(),
        action_ledger={"ledger_sha256": "a" * 64},
        trial_ledger=_trial_ledger(),
        folds_1d=fold,
        folds_5d=fold,
        folds_20d=fold,
        l2=1.0,
    )
    assert report["primary_1d"]["augmented"]["ridge"]["mean_rank_ic"] == 0.06
    assert report["primary_1d"]["base"]["ridge"]["mean_rank_ic"] == 0.04
    assert (
        report["primary_1d"]["augmented_minus_base_inference"]["metrics"][
            "rank_ic"
        ]["mean"]
        == pytest.approx(0.02)
    )
    assert calls[0][1] == tuple(
        definition.name for definition in PRICE_VOLUME_DEFINITIONS
    )
    assert len(calls[1][1]) == 27
    assert report["horizon_60_excluded_by_frozen_trial"] is True


def test_delivery_trial_rejects_changed_fold_before_outcomes(monkeypatch):
    with pytest.raises(AlphaContractError, match="folds differ"):
        run_delivery_incremental_trial(
            market_panel={"panel_sha256": "m" * 64},
            feature_panel=_feature_panel(),
            action_ledger={"ledger_sha256": "a" * 64},
            trial_ledger=_trial_ledger(),
            folds_1d=[{"start": "2026-04-02", "end": "2026-06-30"}],
            folds_5d=[{"start": "2026-04-01", "end": "2026-06-30"}],
            folds_20d=[{"start": "2026-04-01", "end": "2026-06-30"}],
            l2=1.0,
        )


def test_delivery_trial_rejects_changed_l2():
    fold = [{"start": "2026-04-01", "end": "2026-06-30"}]
    with pytest.raises(AlphaContractError, match="l2 differs"):
        run_delivery_incremental_trial(
            market_panel={"panel_sha256": "m" * 64},
            feature_panel=_feature_panel(),
            action_ledger={"ledger_sha256": "a" * 64},
            trial_ledger=_trial_ledger(),
            folds_1d=fold,
            folds_5d=fold,
            folds_20d=fold,
            l2=0.5,
        )
