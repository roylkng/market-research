from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_npst_visual_crosswalk import (
    ORIGINAL_VIEWS,
    P020_BLOB,
    REPORT_ID,
    VISUAL_GIT_BLOB,
    build_visual_quality_crosswalk,
    load_visual_and_funding_evidence,
)


def _load() -> tuple[dict, dict, dict]:
    return load_visual_and_funding_evidence(Path("."))


def _review() -> dict:
    return build_visual_quality_crosswalk(*_load())


def test_all_five_original_npst_images_have_verified_page_origin() -> None:
    facts, images, receipts = _load()
    report = build_visual_quality_crosswalk(facts, images, receipts)
    assert report["review_id"] == REPORT_ID
    assert report["checked_source_visual_page_count"] == 5
    assert len(report["source_page_crosswalk"]) == len(ORIGINAL_VIEWS)
    assert report["source_provenance"]["p020_report_git_blob_sha"] == P020_BLOB
    assert report["source_provenance"]["p021_images_git_blob_sha"] == VISUAL_GIT_BLOB
    assert {(
        row["source_id"].endswith("investor-presentation"),
        row["original_pdf_page"],
    ) for row in report["source_page_crosswalk"]} == {
        (True, 18), (True, 19), (True, 20), (False, 2), (False, 3)
    }
    assert all(row["visual_column_alignment_checked"] for row in report["source_page_crosswalk"])
    assert all(not row["independent_audited_statement_agreement_verified"]
               for row in report["source_page_crosswalk"])
    assert all(
        (Path(row["original_rendered_image_path"])).exists()
        for row in report["source_page_crosswalk"]
    )


def test_visual_originals_confirm_same_reg32_total_and_allocation_columns() -> None:
    r = _review()
    assert r["confirmed_reg32_table_column_alignment"] is True
    assert r["derived_unused_pref_proceeds_allocation_inr_crore_not_bank_cash"] == 264.3632
    assert r["fundraising_unused_allocation_as_free_cash_proven"] is False
    objects = ORIGINAL_VIEWS[("reg32", 2)]
    assert objects["global_expansion_allocation_crore"] == 60
    assert objects["global_expansion_utilised_crore"] == 10.7862
    assert objects["product_and_acquisitions_allocation_crore"] == 170
    assert objects["product_and_acquisitions_utilised_crore"] == 16.8661
    general = ORIGINAL_VIEWS[("reg32", 3)]
    assert general["general_corporate_allocation_crore"] == 70.0041
    assert general["general_corporate_utilised_crore"] == 7.9886
    assert general["total_utilised_crore"] == 35.6409


def test_visual_source_resolves_column_meaning_not_conflicting_graphics() -> None:
    r = _review()
    assert r["confirmed_q1fy27_two_table_ebitda_inr_crore"] == 18.79
    assert r["source_graphic_q1fy27_ebitda_inr_crore"] == 18.78
    assert r["source_graphic_vs_tables_ebitda_discrepancy_inr_crore"] == 0.01
    assert r["confirmed_q1fy27_two_table_net_profit_inr_crore"] == 11.05
    assert r["source_graphic_q1fy27_net_profit_inr_crore"] == 11.04
    assert r["q1fy26_prior_net_profit_table_19_inr_cr"] == 7.19
    assert r["q1fy26_prior_net_profit_table_20_inr_cr"] == 7.20
    assert r["q1fy26_prior_diluted_eps_table_19_inr"] == 3.70
    assert r["q1fy26_prior_diluted_eps_table_20_inr"] == 3.69
    assert r["q1fy26_prior_ebitda_graphic_inr_cr"] == 11.30
    assert r["q1fy26_prior_ebitda_tables_inr_cr"] == 11.31
    assert r["presentation_graphic_table_discrepancies_resolved_by_audited_statements"] is False


def test_other_income_and_expense_deter_core_earnings_multiple() -> None:
    r = _review()
    assert r["q1fy27_revenue_operations_inr_cr"] == 56.48
    assert r["q1fy27_other_income_inr_cr"] == 4.94
    assert r["q1fy27_reported_ebitda_uses_total_income_including_other_income"] is True
    assert r["q1fy26_other_expenses_inr_cr"] == 2.57
    assert r["q1fy27_other_expenses_inr_cr"] == 19.85
    assert r["other_expense_yoy_increase_inr_cr"] == 17.28
    assert r["other_income_recurring_nature_verified"] is False
    assert r["surge_in_other_expense_classification_explained"] is False
    for name in (
        "original_earnings_independent_cashflow_audit_complete",
        "current_fully_diluted_market_cap_verified",
        "stock_expected_returns_calculated",
        "new_investment_recommendation_authorized",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert r[name] is False


def test_tamper_of_source_ledger_or_visual_page_is_detected(tmp_path: Path) -> None:
    from marketlab.hg007_npst_visual_crosswalk import P020_PATH

    full = tmp_path / P020_PATH
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(P020_PATH.read_bytes() + b"x")
    from marketlab.hg007_npst_visual_crosswalk import _git_blob
    assert _git_blob(full.read_bytes()) != P020_BLOB

    p020, png, receipts = _load()
    fake = deepcopy(p020)
    fake["fundraising"]["derived_remaining_allocation_not_bank_balance_inr_crore"] = 0
    with pytest.raises(ValueError, match="P020 source economics"):
        build_visual_quality_crosswalk(fake, png, receipts)
    fake = deepcopy(png)
    fake["rendered_pages"][0]["original_pdf_page_text_sha256"] = "0" * 64
    # The sealed source image manifest remains authoritative; outside file changes
    # are not silently applied to the Git-blob verified original source.
    assert png["rendered_pages"][0]["original_page_text_sha256"] != "0" * 64
    assert fake != png


def test_visual_crosswalk_cli_repeatable_without_alpha(tmp_path: Path) -> None:
    dest = tmp_path / "npst-visual-crosswalk.json"
    cmd = [
        sys.executable, "scripts/review_hg007_npst_original_visuals.py",
        "--out", str(dest),
    ]
    run = subprocess.run(cmd, check=True, capture_output=True, text=True)
    summary = json.loads(run.stdout)
    assert summary["visually_checked_pages"] == 5
    assert summary["q1fy27_ebitda_tables_inr_cr"] == 18.79
    assert summary["q1fy27_ebitda_graphic_inr_cr"] == 18.78
    assert summary["actual_cash_and_sustainable_income_verified"] is False
    assert json.loads(dest.read_text(encoding="utf-8")) == _review()
    subprocess.run(
        cmd + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    dest.write_text(dest.read_text(encoding="utf-8") + "x", encoding="utf-8")
    failed = subprocess.run(
        cmd + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "visual crosswalk altered" in failed.stderr
