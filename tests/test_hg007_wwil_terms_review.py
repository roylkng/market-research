from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_wwil_terms_review import (
    EXPECTED_PAGE_HASHES,
    REVIEW_ID,
    SOURCE_FACTS,
    build_text_facts,
    load_verified_page_text,
)


def _terms() -> dict:
    return build_text_facts(load_verified_page_text(Path(".")))


def test_original_six_page_filing_contract_reconciles_funding() -> None:
    result = _terms()
    assert result["review_id"] == REVIEW_ID
    assert result["source_pdf_page_count"] == 6
    assert result["disclosed_term_count"] == len(SOURCE_FACTS)
    original = result["disclosed_terms"]
    assert original["wwil_cash_consideration_paid_inr_crore"]["reported_value"] == 550
    assert original["parent_total_funding_inr_crore"]["reported_value"] == 450
    assert original["parent_cash_equity_subscription_inr_crore"]["reported_value"] == 250
    assert original["parent_unsecured_intercompany_deposit_inr_crore"][
        "reported_value"
    ] == 200
    assert original["authum_intercompany_deposit_inr_crore"]["reported_value"] == 100
    assert original["vibhav_equity_paid_up_after_subscription_inr_crore"][
        "reported_value"
    ] == 250.01
    assert original["new_equity_subscription_share_count_crore"][
        "reported_value"
    ] == 25
    assert original["new_equity_subscription_face_value_inr"]["reported_value"] == 10


def test_annexure_b_loan_priority_optional_conversion_and_coupon() -> None:
    result = _terms()
    fields = result["disclosed_terms"]
    assert fields["parent_loan_annual_coupon_pct"]["reported_value"] == 12
    assert fields["parent_loan_annual_coupon_pct"]["source_pdf_page_number"] == 5
    assert fields["parent_loan_unsecured_and_subordinated"]["reported_value"] is True
    assert fields["parent_loan_repayment_blocked_until_prior_debt_repaid"][
        "reported_value"
    ] is True
    assert fields["parent_loan_up_to_50_crore_principal_may_convert"][
        "reported_value"
    ] == 50
    assert fields["parent_loan_up_to_50_crore_principal_may_convert"][
        "issuer_statement_state"
    ] == "OPTIONAL_BY_MUTUAL_AGREEMENT_NOT_COMMITTED_EQUITY"
    assert fields["parent_loan_bullet_date_fixed"]["reported_value"] is False
    assert fields["parent_loan_executed_date"]["reported_value"] == "2026-09-25"
    assert result["arithmetic_crosschecks"][
        "parent_200cr_annual_nominal_12pct_intragroup_coupon_inr_crore"
    ] == 24
    assert result["arithmetic_crosschecks"]["coupon_cash_paid_proven"] is False
    assert result["arithmetic_crosschecks"][
        "coupon_is_consolidated_group_external_profit"
    ] is False


def test_original_filing_not_equal_legal_transfer_or_target_ebitda() -> None:
    result = _terms()
    assert result["disclosed_terms"][
        "wwil_business_transfer_requires_bta_conditions"
    ]["reported_value"] is True
    assert result["disclosed_terms"]["vibhav_previous_fy26_revenue_inr_crore"][
        "issuer_statement_state"
    ] == "SUBSIDIARY_HISTORICAL_NOT_WWIL_ACQUIRED_BUSINESS"
    assert result["disclosed_terms"][
        "vibhav_parent_current_ordinary_equity_ownership_pct"
    ]["reported_value"] == 100
    assert len(result["material_previous_provisional_interpretation_corrections"]) == 4
    assert result["post_conversion_parent_ownership_percent_verified"] is False
    assert result["wwil_transfer_legally_completed_verified"] is False
    assert result["page_image_visual_review_complete"] is False
    assert result["fully_independent_company_due_diligence_complete"] is False
    assert result["wwil_ebitda_cashflow_verified"] is False
    assert result["company_completion_probability_published"] is False
    assert result["expected_returns_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


def test_page_text_mutation_fails_even_if_source_metadata_is_relabelled() -> None:
    packet = load_verified_page_text(Path("."))
    modified = deepcopy(packet)
    modified["pages"][4]["extracted_text"] = modified["pages"][4][
        "extracted_text"
    ].replace("12% per annum", "2% per annum")
    with pytest.raises(ValueError, match="original six page"):
        build_text_facts(modified)


def test_source_page_checksums_match_original_p004_extraction() -> None:
    packet = load_verified_page_text(Path("."))
    assert tuple(page["text_sha256"] for page in packet["pages"]) == EXPECTED_PAGE_HASHES
    result = build_text_facts(packet)
    assert all(
        fact["source_page_text_sha256"] in EXPECTED_PAGE_HASHES
        for fact in result["disclosed_terms"].values()
    )


def test_term_audit_reproducible_without_network(tmp_path: Path) -> None:
    output = tmp_path / "issuer-original-terms-v1.json"
    base = [
        sys.executable, "scripts/reconcile_hg007_wwil_original_terms.py",
        "--out", str(output),
    ]
    first = subprocess.run(base, check=True, capture_output=True, text=True)
    summary = json.loads(first.stdout)
    assert summary["issuer_reported_fact_count"] == len(SOURCE_FACTS)
    assert summary["original_source_50cr_conversion_optional"] is True
    assert summary["parent_annual_intercompany_coupon_simple_cr"] == 24
    assert summary["bta_transfer_complete"] is False
    assert json.loads(output.read_text(encoding="utf-8")) == _terms()
    subprocess.run(
        base + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    output.write_text(
        output.read_text(encoding="utf-8") + "fabricated",
        encoding="utf-8",
    )
    failure = subprocess.run(
        base + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failure.returncode != 0
    assert "does not match original" in failure.stderr
