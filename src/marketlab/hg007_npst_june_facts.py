"""Source-pinned June 2026 NPST earnings and preferential-proceeds arithmetic.

Issuer investor-presentation and Regulation 32 facts are reportable; cash
availability, normalized EBITDA, investment returns and accounting audit are
NOT established. Preserve the issuer's 0.01cr graphic/table inconsistencies.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

SOURCE_ID = "HG007-P020-NPST-JUNE2026-FINANCIAL-AND-REG32-SOURCE-LEDGER-v1"
P019_PATH = Path("research/hg007/npst-aug2026-originals/june-original-page-text-v1.json")
P019_BLOB = "4fd4b6b9c09b425284c1b4c420bdc0f4b0092506"
HURDLE_PATH = Path("research/hg005-d003-result-v1.json")
HURDLE_BLOB = "b235bd9168bc658f7511f9cec1913f20f82cf311"
DOCUMENTS = {
    "presentation": {
        "id": "2026-08-11-investor-presentation",
        "page_count": 22,
        "sha256": "5afd8b272e7bd2f7f3fad549aa1270e4899e1d24c8d982268cab16a17bbe2225",
        "receipt_blob": "c626b459562f1d25b91d8a178d17d0cc7d56b043",
    },
    "reg32": {
        "id": "2026-08-11-june-reg32-use-of-funds",
        "page_count": 3,
        "sha256": "79010c968b0fe8359f685d27a203c891a8e35f684a73b86a67cf78ee46b54013",
        "receipt_blob": "003c821ec49ce5a331768350a77c1678119baec3",
    },
}

# Only original, SHA-matched page text is permitted to support these
# page-level numeric statements. Mixed HTML/secondary estimates are excluded.
ORIGINAL_ANCHORS: dict[str, tuple[str, int, tuple[str, ...]]] = {
    "total_income": ("presentation", 19, ("61.42Total Income", "35.09")),
    "q1fy27_ebitda_table": ("presentation", 19, ("11.3118.79EBITDA", "30.59%EBITDA")),
    "q1fy27_ebitda_repeated": ("presentation", 20, ("11.3118.79EBITDA", "23.7742.63Total Expenditure")),
    "q1fy27_net_profit": ("presentation", 19, ("7.1911.05Net Profit",)),
    "q1fy27_net_profit_repeated": ("presentation", 20, ("7.2011.05Net Profit",)),
    "q1fy27_revenue": ("presentation", 20, ("33.6256.48Revenues",)),
    "q1fy27_other_income": ("presentation", 20, ("1.474.94Other Income",)),
    "q1fy27_finance_cost": ("presentation", 20, ("0.210.21Finance Costs",)),
    "q1fy27_depreciation": ("presentation", 20, ("1.434.09Depreciation",)),
    "q1fy27_pbt": ("presentation", 20, ("9.6714.49PBT",)),
    "q1fy27_tax": ("presentation", 20, ("2.483.44Tax",)),
    "graphic_ebitda_and_net_profit": ("presentation", 18, ("11.0411.3", "18.78")),
    "pref_issuance": ("reg32", 1, ("14,46,500 equity shares", "June 30, 2026")),
    "fundraising": ("reg32", 2, ("Amount Raised Rs. 300.0041 Crore", "September 05, 2025")),
    "total_spend": ("reg32", 3, ("Total  300.0041  35.6409",)),
    "global_expansion": ("reg32", 2, ("Global Expansion", "Brand Building", "10.7862", "60.0000")),
    "product_infrastructure": ("reg32", 2, ("170.0000", "16.8661", "Product", "Infrastructure")),
    "general_corporate": ("reg32", 3, ("70.0041", "7.9886", "Corporate", "Fund")),
}


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _read_exact_json(path: Path, blob: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if _blob(raw) != blob:
        raise ValueError(f"source Git blob changed: {path}")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise TypeError("source JSON must contain an object")
    return obj


def load_npst_originals(root: Path) -> tuple[dict, dict, dict]:
    p019 = _read_exact_json(root / P019_PATH, P019_BLOB)
    historical_hurdle = _read_exact_json(root / HURDLE_PATH, HURDLE_BLOB)
    if (
        p019.get("source_evidence_id") != "HG007-P019-NPST-JUNE-2026-ORIGINAL-PDF-PAGE-SPINE-v1"
        or p019.get("reporting_period") != "2026-06-30"
        or p019.get("document_count") != 2
        or p019.get("original_page_count") != 25
        or p019.get("actual_quarterly_ebitda_figure_approved") is not False
        or p019.get("unused_funds_balance_approved") is not False
        or p019.get("live_capital_allowed") is not False
    ):
        raise ValueError("P019 original frozen review boundary changed")
    documents = p019.get("original_documents")
    if not isinstance(documents, list) or len(documents) != 2:
        raise ValueError("P019 original filings missing")
    by_doc: dict[str, dict] = {}
    receipts: dict[str, dict] = {
        "p019_exact_source_blob": P019_BLOB,
        "hg005_original_hurdle_blob": HURDLE_BLOB,
    }
    for role, contract in DOCUMENTS.items():
        match = [d for d in documents if d.get("source_id") == contract["id"]]
        if len(match) != 1:
            raise ValueError(f"P019 original NPST {role} document identity mismatch")
        doc = match[0]
        raw_sha = contract["sha256"]
        if (
            doc.get("original_source_sha256") != raw_sha
            or doc.get("original_pdf_pages") != contract["page_count"]
            or doc.get("source_receipt_git_blob_sha") != contract["receipt_blob"]
            or doc.get("reporting_period") != "2026-06-30"
            or doc.get("independent_original_semantic_financial_review_complete") is not False
            or len(doc.get("pages", [])) != contract["page_count"]
        ):
            raise ValueError(f"NPST {role} original PDF or page source contract changed")
        folder = root / "research/hg007/npst-aug2026-originals" / contract["id"]
        original_file = folder / "raw" / "sha256" / f"{raw_sha}.pdf"
        original_bytes = original_file.read_bytes()
        if hashlib.sha256(original_bytes).hexdigest() != raw_sha:
            raise ValueError(f"NPST {role} original BSE PDF SHA mismatch")
        receipt_path = folder / "original-receipt-v1.json"
        receipt = _read_exact_json(receipt_path, contract["receipt_blob"])
        if (
            receipt.get("original_raw_sha256") != raw_sha
            or receipt.get("original_raw_byte_count") != len(original_bytes)
            or receipt.get("symbol") != "NPST"
            or receipt.get("isin") != "INE0FFK01017"
            or receipt.get("source_declared_reporting_period") != "2026-06-30"
            or receipt.get("status") != "ORIGINAL_PDF_BYTE_AND_PAGE_STRUCTURE_CAPTURED"
            or receipt.get("original_pdf_text_economic_facts_approved") is not False
            or receipt.get("live_capital_allowed") is not False
        ):
            raise ValueError(f"NPST {role} original BSE source receipt changed")
        page_hashes = receipt["original_pdf_page_evidence"]["page_text_sha256"]
        for i, (page, sha) in enumerate(zip(doc["pages"], page_hashes, strict=True), 1):
            raw_text = page.get("extracted_text")
            if (
                page.get("page_number_one_based") != i
                or not isinstance(raw_text, str)
                or page.get("extracted_text_sha256") != sha
                or hashlib.sha256(raw_text.encode("utf-8")).hexdigest() != sha
            ):
                raise ValueError(f"NPST {role} source page SHA/order mismatch: page {i}")
        by_doc[role] = doc
        receipts[role] = {
            "source_id": contract["id"],
            "original_bse_url": doc["original_bse_url"],
            "original_pdf_sha256": raw_sha,
            "original_byte_count": len(original_bytes),
            "receipt_git_blob": contract["receipt_blob"],
            "page_count": contract["page_count"],
        }
    case = historical_hurdle.get("key_hurdles", {}).get("NPST")
    if (
        not isinstance(case, dict)
        or historical_hurdle.get("expected_returns_calculated") is not False
        or historical_hurdle.get("live_capital_allowed") is not False
        or case.get("state") != "REVERSE_HURDLE_READY"
        or case.get("fifty_pct_uplift_at_30x_required_incremental_annual_ebitda_inr_crore")
        != 61.42562125
    ):
        raise ValueError("NPST frozen HG005 hurdle or capital gating changed")
    return by_doc, case, receipts


def _page(doc: dict, index: int) -> dict:
    pages = doc["pages"]
    return pages[index - 1]


def _cite(documents: dict[str, dict], role: str, page: int) -> dict:
    src = documents[role]
    ref = _page(src, page)
    return {
        "source_id": src["source_id"],
        "original_pdf_sha256": src["original_source_sha256"],
        "page_number": page,
        "page_text_sha256": ref["extracted_text_sha256"],
    }


def _round_cr(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.0001")))


def build_npst_financial_and_funding_ledger(
    documents: dict[str, dict],
    frozen_hurdle: dict,
    provenance: dict,
) -> dict[str, Any]:
    if set(documents) != {"presentation", "reg32"}:
        raise ValueError("both original June source families required")
    for name, (role, page_num, substrings) in ORIGINAL_ANCHORS.items():
        original_page = _page(documents[role], page_num)
        text = original_page.get("extracted_text")
        if not isinstance(text, str) or not all(term in text for term in substrings):
            raise ValueError(f"NPST original page text cannot support {name}")

    raise_total = Decimal("300.0041")
    allocations = [
        {
            "object": "GLOBAL_EXPANSION_AND_BRAND_BUILDING",
            "original_budget_inr_cr": Decimal("60.0000"),
            "utilised_through_jun30_inr_cr": Decimal("10.7862"),
            "source_page": 2,
        },
        {
            "object": "PRODUCT_INFRASTRUCTURE_ENHANCEMENT_AND_STRATEGIC_ACQUISITIONS",
            "original_budget_inr_cr": Decimal("170.0000"),
            "utilised_through_jun30_inr_cr": Decimal("16.8661"),
            "source_page": 2,
        },
        {
            "object": "GENERAL_CORPORATE_PURPOSES_INCLUDING_ISSUE_EXPENSES",
            "original_budget_inr_cr": Decimal("70.0041"),
            "utilised_through_jun30_inr_cr": Decimal("7.9886"),
            "source_page": 3,
        },
    ]
    spent = Decimal("35.6409")
    if (
        sum((r["original_budget_inr_cr"] for r in allocations), Decimal(0))
        != raise_total
        or sum((r["utilised_through_jun30_inr_cr"] for r in allocations), Decimal(0))
        != spent
    ):
        raise ValueError("original Reg32 utilization objects fail total reconciliation")
    source_objects = []
    for r in allocations:
        source_objects.append({
            "object": r["object"],
            "original_allocation_inr_crore": _round_cr(r["original_budget_inr_cr"]),
            "utilised_through_2026_06_30_inr_crore": _round_cr(
                r["utilised_through_jun30_inr_cr"]
            ),
            "unutilised_allocation_arithmetic_inr_crore": _round_cr(
                r["original_budget_inr_cr"] - r["utilised_through_jun30_inr_cr"]
            ),
            "source": _cite(documents, "reg32", r["source_page"]),
        })
    not_utilized = raise_total - spent
    if sum((Decimal(str(r["unutilised_allocation_arithmetic_inr_crore"])) for r in source_objects), Decimal(0)) != not_utilized:
        raise ValueError("Reg32 unused allocation does not reconcile")
    quarterly_total_income = Decimal("61.42")
    quarterly_revenues = Decimal("56.48")
    quarterly_other_income = Decimal("4.94")
    quarterly_total_expenditure = Decimal("42.63")
    quarterly_ebitda_table = Decimal("18.79")
    quarterly_ebitda_graphic = Decimal("18.78")
    quarterly_finance = Decimal("0.21")
    quarterly_depreciation = Decimal("4.09")
    quarterly_pbt = Decimal("14.49")
    quarterly_tax = Decimal("3.44")
    quarterly_net = Decimal("11.05")
    quarterly_net_graphic = Decimal("11.04")
    previous_ebitda = Decimal("11.31")
    if not (
        quarterly_revenues + quarterly_other_income == quarterly_total_income
        and quarterly_total_income - quarterly_total_expenditure == quarterly_ebitda_table
        and quarterly_ebitda_table - quarterly_finance - quarterly_depreciation
        == quarterly_pbt
        and quarterly_pbt - quarterly_tax == quarterly_net
        and (quarterly_ebitda_table - quarterly_ebitda_graphic) == Decimal("0.01")
        and (quarterly_net - quarterly_net_graphic) == Decimal("0.01")
    ):
        raise ValueError("NPST original quarter accounting identities or graphic variance changed")

    annual_illustration = quarterly_ebitda_table * 4
    frozen_hurdle_value = Decimal(
        str(frozen_hurdle["fifty_pct_uplift_at_30x_required_incremental_annual_ebitda_inr_crore"])
    )
    if (
        frozen_hurdle.get("q1fy27_ebitda_inr_crore") != 18.79
        or not math.isclose(
            frozen_hurdle["fifty_pct_uplift_at_30x_quarterly_equivalent_vs_observed_q1_ebitda"],
            float(frozen_hurdle_value / annual_illustration),
            abs_tol=1e-12,
        )
    ):
        raise ValueError("frozen NPST 30x reverse hurdle inconsistent with source EBITDA")

    return {
        "schema_version": 1,
        "review_id": SOURCE_ID,
        "classification": "ORIGINAL_NPST_PRESENTATION_AND_REG32_PAGE_FACTS_NOT_AUDITED_RETURN",
        "issuer": "Network People Services Technologies Limited",
        "nse_symbol": "NPST",
        "isin": "INE0FFK01017",
        "reporting_quarter_ended": "2026-06-30",
        "filed_on": "2026-08-11",
        "original_source_receipts": provenance,
        "fundraising": {
            "mode": "PREFERENTIAL_ALLOTMENT",
            "funds_raise_date": "2025-09-05",
            "preferential_shares_filing_reports": 1_446_500,
            "raised_inr_crore": _round_cr(raise_total),
            "total_utilised_through_june_inr_crore": _round_cr(spent),
            "derived_remaining_allocation_not_bank_balance_inr_crore": _round_cr(
                not_utilized
            ),
            "derived_allocation_used_fraction": float(spent / raise_total),
            "no_deviation_reported_by_issuer": True,
            "allocation_by_reported_purpose": source_objects,
            "source_cover": _cite(documents, "reg32", 1),
            "source_total_row": _cite(documents, "reg32", 3),
            "reported_cash_and_bank_balance_independently_reconciled": False,
            "proceeds_deployment_to_incremental_ebitda_verified": False,
            "reg32_march_monitoring_report_substituted_for_june": False,
        },
        "financials_q1fy27_consolidated_issuer_presentation": {
            "total_income_inr_crore": float(quarterly_total_income),
            "revenue_operations_inr_crore": float(quarterly_revenues),
            "other_income_inr_crore": float(quarterly_other_income),
            "total_expenditure_inr_crore": float(quarterly_total_expenditure),
            "ebitda_financial_tables_inr_crore": float(quarterly_ebitda_table),
            "ebitda_prior_year_same_quarter_inr_crore": float(previous_ebitda),
            "ebitda_graphic_discrepancy_inr_crore": float(quarterly_ebitda_graphic),
            "net_profit_financial_tables_inr_crore": float(quarterly_net),
            "net_profit_graphic_discrepancy_inr_crore": float(quarterly_net_graphic),
            "finance_cost_inr_crore": float(quarterly_finance),
            "depreciation_inr_crore": float(quarterly_depreciation),
            "pbt_inr_crore": float(quarterly_pbt),
            "tax_inr_crore": float(quarterly_tax),
            "ebitda_margin_on_total_income_pct": float(
                quarterly_ebitda_table / quarterly_total_income * 100
            ),
            "table_ebitda_reconciles_total_income_less_expenditure": True,
            "net_profit_reconciles_pbt_less_tax": True,
            "summary_graphic_and_tables_disagree_by_inr_crore": 0.01,
            "text_extraction_financial_table_layout_visual_verified": False,
            "standalone_to_consolidated_and_audited_statement_reconciled": False,
            "presentation_page18": _cite(documents, "presentation", 18),
            "presentation_page19": _cite(documents, "presentation", 19),
            "presentation_page20": _cite(documents, "presentation", 20),
        },
        "historical_hg005_hurdle_not_forecast": {
            "source": HURDLE_PATH.as_posix(),
            "source_git_blob": HURDLE_BLOB,
            "illustrative_fifty_pct_uplift_at_30x_additional_annual_ebitda_inr_cr": float(
                frozen_hurdle_value
            ),
            "q1fy27_quarterly_ebitda_times_four_not_a_forecast_inr_cr": float(
                annual_illustration
            ),
            "incremental_annual_hurdle_fraction_of_one_quarter_annualization": float(
                frozen_hurdle_value / annual_illustration
            ),
            "quarterly_seasonality_and_profit_persistence_audited": False,
            "30x_multiple_validated": False,
        },
        "source_review": {
            "issuer_text_page_amounts_and_period_semantics_reconciled": True,
            "visual_financial_layout_approved": False,
            "original_fully_independent_financial_audit_completed": False,
            "discrepancy_requires_visual_and_financial_statement_check": True,
            "preferred_amount_for_conditional_accounting_bridge": (
                "18.79 TABLE_FIGURE_RECONCILES_61.42_MINUS_42.63_NOT_PROFIT_FORECAST"
            ),
        },
        "current_cash_from_unspent_proceeds_proven": False,
        "normalized_recurrent_earnings_proven": False,
        "current_fully_diluted_shares_proven": False,
        "current_equity_value_and_net_debt_proven": False,
        "probability_weighted_expected_return_calculated": False,
        "investment_recommendation_authorized": False,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
    }
