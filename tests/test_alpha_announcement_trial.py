from marketlab.alpha import digest
from marketlab.alpha_announcement_features import (
    ANNOUNCEMENT_DEFINITIONS,
    ANNOUNCEMENT_FEATURE_DEFINITION_SHA256,
    ANNOUNCEMENT_TAXONOMY_SHA256,
)
from marketlab.alpha_announcement_trial import run_announcement_incremental_trial
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import append_trial_event, new_trial_ledger


def _metric(value):
    return {
        "session_count": 3,
        "prediction_count": 30,
        "mean_rank_ic": value,
        "median_rank_ic": value,
        "mean_top_decile_excess": value / 10,
        "mean_top_minus_bottom_spread": value / 5,
        "average_top_decile_selection_churn": 0.2,
        "session_metrics": [
            {
                "feature_session": f"2026-04-0{day}",
                "rank_ic": value,
                "top_decile_mean_excess": value / 10,
                "bottom_decile_mean_excess": -value / 10,
                "top_minus_bottom_spread": value / 5,
                "observation_count": 10,
            }
            for day in range(1, 4)
        ],
        "live_capital_allowed": False,
    }


def _ledger():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T007",
        recorded_at_utc="2026-09-30T12:22:36+00:00",
        payload={
            "status": "FROZEN_BEFORE_OUTCOME_MATERIALIZATION",
            "new_feature_count": 16,
            "model": {"type": "ridge", "l2": 1.0},
            "primary": {
                "folds": [
                    ["2026-04-01", "2026-06-30"],
                    ["2026-07-01", "2026-09-24"],
                ],
                "newey_west_lag": 5,
            },
            "secondary": {
                "folds": [
                    ["2026-04-01", "2026-06-30"],
                    ["2026-07-01", "2026-09-18"],
                ],
                "newey_west_lag": 4,
            },
        },
    )
    return append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T007",
        recorded_at_utc="2026-09-30T12:30:00+00:00",
        payload={
            "protocol_id": "AE001-T007-P1",
            "announcement_taxonomy_sha256": ANNOUNCEMENT_TAXONOMY_SHA256,
            "announcement_feature_definition_sha256": (
                ANNOUNCEMENT_FEATURE_DEFINITION_SHA256
            ),
            "d003_report_sha256": (
                "7f402beecaf90f054c93ca2ceeaa01f38fcc5cd8f7f8f6391f60791768f8a91f"
            ),
            "source_query_granularity": (
                "ONE_WHOLE_MARKET_QUERY_PER_CALENDAR_DATE"
            ),
            "zero_event_policy": (
                "VALID_ONLY_WITH_COMPLETE_DAILY_SOURCE_WINDOW"
            ),
        },
    )


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
        for definition in [
            *PRICE_VOLUME_DEFINITIONS,
            *DELIVERY_DEFINITIONS,
            *ANNOUNCEMENT_DEFINITIONS,
        ]
    ]
    panel = {
        "schema_version": 1,
        "panel_id": "AE001-T007-CORE43-v1",
        "base_feature_panel_sha256": "b" * 64,
        "announcement_panel_sha256": "n" * 64,
        "feature_definitions": definitions,
        "rows": [],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def test_t007_trial_uses_frozen_feature_subsets_and_horizons(monkeypatch):
    calls = []

    def fake_walkforward(**kwargs):
        names = tuple(kwargs["feature_names"])
        calls.append((names, kwargs["folds_by_horizon"]))
        score = 0.06 if len(names) == 43 else 0.04
        return {
            "horizons": {
                "1": {"ridge": _metric(score)},
                "5": {"ridge": _metric(score / 2)},
            }
        }

    monkeypatch.setattr(
        "marketlab.alpha_announcement_trial."
        "run_action_safe_horizon_walkforward",
        fake_walkforward,
    )
    report = run_announcement_incremental_trial(
        market_panel={"panel_sha256": "m" * 64},
        feature_panel=_feature_panel(),
        action_ledger={"ledger_sha256": "a" * 64},
        trial_ledger=_ledger(),
    )
    assert len(calls) == 2
    assert len(calls[0][0]) == 27
    assert len(calls[1][0]) == 43
    assert set(calls[0][1]) == {1, 5}
    assert report["primary_1d"][
        "augmented_minus_base_inference"
    ]["metrics"]["rank_ic"]["mean"] > 0
    assert report["secondary_may_rescue_primary"] is False
    assert report["announcement_taxonomy_sha256"] == (
        ANNOUNCEMENT_TAXONOMY_SHA256
    )
