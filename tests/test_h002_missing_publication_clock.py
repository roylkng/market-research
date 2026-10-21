"""Undated official result rows quarantine one H002 name, never the cohort."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from marketlab.prospective import ObservationStore
from marketlab.runner import TARGET_PERIOD_END, H002CohortRunner, RawEvidenceStore

RAW_SOURCE = {
    "data": [
        {
            "type": "Integrated Filing- Financials",
            "symbol": "TEST",
            "consolidated": "Consolidated",
            "qe_Date": "30-Sep-2026",
            "broadcast_Date": None,
            "creationDate": None,
            "xbrl": "https://nsearchives.nseindia.com/corporate/test-first.xml",
        },
        {
            "type": "Integrated Filing- Financials",
            "symbol": "TEST",
            "consolidated": "Consolidated",
            "qe_Date": "30-Sep-2026",
            "broadcast_Date": "21-Oct-2026 16:00:00",
            "xbrl": "https://nsearchives.nseindia.com/corporate/test-second.xml",
        },
    ],
}


class FakeClient:
    def integrated_financial_filings_with_raw(self, symbol):
        if symbol == "CONTROL":
            raw = b'{"data":[]}'
            return json.loads(raw), raw
        raw = json.dumps(RAW_SOURCE, sort_keys=True).encode("utf-8")
        return json.loads(raw), raw


def _runner(tmp_path: Path):
    runner = H002CohortRunner.__new__(H002CohortRunner)
    runner.universe = SimpleNamespace(cohort_id="TEST_FY27_Q2")
    runner.bundle = SimpleNamespace(records_by_symbol={
        name: SimpleNamespace(
            record_id="TEST_IMMUTABLE_" + name,
            expectation=SimpleNamespace(accounting_basis="Consolidated"),
        )
        for name in ("TEST", "CONTROL")
    })
    runner.client = FakeClient()
    runner.observations = ObservationStore(tmp_path)
    runner.raw_store = RawEvidenceStore(tmp_path)
    return runner


def test_undated_matching_first_filing_cannot_be_ignored_for_later_report(
    tmp_path: Path,
):
    runner = _runner(tmp_path)
    at = datetime(2026, 10, 21, 16, 0, tzinfo=UTC)
    tested = runner._run_symbol(
        SimpleNamespace(symbol="TEST"),
        as_of=at,
        discovery_enabled=True,
    )
    assert tested.outcome == "UPDATED"
    assert tested.state == "ERROR"
    assert tested.detail == "unverifiable_integrated_filing_publication_order"
    state = runner.observations.latest(
        "TEST_FY27_Q2", "TEST", TARGET_PERIOD_END
    )
    assert state is not None
    assert state.event is None
    assert state.signal is None
    assert state.paper_position is None
    assert state.evidence["source_clock_verified"] is False
    assert "no parseable official timestamp" in state.evidence["source_clock_error"]
    path = Path(state.evidence["unverifiable_discovery_raw_path"])
    raw = json.dumps(RAW_SOURCE, sort_keys=True).encode("utf-8")
    assert path.exists()
    assert path.read_bytes() == raw
    assert state.evidence["discovery_sha256"] == hashlib.sha256(raw).hexdigest()
    assert state.evidence["unverifiable_discovery_raw_sha256"] == (
        hashlib.sha256(raw).hexdigest()
    )
    assert len(list(
        tmp_path.glob("raw-evidence/unverifiable-result-discovery/sha256/*.json")
    )) == 1


def test_bad_source_does_not_block_unrelated_company_and_is_idempotent(
    tmp_path: Path,
):
    runner = _runner(tmp_path)
    at = datetime(2026, 10, 21, 16, 0, tzinfo=UTC)
    first = runner._run_symbol(
        SimpleNamespace(symbol="TEST"), as_of=at, discovery_enabled=True
    )
    second = runner._run_symbol(
        SimpleNamespace(symbol="TEST"),
        as_of=datetime(2026, 10, 21, 17, tzinfo=UTC),
        discovery_enabled=True,
    )
    good = runner._run_symbol(
        SimpleNamespace(symbol="CONTROL"),
        as_of=at,
        discovery_enabled=True,
    )
    assert first.outcome == "UPDATED"
    assert second.outcome == "UNCHANGED"
    assert good.outcome == "NO_EVENT"
    assert runner.observations.latest(
        "TEST_FY27_Q2", "CONTROL", TARGET_PERIOD_END
    ) is None
    assert runner.observations.latest(
        "TEST_FY27_Q2", "TEST", TARGET_PERIOD_END
    ).sequence == 1
