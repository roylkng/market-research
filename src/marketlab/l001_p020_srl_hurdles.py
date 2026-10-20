"""L001 P020: independently replay SunRisers Leeds franchise ROIC *hurdles*.

The frozen original FY26 Sun TV full issuer PDF supplies AOC-1 subsidiary
period earnings and management impairment assumptions. PAT and historical
acquisition price alone cannot identify shareholder IRR or sustainable cash
return. None of these source items were a prospective pre-Oct15 stock signal.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p019_suntv_rights import (
    ANNUAL_REPORT_URL,
    build_suntv_2026_cash_reconciliation,
    load_prior_evidence,
)

RESEARCH_ID = "L001-P020-ORIGINAL-SRL-PERIOD-PROFIT-AND-IMPAIRMENT-HURDLE-v1"
ARCHIVED_PDF_SHA = "4bb81cf41e5cd65f83f8b7acb41ccb8039135efaadb28b13bd469bd0b3dc356f"
P019_REPORT_SHA = "efb6fa9946db6d8ba16450ab5bbd6aa9648ba5fc0f6fc72fe5e62c66e202097e"
ORIGINAL_SOURCE_RECEIPT_SHA = "27faacde889769ea29cb4d724eeccb7d5131bc3bb42f9948f72f238a8d3f3a1c"
PDF_PATH = Path(
    "research/l001/originals/suntv_fy26/"
    f"suntv-fy26-full-{ARCHIVED_PDF_SHA}.pdf"
)
RECEIPT_PATH = Path(
    "research/l001/originals/suntv_fy26/attempts/39434163106-1.json"
)
P019_REPORT_PATH = Path("research/l001/l001-p019-suntv-franchise-rights-cash-bridge-v1.json")
REPORT_DATE = "2026-10-20"
HURDLE_YIELDS = ("0.05", "0.09", "0.12")
HUMAN_SOURCE_PAGE_IDS = (32, 226)
AOC_SOURCE = {
    "reporting_period_start": "2025-02-01",
    "reporting_period_end": "2026-03-31",
    "parent_control_effective": "2025-07-28",
    "name": "SunRisers Leeds Limited",
    "ownership_percent": "100.00",
    "turnover_cr": "94.52",
    "pretax_profit_cr": "21.20",
    "tax_cr": "4.87",
    "after_tax_profit_cr": "16.33",
    "proposed_dividend_cr": None,
}
IMPAIRMENT_SOURCE = {
    "as_of": "2026-03-31",
    "gross_franchise_asset_carrying_cr": "1248.27",
    "management_dcf_discount_rate_percent": "9",
    "asset_life_indefinite": True,
    "impairment_recorded": False,
    "management_pv_exceeds_carrying_as_reported": True,
}
_REQUIRED_EXCERPTS = {
    32: (
        "SunRisers Leeds Limited", "94.52", "21.20", "4.87", "16.33", "100.00",
        "February 1, 2025", "March 31, 2026", "July 28, 2025",
    ),
    226: (
        "1,248.27", "indefinite useful life", "no impairment loss", "discount rate of 9%",
    ),
}


def _normal(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKD", s).casefold())


def _amount(value: str, label: str) -> Decimal:
    if not isinstance(value, str):
        raise AlphaContractError(f"P020 {label} original decimal string absent")
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed < 0:
        raise AlphaContractError(f"P020 {label} original amount invalid")
    return parsed


def original_page_proof(root: Path) -> dict[str, Any]:
    file = root / PDF_PATH
    if not file.is_file():
        raise AlphaContractError("P020 full original first-party PDF not archived")
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ARCHIVED_PDF_SHA:
        raise AlphaContractError("P020 full original PDF SHA mismatch")
    receipt = json.loads((root / RECEIPT_PATH).read_text(encoding="utf-8"))
    unsigned = copy.deepcopy(receipt)
    stored = unsigned.pop("receipt_sha256", None)
    if (
        stored != ORIGINAL_SOURCE_RECEIPT_SHA
        or stored != digest(unsigned)
        or receipt.get("full_original_pdf_sha256") != ARCHIVED_PDF_SHA
        or receipt.get("full_original_pdf_byte_count") != len(raw)
        or receipt.get("stored_pdf_contains_original_full_document") is not True
        or receipt.get("original_pages_source_verified", {}).get("page_count") != 5
        or receipt.get("source_receipt_state") != "ORIGINAL_PDF_EVIDENCE_CAPTURED"
        or receipt.get("full_original_issuer_pdf_url") != ANNUAL_REPORT_URL
    ):
        raise AlphaContractError("P020 archived PDF receipt mismatched")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if len(reader.pages) != 231:
        raise AlphaContractError("P020 original Sun TV annual report page count drift")
    proof = []
    for page in HUMAN_SOURCE_PAGE_IDS:
        source = reader.pages[page].extract_text()
        if not isinstance(source, str) or len(source) < 200:
            raise AlphaContractError(f"P020 original annual report page {page} absent")
        clean = _normal(source)
        for term in _REQUIRED_EXCERPTS[page]:
            if _normal(term) not in clean:
                raise AlphaContractError(
                    f"P020 original issuer page {page} text missing: {term}"
                )
        proof.append({
            "original_pdf_zero_based_page": page,
            "extracted_page_text_sha256": hashlib.sha256(
                source.encode("utf-8")
            ).hexdigest(),
            "required_exact_terms": list(_REQUIRED_EXCERPTS[page]),
        })
    return {
        "full_original_pdf_repo_path": str(PDF_PATH),
        "full_original_pdf_sha256": ARCHIVED_PDF_SHA,
        "first_real_retrieval_at_utc": receipt["actual_retrieval_utc"],
        "original_capture_receipt_sha256": ORIGINAL_SOURCE_RECEIPT_SHA,
        "original_full_pdf_retained": True,
        "original_page_proofs": proof,
    }


def build_franchise_hurdle(
    *,
    p019: dict[str, Any],
    source_proof: dict[str, Any],
    original_aoc: dict[str, Any] | None = None,
    impairment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    src = AOC_SOURCE if original_aoc is None else original_aoc
    imp = IMPAIRMENT_SOURCE if impairment is None else impairment
    audited_pat = _amount(src["after_tax_profit_cr"], "SRL source period PAT")
    audited_rev = _amount(src["turnover_cr"], "SRL source period revenue")
    audited_pbt = _amount(src["pretax_profit_cr"], "SRL source period PBT")
    tax = _amount(src["tax_cr"], "SRL source period tax")
    initial = Decimal(str(p019["SRL_consolidated_franchise_right_initial_asset_cr"]))
    carry = _amount(imp["gross_franchise_asset_carrying_cr"], "carrying value")
    rate = _amount(imp["management_dcf_discount_rate_percent"], "discount rate")
    if (
        p019["report_sha256"] != P019_REPORT_SHA
        or p019["financial_fair_value_established"] is not False
        or src["parent_control_effective"] <= src["reporting_period_start"]
        or src["reporting_period_end"] != "2026-03-31"
        or src["ownership_percent"] != "100.00"
        or audited_pbt - tax != audited_pat
        or imp["asset_life_indefinite"] is not True
        or imp["impairment_recorded"] is not False
        or not (Decimal(0) < rate < Decimal(30))
        or carry != initial + Decimal(str(p019["SRL_franchise_right_fx_translation_cr_not_new_cash"]))
    ):
        raise AlphaContractError("P020 source period, ownership or impairment assumptions drift")
    if source_proof.get("full_original_pdf_sha256") != ARCHIVED_PDF_SHA:
        raise AlphaContractError("P020 original full PDF source proof absent")
    implied = [
        {
            "illustrative_flat_annual_owner_cash_hurdle_yield": float(Decimal(y)),
            "required_recurring_owner_cash_cr_if_no_growth": round(
                float(initial * Decimal(y)), 4
            ),
            "compared_to_nonannualized_period_PAT_ratio_not_ROIC": round(
                float((initial * Decimal(y)) / audited_pat), 4
            ),
            "verified_shareholder_cash_distribution_or_yield": False,
        }
        for y in HURDLE_YIELDS
    ]
    result = {
        "schema_version": 1,
        "review_id": RESEARCH_ID,
        "research_as_of": REPORT_DATE,
        "source_document": source_proof,
        "p019_audited_cash_bridge_sha256": P019_REPORT_SHA,
        "symbol": "SUNTV",
        "isin": "INE424H01027",
        "franchise": "SUNRISERS_LEEDS",
        "source_aoc1_period": src,
        "source_impairment_note": imp,
        "source_period_PAT_to_initial_asset_cost_percent_not_ROIC": round(
            float(audited_pat / initial) * 100, 4
        ),
        "source_period_reported_PAT_margin_percent": round(
            float(audited_pat / audited_rev) * 100, 4
        ),
        "initial_franchise_right_asset_cr": float(initial),
        "reported_group_carrying_value_cr_not_liquidation_value": float(carry),
        "management_impairment_DCF_discount_rate_percent": float(rate),
        "hypothetical_cash_hurdles_unlinked_to_forecasts": implied,
        "post_acquisition_annual_SRL_owner_cash_cr": None,
        "franchise_acquisition_cash_vs_accounting_asset_mapped_to_bank_records": False,
        "aoc1_period_is_post_control_only": False,
        "AOC_profit_is_cash_flow": False,
        "AOC_PAT_ratio_is_annualized_invested_capital_ROIC": False,
        "9pct_discount_rate_is_proven_investor_required_return": False,
        "no_impairment_means_stock_is_undervalued": False,
        "franchise_perpetuity_cash_flow_assumed": False,
        "sustainable_media_content_reinvestment_cr": None,
        "normalized_parent_owner_FCF_cr": None,
        "current_fully_diluted_share_count_verified": False,
        "historical_return_signal_preregistered_prior_oct15": False,
        "current_stock_fair_value_per_share_inr": None,
        "expected_net_3y_stock_return": None,
        "company_paper_investment_eligible": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def materialize(root: Path) -> dict[str, Any]:
    previous = json.loads((root / P019_REPORT_PATH).read_text(encoding="utf-8"))
    existing, receipts = load_prior_evidence(root)
    recreated = build_suntv_2026_cash_reconciliation(existing, receipts)
    if previous != recreated:
        raise AlphaContractError("P020 earlier original cashflow bridge altered")
    return build_franchise_hurdle(
        p019=previous,
        source_proof=original_page_proof(root),
    )


def validate(value: dict[str, Any], root: Path) -> None:
    unsigned = copy.deepcopy(value)
    stored = unsigned.pop("report_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P020 original source report digest mismatch")
    if value != materialize(root):
        raise AlphaContractError("P020 original source replay not identical")
