from __future__ import annotations

from datetime import date, timedelta

import pytest

from marketlab.alpha import digest
from marketlab.alpha_fundamental import FEATURE_NAMES
from marketlab.alpha_fundamental_trial import (
    _aggregate_period_metrics,
    _cdf_transform,
    _examples_for_fold,
    _fit_ecdf,
    build_t008_event_labels,
)


def _action_ledger(start: str, end: str):
    ledger = {
        "schema_version": 1,
        "ledger_id": "AE001-CORPORATE-ACTIONS-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "coverage_start_date": start,
        "coverage_end_date": end,
        "source_chunks": [],
        "record_count": 0,
        "records": [],
        "no_record_means_no_share_changing_action_in_covered_source": True,
        "historical_source_retrieved_prospectively": False,
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = digest(ledger)
    return ledger


def _market_panel():
    start = date(2026, 1, 1)
    sessions = []
    close = 100.0
    benchmark = 20_000.0
    for index in range(50):
        day = start + timedelta(days=index)
        prior = close
        close *= 1.001
        benchmark_prior = benchmark
        benchmark *= 1.0005
        sessions.append(
            {
                "session_date": day.isoformat(),
                "equities": [
                    {
                        "session_date": day.isoformat(),
                        "symbol": "TEST",
                        "isin": "INE000000001",
                        "open_price": prior,
                        "high_price": close * 1.01,
                        "low_price": prior * 0.99,
                        "close_price": close,
                        "previous_close": prior,
                        "volume": 100000.0,
                        "turnover_inr": 30_000_000.0,
                        "trade_count": 1000.0,
                    }
                ],
                "benchmark": {
                    "benchmark_id": "nifty_500",
                    "index_name": "Nifty 500",
                    "session_date": day.isoformat(),
                    "open_price": benchmark_prior,
                    "close_price": benchmark,
                },
            }
        )
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _record(
    *,
    published: str,
    target_period="2026-03-31",
    symbol="TEST",
    value=0.10,
):
    features = {name: value for name in FEATURE_NAMES}
    record = {
        "schema_version": 1,
        "diagnostic_id": "AE001-T008-D004-v1",
        "symbol": symbol,
        "target_period_end": target_period,
        "baseline_period_end": "2025-03-31",
        "accounting_basis": "Standalone",
        "target_exchange_published_at_utc": published,
        "baseline_exchange_published_at_utc": "2025-12-01T00:00:00Z",
        "target_source_url": "https://example.com/target",
        "baseline_source_url": "https://example.com/base",
        "target_discovery_row_sha256": "a" * 64,
        "baseline_discovery_row_sha256": "b" * 64,
        "discovery_raw_sha256": "c" * 64,
        "target_raw_sha256": "d" * 64,
        "baseline_raw_sha256": "e" * 64,
        "target_parser_version": "x",
        "baseline_parser_version": "x",
        "target_currency": "INR",
        "baseline_currency": "INR",
        "target_rounding": None,
        "baseline_rounding": None,
        "features": features,
        "complete_feature_count": len(FEATURE_NAMES),
        "all_six_features_complete": True,
        "exceptional_items_to_revenue_diagnostic": None,
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
        "source_diagnostic_id": "AE001-T008-D002-v1",
        "source_panel_sha256": "s" * 64,
        "source_workflow_run_id": 1,
        "source_workflow_artifact_id": 2,
        "source_record_sha256": "r" * 64,
    }
    record["record_sha256"] = digest(record)
    return record


def test_training_cdf_is_midrank_and_clips_outside_training_range():
    rows = [
        {"features": {name: value for name in FEATURE_NAMES}}
        for value in (0.0, 1.0, 1.0, 3.0)
    ]
    transform = _fit_ecdf(rows)
    values = transform[FEATURE_NAMES[0]]
    assert _cdf_transform(values, -1.0) == pytest.approx(-1.0)
    assert _cdf_transform(values, 4.0) == pytest.approx(1.0)
    # Two tied values at 1.0: (count_less=1 + half of 2) / 4 = 0.5.
    assert _cdf_transform(values, 1.0) == pytest.approx(0.0)


def test_label_entry_is_next_session_strictly_after_publication_local_date(
    monkeypatch,
):
    market = _market_panel()
    publication_session = market["sessions"][10]["session_date"]
    published = (
        f"{publication_session}T03:00:00Z"
    )
    record = _record(published=published)
    panel = {
        "schema_version": 1,
        "diagnostic_id": "AE001-T008-D004-v1",
        "universe_sha256": "u",
        "records": [record],
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)

    monkeypatch.setattr(
        "marketlab.alpha_fundamental_trial.D004_PANEL_SHA256",
        panel["panel_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_fundamental_trial.EXPECTED_UNIVERSE_SHA256",
        "u",
    )

    actions = _action_ledger(
        market["sessions"][0]["session_date"],
        market["sessions"][-1]["session_date"],
    )
    labels, exclusions = build_t008_event_labels(
        d004_panel=panel,
        market_panel=market,
        action_ledger=actions,
        horizon_sessions=5,
    )
    label = labels[record["record_sha256"]]
    assert label["entry_session"] == market["sessions"][11]["session_date"]
    assert label["exit_session"] == market["sessions"][15]["session_date"]
    assert exclusions == {}


def test_label_fails_closed_when_exit_identity_disappears(monkeypatch):
    market = _market_panel()
    publication_session = market["sessions"][10]["session_date"]
    record = _record(published=f"{publication_session}T12:00:00Z")
    # Horizon five exits at session 15 after strict next-session entry.
    market["sessions"][15]["equities"] = []
    unsigned = dict(market)
    unsigned.pop("panel_sha256", None)
    market["panel_sha256"] = digest(unsigned)

    panel = {
        "schema_version": 1,
        "diagnostic_id": "AE001-T008-D004-v1",
        "universe_sha256": "u",
        "records": [record],
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    monkeypatch.setattr(
        "marketlab.alpha_fundamental_trial.D004_PANEL_SHA256",
        panel["panel_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.alpha_fundamental_trial.EXPECTED_UNIVERSE_SHA256",
        "u",
    )
    actions = _action_ledger(
        market["sessions"][0]["session_date"],
        market["sessions"][-1]["session_date"],
    )
    labels, exclusions = build_t008_event_labels(
        d004_panel=panel,
        market_panel=market,
        action_ledger=actions,
        horizon_sessions=5,
    )
    assert labels == {}
    assert exclusions["EXIT_IDENTITY_MISSING_OR_AMBIGUOUS"] == 1


def test_aggregate_period_metrics_equal_weights_periods():
    rows = {
        "2026-03-31": [
            {
                "symbol": f"A{i}",
                "isin": f"INEA{i:09d}",
                "prediction": float(i),
                "target_excess_return": float(i) / 100.0,
            }
            for i in range(8)
        ],
        "2026-06-30": [
            {
                "symbol": f"B{i}",
                "isin": f"INEB{i:09d}",
                "prediction": float(i),
                "target_excess_return": float(i) / 200.0,
            }
            for i in range(12)
        ],
    }
    result = _aggregate_period_metrics(rows)
    assert result["per_period"]["2026-03-31"]["rank_ic"] == pytest.approx(1.0)
    assert result["per_period"]["2026-06-30"]["rank_ic"] == pytest.approx(1.0)
    assert result["mean_rank_ic"] == pytest.approx(1.0)
    assert result["combined_prediction_count"] == 20


def test_fold_maturity_purge_excludes_label_known_after_oos_start():
    training_good = _record(
        published="2025-10-01T10:00:00Z",
        target_period="2025-09-30",
        value=0.1,
    )
    training_late = _record(
        published="2026-03-01T10:00:00Z",
        target_period="2025-12-31",
        value=0.2,
    )
    oos = _record(
        published="2026-04-10T10:00:00Z",
        target_period="2026-03-31",
        value=0.3,
    )
    panel = {"records": [training_good, training_late, oos]}
    labels = {
        training_good["record_sha256"]: {
            "symbol": "TEST",
            "isin": "INE000000001",
            "publication_local_date": "2025-10-01",
            "entry_session": "2025-10-02",
            "exit_session": "2025-10-31",
            "exit_close_timestamp_utc": "2025-10-31T10:00:00+00:00",
            "excess_return": 0.02,
        },
        training_late["record_sha256"]: {
            "symbol": "TEST",
            "isin": "INE000000001",
            "publication_local_date": "2026-03-01",
            "entry_session": "2026-03-02",
            "exit_session": "2026-04-10",
            # Same instant as OOS publication, therefore prohibited.
            "exit_close_timestamp_utc": "2026-04-10T10:00:00+00:00",
            "excess_return": 0.03,
        },
        oos["record_sha256"]: {
            "symbol": "TEST",
            "isin": "INE000000001",
            "publication_local_date": "2026-04-10",
            "entry_session": "2026-04-11",
            "exit_session": "2026-05-01",
            "exit_close_timestamp_utc": "2026-05-01T10:00:00+00:00",
            "excess_return": 0.04,
        },
    }
    fold = {
        "fold_id": "F1",
        "oos_period": "2026-03-31",
        "training_periods": ("2025-09-30", "2025-12-31"),
    }

    # Lower the gate for this focused unit test only.
    import marketlab.alpha_fundamental_trial as trial

    original = trial.MIN_TRAINING_EXAMPLES
    trial.MIN_TRAINING_EXAMPLES = 1
    try:
        train, test, metadata, _ = _examples_for_fold(
            d004_panel=panel,
            labels=labels,
            fold=fold,
            horizon_sessions=20,
        )
    finally:
        trial.MIN_TRAINING_EXAMPLES = original

    assert len(train) == 1
    assert len(test) == 1
    assert metadata["training_example_count"] == 1
