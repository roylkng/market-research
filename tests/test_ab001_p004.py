from datetime import date, timedelta

import pytest

from marketlab.ab001 import build_alpha_library
from marketlab.alpha import AlphaContractError, digest
from marketlab.ab001_p004 import (
    CONTEXT_VARIABLES,
    _fit_context_ridge,
    run_ab001_p004,
)


def _source_payloads(session_count=70):
    start = date(2026, 1, 1)
    core_predictions = []
    delta_predictions = []
    regime_rows = []

    for session_index in range(session_count):
        session_day = start + timedelta(days=session_index)
        session = session_day.isoformat()
        exit_session = (session_day + timedelta(days=5)).isoformat()
        regime_positive = session_index % 2 == 0
        context_sign = 1.0 if regime_positive else -1.0

        regime_rows.append(
            {
                "session_date": session,
                "known_at": f"{session}T18:00:00+05:30",
                "eligible_equity_count": 10,
                "source_window_sha256": f"{session_index + 1:064x}",
                "values": {
                    "nifty500_return_1": 0.001 * context_sign,
                    "nifty500_return_5": 0.002 * context_sign,
                    "nifty500_return_20": context_sign,
                    "nifty500_return_60": 0.01 * context_sign,
                    "nifty500_realized_vol_20": (
                        0.01 if regime_positive else 0.03
                    ),
                    "nifty500_realized_vol_60": 0.02,
                    "nifty500_drawdown_from_60d_high": -0.01,
                    "breadth_advancer_fraction_1": (
                        0.7 if regime_positive else 0.3
                    ),
                    "breadth_positive_momentum20_fraction": (
                        0.8 if regime_positive else 0.2
                    ),
                    "breadth_median_return_1": 0.001 * context_sign,
                    "breadth_return_dispersion_1": 0.02,
                    "breadth_median_turnover_surprise20": 1.0,
                },
            }
        )

        for stock_index in range(10):
            x = stock_index - 4.5
            target = x if regime_positive else -x
            common = {
                "symbol": f"S{stock_index:03d}",
                "isin": f"INE{stock_index:09d}",
                "feature_session": session,
                "entry_session": session,
                "exit_session": exit_session,
                "horizon_sessions": 5,
                "target_excess_return": target / 100.0,
                "prediction_role": "OOS",
                "oos_only": True,
                "live_capital_allowed": False,
            }
            core_predictions.append(
                {
                    **common,
                    "model_id": "CORE",
                    "prediction": x,
                }
            )
            delta_predictions.append(
                {
                    **common,
                    "model_id": "DELTA",
                    "prediction": -x,
                }
            )

    library = build_alpha_library(
        [
            {
                "alpha_id": "AB001-P003-CORE27",
                "alpha_version": "v1",
                "source_artifact_sha256": "a" * 64,
                "predictions": core_predictions,
            },
            {
                "alpha_id": "AB001-P003-FUTURES-DELTA",
                "alpha_version": "v1",
                "source_artifact_sha256": "b" * 64,
                "predictions": delta_predictions,
            },
        ]
    )

    p003 = {
        "schema_version": 1,
        "pilot_id": "AB001-P003-v1",
        "horizon_sessions": 5,
        "library": library,
        "live_capital_allowed": False,
    }
    p003["report_sha256"] = digest(p003)

    regime = {
        "schema_version": 1,
        "panel_id": "AE001-RG001-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "market_panel_sha256": "c" * 64,
        "historical_archives_captured_prospectively": False,
        "variable_names": [
            "nifty500_return_1",
            "nifty500_return_5",
            "nifty500_return_20",
            "nifty500_return_60",
            "nifty500_realized_vol_20",
            "nifty500_realized_vol_60",
            "nifty500_drawdown_from_60d_high",
            "breadth_advancer_fraction_1",
            "breadth_positive_momentum20_fraction",
            "breadth_median_return_1",
            "breadth_return_dispersion_1",
            "breadth_median_turnover_surprise20",
        ],
        "variable_set_sha256": "d" * 64,
        "state_count": len(regime_rows),
        "rows": regime_rows,
        "stock_level_alpha": False,
        "direct_cross_sectional_feature_use": False,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    regime["panel_sha256"] = digest(regime)
    return p003, regime


def test_context_ridge_learns_relative_efficacy_direction():
    training = []
    for index in range(40):
        context = {
            "nifty500_return_20": 1.0 if index % 2 == 0 else -1.0,
            "nifty500_realized_vol_20": 0.01 if index % 2 == 0 else 0.03,
            "breadth_positive_momentum20_fraction": (
                0.8 if index % 2 == 0 else 0.2
            ),
        }
        training.append(
            {
                "context": context,
                "relative_ic": -2.0 if index % 2 == 0 else 2.0,
            }
        )
    fit = _fit_context_ridge(
        training,
        {
            "nifty500_return_20": -1.0,
            "nifty500_realized_vol_20": 0.03,
            "breadth_positive_momentum20_fraction": 0.2,
        },
    )
    assert fit["training_session_count"] == 40
    assert fit["predicted_relative_ic"] > 0.0


def test_p004_walk_forward_selector_uses_only_mature_prior_sessions(monkeypatch):
    p003, regime = _source_payloads()
    monkeypatch.setattr(
        "marketlab.ab001_p004.EXPECTED_P003_REPORT_SHA",
        p003["report_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.ab001_p004.EXPECTED_P003_LIBRARY_SHA",
        p003["library"]["library_sha256"],
    )

    report = run_ab001_p004(
        p003_report=p003,
        regime_panel=regime,
    )
    assert report["eligible_selector_session_count"] > 0
    assert report["selector_choice_counts"]["CORE27"] > 0
    assert report["selector_choice_counts"]["FUTURES_DELTA"] > 0
    assert report["selector_directional_accuracy"] > 0.9
    assert report["selector"]["mean_rank_ic"] > report[
        "always_futures_delta"
    ]["mean_rank_ic"]
    for decision in report["decisions"]:
        assert decision["training_session_count"] >= 40
        assert decision["exit_session"] >= decision["feature_session"]


def test_p004_current_outcome_cannot_change_current_selector_choice(monkeypatch):
    p003, regime = _source_payloads()
    monkeypatch.setattr(
        "marketlab.ab001_p004.EXPECTED_P003_REPORT_SHA",
        p003["report_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.ab001_p004.EXPECTED_P003_LIBRARY_SHA",
        p003["library"]["library_sha256"],
    )
    first = run_ab001_p004(p003_report=p003, regime_panel=regime)

    target_session = first["decisions"][-1]["feature_session"]
    original_choice = first["decisions"][-1]["choice"]
    original_predicted = first["decisions"][-1]["predicted_relative_ic"]

    for row in p003["library"]["records"]:
        if row["feature_session"] == target_session:
            row["target_excess_return"] = -float(row["target_excess_return"])
            unsigned = {
                key: value
                for key, value in row.items()
                if key != "record_sha256"
            }
            row["record_sha256"] = digest(unsigned)

    unsigned_library = dict(p003["library"])
    unsigned_library.pop("library_sha256", None)
    p003["library"]["library_sha256"] = digest(unsigned_library)
    unsigned_report = dict(p003)
    unsigned_report.pop("report_sha256", None)
    p003["report_sha256"] = digest(unsigned_report)

    monkeypatch.setattr(
        "marketlab.ab001_p004.EXPECTED_P003_REPORT_SHA",
        p003["report_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.ab001_p004.EXPECTED_P003_LIBRARY_SHA",
        p003["library"]["library_sha256"],
    )
    second = run_ab001_p004(p003_report=p003, regime_panel=regime)
    changed = next(
        row
        for row in second["decisions"]
        if row["feature_session"] == target_session
    )
    assert changed["choice"] == original_choice
    assert changed["predicted_relative_ic"] == pytest.approx(
        original_predicted
    )


def test_p004_rejects_missing_frozen_context_variable(monkeypatch):
    p003, regime = _source_payloads()
    monkeypatch.setattr(
        "marketlab.ab001_p004.EXPECTED_P003_REPORT_SHA",
        p003["report_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.ab001_p004.EXPECTED_P003_LIBRARY_SHA",
        p003["library"]["library_sha256"],
    )
    regime["variable_names"].remove(CONTEXT_VARIABLES[0])
    unsigned = dict(regime)
    unsigned.pop("panel_sha256", None)
    regime["panel_sha256"] = digest(unsigned)
    with pytest.raises(AlphaContractError, match="context variables"):
        run_ab001_p004(p003_report=p003, regime_panel=regime)
