from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab import h022_dependence_diagnostic as diagnostic


def _selection_row(
    source_id: str,
    symbol: str,
    published: str,
    entry: str,
    exit_day: str,
    signal: float,
    future: float,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "symbol": symbol,
        "exchange_published_at_utc": published,
        "publication_month": published[:7],
        "entry_session_date": entry,
        "exit_session_date": exit_day,
        "h022_signal": signal,
        "future_60d_excess_pp": future,
        "z_h022": signal,
    }


def test_first_complete_event_is_timestamp_then_source_id() -> None:
    rows = [
        _selection_row("late", "AAA", "2026-02-01T10:00:00+00:00", "2026-02-02", "2026-04-30", 99.0, 99.0),
        _selection_row("b", "AAA", "2026-01-01T10:00:00+00:00", "2026-01-02", "2026-03-31", -50.0, -50.0),
        _selection_row("a", "AAA", "2026-01-01T10:00:00+00:00", "2026-01-02", "2026-03-31", 50.0, 50.0),
        _selection_row("bbb", "BBB", "2026-01-05T10:00:00+00:00", "2026-01-06", "2026-04-03", 1.0, 1.0),
    ]
    selected = diagnostic.first_complete_event_rows(rows)
    by_symbol = {str(row["symbol"]): row for row in selected}
    assert by_symbol["AAA"]["source_id"] == "a"
    assert by_symbol["BBB"]["source_id"] == "bbb"


def test_nonoverlap_selector_uses_dates_not_signal_or_return() -> None:
    rows = [
        _selection_row("a1", "AAA", "2026-01-01T10:00:00+00:00", "2026-01-02", "2026-03-31", -100.0, -100.0),
        _selection_row("a2", "AAA", "2026-02-01T10:00:00+00:00", "2026-02-02", "2026-04-30", 1000.0, 1000.0),
        _selection_row("a3", "AAA", "2026-04-01T10:00:00+00:00", "2026-04-02", "2026-06-30", 1.0, 1.0),
        _selection_row("b1", "BBB", "2026-01-10T10:00:00+00:00", "2026-01-12", "2026-04-10", 2.0, 2.0),
    ]
    selected = diagnostic.nonoverlapping_event_rows(rows)
    assert {str(row["source_id"]) for row in selected} == {"a1", "a3", "b1"}


def test_company_balanced_slope_is_invariant_to_within_company_duplication() -> None:
    base = [
        {"symbol": "AAA", "z_h022": -1.0, "future_60d_excess_pp": -2.0},
        {"symbol": "AAA", "z_h022": 0.0, "future_60d_excess_pp": 0.0},
        {"symbol": "BBB", "z_h022": 0.0, "future_60d_excess_pp": 0.0},
        {"symbol": "BBB", "z_h022": 1.0, "future_60d_excess_pp": 2.0},
    ]
    duplicated = deepcopy(base)
    duplicated.extend(deepcopy(base[:2]))
    duplicated.extend(deepcopy(base[:2]))
    assert diagnostic._company_balanced_slope(base) == pytest.approx(2.0)
    assert diagnostic._company_balanced_slope(duplicated) == pytest.approx(2.0)


def test_build_panel_rejects_digest_change(monkeypatch: pytest.MonkeyPatch) -> None:
    unsigned = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "execution_rule_id": "H022-X001",
        "records": [],
    }
    digest = diagnostic._canonical_hash(unsigned)
    report = dict(unsigned)
    report["report_sha256"] = digest
    monkeypatch.setattr(diagnostic, "OUTCOME_REPORT_SHA256", digest)
    monkeypatch.setattr(diagnostic, "EXPECTED_COMPLETE_ROWS", 0)
    panel = diagnostic.build_dependence_panel(report)
    assert panel["record_count"] == 0

    report["schema_version"] = 2
    with pytest.raises(diagnostic.H022DependenceDiagnosticError, match="hash mismatch"):
        diagnostic.build_dependence_panel(report)


def test_summary_positive_synthetic_case(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = []
    for index in range(12):
        signal = float(index)
        rows.append(
            _selection_row(
                f"s{index}",
                f"SYM{index:02d}",
                f"2026-0{1 + index % 2}-01T10:00:00+00:00",
                f"2026-0{1 + index % 2}-02",
                f"2026-0{3 + index % 2}-28",
                signal,
                signal * 0.5 - 2.0,
            )
        )
    for row in rows:
        row.pop("z_h022")
    panel = {
        "schema_version": 1,
        "diagnostic_id": "H022-D004",
        "hypothesis_id": "H022",
        "evidence_class": "POST_OUTCOME_DEPENDENCE_DIAGNOSTIC",
        "outcome_report_sha256": "synthetic",
        "primary_horizon_sessions": 60,
        "record_count": len(rows),
        "records": rows,
    }
    panel["panel_sha256"] = diagnostic._canonical_hash(panel)

    monkeypatch.setattr(diagnostic, "OUTCOME_REPORT_SHA256", "synthetic")
    monkeypatch.setattr(diagnostic, "EXPECTED_COMPLETE_ROWS", 12)
    monkeypatch.setattr(diagnostic, "MIN_REDUCED_ROWS", 10)
    monkeypatch.setattr(diagnostic, "MIN_PUBLICATION_MONTHS", 2)
    monkeypatch.setattr(diagnostic, "BOOTSTRAP_ITERATIONS", 50)

    summary = diagnostic.summarize_dependence(panel)
    assert summary["sign_classification"] == "BROAD_POSITIVE"
    assert summary["sensitivity_flags"] == []
    assert summary["first_event_per_symbol"]["observation_count"] == 12
    assert summary["nonoverlapping_events"]["observation_count"] == 12
