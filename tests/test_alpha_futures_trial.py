from dataclasses import asdict

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_futures_trial import run_futures_incremental_trial
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import append_trial_event, new_trial_ledger


MARKET_SHA = "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
BASE_SHA = "300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8"
ACTION_SHA = "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
DELIVERY_SHA = "99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90"


def _ledger():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T005",
        recorded_at_utc="2026-09-30T08:34:25+00:00",
        payload={
            "status": "FROZEN_BEFORE_OUTCOME_MATERIALIZATION",
            "base_feature_count": 27,
            "derivative_feature_count": 10,
            "model": {"type": "ridge", "l2": 1.0},
            "primary": {
                "folds": [
                    ["2026-04-01", "2026-06-30"],
                    ["2026-07-01", "2026-09-18"],
                ],
                "horizon_sessions": 5,
                "newey_west_lag": 4,
            },
            "secondary": {
                "folds": [
                    ["2026-04-01", "2026-06-30"],
                    ["2026-07-01", "2026-09-24"],
                ],
                "horizon_sessions": 1,
                "newey_west_lag": 5,
            },
            "diagnostic": {
                "folds": [
                    ["2026-04-01", "2026-06-30"],
                    ["2026-07-01", "2026-08-27"],
                ],
                "horizon_sessions": 20,
                "newey_west_lag": 19,
            },
        },
    )
    ledger = append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T005",
        recorded_at_utc="2026-09-30T08:37:36+00:00",
        payload={
            "protocol_id": "AE001-T005-P1",
            "selection_rule": (
                "FEATURE_CONSTRUCTION_USES_ONLY_STF_CONTRACTS_WITH_"
                "EXPIRY_STRICTLY_GREATER_THAN_TRADE_DATE"
            ),
        },
    )
    return append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T005",
        recorded_at_utc="2026-09-30T08:41:00+00:00",
        payload={
            "protocol_id": "AE001-T005-P2",
            "market_panel_sha256": MARKET_SHA,
            "action_safe_base_feature_panel_sha256": BASE_SHA,
            "corporate_action_ledger_sha256": ACTION_SHA,
            "delivery_augmented_feature_panel_sha256": DELIVERY_SHA,
        },
    )


def _feature_panel():
    definitions = [
        asdict(definition)
        for definition in [
            *PRICE_VOLUME_DEFINITIONS,
            *DELIVERY_DEFINITIONS,
            *FUTURES_DEFINITIONS,
        ]
    ]
    return {
        "panel_sha256": "f" * 64,
        "base_feature_panel_sha256": DELIVERY_SHA,
        "base_action_safe_feature_panel_sha256": BASE_SHA,
        "corporate_action_ledger_sha256": ACTION_SHA,
        "futures_panel_sha256": "u" * 64,
        "feature_definitions": definitions,
    }


def _metric(mean_ic, spread):
    metrics = []
    for index in range(10):
        metrics.append(
            {
                "feature_session": f"2026-05-{index + 1:02d}",
                "observation_count": 100,
                "rank_ic": mean_ic,
                "top_decile_mean_excess": spread / 2,
                "bottom_decile_mean_excess": -spread / 2,
                "top_minus_bottom_spread": spread,
            }
        )
    return {
        "schema_version": 1,
        "session_count": 10,
        "prediction_count": 1000,
        "mean_rank_ic": mean_ic,
        "median_rank_ic": mean_ic,
        "mean_top_decile_excess": spread / 2,
        "mean_top_minus_bottom_spread": spread,
        "average_top_decile_selection_churn": 0.3,
        "session_metrics": metrics,
        "live_capital_allowed": False,
    }


def test_t005_compares_base_and_augmented_on_frozen_horizons(monkeypatch):
    calls = []

    def fake_walkforward(**kwargs):
        count = len(kwargs["feature_names"])
        calls.append((count, kwargs["folds_by_horizon"]))
        score = 0.02 if count == 37 else 0.01
        spread = 0.004 if count == 37 else 0.002
        return {
            "horizons": {
                str(horizon): {"ridge": _metric(score, spread)}
                for horizon in (1, 5, 20)
            }
        }

    monkeypatch.setattr(
        "marketlab.alpha_futures_trial.run_action_safe_horizon_walkforward",
        fake_walkforward,
    )
    report = run_futures_incremental_trial(
        market_panel={"panel_sha256": MARKET_SHA},
        feature_panel=_feature_panel(),
        action_ledger={"ledger_sha256": ACTION_SHA},
        trial_ledger=_ledger(),
    )
    assert [call[0] for call in calls] == [27, 37]
    delta = report["primary_5d"]["augmented_minus_base_inference"][
        "metrics"
    ]["rank_ic"]["mean"]
    assert delta == pytest.approx(0.01)
    assert report["secondary_1d"]["horizon_sessions"] == 1
    assert report["diagnostic_20d"]["horizon_sessions"] == 20
    assert report["prospective_claim_allowed"] is False


def test_t005_fails_closed_without_upstream_p2(monkeypatch):
    ledger = _ledger()
    ledger["events"] = ledger["events"][:-1]
    ledger["event_count"] -= 1
    unsigned = dict(ledger)
    unsigned.pop("ledger_sha256", None)
    from marketlab.alpha import digest

    ledger["ledger_sha256"] = digest(unsigned)
    with pytest.raises(AlphaContractError, match="protocol amendment"):
        run_futures_incremental_trial(
            market_panel={"panel_sha256": MARKET_SHA},
            feature_panel=_feature_panel(),
            action_ledger={"ledger_sha256": ACTION_SHA},
            trial_ledger=ledger,
        )
