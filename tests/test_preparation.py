from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.events import EventStore
from marketlab.expectations import ExpectationStore
from marketlab.nse import NSEAcquisitionError
from marketlab.preparation import (
    PreparationError,
    PreparationStore,
    analyze_eps_basis_actions,
    build_preparation_report,
    freeze_complete_bundle,
    prepare_symbol,
    select_baseline_candidate,
)
from marketlab.universe import UniverseMember, UniverseSnapshot


BASELINE_HTML = b"""<html><table>
<tr><td>NSE Symbol</td><td>TESTCO</td></tr>
<tr><td>ISIN</td><td>INE000A01001</td></tr>
<tr><td>Name of company</td><td>Test Company Ltd.</td></tr>
<tr><td>Date of start of financial year</td><td>01-04-2025</td></tr>
<tr><td>Date of end of financial year</td><td>31-03-2026</td></tr>
<tr><td>Date of start of reporting period</td><td>01-07-2025</td></tr>
<tr><td>Date of end of reporting period</td><td>30-09-2025</td></tr>
<tr><td>Reporting Type</td><td>Quarterly</td></tr>
<tr><td>Reporting Quarter</td><td>Second quarter</td></tr>
<tr><td>Nature of report standalone or consolidated</td><td>Consolidated</td></tr>
<tr><td>Basic earnings (loss) per share from continuing and discontinued operations</td><td>10.00</td></tr>
</table></html>"""


def _universe(two: bool = False) -> UniverseSnapshot:
    members = [
        UniverseMember(
            rank=1,
            source_rank=1,
            symbol="TESTCO",
            isin="INE000A01001",
            ffmc=100.0,
            company_name="Test Company Ltd.",
            constituent_industry="Information Technology",
            series="EQ",
        )
    ]
    if two:
        members.append(
            UniverseMember(
                rank=2,
                source_rank=2,
                symbol="OTHER",
                isin="INE000A01002",
                ffmc=90.0,
                company_name="Other Ltd.",
                constituent_industry="Healthcare",
                series="EQ",
            )
        )
    provisional = UniverseSnapshot(
        schema_version=2,
        rule_version="U001-test",
        cohort_id="FY27-Q2-TEST",
        captured_at_utc="2026-09-01T00:00:00Z",
        index_name="NIFTY 200",
        index_timestamp="01-Sep-2026 16:00:00",
        selection_size=len(members),
        source_urls={"index": "https://example.invalid/index"},
        source_hashes={"index": "a" * 64},
        members=members,
        sha256="b" * 64,
    )
    return provisional


def _payload(*rows):
    return {"data": list(rows)}


def _row(**changes):
    row = {
        "type": "Integrated Filing- Financials",
        "symbol": "TESTCO",
        "cmName": "Test Company Ltd.",
        "consolidated": "Consolidated",
        "qe_Date": "30-Sep-2025",
        "broadcast_Date": "17-Oct-2025 19:36:44",
        "xbrl": "https://nsearchives.nseindia.com/corporate/ixbrl/test_WEB.html",
    }
    row.update(changes)
    return row


class FakeClient:
    def __init__(self, *, filing_payload=None, action_payload=None, source=BASELINE_HTML):
        self.filing_payload = filing_payload if filing_payload is not None else _payload(_row())
        self.action_payload = action_payload if action_payload is not None else []
        self.source = source

    def integrated_financial_filings_with_raw(self, symbol):
        raw = json.dumps(self.filing_payload, sort_keys=True).encode()
        return self.filing_payload, raw

    def corporate_actions_with_raw(self, symbol, *, from_date, to_date):
        raw = json.dumps(self.action_payload, sort_keys=True).encode()
        return self.action_payload, raw

    def archive_bytes(self, url):
        return self.source


def test_selects_latest_official_revision_deterministically():
    payload = _payload(
        _row(broadcast_Date="17-Oct-2025 18:00:00", xbrl="https://nsearchives.nseindia.com/old.html"),
        _row(broadcast_Date="17-Oct-2025 19:36:44", xbrl="https://nsearchives.nseindia.com/new.html"),
    )
    selected = select_baseline_candidate(
        payload, symbol="TESTCO", baseline_period_end="2025-09-30"
    )
    assert selected.source_url.endswith("new.html")
    assert selected.revision_count == 2
    assert selected.exchange_available_at_utc == "2025-10-17T14:06:44Z"


def test_same_timestamp_different_urls_is_ambiguous():
    payload = _payload(_row(xbrl="https://nsearchives.nseindia.com/a.html"), _row(xbrl="https://nsearchives.nseindia.com/b.html"))
    with pytest.raises(PreparationError, match="AMBIGUOUS"):
        select_baseline_candidate(payload, symbol="TESTCO", baseline_period_end="2025-09-30")


def test_wrong_basis_and_wrong_period_do_not_become_baseline():
    payload = _payload(
        _row(consolidated="Standalone"),
        _row(qe_Date="30-Jun-2025"),
    )
    with pytest.raises(PreparationError, match="NO_BASELINE"):
        select_baseline_candidate(payload, symbol="TESTCO", baseline_period_end="2025-09-30")


