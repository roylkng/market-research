from __future__ import annotations

from datetime import date

import pytest

from marketlab import h022_expanded_outcomes as expanded
from marketlab.h022_outcomes import build_frozen_sessions, first_entry_session, horizon_session


def _panel() -> dict:
    return {
        "panel_sha256": expanded.FEATURE_PANEL_SHA256,
        "records": [
            {
                "source_id": "eligible",
                "symbol": "AAA",
                "exchange_published_at_utc": "2025-10-01T03:00:00Z",
                "membership_status": "SIGNAL_ELIGIBLE",
                "feature_status": "SIGNAL",
                "evaluation_eligible": True,
                "primary_signal": 2.0,
            },
            {
                "source_id": "context",
                "symbol": "BBB",
                "exchange_published_at_utc": "2025-10-01T03:00:00Z",
                "membership_status": "CONTEXT_ONLY_NONMEMBER",
                "feature_status": "SIGNAL",
                "evaluation_eligible": False,
                "primary_signal": 10.0,
            },
        ],
    }


def test_challenge_rows_use_evaluation_eligibility(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(expanded, "validate_expanded_feature_panel", lambda _panel: None)
    monkeypatch.setattr(expanded, "CHALLENGE_SIGNAL_COUNT", 1)
    rows = expanded.challenge_rows(_panel())
    assert [row["source_id"] for row in rows] == ["eligible"]


def test_expanded_report_uses_same_horizon_convention(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(expanded, "validate_expanded_feature_panel", lambda _panel: None)
    monkeypatch.setattr(expanded, "CHALLENGE_SIGNAL_COUNT", 1)
    panel = _panel()
    sessions = build_frozen_sessions(
        start_date=date(2025, 10, 1), end_date=date(2026, 9, 11)
    )
    entry_index, entry = first_entry_session(
        "2025-10-01T03:00:00Z", sessions
    ) or (-1, None)
    assert entry is not None

    stock_bars = {(entry.session_date, "AAA"): {"open": 100.0, "close": 100.0}}
    benchmark_bars = {entry.session_date: {"open": 1000.0, "close": 1000.0}}
    for horizon in (20, 60, 120):
        exit_session = horizon_session(sessions, entry_index=entry_index, horizon=horizon)
        assert exit_session is not None
        stock_bars[(exit_session.session_date, "AAA")] = {
            "open": 100.0,
            "close": 110.0,
        }
        benchmark_bars[exit_session.session_date] = {
            "open": 1000.0,
            "close": 1050.0,
        }

    report = expanded.build_expanded_outcome_report(
        panel,
        sessions=sessions,
        stock_bars=stock_bars,
        benchmark_bars=benchmark_bars,
        corporate_actions={
            "AAA": {"status": "READY", "actions": [], "unresolved_subjects": []}
        },
    )
    assert len(report["records"]) == 1
    assert report["records"][0]["membership_status"] == "SIGNAL_ELIGIBLE"
    outcome = report["records"][0]["horizons"]["60"]
    assert outcome["status"] == "COMPLETE"
    assert outcome["stock_return_pct"] == pytest.approx(10.0)
    assert outcome["benchmark_return_pct"] == pytest.approx(5.0)
    assert outcome["gross_excess_pp"] == pytest.approx(5.0)
    assert outcome["cost_adjusted_excess_pp"] == pytest.approx(4.5)


def test_expanded_report_blocks_share_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(expanded, "validate_expanded_feature_panel", lambda _panel: None)
    monkeypatch.setattr(expanded, "CHALLENGE_SIGNAL_COUNT", 1)
    panel = _panel()
    sessions = build_frozen_sessions(
        start_date=date(2025, 10, 1), end_date=date(2026, 9, 11)
    )
    entry_index, entry = first_entry_session(
        "2025-10-01T03:00:00Z", sessions
    ) or (-1, None)
    assert entry is not None
    exit60 = horizon_session(sessions, entry_index=entry_index, horizon=60)
    assert exit60 is not None
    stock_bars = {
        (entry.session_date, "AAA"): {"open": 100.0, "close": 100.0},
        (exit60.session_date, "AAA"): {"open": 100.0, "close": 110.0},
    }
    benchmark_bars = {
        entry.session_date: {"open": 1000.0, "close": 1000.0},
        exit60.session_date: {"open": 1000.0, "close": 1050.0},
    }
    report = expanded.build_expanded_outcome_report(
        panel,
        sessions=sessions,
        stock_bars=stock_bars,
        benchmark_bars=benchmark_bars,
        corporate_actions={
            "AAA": {
                "status": "READY",
                "actions": [
                    {"ex_date": "2025-11-03", "subject": "Bonus issue"}
                ],
                "unresolved_subjects": [],
            }
        },
    )
    assert report["records"][0]["horizons"]["60"]["status"] == "CORPORATE_ACTION_BLOCKED"
