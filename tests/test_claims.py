from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from marketlab.claims import (
    ClaimLedger,
    ClaimLedgerError,
    ClaimOutcome,
    ManagementClaim,
    load_claim_ledger,
)

LEDGER = Path("research/company-intelligence/claims_v1.yaml")


def _claim(claim_id: str, *, source_date: str, status: str = "CLOSED") -> ManagementClaim:
    return ManagementClaim(
        claim_id=claim_id,
        symbol="TEST",
        source_date=source_date,
        source_url=f"https://example.com/{claim_id}",
        source_type="EARNINGS_CALL_TRANSCRIPT",
        source_locator="p.1",
        claim_type="CAPACITY_COMMISSIONING",
        metric="capacity",
        unit="units",
        target_min=100.0,
        target_max=None,
        target_deadline="2026-12-31",
        target_horizon="FY27",
        normalized_claim="Test claim",
        status=status,
    )


def _outcome(
    outcome_id: str,
    claim_id: str,
    *,
    observed_date: str,
    status: str,
) -> ClaimOutcome:
    return ClaimOutcome(
        outcome_id=outcome_id,
        claim_id=claim_id,
        observed_date=observed_date,
        source_url=f"https://example.com/{outcome_id}",
        source_type="EARNINGS_PRESENTATION",
        source_locator="p.2",
        status=status,
        observed_value=None,
        observed_unit=None,
        observed_is_approximate=False,
        normalized_observation="Test outcome",
    )


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


def test_company_report_as_of_excludes_future_outcome():
    ledger = load_claim_ledger(LEDGER)

    before = ledger.company_report_as_of("CCL", "2025-05-05")
    assert before["claim_count"] == 1
    assert before["latest_outcome_count"] == 0
    assert before["pending_without_outcome_count"] == 1
    assert before["resolved_count"] == 0
    assert before["met_rate_resolved"] is None

    after = ledger.company_report_as_of("CCL", "2025-05-06")
    assert after["latest_outcome_count"] == 1
    assert after["status_counts"]["MET"] == 1
    assert after["met_rate_resolved"] == 1.0


def test_as_of_feature_requires_three_resolved_claims_and_ignores_future_evidence():
    claims = tuple(
        _claim(f"C{i}", source_date="2025-01-01", status="CLOSED") for i in range(1, 4)
    )
    outcomes = (
        _outcome("O1", "C1", observed_date="2025-02-01", status="MET"),
        _outcome("O2", "C2", observed_date="2025-03-01", status="MISSED"),
        _outcome("O3", "C3", observed_date="2025-10-01", status="MET"),
    )
    ledger = ClaimLedger(version=1, mode="HISTORICAL_RECONSTRUCTION", claims=claims, outcomes=outcomes)

    june = ledger.delivery_feature_as_of("TEST", "2025-06-30", min_resolved_claims=3)
    assert june["resolved_count"] == 2
    assert june["signal_state"] == "NO_SIGNAL"
    assert june["value"] is None

    december = ledger.delivery_feature_as_of("TEST", "2025-12-31", min_resolved_claims=3)
    assert december["resolved_count"] == 3
    assert december["status_counts"]["MET"] == 2
    assert december["status_counts"]["MISSED"] == 1
    assert december["signal_state"] == "ELIGIBLE"
    assert december["value"] == pytest.approx(2 / 3)


def test_as_of_feature_does_not_use_current_claim_lifecycle_status():
    claims = tuple(_claim(f"C{i}", source_date="2025-01-01", status="CLOSED") for i in range(3))
    outcomes = tuple(
        _outcome(f"O{i}", f"C{i}", observed_date="2025-02-01", status="MET")
        for i in range(3)
    )
    ledger = ClaimLedger(version=1, mode="HISTORICAL_RECONSTRUCTION", claims=claims, outcomes=outcomes)
    feature = ledger.delivery_feature_as_of("TEST", "2025-03-01")
    assert feature["signal_state"] == "ELIGIBLE"
    assert feature["value"] == 1.0


def test_claim_published_after_as_of_is_excluded_even_if_ledger_contains_it():
    claims = (
        _claim("C1", source_date="2025-01-01"),
        _claim("C2", source_date="2026-01-01"),
    )
    outcomes = (
        _outcome("O1", "C1", observed_date="2025-02-01", status="MET"),
        _outcome("O2", "C2", observed_date="2026-02-01", status="MET"),
    )
    ledger = ClaimLedger(version=1, mode="HISTORICAL_RECONSTRUCTION", claims=claims, outcomes=outcomes)
    report = ledger.company_report_as_of("TEST", "2025-12-31")
    assert report["claim_count"] == 1
    assert report["resolved_count"] == 1


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