def test_bonus_and_split_adjustment_is_deterministic():
    actions = [
        {"symbol": "TESTCO", "subject": "Bonus 1:1", "exDate": "01-Jan-2026"},
        {
            "symbol": "TESTCO",
            "subject": "Face Value Split (Sub-Division) - From Rs 10 Per Share To Rs 2 Per Share",
            "exDate": "01-Jun-2026",
        },
        {"symbol": "TESTCO", "subject": "Dividend - Rs 10 Per Share", "exDate": "01-Jul-2026"},
    ]
    raw = json.dumps(actions).encode()
    result = analyze_eps_basis_actions(
        actions,
        raw_payload=raw,
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
        as_of_utc="2026-09-06T12:00:00Z",
    )
    assert result.status == "READY"
    assert result.factor == pytest.approx(0.1)
    assert result.version.startswith("EPSCA-")
    assert len(result.relevant_actions) == 2


def test_unparseable_share_change_fails_closed():
    actions = [{"symbol": "TESTCO", "subject": "Bonus issue approved", "exDate": "01-Jan-2026"}]
    result = analyze_eps_basis_actions(
        actions,
        raw_payload=json.dumps(actions).encode(),
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
        as_of_utc="2026-09-06T12:00:00Z",
    )
    assert result.status == "UNRESOLVED"
    assert result.factor is None


def test_rights_issue_is_unresolved_not_guessed():
    actions = [{"symbol": "TESTCO", "subject": "Rights Issue 1:5", "exDate": "01-Jan-2026"}]
    result = analyze_eps_basis_actions(
        actions,
        raw_payload=json.dumps(actions).encode(),
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
        as_of_utc="2026-09-06T12:00:00Z",
    )
    assert result.status == "UNRESOLVED"


def test_prepare_symbol_captures_complete_source_provenance(tmp_path):
    universe = _universe()
    prep = PreparationStore(tmp_path)
    attempt = prepare_symbol(
        FakeClient(),
        universe=universe,
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
        attempted_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
        event_store=EventStore(tmp_path),
        expectation_store=ExpectationStore(tmp_path, clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC)),
        preparation_store=prep,
    )
    assert attempt.outcome == "CAPTURED"
    assert attempt.expectation_id is not None
    assert attempt.expectation_record_id is not None
    assert attempt.baseline_source_sha256 is not None
    assert attempt.discovery_payload_sha256 is not None
    assert attempt.corporate_action_payload_sha256 is not None
    assert attempt.corporate_action_factor == 1.0
    assert prep.latest(universe.cohort_id, "TESTCO") == attempt


def test_prepare_symbol_records_no_baseline_reason(tmp_path):
    universe = _universe()
    attempt = prepare_symbol(
        FakeClient(filing_payload={"data": []}),
        universe=universe,
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
        attempted_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
        event_store=EventStore(tmp_path),
        expectation_store=ExpectationStore(tmp_path, clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC)),
        preparation_store=PreparationStore(tmp_path),
    )
    assert attempt.outcome == "UNCOVERED"
    assert attempt.reason_code == "NO_BASELINE_FILING"
    assert attempt.discovery_payload_sha256 is not None


def test_prepare_symbol_records_unresolved_corporate_action(tmp_path):
    actions = [{"symbol": "TESTCO", "subject": "Bonus issue approved", "exDate": "01-Jan-2026"}]
    universe = _universe()
    attempt = prepare_symbol(
        FakeClient(action_payload=actions),
        universe=universe,
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
        attempted_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
        event_store=EventStore(tmp_path),
        expectation_store=ExpectationStore(tmp_path, clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC)),
        preparation_store=PreparationStore(tmp_path),
    )
    assert attempt.reason_code == "UNRESOLVED_CORPORATE_ACTION"
    assert attempt.corporate_action_payload_sha256 is not None


def test_report_requires_every_company_captured_for_v1_freeze(tmp_path):
    universe = _universe(two=True)
    prep = PreparationStore(tmp_path)
    first = replace(
        prepare_symbol(
            FakeClient(),
            universe=universe,
            symbol="TESTCO",
            baseline_period_end="2025-09-30",
            attempted_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
            event_store=EventStore(tmp_path),
            expectation_store=ExpectationStore(tmp_path, clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC)),
            preparation_store=prep,
        )
    )
    assert first.outcome == "CAPTURED"
    report = build_preparation_report(
        universe=universe,
        preparation_store=prep,
        baseline_period_end="2025-09-30",
        generated_at=datetime(2026, 9, 6, 13, tzinfo=UTC),
    )
    assert report.captured_count == 1
    assert report.uncovered_count == 1
    assert report.freeze_ready is False
    with pytest.raises(PreparationError, match="not freeze-ready"):
        freeze_complete_bundle(
            universe=universe,
            expectation_store=ExpectationStore(tmp_path),
            preparation_store=prep,
            baseline_period_end="2025-09-30",
            generated_at=datetime(2026, 9, 6, 13, tzinfo=UTC),
        )


def test_network_failure_is_evidence_not_silent_omission(tmp_path):
    class Broken(FakeClient):
        def integrated_financial_filings_with_raw(self, symbol):
            raise NSEAcquisitionError("offline")

    universe = _universe()
    attempt = prepare_symbol(
        Broken(),
        universe=universe,
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
        attempted_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
        event_store=EventStore(tmp_path),
        expectation_store=ExpectationStore(tmp_path, clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC)),
        preparation_store=PreparationStore(tmp_path),
    )
    assert attempt.reason_code == "DISCOVERY_FETCH_FAILED"
    assert "offline" in (attempt.detail or "")
