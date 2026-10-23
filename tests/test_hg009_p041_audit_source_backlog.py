"""Exact-identity and missing-source fail-closed tests for P041."""
import csv
import importlib.util
from pathlib import Path

import pytest

FILE = Path(__file__).resolve().parents[1] / "scripts/hg009_p041_audit_source_backlog.py"
SPEC = importlib.util.spec_from_file_location("p041_audit", FILE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_real_queue_counts_and_no_false_admission():
    result = MODULE.audit()
    assert result["original_denominator"] == 300
    assert result["uncovered"] == 158
    assert result["by_arm"] == {"ONE_LANE": 57, "SELECTED": 54, "ZERO_LANE": 47}
    assert result["source_verified"] == 0
    assert result["next_trial_admitted"] is False


def test_reject_backlog_identity_edit(tmp_path):
    rows = list(csv.DictReader(MODULE.BACKLOG.open(newline="", encoding="utf-8")))
    rows[0]["isin"] = "INEFAKE"
    new_file = tmp_path / "queue.csv"
    with new_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MODULE.FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="identity mismatch"):
        MODULE.audit(backlog_path=new_file)


def test_reject_pretend_receipt(tmp_path):
    rows = list(csv.DictReader(MODULE.BACKLOG.open(newline="", encoding="utf-8")))
    rows[0]["classification_status"] = "VERIFIED"
    new_file = tmp_path / "queue.csv"
    with new_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MODULE.FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="not evidence"):
        MODULE.audit(backlog_path=new_file)
