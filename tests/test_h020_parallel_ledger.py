from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_h020_parallel.py"
spec = importlib.util.spec_from_file_location("run_h020_parallel", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_zero_parallel_ledger_validates() -> None:
    ledger = module.new_ledger()
    module.validate_ledger(ledger)
    assert ledger["record_count"] == 0
    assert ledger["records"] == []
    assert ledger["prospective_start_session"] == "2026-09-16"
    assert ledger["outcome_data_attached"] is False
    assert ledger["live_capital_allowed"] is False


def test_parallel_ledger_rejects_tamper() -> None:
    ledger = module.new_ledger()
    ledger["prospective_start_session"] = "2026-09-15"
    with pytest.raises(ValueError, match="hash mismatch"):
        module.validate_ledger(ledger)


def test_parallel_ledger_rejects_duplicate_session() -> None:
    record = {
        "as_of_session": "2026-09-16",
        "results": [],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    record["record_sha256"] = module.canonical_hash(record)
    ledger = module.new_ledger()
    ledger["records"] = [record, dict(record)]
    ledger = module.seal_ledger(ledger)
    with pytest.raises(ValueError, match="duplicate H020 parallel session"):
        module.validate_ledger(ledger)
