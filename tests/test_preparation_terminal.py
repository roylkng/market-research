from __future__ import annotations

import json
from datetime import UTC, datetime

from marketlab.events import EventStore
from marketlab.expectations import ExpectationStore
from marketlab.preparation import (
    PreparationStore,
    freeze_complete_bundle,
    prepare_symbol,
    select_baseline_candidate,
    select_preferred_baseline_candidate,
)
from marketlab.universe import UniverseMember, UniverseSnapshot


def _row(**changes):
    row = {
        "type": "Integrated Filing- Financials",
        "symbol": "TESTCO",
        "cmName": "Test Company Ltd.",
        "consolidated": "Consolidated",
        "qe_Date": "30-Sep-2025",
        "broadcast_Date": "17-Oct-2025 19:36:44",
        "xbrl": "https://nsearchives.nseindia.com/test.html",
    }
    row.update(changes)
    return row


def _universe() -> UniverseSnapshot:
    return UniverseSnapshot(
        schema_version=2,
        rule_version="U001-test",
        cohort_id="FY27-Q2-TERMINAL-TEST",
        captured_at_utc="2026-09-01T00:00:00Z",
        index_name="NIFTY 200",
        index_timestamp="01-Sep-2026 16:00:00",
        selection_size=1,
        source_urls={"index": "https://example.invalid/index"},
        source_hashes={"index": "a" * 64},
        members=[
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
        ],
        sha256="b" * 64,
    )


def _html(symbol: str = "TESTCO", basis: str = "Consolidated") -> bytes:
    return f"""<html><table>
<tr><td>NSE Symbol</td><td>{symbol}</td></tr>
<tr><td>ISIN</td><td>INE000A01001</td></tr>
<tr><td>Name of company</td><td>Test Company Ltd.</td></tr>
<tr><td>Date of start of reporting period</td><td>01-07-2025</td></tr>
<tr><td>Date of end of reporting period</td><td>30-09-2025</td></tr>
<tr><td>Reporting Type</td><td>Quarterly</td></tr>
<tr><td>Reporting Quarter</td><td>Second quarter</td></tr>
<tr><td>Nature of report standalone or consolidated</td><td>{basis}</td></tr>
<tr><td>Basic earnings (loss) per share from continuing and discontinued operations</td><td>10.00</td></tr>
</table></html>""".encode()


class Client:
    def __init__(self, *, filing_payload, source, actions=None):
        self.filing_payload = filing_payload
        self.source = source
        self.actions = [] if actions is None else actions

    def integrated_financial_filings_with_raw(self, symbol):
        raw = json.dumps(self.filing_payload, sort_keys=True).encode()
        return self.filing_payload, raw

    def corporate_actions_with_raw(self, symbol, *, from_date, to_date):
        raw = json.dumps(self.actions, sort_keys=True).encode()
        return self.actions, raw

    def archive_bytes(self, url):
        return self.source


def _prepare(tmp_path, client):
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    universe = _universe()
    expectation_store = ExpectationStore(tmp_path, clock=lambda: now)
    preparation_store = PreparationStore(tmp_path)
    attempt = prepare_symbol(
        client,
        universe=universe,
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
        attempted_at=now,
        event_store=EventStore(tmp_path),
        expectation_store=expectation_store,
        preparation_store=preparation_store,
    )
    return attempt, expectation_store, preparation_store


def test_preferred_baseline_uses_standalone_only_when_consolidated_absent():
    payload = {"data": [_row(consolidated="Standalone")]}
    selected = select_preferred_baseline_candidate(
        payload, symbol="TESTCO", baseline_period_end="2025-09-30"
    )
    assert selected.accounting_basis == "Standalone"

    payload["data"].append(_row(consolidated="Consolidated"))
    selected = select_preferred_baseline_candidate(
        payload, symbol="TESTCO", baseline_period_end="2025-09-30"
    )
    assert selected.accounting_basis == "Consolidated"


def test_revision_and_creation_timestamps_are_official_availability_fallbacks():
    revision = select_baseline_candidate(
        {
            "data": [
                _row(
                    broadcast_Date=None,
                    revised_Date="27-JAN-2026 15:16:51",
                    creation_Date="27-Jan-2026 15:16:52",
                )
            ]
        },
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
    )
    assert revision.exchange_available_at_utc == "2026-01-27T09:46:51Z"

    creation = select_baseline_candidate(
        {
            "data": [
                _row(
                    broadcast_Date=None,
                    revised_Date=None,
                    creation_Date="27-Jan-2026 15:16:52",
                )
            ]
        },
        symbol="TESTCO",
        baseline_period_end="2025-09-30",
    )
    assert creation.exchange_available_at_utc == "2026-01-27T09:46:52Z"


def test_standalone_company_captures_a_normal_expectation(tmp_path):
    payload = {"data": [_row(consolidated="Standalone")]}
    attempt, expectation_store, preparation_store = _prepare(
        tmp_path, Client(filing_payload=payload, source=_html(basis="Standalone"))
    )
    assert attempt.outcome == "CAPTURED"
    assert attempt.reason_code == "CAPTURED"
    bundle = freeze_complete_bundle(
        universe=_universe(),
        expectation_store=expectation_store,
        preparation_store=preparation_store,
        baseline_period_end="2025-09-30",
        generated_at=datetime(2026, 9, 6, 13, tzinfo=UTC),
    )
    assert bundle.expectations[0].expectation.accounting_basis == "Standalone"
    assert bundle.expectations[0].expectation.status == "READY"


def test_same_isin_historical_symbol_change_freezes_no_signal(tmp_path):
    payload = {"data": [_row()]}
    attempt, expectation_store, preparation_store = _prepare(
        tmp_path, Client(filing_payload=payload, source=_html(symbol="OLDCO"))
    )
    assert attempt.outcome == "CAPTURED"
    assert attempt.reason_code == "CAPTURED_NO_SIGNAL"
    assert "ISIN matched" in (attempt.detail or "")
    bundle = freeze_complete_bundle(
        universe=_universe(),
        expectation_store=expectation_store,
        preparation_store=preparation_store,
        baseline_period_end="2025-09-30",
        generated_at=datetime(2026, 9, 6, 13, tzinfo=UTC),
    )
    expectation = bundle.expectations[0].expectation
    assert expectation.symbol == "TESTCO"
    assert expectation.status == "NO_SIGNAL"
    assert expectation.expected_eps is None
    assert expectation.baseline_basic_eps == 10.0
    assert expectation.no_signal_reason == "baseline_identity_mismatch"


def test_exact_discovery_and_action_payloads_are_content_addressed(tmp_path):
    payload = {"data": [_row()]}
    attempt, _, _ = _prepare(
        tmp_path, Client(filing_payload=payload, source=_html())
    )
    assert attempt.discovery_payload_sha256 is not None
    assert attempt.corporate_action_payload_sha256 is not None
    discovery = (
        tmp_path
        / "h002-inputs"
        / "integrated-financial-filings"
        / "sha256"
        / f"{attempt.discovery_payload_sha256}.bin"
    )
    actions = (
        tmp_path
        / "h002-inputs"
        / "corporate-actions"
        / "sha256"
        / f"{attempt.corporate_action_payload_sha256}.bin"
    )
    assert discovery.exists()
    assert actions.exists()
    assert json.loads(discovery.read_bytes()) == payload
    assert json.loads(actions.read_bytes()) == []
