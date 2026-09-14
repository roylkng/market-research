from __future__ import annotations

import pytest

from marketlab import h022_within_company_diagnostic as diagnostic


def _row(
    symbol: str,
    source_id: str,
    signal: float,
    future: float,
    entry: str,
    exit_day: str,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "symbol": symbol,
        "exchange_published_at_utc": f"{entry}T00:00:00+00:00",
        "publication_month": entry[:7],
        "entry_session_date": entry,
        "exit_session_date": exit_day,
        "h022_signal": signal,
        "future_60d_excess_pp": future,
    }


def test_within_slope_removes_company_level_intercepts() -> None:
    rows = [
        {"symbol": "AAA", "z_h022": -1.0, "future_60d_excess_pp": 98.0},
        {"symbol": "AAA", "z_h022": 1.0, "future_60d_excess_pp": 102.0},
        {"symbol": "BBB", "z_h022": -1.0, "future_60d_excess_pp": -102.0},
        {"symbol": "BBB", "z_h022": 1.0, "future_60d_excess_pp": -98.0},
    ]
    assert diagnostic._within_slope(rows) == pytest.approx(2.0)


def test_highest_lowest_pair_selection_uses_signal_not_future_return() -> None:
    rows = [
        _row("AAA", "low", -2.0, 1000.0, "2026-01-02", "2026-03-31"),
        _row("AAA", "mid", 0.0, -1000.0, "2026-04-02", "2026-06-30"),
        _row("AAA", "high", 3.0, 5.0, "2026-07-02", "2026-09-30"),
        _row("BBB", "same1", 1.0, 1.0, "2026-01-02", "2026-03-31"),
        _row("BBB", "same2", 1.0, 2.0, "2026-04-02", "2026-06-30"),
    ]
    pairs = diagnostic.highest_lowest_pairs(rows)
    assert len(pairs) == 1
    assert pairs[0]["symbol"] == "AAA"
    assert pairs[0]["low_source_id"] == "low"
    assert pairs[0]["high_source_id"] == "high"
    assert pairs[0]["high_minus_low_future_excess_pp"] == pytest.approx(-995.0)


def test_input_hash_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = {
        "schema_version": 1,
        "diagnostic_id": "H022-D004",
        "records": [],
    }
    digest = diagnostic._canonical_hash(panel)
    panel["panel_sha256"] = digest
    monkeypatch.setattr(diagnostic, "INPUT_PANEL_SHA256", digest)
    monkeypatch.setattr(diagnostic, "EXPECTED_ROWS", 0)
    assert diagnostic.validate_input_panel(panel) == []

    panel["schema_version"] = 2
    with pytest.raises(diagnostic.H022WithinCompanyDiagnosticError, match="hash mismatch"):
        diagnostic.validate_input_panel(panel)


def test_summary_positive_synthetic_case(monkeypatch: pytest.MonkeyPatch) -> None:
    rows: list[dict[str, object]] = []
    for company in range(12):
        base = float(company - 6)
        rows.append(
            _row(
                f"SYM{company:02d}",
                f"{company}-low",
                -1.0,
                base - 2.0,
                "2025-10-01",
                "2025-12-30",
            )
        )
        rows.append(
            _row(
                f"SYM{company:02d}",
                f"{company}-high",
                1.0,
                base + 2.0,
                "2026-01-05",
                "2026-04-03",
            )
        )

    panel = {
        "schema_version": 1,
        "diagnostic_id": "H022-D004",
        "hypothesis_id": "H022",
        "record_count": len(rows),
        "records": rows,
    }
    panel["panel_sha256"] = diagnostic._canonical_hash(panel)

    monkeypatch.setattr(diagnostic, "INPUT_PANEL_SHA256", panel["panel_sha256"])
    monkeypatch.setattr(diagnostic, "EXPECTED_ROWS", len(rows))
    monkeypatch.setattr(diagnostic, "MIN_FULL_SYMBOLS", 10)
    monkeypatch.setattr(diagnostic, "MIN_FULL_ROWS", 20)
    monkeypatch.setattr(diagnostic, "MIN_NONOVERLAP_SYMBOLS", 10)
    monkeypatch.setattr(diagnostic, "MIN_NONOVERLAP_ROWS", 20)
    monkeypatch.setattr(diagnostic, "MIN_PAIRS", 10)
    monkeypatch.setattr(diagnostic, "BOOTSTRAP_ITERATIONS", 50)

    summary = diagnostic.summarize_within_company(panel)
    assert summary["sign_classification"] == "WITHIN_POSITIVE"
    assert summary["company_fixed_effect"]["standardized_h022_within_slope_pp"] > 0
    assert summary["nonoverlap_company_fixed_effect"]["standardized_h022_within_slope_pp"] > 0
    assert summary["highest_vs_lowest_signal_pair"]["mean_high_minus_low_excess_pp"] == pytest.approx(4.0)
