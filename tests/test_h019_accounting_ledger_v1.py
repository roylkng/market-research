from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import h019_accounting_ledger_v1 as ledger


def _record(year: int, available: str, suffix: str) -> dict[str, object]:
    return {
        "symbol": "TEST",
        "group": "SURVIVOR_PROXY",
        "company": "Test Limited",
        "from_year": year - 1,
        "to_year": year,
        "available_at": available,
        "broadcast_dttm": "",
        "disseminationDateTime": "",
        "report_url": f"https://nsearchives.nseindia.com/annual_reports/test-{suffix}.pdf",
        "api_source_sha256": "a" * 64,
    }


def _observation(*, fiscal_year: int, available: str, report_year: int, value: float, ident: str) -> dict[str, object]:
    return {
        "observation_id": ident,
        "symbol": "TEST",
        "group": "SURVIVOR_PROXY",
        "fact": "revenue",
        "fiscal_year_to": fiscal_year,
        "period_role": "CURRENT" if fiscal_year == report_year else "PRIOR_COMPARATIVE",
        "observed_in_report_to_year": report_year,
        "available_at": available,
        "value": value,
        "normalized_unit": "INR",
        "report_url": "https://nsearchives.nseindia.com/annual_reports/test.pdf",
        "report_sha256": "b" * 64,
        "pdf_sha256": "c" * 64,
        "statement": "PROFIT_AND_LOSS",
        "page_number": 10,
        "source_line": "Revenue From Operations 100 90",
        "derivation": "DIRECT",
    }


def test_report_selection_is_metadata_first_and_limited_to_two_years() -> None:
    records = [
        _record(2018, "2018-07-01T12:00:00+05:30", "2018"),
        _record(2019, "2019-07-01T12:00:00+05:30", "2019-old"),
        _record(2019, "2019-08-01T12:00:00+05:30", "2019-new"),
        _record(2020, "2020-09-01T12:00:00+05:30", "2020"),
        _record(2021, "2020-09-15T12:00:00+05:30", "2021-label"),
        _record(2020, "2020-11-01T12:00:00+05:30", "2020-future"),
    ]
    selected = ledger.freeze_report_selection(records)
    assert [row["to_year"] for row in selected] == [2020, 2019]
    assert str(selected[1]["report_url"]).endswith("2019-new.pdf")
    assert all(datetime.fromisoformat(str(row["available_at"])) <= ledger.CUTOFF for row in selected)


def test_later_comparative_restatement_only_supersedes_after_publication() -> None:
    earlier = _observation(
        fiscal_year=2019,
        available="2019-07-01T12:00:00+05:30",
        report_year=2019,
        value=100.0,
        ident="earlier",
    )
    restated = _observation(
        fiscal_year=2019,
        available="2020-08-01T12:00:00+05:30",
        report_year=2020,
        value=110.0,
        ident="restated",
    )

    before, ambiguities = ledger.resolve_as_of(
        [earlier, restated],
        datetime.fromisoformat("2020-01-01T00:00:00+05:30"),
    )
    assert ambiguities == []
    assert len(before) == 1
    assert before[0]["value"] == 100.0
    assert before[0]["resolved_from_observation_id"] == "earlier"

    after, ambiguities = ledger.resolve_as_of([earlier, restated], ledger.CUTOFF)
    assert ambiguities == []
    assert len(after) == 1
    assert after[0]["value"] == 110.0
    assert after[0]["resolved_from_observation_id"] == "restated"


def test_future_observation_is_never_resolved() -> None:
    visible = _observation(
        fiscal_year=2020,
        available="2020-09-01T12:00:00+05:30",
        report_year=2020,
        value=200.0,
        ident="visible",
    )
    future = _observation(
        fiscal_year=2020,
        available="2020-11-01T12:00:00+05:30",
        report_year=2021,
        value=999.0,
        ident="future",
    )
    resolved, ambiguities = ledger.resolve_as_of([visible, future], ledger.CUTOFF)
    assert ambiguities == []
    assert len(resolved) == 1
    assert resolved[0]["value"] == 200.0
    assert resolved[0]["resolved_from_observation_id"] == "visible"


def test_same_timestamp_conflict_fails_closed() -> None:
    first = _observation(
        fiscal_year=2020,
        available="2020-09-01T12:00:00+05:30",
        report_year=2020,
        value=200.0,
        ident="first",
    )
    second = _observation(
        fiscal_year=2020,
        available="2020-09-01T12:00:00+05:30",
        report_year=2020,
        value=201.0,
        ident="second",
    )
    resolved, ambiguities = ledger.resolve_as_of([first, second], ledger.CUTOFF)
    assert resolved == []
    assert len(ambiguities) == 1
    assert ambiguities[0]["status"] == "AMBIGUOUS_LATEST_OBSERVATION"


def test_consecutive_triple_requires_contiguous_fiscal_years() -> None:
    assert ledger.consecutive_triple({2018, 2019, 2020}) == [2018, 2019, 2020]
    assert ledger.consecutive_triple({2017, 2019, 2020}) is None
    assert ledger.consecutive_triple({2017, 2018, 2019, 2021}) == [2017, 2018, 2019]
