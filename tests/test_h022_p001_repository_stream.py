from __future__ import annotations

import json
from pathlib import Path

from marketlab.h022_p001_stream import (
    new_e002_ledger,
    new_source_ledger,
    validate_e002_ledger,
    validate_source_ledger,
)
from marketlab.h022_prospective import validate_signal_ledger

ROOT = Path("research/prospective/h022/P001")


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_repository_source_and_e002_ledgers_are_exact_empty_seeds() -> None:
    source = _load(ROOT / "source-ledger.json")
    e002 = _load(ROOT / "e002-ledger.json")
    assert source == new_source_ledger()
    assert e002 == new_e002_ledger()
    validate_source_ledger(source)
    validate_e002_ledger(e002)


def test_repository_signal_ledger_is_still_empty_before_boundary() -> None:
    ledger = _load(ROOT / "signal-ledger.json")
    validate_signal_ledger(ledger)
    assert ledger["record_count"] == 0
    assert ledger["records"] == []
