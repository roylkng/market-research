"""NPST original-page visual crosswalk for Q1/Reg32 tables.

The five actual original issuer PDF PNGs were visually inspected against
the P020 textual numerical ledger. No independent financial-statement
audit, audited recurring EBITDA or investable return is asserted.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.hg007_npst_june_facts import P019_BLOB
from marketlab.hg007_npst_june_facts import DOCUMENTS

REPORT_ID = "HG007-P022-NPST-VISUAL-CROSSWALK-AND-EARNINGS-QUALITY-v1"
P020_PATH = Path(
    "research/hg007/npst-aug2026-originals/june-2026-financial-and-funding-ledger-v1.json"
)
P020_BLOB = "73809c3d731468b4ef9e43438cd25454a9a6cf0d"
VISUAL_DIR = Path(
    "research/hg007/npst-aug2026-originals/june-source-financial-visuals"
)
VISUAL_GIT_BLOB = "4dc4e80d8b58a1f4ec9b83b1be1e682c0572a445"
ORIGINAL_VIEWS = {
    ("presentation", 18): {
        "figure_2026_q1_ebitda": 11.30,
        "figure_2027_q1_ebitda": 18.78,
        "figure_2026_q1_net_profit": 7.19,
        "figure_2027_q1_net_profit": 11.04,
    },
    ("presentation", 19): {
        "2027_q1_total_income": 61.42,
        "2027_q1_ebitda": 18.79,
        "2026_q1_ebitda": 11.31,
        "2027_q1_net_profit": 11.05,
        "2026_q1_net_profit": 7.19,
        "2027_q1_diluted_eps": 5.26,
        "2026_q1_diluted_eps": 3.70,
        "ebitda_margin_reported_percent": 30.59,
    },
    ("presentation", 20): {
        "2027_q1_revenue": 56.48,
        "2027_q1_other_income": 4.94,
        "2027_q1_total_income": 61.42,
        "2027_q1_total_expense": 42.63,
        "2027_q1_ebitda": 18.79,
        "2026_q1_other_expense": 2.57,
        "2027_q1_other_expense": 19.85,
        "2027_q1_net_profit": 11.05,
        "2026_q1_net_profit": 7.20,
        "2027_q1_diluted_eps": 5.26,
        "2026_q1_diluted_eps": 3.69,
        "ebitda_margin_reported_percent": 30.59,
    },
    ("reg32", 2): {
        "raised_crore": 300.0041,
        "global_expansion_allocation_crore": 60.0000,
        "global_expansion_utilised_crore": 10.7862,
        "product_and_acquisitions_allocation_crore": 170.0000,
        "product_and_acquisitions_utilised_crore": 16.8661,
    },
    ("reg32", 3): {
        "general_corporate_allocation_crore": 70.0041,
        "general_corporate_utilised_crore": 7.9886,
        "total_raised_crore": 300.0041,
        "total_utilised_crore": 35.6409,
    },
}


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()



def _validate_pinned_source_images(root: Path) -> dict[str, Any]:
    """Verify exact P021 bytes without depending on a non-packaged script."""
    raw = (root / "source-visuals-v1.json").read_bytes()
    if _git_blob(raw) != VISUAL_GIT_BLOB:
        raise ValueError("unrecognized immutable original PNG source manifest")
    record = json.loads(raw)
    if (
        not isinstance(record, dict)
        or record.get("render_id") != "HG007-P021-NPST-2026-JUNE-ORIGINAL-FINANCIAL-TABLE-VISUALS-v1"
        or record.get("selected_page_count") != 5
        or record.get("source_p019_original_page_spine_git_blob") != P019_BLOB
        or record.get("page_layout_review_approved") is not False
        or record.get("live_capital_allowed") is not False
    ):
        raise ValueError("original NPST P021 image identity or research-only state changed")
    entries = record.get("rendered_pages")
    if not isinstance(entries, list) or len(entries) != 5:
        raise ValueError("all five original issuer pages required")
    required = {
        ("presentation", 18), ("presentation", 19), ("presentation", 20),
        ("reg32", 2), ("reg32", 3),
    }
    present = set()
    for row in entries:
        if not isinstance(row, dict):
            raise TypeError("source image entry must be a JSON object")
        role, page = row.get("document_source_role"), row.get("original_page_number")
        if (role, page) not in required or (role, page) in present:
            raise ValueError("original NPST page substituted or duplicated")
        present.add((role, page))
        if (
            row.get("file_name") != f"{role}-original-page-{page:02d}.png"
            or row.get("original_pdf_sha256") != DOCUMENTS[role]["sha256"]
            or row.get("layout_and_visual_semantics_independently_reviewed") is not False
        ):
            raise ValueError("original source PDF-image identity or status wrong")
        image = (root / row["file_name"]).read_bytes()
        if (
            image[:8] != b"\x89PNG\r\n\x1a\n"
            or hashlib.sha256(image).hexdigest() != row.get("image_sha256")
        ):
            raise ValueError("original NPST PNG page sha mismatch")
    if present != required:
        raise ValueError("not all five original financial table pages present")
    return record

def load_visual_and_funding_evidence(
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    original_source = repo_root / P020_PATH
    original_bytes = original_source.read_bytes()
    if _git_blob(original_bytes) != P020_BLOB:
        raise ValueError("P020 original June financial ledger changed")
    p020 = json.loads(original_bytes)
    if (
        p020.get("review_id")
        != "HG007-P020-NPST-JUNE2026-FINANCIAL-AND-REG32-SOURCE-LEDGER-v1"
        or p020.get("original_source_receipts", {}).get("p019_exact_source_blob")
        != P019_BLOB
        or p020.get("investment_recommendation_authorized") is not False
        or p020.get("live_capital_allowed") is not False
    ):
        raise ValueError("unrecognized original P020 NPST issuer fact evidence")
    root = repo_root / VISUAL_DIR
    manifest_raw = (root / "source-visuals-v1.json").read_bytes()
    if _git_blob(manifest_raw) != VISUAL_GIT_BLOB:
        raise ValueError("P021 immutable original source images manifest changed")
    images = _validate_pinned_source_images(root)
    if (
        images.get("source_p019_original_page_spine_git_blob") != P019_BLOB
        or images.get("page_layout_review_approved") is not False
        or images.get("live_capital_allowed") is not False
    ):
        raise ValueError("P021 image source review not frozen")
    provenance = {
        "p020_report_git_blob_sha": P020_BLOB,
        "p020_report_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "p021_images_git_blob_sha": VISUAL_GIT_BLOB,
        "p021_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
    }
    return p020, images, provenance


def build_visual_quality_crosswalk(
    p020: dict[str, Any],
    images: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if images.get("selected_page_count") != 5 or len(images.get("rendered_pages", [])) != 5:
        raise ValueError("need all five original PNG source pages")
    page_map = {
        (p["document_source_role"], p["original_page_number"]): p
        for p in images["rendered_pages"]
    }
    if len(page_map) != 5 or set(page_map) != set(ORIGINAL_VIEWS):
        raise ValueError("original NPST page or case identity substituted")
    ref = p020.get("fundraising")
    f = p020.get("financials_q1fy27_consolidated_issuer_presentation")
    if not isinstance(ref, dict) or not isinstance(f, dict):
        raise TypeError("P020 original financial or Reg32 evidence missing")
    if (
        not math.isclose(ref.get("raised_inr_crore"), 300.0041)
        or not math.isclose(ref.get("total_utilised_through_june_inr_crore"), 35.6409)
        or not math.isclose(
            ref.get("derived_remaining_allocation_not_bank_balance_inr_crore"),
            264.3632,
        )
        or not math.isclose(f.get("ebitda_financial_tables_inr_crore"), 18.79)
        or not math.isclose(f.get("ebitda_graphic_discrepancy_inr_crore"), 18.78)
        or not math.isclose(f.get("other_income_inr_crore"), 4.94)
    ):
        raise ValueError("P020 source economics do not reconcile visual observations")
    objects = {
        row["object"]: row for row in ref.get("allocation_by_reported_purpose", [])
    }
    if set(objects) != {
        "GLOBAL_EXPANSION_AND_BRAND_BUILDING",
        "PRODUCT_INFRASTRUCTURE_ENHANCEMENT_AND_STRATEGIC_ACQUISITIONS",
        "GENERAL_CORPORATE_PURPOSES_INCLUDING_ISSUE_EXPENSES",
    }:
        raise ValueError("three original Reg32 funding objects missing")
    view = ORIGINAL_VIEWS
    if (
        objects["GLOBAL_EXPANSION_AND_BRAND_BUILDING"]["original_allocation_inr_crore"]
        != view[("reg32", 2)]["global_expansion_allocation_crore"]
        or objects["GENERAL_CORPORATE_PURPOSES_INCLUDING_ISSUE_EXPENSES"][
            "utilised_through_2026_06_30_inr_crore"
        ] != view[("reg32", 3)]["general_corporate_utilised_crore"]
        or f.get("revenue_operations_inr_crore")
        != view[("presentation", 20)]["2027_q1_revenue"]
    ):
        raise ValueError("visual column assignments disagree with source statements")

    checks = []
    for (role, page), facts in view.items():
        p = page_map[(role, page)]
        checks.append({
            "source_id": p["source_id"],
            "original_pdf_page": page,
            "original_pdf_sha256": p["original_pdf_sha256"],
            "original_page_text_sha256": p["original_page_text_sha256"],
            "original_page_image_sha256": p["image_sha256"],
            "original_rendered_image_path": str(VISUAL_DIR / p["file_name"]),
            "visually_observed_reported_figures": facts,
            "visual_column_alignment_checked": True,
            "checked_by": "ASSISTANT_VISUAL_SOURCE_INSPECTION_NOT_FINANCIAL_AUDITOR",
            "independent_audited_statement_agreement_verified": False,
        })

    delta_expense = (
        view[("presentation", 20)]["2027_q1_other_expense"]
        - view[("presentation", 20)]["2026_q1_other_expense"]
    )
    return {
        "schema_version": 1,
        "review_id": REPORT_ID,
        "classification": "HUMAN_READABLE_ASSISTANT_VISUAL_ISSUER_SOURCE_CROSSWALK_NOT_ALLOCATION",
        "source_provenance": provenance,
        "checked_source_visual_page_count": len(checks),
        "source_page_crosswalk": checks,
        "confirmed_reg32_table_column_alignment": True,
        "derived_unused_pref_proceeds_allocation_inr_crore_not_bank_cash": 264.3632,
        "confirmed_q1fy27_two_table_ebitda_inr_crore": 18.79,
        "source_graphic_q1fy27_ebitda_inr_crore": 18.78,
        "source_graphic_vs_tables_ebitda_discrepancy_inr_crore": 0.01,
        "confirmed_q1fy27_two_table_net_profit_inr_crore": 11.05,
        "source_graphic_q1fy27_net_profit_inr_crore": 11.04,
        "source_graphic_vs_tables_net_profit_discrepancy_inr_crore": 0.01,
        "q1fy26_prior_net_profit_table_19_inr_cr": 7.19,
        "q1fy26_prior_net_profit_table_20_inr_cr": 7.20,
        "q1fy26_prior_diluted_eps_table_19_inr": 3.70,
        "q1fy26_prior_diluted_eps_table_20_inr": 3.69,
        "q1fy26_prior_ebitda_graphic_inr_cr": 11.30,
        "q1fy26_prior_ebitda_tables_inr_cr": 11.31,
        "q1fy27_revenue_operations_inr_cr": 56.48,
        "q1fy27_other_income_inr_cr": 4.94,
        "q1fy27_reported_ebitda_uses_total_income_including_other_income": True,
        "q1fy26_other_expenses_inr_cr": 2.57,
        "q1fy27_other_expenses_inr_cr": 19.85,
        "other_expense_yoy_increase_inr_cr": round(delta_expense, 2),
        "other_income_recurring_nature_verified": False,
        "surge_in_other_expense_classification_explained": False,
        "presentation_graphic_table_discrepancies_resolved_by_audited_statements": False,
        "original_earnings_independent_cashflow_audit_complete": False,
        "fundraising_unused_allocation_as_free_cash_proven": False,
        "current_fully_diluted_market_cap_verified": False,
        "stock_expected_returns_calculated": False,
        "new_investment_recommendation_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
