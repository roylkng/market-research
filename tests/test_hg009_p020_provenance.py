"""Negative security checks for the additional provenance gate."""
from dataclasses import replace
from hashlib import sha256

from marketlab.hg009_p019_expectations import Case, Scenario
from marketlab.hg009_p020_provenance import (
    REQUIRED_ROLES,
    SourceEvidence,
    evaluate_with_provenance,
)


def case():
    return Case(
        symbol="ACE", price_inr=100, fully_diluted_shares_cr=10,
        shares_source="reviewed cap table", price_source="NSE",
        owner_cash_source="reviewed bridge",
        scenarios=(Scenario("base", 1, 100, 10),),
        as_of="2026-10-16", terminal_years=3,
        execution_cost_fraction=0.01, annual_discount_rate=0.1,
        independent_probability_basis="frozen validation",
    )


def evidence():
    return {
        role: SourceEvidence(
            role=role, source_id=f"source:{role}", original_bytes=role.encode(),
            expected_sha256=sha256(role.encode()).hexdigest(),
            published_utc="2026-10-15T09:00:00Z",
            issuer_symbol="ACE", review_status="INDEPENDENTLY_REVIEWED",
            reviewed_scope=role,
        )
        for role in REQUIRED_ROLES
    }


def test_complete_synthetic_evidence_is_still_math_only():
    out = evaluate_with_provenance(case(), evidence())
    assert out["status"] == "SCENARIO_MATH_ONLY"
    assert out["investment_authorized"] is False
    assert out["source_content_economic_truth_verified_by_code"] is False


def test_unverified_digest_abstains():
    e = evidence()
    e["price"] = replace(e["price"], original_bytes=b"tampered")
    assert evaluate_with_provenance(case(), e)["status"] == "ABSTAIN"


def test_later_publication_abstains():
    e = evidence()
    e["price"] = replace(e["price"], published_utc="2026-10-17T00:00:00Z")
    assert evaluate_with_provenance(case(), e)["status"] == "ABSTAIN"


def test_missing_role_abstains():
    e = evidence()
    del e["probability_calibration"]
    assert evaluate_with_provenance(case(), e)["status"] == "ABSTAIN"


def test_wrong_issuer_abstains():
    e = evidence()
    e["fully_diluted_shares"] = replace(e["fully_diluted_shares"], issuer_symbol="ACUTAAS")
    assert evaluate_with_provenance(case(), e)["status"] == "ABSTAIN"


def test_self_reported_unreviewed_abstains():
    e = evidence()
    e["parent_owner_cash"] = replace(e["parent_owner_cash"], review_status="SELF_REPORTED")
    assert evaluate_with_provenance(case(), e)["status"] == "ABSTAIN"


def test_wrong_scope_abstains():
    e = evidence()
    e["parent_owner_cash"] = replace(e["parent_owner_cash"], reviewed_scope="standalone_PBT")
    assert evaluate_with_provenance(case(), e)["status"] == "ABSTAIN"
