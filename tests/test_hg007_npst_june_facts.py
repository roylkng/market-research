from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_npst_june_facts import (
    DOCUMENTS,
    HURDLE_BLOB,
    HURDLE_PATH,
    P019_BLOB,
    P019_PATH,
    SOURCE_ID,
    build_npst_financial_and_funding_ledger,
    load_npst_originals,
)


def _ledger() -> dict:
    documents, hurdle, provenance = load_npst_originals(Path("."))
    return build_npst_financial_and_funding_ledger(documents, hurdle, provenance)


def test_immutable_two_exact_bse_source_pdf_families() -> None:
    documents, hurdle, receipts = load_npst_originals(Path("."))
    assert receipts["p019_exact_source_blob"] == P019_BLOB
    assert receipts["hg005_original_hurdle_blob"] == HURDLE_BLOB
    assert set(documents) == set(DOCUMENTS)
    assert len(documents["presentation"]["pages"]) == 22
    assert len(documents["reg32"]["pages"]) == 3
    assert sum(d["original_pdf_pages"] for d in documents.values()) == 25
    assert hurdle["q1fy27_ebitda_inr_crore"] == 18.79
    assert all(
        receipt["original_pdf_sha256"] == DOCUMENTS[role]["sha256"]
        for role, receipt in receipts.items() if role in DOCUMENTS
    )


def test_original_reg32_objects_and_exact_unused_amount() -> None:
    facts = _ledger()
    assert facts["review_id"] == SOURCE_ID
    assert facts["reporting_quarter_ended"] == "2026-06-30"
    f = facts["fundraising"]
    assert f["mode"] == "PREFERENTIAL_ALLOTMENT"
    assert f["preferential_shares_filing_reports"] == 1_446_500
    assert f["raised_inr_crore"] == 300.0041
    assert f["total_utilised_through_june_inr_crore"] == 35.6409
    assert f["derived_remaining_allocation_not_bank_balance_inr_crore"] == 264.3632
    assert f["derived_allocation_used_fraction"] == pytest.approx(
        35.6409 / 300.0041
    )
    assert sum(row["original_allocation_inr_crore"] for row in
               f["allocation_by_reported_purpose"]) == pytest.approx(300.0041)
    assert sum(row["utilised_through_2026_06_30_inr_crore"] for row in
               f["allocation_by_reported_purpose"]) == pytest.approx(35.6409)
    by_object = {row["object"]: row for row in f["allocation_by_reported_purpose"]}
    assert by_object["GLOBAL_EXPANSION_AND_BRAND_BUILDING"][
        "unutilised_allocation_arithmetic_inr_crore"
    ] == pytest.approx(49.2138)
    assert by_object["PRODUCT_INFRASTRUCTURE_ENHANCEMENT_AND_STRATEGIC_ACQUISITIONS"][
        "unutilised_allocation_arithmetic_inr_crore"
    ] == pytest.approx(153.1339)
    assert by_object["GENERAL_CORPORATE_PURPOSES_INCLUDING_ISSUE_EXPENSES"][
        "unutilised_allocation_arithmetic_inr_crore"
    ] == pytest.approx(62.0155)
    assert f["source_total_row"]["page_number"] == 3
    assert f["reported_cash_and_bank_balance_independently_reconciled"] is False
    assert f["proceeds_deployment_to_incremental_ebitda_verified"] is False
    assert f["reg32_march_monitoring_report_substituted_for_june"] is False


def test_consolidated_q1_financial_bridge_and_001crore_chart_ambiguity() -> None:
    facts = _ledger()
    q = facts["financials_q1fy27_consolidated_issuer_presentation"]
    assert q["total_income_inr_crore"] == 61.42
    assert q["revenue_operations_inr_crore"] == 56.48
    assert q["other_income_inr_crore"] == 4.94
    assert q["total_expenditure_inr_crore"] == 42.63
    assert q["ebitda_financial_tables_inr_crore"] == 18.79
    assert q["ebitda_graphic_discrepancy_inr_crore"] == 18.78
    assert q["net_profit_financial_tables_inr_crore"] == 11.05
    assert q["net_profit_graphic_discrepancy_inr_crore"] == 11.04
    assert q["ebitda_margin_on_total_income_pct"] == pytest.approx(30.59, abs=0.01)
    assert q["table_ebitda_reconciles_total_income_less_expenditure"] is True
    assert q["net_profit_reconciles_pbt_less_tax"] is True
    assert q["standalone_to_consolidated_and_audited_statement_reconciled"] is False
    assert q["summary_graphic_and_tables_disagree_by_inr_crore"] == 0.01
    assert q["presentation_page18"]["page_number"] == 18
    assert q["presentation_page19"]["page_number"] == 19
    assert q["presentation_page20"]["page_number"] == 20
    assert facts["source_review"]["discrepancy_requires_visual_and_financial_statement_check"] is True


