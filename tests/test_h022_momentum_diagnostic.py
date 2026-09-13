from __future__ import annotations

from datetime import date

import pytest

from marketlab import h022_momentum_diagnostic as diagnostic


def test_extended_calendar_excludes_prechallenge_holidays() -> None:
    sessions = diagnostic.build_diagnostic_sessions(
        start_date=date(2025, 8, 14), end_date=date(2025, 8, 28)
    )
    dates = {row.session_date for row in sessions}
    assert "2025-08-15" not in dates
    assert "2025-08-27" not in dates
    assert "2025-08-14" in dates
    assert "2025-08-28" in dates


def test_control_window_is_strictly_pre_entry_and_60_sessions() -> None:
    sessions = diagnostic.build_diagnostic_sessions(
        start_date=date(2025, 6, 15), end_date=date(2025, 12, 31)
    )
    entry_index = 80
    entry = sessions[entry_index]
    window = diagnostic.control_window(sessions, entry.session_date)
    assert window is not None
    start, end = window
    by_date = {row.session_date: index for index, row in enumerate(sessions)}
    assert by_date[start.session_date] == entry_index - 60
    assert by_date[end.session_date] == entry_index - 1
    assert end.session_date < entry.session_date


def test_control_window_blocks_share_action_after_start_close() -> None:
    audit = diagnostic.parse_control_action_audit(
        [
            {"symbol": "AAA", "subject": "Bonus issue", "exDate": "20-Aug-2025"},
            {"symbol": "AAA", "subject": "Interim Dividend", "exDate": "22-Aug-2025"},
        ],
        symbol="AAA",
    )
    blocked = diagnostic.control_window_blocked(
        audit, start_date="2025-08-01", end_date="2025-08-29"
    )
    assert len(blocked) == 1
    assert blocked[0]["ex_date"] == "2025-08-20"


def test_control_panel_missing_stock_bar_is_not_imputed(monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = diagnostic.build_diagnostic_sessions(
        start_date=date(2025, 6, 15), end_date=date(2025, 12, 31)
    )
    entry = sessions[80]
    start, end = diagnostic.control_window(sessions, entry.session_date) or (None, None)
    assert start is not None and end is not None
    report = {
        "hypothesis_id": "H022",
        "execution_rule_id": "H022-X001",
        "records": [
            {
                "source_id": "s1",
                "symbol": "AAA",
                "primary_signal": 2.0,
                "entry_session": {"session_date": entry.session_date},
                "horizons": {"60": {"status": "COMPLETE", "gross_excess_pp": 5.0}},
            }
        ],
    }
    monkeypatch.setattr(diagnostic, "validate_outcome_report", lambda _report: None)
    panel = diagnostic.build_control_panel(
        report,
        sessions=sessions,
        stock_closes={(start.session_date, "AAA"): 100.0, (end.session_date, "AAA"): None},
        benchmark_closes={start.session_date: 1000.0, end.session_date: 1010.0},
        corporate_actions={"AAA": {"status": "READY", "actions": [], "unresolved_subjects": []}},
    )
    assert panel["records"][0]["control_status"] == "NO_CONTROL_MISSING_STOCK_BAR"
    assert panel["records"][0]["prior_60d_relative_return_pp"] is None


def test_diagnostic_recovers_incremental_h022_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = []
    for index in range(120):
        signal = (index % 20) - 9.5
        momentum = ((index * 7) % 23) - 11.0
        future = 1.8 * signal + 0.6 * momentum + ((index % 5) - 2) * 0.1
        rows.append(
            {
                "source_id": f"s{index:03d}",
                "symbol": f"C{index % 30:02d}",
                "h022_signal": signal,
                "prior_60d_relative_return_pp": momentum,
                "future_60d_excess_pp": future,
                "control_status": "READY",
            }
        )
    panel = {
        "schema_version": 1,
        "diagnostic_id": diagnostic.DIAGNOSTIC_ID,
        "hypothesis_id": "H022",
        "outcome_report_sha256": diagnostic.OUTCOME_REPORT_SHA256,
        "record_count": len(rows),
        "ready_count": len(rows),
        "records": rows,
    }
    panel["panel_sha256"] = diagnostic._canonical_hash(panel)
    monkeypatch.setattr(diagnostic, "BOOTSTRAP_ITERATIONS", 500)
    summary = diagnostic.summarize_independence(panel)
    assert summary["metrics"]["standardized_h022_ols_coefficient_pp"] > 0
    assert summary["metrics"]["residualized_h022_spearman_vs_future_excess"] > 0
    assert summary["classification"] in {"PARTIAL_INDEPENDENCE", "SUPPORTIVE_INDEPENDENCE"}


def test_control_panel_hash_detects_mutation() -> None:
    panel = {
        "schema_version": 1,
        "diagnostic_id": diagnostic.DIAGNOSTIC_ID,
        "hypothesis_id": "H022",
        "outcome_report_sha256": diagnostic.OUTCOME_REPORT_SHA256,
        "record_count": 1,
        "ready_count": 1,
        "records": [
            {
                "source_id": "s1",
                "symbol": "AAA",
                "h022_signal": 1.0,
                "prior_60d_relative_return_pp": 2.0,
                "future_60d_excess_pp": 3.0,
                "control_status": "READY",
            }
        ],
    }
    panel["panel_sha256"] = diagnostic._canonical_hash(panel)
    panel["records"][0]["future_60d_excess_pp"] = 99.0
    with pytest.raises(diagnostic.H022MomentumDiagnosticError, match="hash mismatch"):
        diagnostic.summarize_independence(panel)
