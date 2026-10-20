"""L001-P019: Sun TV FY26 audited franchise-right cash reconciliation.

Research method developed October 20, 2026. Historical issuer disclosures
cannot be a preregistered October 15 trading signal.

Separately identify (1) original consolidated cash-flow purchases, (2) SunRisers
Leeds parent cash investment, (3) identical consolidated franchise-right
recognition, and (4) foreign-currency carrying-value remeasurement. Never claim
the subsidiary-to-consolidated cash-line allocation is proven without exact
transaction cash schedules, or that remaining rights spending is maintenance.
"""

from __future__ import annotations

import copy
import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
import json

REVIEW_ID = "L001-P019-SUNTV-AUDITED-FRANCHISE-RIGHTS-CASH-BRIDGE-v1"
SOURCE_PATHS = {
    "p014": (
        "research/l001/l001-p014-fy26-intangible-cash-and-suntv-reconciliation.md",
        "931f7954c3270ce157b38f22ef06bde68aaad4db",
    ),
    "p016": (
        "research/l001/l001-p016-owner-cash-evidence-gates-100-v1.json",
        "00241232ca88aa8f1217407be0929e686335f928",
    ),
}
ANNUAL_REPORT_URL = (
    "https://www.suntv.in/pdf/Finance/2025/"
    "Sun_TV-41st_Annual_Report_25-26.pdf"
)
ISSUER_ISIN = "INE424H01027"
REPORT_DATE = "2026-10-20"
SOURCE_FINANCIAL_YEAR = "2026-03-31"

