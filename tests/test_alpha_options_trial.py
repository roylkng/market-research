from dataclasses import asdict

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_options import OPTIONS_DEFINITIONS
from marketlab.alpha_options_trial import run_options_incremental_trial
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import append_trial_event, new_trial_ledger

MARKET_SHA = "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
ACTION_SHA = "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
BASE37_SHA = "62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f"
SOURCE_HASHES_SHA = "edf21ed30ea4021a82118c8699f1a7470442bcee29155810772a09c4b24bc6dc"
OPTIONS_SHA = "o" * 64
FEATURE47_SHA = "f" * 64


def _ledger(*, include_p1=True):
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T009",
        recorded_at_utc="2026-10-01T04:06:00+00:00",
        payload={
            "status": "FROZEN_BEFORE_OUTCOME_MATERIALIZATION",
            "base_feature_count": 37,
            "option_feature_count": 10,
            "augmented_feature_count": 47,
            "model": {"type": "ridge", "l2": 1.0},
            "primary": {
                "horizon_sessions": 5,
                "folds": [
                    ["2026-04-01", "2026-06-30"],
                    ["2026-07-01", "2026-09-18"],
                ],
                "newey_west_lag": 4,
            },
            "secondary": {
                "horizon_sessions": 1,
                "folds": [
                    ["2026-04-01", "2026-06-30"],
                    ["2026-07-01", "2026-09-24"],
                ],
                "newey_west_lag": 5,
                "rescues_failed_primary": False,
            },
            "diagnostic": {
                "horizon_sessions": 20,
                "folds": [
                    ["2026-04-01", "2026-06-30"],
                    ["2026-07-01", "2026-08-27"],
                ],
                "newey_west_lag": 19,
                "rescues_failed_primary": False,
            },
        },
    )
    if not include_p1:
        return ledger
    ledger = append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T009",
        recorded_at_utc="2026-10-01T06:00:00+00:00",
        payload={
            "protocol_id": "AE001-T009-P1",
            "market_panel_sha256": MARKET_SHA,
            "corporate_action_ledger_sha256": ACTION_SHA,
            "base_37_feature_panel_sha256": BASE37_SHA,
            "options_panel_sha256": OPTIONS_SHA,
            "options_source_hashes_sha256": SOURCE_HASHES_SHA,
            "augmented_47_feature_panel_sha256": FEATURE47_SHA,
            "options_ready_session_count": 266,
            "options_unavailable_session_count": 0,
            "options_parser_rejected_session_count": 0,
            "option_complete_feature_row_count": 20_000,
            "option_complete_session_count": 200,
            "exclusion_counts": {},
            "outcomes_opened_before_amendment": False,
            "model_fit_started_before_amendment": False,
            "live_capital_allowed": False,
        },
    )
    return append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T009",
        recorded_at_utc="2026-10-01T07:06:50+00:00",
        payload={
            "protocol_id": "AE001-T009-P2",
            "repair_scope": "SIGNED_SINGLE_FEATURE_DIAGNOSTICS_ONLY",
            "multivariate_ridge_feature_retained": True,
            "primary_success_criteria_changed": False,
        },
    )


def _feature_panel():
    definitions = [
        asdict(definition)
        for definition in [
            *PRICE_VOLUME_DEFINITIONS,
            *DELIVERY_DEFINITIONS,
            *FUTURES_DEFINITIONS,
            *OPTIONS_DEFINITIONS,
        ]
    ]
    return {
        "panel_sha256": FEATURE47_SHA,
        "base_feature_panel_sha256": BASE37_SHA,
        "options_panel_sha256": OPTIONS_SHA,
        "options_source_hashes_sha256": SOURCE_HASHES_SHA,
        "corporate_action_ledger_sha256": ACTION_SHA,
        "feature_definitions": definitions,
    }


def _metric(mean_ic, spread):
    rows = [
        {
            "feature_session": f"2026-05-{index + 1:02d}",
            "observation_count": 100,
            "rank_ic": mean_ic,
            "top_decile_mean_excess": spread / 2,
            "bottom_decile_mean_excess": -spread / 2,
            "top_minus_bottom_spread": spread,
        }
        for index in range(10)
    ]
    return {
        "schema_version": 1,
        "session_count": 10,
        "prediction_count": 1000,
        "mean_rank_ic": mean_ic,
        "median_rank_ic": mean_ic,
        "mean_top_decile_excess": spread / 2,
        "mean_top_minus_bottom_spread": spread,
        "average_top_decile_selection_churn": 0.3,
        "session_metrics": rows,
        "live_capital_allowed": False,
    }


def test_t009_compares_base37_vs_augmented47_on_same_rows(monkeypatch):
    calls = []

    def fake_walkforward(**kwargs):
        count = len(kwargs["feature_names"])
        calls.append((count, kwargs["folds_by_horizon"]))
        mean_ic = 0.01 if count == 37 else 0.03
        spread = 0.001 if count == 37 else 0.004
        return {
            "horizons": {
                str(horizon): {"ridge": _metric(mean_ic, spread)}
                for horizon in (1, 5, 20)
            }
        }

    monkeypatch.setattr(
        "marketlab.alpha_options_trial.run_action_safe_horizon_walkforward",
        fake_walkforward,
    )
    report = run_options_incremental_trial(
        market_panel={"panel_sha256": MARKET_SHA},
        feature_panel=_feature_panel(),
        action_ledger={"ledger_sha256": ACTION_SHA},
        trial_ledger=_ledger(),
    )
    assert [call[0] for call in calls] == [37, 47]
    delta = report["primary_5d"]["augmented_minus_base_inference"][
        "metrics"
    ]["rank_ic"]["mean"]
    assert delta == pytest.approx(0.02)
    assert report["secondary_1d"]["horizon_sessions"] == 1
    assert report["diagnostic_20d"]["horizon_sessions"] == 20
    assert report["prospective_claim_allowed"] is False


def test_t009_fails_closed_without_p1_source_hash_amendment():
    with pytest.raises(AlphaContractError, match="protocol amendment"):
        run_options_incremental_trial(
            market_panel={"panel_sha256": MARKET_SHA},
            feature_panel=_feature_panel(),
            action_ledger={"ledger_sha256": ACTION_SHA},
            trial_ledger=_ledger(include_p1=False),
        )


def test_t009_fails_closed_if_frozen_47_feature_hash_changes():
    panel = _feature_panel()
    panel["panel_sha256"] = "x" * 64
    with pytest.raises(AlphaContractError, match="47-feature panel"):
        run_options_incremental_trial(
            market_panel={"panel_sha256": MARKET_SHA},
            feature_panel=panel,
            action_ledger={"ledger_sha256": ACTION_SHA},
            trial_ledger=_ledger(),
        )


def test_t009_fails_closed_if_p1_source_chain_changes():
    ledger = _ledger()
    for event in ledger["events"]:
        if event["payload"].get("protocol_id") == "AE001-T009-P1":
            event["payload"]["options_ready_session_count"] = 265
            unsigned_event = dict(event)
            unsigned_event.pop("event_sha256", None)
            event["event_sha256"] = digest(unsigned_event)
    unsigned = dict(ledger)
    unsigned.pop("ledger_sha256", None)
    ledger["ledger_sha256"] = digest(unsigned)
    with pytest.raises(AlphaContractError, match="source contract"):
        run_options_incremental_trial(
            market_panel={"panel_sha256": MARKET_SHA},
            feature_panel=_feature_panel(),
            action_ledger={"ledger_sha256": ACTION_SHA},
            trial_ledger=ledger,
        )
