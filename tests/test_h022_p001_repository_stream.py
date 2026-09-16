from __future__ import annotations

import json
from pathlib import Path

from marketlab.h022_p001_stream import validate_e002_ledger, validate_source_ledger
from marketlab.h022_prospective import validate_signal_ledger

ROOT = Path("research/prospective/h022/P001")


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_repository_source_and_e002_ledgers_are_valid_live_state() -> None:
    source = _load(ROOT / "source-ledger.json")
    e002 = _load(ROOT / "e002-ledger.json")

    validate_source_ledger(source)
    validate_e002_ledger(e002)

    assert source["record_count"] == len(source["records"])
    assert e002["record_count"] == len(e002["records"])
    assert source["outcome_data_attached"] is False
    assert e002["outcome_data_attached"] is False
    assert source["live_capital_allowed"] is False
    assert e002["live_capital_allowed"] is False

    source_ids = {record["source"]["source_id"] for record in source["records"]}
    assert all(record["source_id"] in source_ids for record in e002["records"])


def test_repository_signal_ledger_is_valid_live_state_without_outcomes() -> None:
    ledger = _load(ROOT / "signal-ledger.json")

    validate_signal_ledger(ledger)

    assert ledger["record_count"] == len(ledger["records"])
    assert ledger["outcome_data_attached"] is False
    assert all(record["outcome_data_attached"] is False for record in ledger["records"])
