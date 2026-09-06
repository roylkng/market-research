from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from marketlab.claims import ClaimLedgerError, load_claim_ledger

LEDGER = Path("research/company-intelligence/claims_v1.yaml")


def test_published_claim_ledger_is_valid_and_reports_first_three_companies():
    ledger = load_claim_ledger(LEDGER)

    ccl = ledger.company_report("CCL")
    assert ccl["claim_count"] == 1
    assert ccl["status_counts"]["MET"] == 1
    assert ccl["met_rate_resolved"] == 1.0

    shaily = ledger.company_report("SHAILY")
    assert shaily["status_counts"]["LATE"] == 1
    assert shaily["met_rate_resolved"] == 0.0

    netweb = ledger.company_report("NETWEB")
    assert netweb["status_counts"]["MET"] == 1
    assert netweb["claims"][0]["latest_outcome"]["observed_value"] == 29.0


def test_outcome_cannot_precede_claim(tmp_path):
    document = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    document["outcomes"][0]["observed_date"] = "2024-01-01"
    document["outcomes"][0]["outcome_hash"] = None
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    with pytest.raises(ClaimLedgerError, match="outcome precedes claim"):
        load_claim_ledger(path)


def test_claim_content_change_breaks_frozen_hash(tmp_path):
    document = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    document["claims"][0]["target_min"] = 11.0
    path = tmp_path / "mutated.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    with pytest.raises(ClaimLedgerError, match="claim_hash mismatch"):
        load_claim_ledger(path)


def test_unresolved_outcome_is_valid_and_not_counted_as_resolved(tmp_path):
    document = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    document["outcomes"][0].update(
        {
            "status": "UNRESOLVED",
            "observed_value": None,
            "observed_unit": None,
            "normalized_observation": "Evidence exists but does not resolve the numeric target.",
            "outcome_hash": None,
        }
    )
    path = tmp_path / "unresolved.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    ledger = load_claim_ledger(path)
    report = ledger.company_report("CCL")
    assert report["resolved_count"] == 0
    assert report["status_counts"]["UNRESOLVED"] == 1
    assert report["met_rate_resolved"] is None


def test_numeric_outcome_requires_unit(tmp_path):
    document = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    document["outcomes"][0]["observed_unit"] = None
    document["outcomes"][0]["outcome_hash"] = None
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    with pytest.raises(ClaimLedgerError, match="observed_unit required"):
        load_claim_ledger(path)