# Human visually confirmed against PDF's actual numbered pages.
# They are source-fact transcriptions, not a downloaded original-byte receipt.
PAGE_EVIDENCE = {
    "STANDALONE_CASH_FLOWS": {
        "page_index_zero_based": 77,
        "audited_2026_cfo_cr": "1736.10",
        "audited_2026_ppe_cash_cr": "71.17",
        "audited_2026_intangible_cash_cr": "938.51",
        "audited_2026_subsidiary_investment_cash_cr": "1190.88",
    },
    "STANDALONE_SUBSIDIARY_CASH": {
        "page_index_zero_based": 78,
        "audited_2026_subsidiary_investment_cash_cr": "1190.88",
    },
    "CONSOLIDATED_CASH_FLOWS": {
        "page_index_zero_based": 160,
        "audited_2026_cfo_cr": "1801.64",
        "audited_2025_cfo_cr": "1664.51",
        "audited_2026_ppe_cash_cr": "83.91",
        "audited_2025_ppe_cash_cr": "28.89",
        "audited_2026_intangible_cash_cr": "2130.31",
        "audited_2025_intangible_cash_cr": "354.97",
    },
    "CONSOLIDATED_INTANGIBLE_NOTE_5": {
        "page_index_zero_based": 184,
        "franchise_rights_initial_cost_cr": "1190.88",
        "franchise_rights_fx_translation_cr": "57.39",
        "franchise_rights_closing_carrying_cr": "1248.27",
        "total_new_intangible_additions_cr": "1559.90",
    },
    "CONSOLIDATED_NOTE_46_C": {
        "page_index_zero_based": 228,
        "purchase_consideration_gbp_million": "100.5",
        "purchase_consideration_inr_cr": "1184.99",
        "transaction_completion_date": "2025-07-28",
        "ind_as_treatment": "ASSET_ACQUISITION_FRANCHISE_RIGHTS",
    },
}


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_prior_evidence(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    receipts = {}
    for label, (path, git_blob) in SOURCE_PATHS.items():
        raw = (root / path).read_bytes()
        if _git_blob(raw) != git_blob:
            raise AlphaContractError(
                f"P019 original {label} source Git blob changed"
            )
        receipts[label] = {
            "original_source_path": path,
            "original_git_blob_sha1": git_blob,
            "original_source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        if label == "p016":
            p016 = json.loads(raw)
    if p016.get("issuer_count") != 100:
        raise AlphaContractError("P019 original 100-company HG009 population drift")
    rows = [
        row for row in p016["company_cashflow_classification_rows"]
        if row["symbol"] == "SUNTV" and row["isin"] == ISSUER_ISIN
    ]
    if len(rows) != 1:
        raise AlphaContractError("P019 SUNTV original frozen symbol/ISIN missing")
    if (
        rows[0].get("normalized_attributable_owner_cash_cr") is not None
        or rows[0].get("capital_eligible") is not False
    ):
        raise AlphaContractError("P019 cannot promote earlier unvalued company")
    return rows[0], receipts


def _d(source: dict[str, Any], key: str) -> Decimal:
    x = source[key]
    if not isinstance(x, str):
        raise AlphaContractError(f"P019 audited financial amount {key} not exact")
    result = Decimal(x)
    if not result.is_finite() or result < 0:
        raise AlphaContractError(f"P019 audited amount invalid: {key}")
    return result


def _cr(n: Decimal) -> float:
    return float(n.quantize(Decimal("0.01")))


def build_suntv_2026_cash_reconciliation(
    previous: dict[str, Any], receipts: dict[str, Any]
) -> dict[str, Any]:
    standalone = PAGE_EVIDENCE["STANDALONE_CASH_FLOWS"]
    consolidated = PAGE_EVIDENCE["CONSOLIDATED_CASH_FLOWS"]
    rights = PAGE_EVIDENCE["CONSOLIDATED_INTANGIBLE_NOTE_5"]
    note = PAGE_EVIDENCE["CONSOLIDATED_NOTE_46_C"]
    cfo = _d(consolidated, "audited_2026_cfo_cr")
    ppe = _d(consolidated, "audited_2026_ppe_cash_cr")
    intang = _d(consolidated, "audited_2026_intangible_cash_cr")
    rights_cost = _d(rights, "franchise_rights_initial_cost_cr")
    parent_paid = _d(
        standalone, "audited_2026_subsidiary_investment_cash_cr"
    )
    consideration = _d(note, "purchase_consideration_inr_cr")
    fx = _d(rights, "franchise_rights_fx_translation_cr")
    carrying = _d(rights, "franchise_rights_closing_carrying_cr")

    if (
        previous.get("fy26_cfo_cr_reported") != float(cfo)
        or previous.get("fy26_ppe_cash_purchase_cr_reported") != float(ppe)
        or previous.get("fy26_intangible_cash_purchase_cr_reported")
        != float(intang)
        or previous.get("fy26_cfo_minus_ppe_intangibles_cr_not_owner_cash")
        != float(cfo - ppe - intang)
        or rights_cost != parent_paid
        or rights_cost + fx != carrying
        or not (Decimal(0) < consideration < rights_cost < intang)
    ):
        raise AlphaContractError("P019 original FY26 annual/source cash terms conflict")

    recurring_unknown = intang - rights_cost
    no_franchise_stress = cfo - ppe - recurring_unknown
    prior_cfo = _d(consolidated, "audited_2025_cfo_cr")
    prior_ppe = _d(consolidated, "audited_2025_ppe_cash_cr")
    prior_intang = _d(consolidated, "audited_2025_intangible_cash_cr")
    parent_cfo = _d(standalone, "audited_2026_cfo_cr")
    parent_ppe = _d(standalone, "audited_2026_ppe_cash_cr")
    parent_rights = _d(standalone, "audited_2026_intangible_cash_cr")

    if no_franchise_stress <= 0:
        raise AlphaContractError("P019 conditional source arithmetic drift")
    result = {
        "schema_version": 1,
        "review_id": REVIEW_ID,
        "research_review_date": REPORT_DATE,
        "original_report_period_end": SOURCE_FINANCIAL_YEAR,
        "original_issuer": "Sun TV Network Limited",
        "symbol": "SUNTV",
        "isin": ISSUER_ISIN,
        "original_report_pdf_url": ANNUAL_REPORT_URL,
        "original_pdf_full_bytes_archived_in_this_report": False,
        "original_pdf_full_file_sha256_verified": False,
        "pages_manually_checked_against_original_issuer_pdf": True,
        "original_filing_page_evidence": PAGE_EVIDENCE,
        "earlier_source_p014_p016_pinned_receipts": receipts,
        "fy26_consolidated_cfo_cr": _cr(cfo),
        "fy26_consolidated_ppe_cash_cr": _cr(ppe),
        "fy26_consolidated_intangible_cash_cr": _cr(intang),
        "fy26_cfo_less_ppe_only_proxy_cr_not_owner_cash": _cr(cfo - ppe),
        "fy26_cfo_less_ppe_intangibles_proxy_cr_not_owner_cash": _cr(
            cfo - ppe - intang
        ),
        "acquired_SRL_100pct_effective_date": "2025-07-28",
        "acquired_SRL_asset_treatment": (
            "IND_AS_103_ASSET_ACQUISITION_OF_CRICKET_FRANCHISE_RIGHTS"
        ),
        "SRL_purchase_consideration_in_annual_note_cr": _cr(consideration),
        "SRL_parent_reported_cash_investment_cr": _cr(parent_paid),
        "SRL_consolidated_franchise_right_initial_asset_cr": _cr(rights_cost),
        "SRL_franchise_right_fx_translation_cr_not_new_cash": _cr(fx),
        "SRL_franchise_right_end_fy26_carrying_cr_not_cash": _cr(carrying),
        "purchase_consideration_vs_initial_right_asset_difference_cr": _cr(
            rights_cost - consideration
        ),
        "source_categorized_franchise_rights_percent_of_intangible_cash": round(
            100 * float(rights_cost / intang), 2
        ),
        "reported_intangible_cash_less_initial_franchise_rights_conditional_cr": _cr(
            recurring_unknown
        ),
        "conditional_cfo_minus_ppe_less_residual_intangible_cr_not_owner_cash": _cr(
            no_franchise_stress
        ),
        "conditional_2026_cash_proxy_not_proven_sustainable": True,
        "source_2025_consolidated_cfo_less_ppe_and_intangibles_cr": _cr(
            prior_cfo - prior_ppe - prior_intang
        ),
        "standalone_2026_cfo_less_ppe_and_non_franchise_intangibles_cr": _cr(
            parent_cfo - parent_ppe - parent_rights
        ),
        "standalone_cash_investment_can_be_added_to_group_franchise_cash": False,
        "foreign_exchange_carrying_value_is_new_cash_spend": False,
        "cashline_SRL_allocation_independently_traced_to_bank_payments": False,
        "residual_content_cash_is_maintenance_spending_verified": False,
        "group_shareholder_owner_cash_cr": None,
        "current_2026_10_20_equity_price": None,
        "current_fully_diluted_shares_verified": False,
        "parent_distributable_cash_including_cricket_rights": None,
        "financial_fair_value_established": False,
        "stock_expected_1y_or_3y_return": None,
        "historical_method_frozen_prior_to_2026_10_15": False,
        "result_claims_prospective_oct15_alpha": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def validate_suntv_reconciliation(
    value: dict[str, Any], *, root: Path
) -> None:
    unsigned = copy.deepcopy(value)
    seal = unsigned.pop("report_sha256", None)
    if seal != digest(unsigned):
        raise AlphaContractError("P019 source cash report SHA mismatch")
    p016_row, receipts = load_prior_evidence(root)
    if value != build_suntv_2026_cash_reconciliation(p016_row, receipts):
        raise AlphaContractError("P019 original source-reconciliation drift")