def test_50pct_at_30x_remains_hypothetical_not_a_forecast() -> None:
    facts = _ledger()
    hurdle = facts["historical_hg005_hurdle_not_forecast"]
    assert hurdle[
        "illustrative_fifty_pct_uplift_at_30x_additional_annual_ebitda_inr_cr"
    ] == 61.42562125
    assert hurdle["q1fy27_quarterly_ebitda_times_four_not_a_forecast_inr_cr"] == 75.16
    assert hurdle["incremental_annual_hurdle_fraction_of_one_quarter_annualization"] == pytest.approx(
        0.8172647851250665
    )
    for flag in (
        "current_cash_from_unspent_proceeds_proven",
        "normalized_recurrent_earnings_proven",
        "current_fully_diluted_shares_proven",
        "current_equity_value_and_net_debt_proven",
        "probability_weighted_expected_return_calculated",
        "investment_recommendation_authorized",
        "live_capital_allowed",
        "portfolio_eligibility_allowed",
    ):
        assert facts[flag] is False


def test_tampered_financial_page_or_reg32_receipt_fails_closed(tmp_path: Path) -> None:
    from marketlab.hg007_npst_june_facts import _read_exact_json

    for source in [P019_PATH, HURDLE_PATH]:
        dst = tmp_path / source
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(source.read_bytes())
    source = tmp_path / P019_PATH
    source.write_bytes(source.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="source Git blob changed"):
        _read_exact_json(source, P019_BLOB)

    originals, hurdle, receipts = load_npst_originals(Path("."))
    altered = deepcopy(originals)
    altered["reg32"]["pages"][2]["extracted_text"] = altered["reg32"]["pages"][2][
        "extracted_text"
    ].replace("35.6409", "0.0000")
    with pytest.raises(ValueError, match="original page text cannot support total_spend"):
        build_npst_financial_and_funding_ledger(altered, hurdle, receipts)
    altered = deepcopy(originals)
    altered["presentation"]["pages"][18]["extracted_text"] = altered[
        "presentation"
    ]["pages"][18]["extracted_text"].replace("18.79", "18.78")
    with pytest.raises(ValueError, match="original page text cannot support q1fy27_ebitda_table"):
        build_npst_financial_and_funding_ledger(altered, hurdle, receipts)


def test_output_has_source_page_sha_and_never_claims_audited_profit() -> None:
    facts = _ledger()
    for purpose in facts["fundraising"]["allocation_by_reported_purpose"]:
        assert len(purpose["source"]["page_text_sha256"]) == 64
        assert purpose["source"]["source_id"].endswith("june-reg32-use-of-funds")
    for page in (18, 19, 20):
        ref = facts["financials_q1fy27_consolidated_issuer_presentation"][
            f"presentation_page{page}"
        ]
        assert ref["page_number"] == page
        assert len(ref["original_pdf_sha256"]) == 64
    assert facts["source_review"]["visual_financial_layout_approved"] is False
    assert facts["source_review"]["original_fully_independent_financial_audit_completed"] is False


def test_offline_reproducible_and_overwrite_fails(tmp_path: Path) -> None:
    path = tmp_path / "npst-original-sources-v1.json"
    args = [
        sys.executable, "scripts/reconcile_hg007_npst_june_facts.py",
        "--out", str(path),
    ]
    finished = subprocess.run(args, check=True, capture_output=True, text=True)
    summary = json.loads(finished.stdout)
    assert summary["raised_cr"] == 300.0041
    assert summary["derived_unused_allocation_not_bank_cash_cr"] == 264.3632
    assert summary["q1fy27_reported_table_ebitda_cr"] == 18.79
    assert summary["different_graphic_ebitda_cr"] == 18.78
    assert json.loads(path.read_text(encoding="utf-8")) == _ledger()
    subprocess.run(
        args + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    path.write_text(path.read_text(encoding="utf-8") + "wrong", encoding="utf-8")
    failed = subprocess.run(
        args + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "reported-facts ledger drifted" in failed.stderr
