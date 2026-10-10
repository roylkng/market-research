"""Point-in-time source-bound DEVX lease economics and creditor sensitivity.

Issuer FY26 standalone EBITDA and cash EBIT have a material lease-rent
difference. Independent October credit review reflects *consolidated*
leverage and later NCD financing. Do not combine mismatched bases into
fabricated enterprise-value or stock-return predictions.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

REPORT_ID = "HG007-P015-DEVX-FY26-CASH-EBIT-CREDIT-AND-WINSTON-HURDLE-v1"
BUNDLE_PATH = Path("research/hg007/devx-originals/source-bundle-v1.json")
BUNDLE_GIT_BLOB = "0aa2eb193772a509447ac4d46ab5e76caa94a0c4"
NSE_SHA = "2a3c319d7965a0c3c8602b65b6375bf5af63c0689dd5455ad05478724901a2a7"
CREDIT_SHA = "958e9f33b27d2299b6e49ae5cfbdaf042bd6f9248481ab1e5cadc21429876333"
ORIGINAL_HURDLES_PATH = Path("research/hg005-d003-result-v1.json")
ORIGINAL_HURDLES_GIT_BLOB = "b235bd9168bc658f7511f9cec1913f20f82cf311"
ORIGINAL_MARKET_PATH = Path("research/hg005-d001-result-v1.json")
ORIGINAL_MARKET_GIT_BLOB = "2dbbc3055d1aacec8a37dd510a1a75a3c7868006"
STANDALONE_INR_CRORE = {
    "fy26_revenue": 170.91,
    "fy26_indas_ebitda": 103.46,
    "fy26_cash_ebit": 36.55,
    "fy26_rent_outflow": 66.92,
    "fy26_lease_interest": 27.20,
    "fy26_right_of_use_depreciation": 50.24,
}
CREDIT_REVIEW = {
    "credit_date": "2026-10-08",
    "rating": "ACUITE BBB",
    "outlook": "Stable",
    "rated_ncd_outstanding_cr": 100.0,
    "additional_ncd_proposed_not_issued_cr": 50.0,
    "ncd_coupon_pct": 11.75,
    "fy26_debt_ebitda_including_lease": 3.11,
    "fy26_debt_ebitda_excluding_lease": 1.32,
    "fy26_ahmedabad_revenue_pct_approx": 46.0,
    "september_operational_space_msf": 1.13,
    "september_operational_seats": 17294,
}
Winston_SIGNED_SQFT = 450000


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _normalize(source: str) -> str:
    return re.sub(r"\s+", " ", source.casefold()).strip()


def _load_exact(root: Path, path: Path, expected_blob: str) -> tuple[dict, dict]:
    raw = (root / path).read_bytes()
    if _git_blob(raw) != expected_blob:
        raise ValueError(f"original DEVX research source changed: {path}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("original DEVX source JSON must contain an object")
    return payload, {
        "path": str(path),
        "git_blob_sha": expected_blob,
        "raw_sha256": _sha(raw),
    }


def _require_tokens(source: str, tokens: tuple[str, ...], label: str) -> None:
    for token in tokens:
        if token not in source:
            raise ValueError(f"original source missing {label}: {token}")


def _read_pdf(raw: bytes) -> tuple[list[str], tuple[str, ...]]:
    if _sha(raw) != NSE_SHA or len(raw) != 5537004 or not raw.startswith(b"%PDF-"):
        raise ValueError("original DEVX NSE PDF identity changed")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != 34:
            raise ValueError("DEVX original PDF page count changed")
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("original DEVX PDF pages cannot be parsed") from exc
    if len(pages) != 34:
        raise ValueError("original PDF page identity unavailable")
    fingerprints = tuple(_sha(page.encode("utf-8")) for page in pages)
    return pages, fingerprints


def load_original_devx_evidence(root: Path) -> tuple[dict, dict, dict]:
    bundle, bundle_receipt = _load_exact(root, BUNDLE_PATH, BUNDLE_GIT_BLOB)
    if (
        bundle.get("source_bundle_id") != (
            "HG007-P013-DEVX-FY26-LEASE-AND-OCT8-CREDIT-ORIGINALS-v1"
        )
        or bundle.get("both_independent_originals_available") is not True
        or bundle.get("live_capital_allowed") is not False
        or bundle.get("company_expected_returns_calculated") is not False
    ):
        raise ValueError("source-only DEVX originals not both independently captured")
    pdfreceipt = bundle["source_receipts"]["nse_pdf"]
    ratreceipt = bundle["source_receipts"]["acuite_html"]
    if (
        pdfreceipt["status"] != "SOURCE_CAPTURED_IDENTITY_CHECKED"
        or ratreceipt["status"] != "SOURCE_CAPTURED_IDENTITY_CHECKED"
        or pdfreceipt["raw_sha256"] != NSE_SHA
        or ratreceipt["raw_sha256"] != CREDIT_SHA
        or pdfreceipt.get("raw_byte_count") != 5537004
        or ratreceipt.get("raw_byte_count") != 87503
        or pdfreceipt.get("http_status") != 200
        or ratreceipt.get("http_status") != 200
        or pdfreceipt["structural_evidence"]["page_count"] != 34
        or ratreceipt["structural_evidence"]["source_rating_date"] != "2026-10-08"
    ):
        raise ValueError("original DEVX NSE or credit original source hash/receipt changed")
    pdf_path = root / "research/hg007/devx-originals/raw/sha256" / f"{NSE_SHA}.pdf"
    html_path = root / "research/hg007/devx-originals/raw/sha256" / f"{CREDIT_SHA}.html"
    pdf_raw, html_raw = pdf_path.read_bytes(), html_path.read_bytes()
    if _sha(pdf_raw) != NSE_SHA or _sha(html_raw) != CREDIT_SHA:
        raise ValueError("original NSE PDF or Acuite credit bytes modified")

    pages, page_hashes = _read_pdf(pdf_raw)
    if list(page_hashes) != pdfreceipt["structural_evidence"]["page_text_sha256"]:
        raise ValueError("original 34 PDF page text SHA hashes changed")
    # Page 28 (1-based) is the standalone IndAS/IGAAP bridge, *not*
    # the consolidated income statement on page 27.
    standalone = _normalize(pages[27])
    all_text = _normalize("\n".join(pages))
    _require_tokens(
        standalone,
        ("170.91", "103.46", "36.55", "66.92", "27.20", "50.24"),
        "FY26 standalone IndAS/lease/Cash EBIT original page 28",
    )
    _require_tokens(
        all_text, ("winston", "development management", "capital one"),
        "distinct future straight-lease and development pipeline",
    )

    rendered_html = BeautifulSoup(html_raw.decode("utf-8-sig"), "html.parser")
    credit = _normalize(rendered_html.get_text(" ", strip=True))
    _require_tokens(
        credit,
        ("dev accelerator limited", "october 08, 2026",
         "acuite bbb", "stable", "3.11", "1.32",
         "11.75", "1.13", "17,294", "46%", "ahmedabad"),
        "original October 8 credit review",
    )
    if _sha(credit.encode()) != ratreceipt["structural_evidence"]["source_text_sha256"]:
        raise ValueError("original credit source normalized text SHA changed")

    original_hurdles, original_hurdle_receipt = _load_exact(
        root, ORIGINAL_HURDLES_PATH, ORIGINAL_HURDLES_GIT_BLOB
    )
    market, market_receipt = _load_exact(
        root, ORIGINAL_MARKET_PATH, ORIGINAL_MARKET_GIT_BLOB
    )
    if (
        original_hurdles.get("context_id") != "HG005-D003-v1"
        or original_hurdles.get("completion_probabilities_assigned") is not False
        or original_hurdles.get("expected_returns_calculated") is not False
        or market.get("price_session") != "2026-10-01"
        or market.get("live_capital_allowed") is not False
    ):
        raise ValueError("frozen HG005 baseline/hurdle boundaries changed")
    proof = {
        "bundle_source": bundle_receipt,
        "nse_pdf": {"path": str(pdf_path.relative_to(root)), "sha256": NSE_SHA,
                    "byte_count": len(pdf_raw), "standalone_statement_page": 28,
                    "page_text_sha256": page_hashes[27]},
        "oct8_acuite": {"path": str(html_path.relative_to(root)), "sha256": CREDIT_SHA,
                        "byte_count": len(html_raw),
                        "normalized_text_sha256": _sha(credit.encode())},
        "hg005_original_hurdles": original_hurdle_receipt,
        "hg005_original_market_context": market_receipt,
    }
    return original_hurdles, market, proof


def build_devx_lease_cash_bridge(
    original: dict[str, Any], market: dict[str, Any], sources: dict
) -> dict[str, Any]:
    h = original.get("key_hurdles", {}).get("DEVX")
    price = market.get("key_mechanical_context", {}).get("DEVX")
    if not isinstance(h, dict) or not isinstance(price, dict):
        raise TypeError("missing original HG005 DEVX hurdle/market source")
    original_ebitda = h.get("fifty_pct_uplift_at_15x_required_incremental_annual_ebitda_inr_crore")
    if (
        h.get("state") != "REVERSE_HURDLE_READY"
        or h.get("winston_area_sqft") != Winston_SIGNED_SQFT
        or not isinstance(original_ebitda, (float, int))
        or not math.isclose(float(original_ebitda), 11.847268466, abs_tol=1e-8)
        or not math.isclose(price.get("reported_fd_market_cap_inr_crore", 0),
                            355.41805398, abs_tol=1e-8)
    ):
        raise ValueError("original DevX half-uplift hurdle/share price no longer frozen")
    rev = STANDALONE_INR_CRORE["fy26_revenue"]
    ebitda = STANDALONE_INR_CRORE["fy26_indas_ebitda"]
    rent = STANDALONE_INR_CRORE["fy26_rent_outflow"]
    cash = STANDALONE_INR_CRORE["fy26_cash_ebit"]
    difference = ebitda - rent - cash
    if not math.isclose(difference, 0, abs_tol=0.02):
        raise ValueError("FY26 lease EBITDA to Cash EBIT source math inconsistent")
    ratio = cash / ebitda
    nominal_annual_debt_coupon = (
        CREDIT_REVIEW["rated_ncd_outstanding_cr"] *
        CREDIT_REVIEW["ncd_coupon_pct"] / 100
    )
    if nominal_annual_debt_coupon != 11.75:
        raise ValueError("actual credit NCD 11.75 percent simple-coupon math changed")

    return {
        "schema_version": 1,
        "analysis_id": REPORT_ID,
        "classification": "DEVX_HISTORICAL_LEASE_CASH_RECONCILIATION_NOT_ALPHA_OR_STOCK_TARGET",
        "symbol": "DEVX",
        "evidence_as_of_ist": "2026-10-10",
        "source_provenance": sources,
        "fy26_standalone_issuer_reported": {
            **STANDALONE_INR_CRORE,
            "reported_ebitda_margin_pct": 100 * ebitda/rev,
            "reported_cash_ebit_margin_pct": 100 * cash/rev,
            "cash_ebit_as_ratio_of_indas_ebitda_pct": 100 * ratio,
            "lease_rental_outflow_as_ratio_of_indas_ebitda_pct": 100 * rent/ebitda,
            "indas_ebitda_less_cash_rent_less_cash_ebit_rounding_cr": difference,
            "standalone_does_not_equal_rating_consolidated_scope": True,
        },
        "oct8_independent_credit_report": {
            **CREDIT_REVIEW,
            "rated_ncd_tranches_cr": [25.0, 75.0],
            "full_year_nominal_coupon_on_100cr_ncd_at_11_75pct_cr": nominal_annual_debt_coupon,
            "full_year_coupon_is_not_fy26_expense_or_sep_cashflow": True,
            "50cr_proposed_ncd_interest_rate_unknown": True,
            "credit_rating_is_not_audited_stock_return_or_fair_value": True,
        },
        "frozen_hg005_hurdle_not_modified": {
            "legacy_price_session": "2026-10-01",
            "legacy_fd_market_cap_reference_cr": price["reported_fd_market_cap_inr_crore"],
            "signed_winston_straight_lease_area_sqft": Winston_SIGNED_SQFT,
            "legacy_50pct_uplift_15x_incremental_indas_ebitda_hurdle_cr": original_ebitda,
            "legacy_straight_lease_project_earnings_verified": False,
            "legacy_hurdle_is_an_approved_stock_target": False,
        },
        "purely_algebraic_not_prospective_scenarios": {
            "if_same_historic_company_mix_cash_ebit_hurdle_equivalent_cr": (
                original_ebitda * ratio
            ),
            "if_cash_ebit_hurdle_equals_legacy_ebitda_cr_needed_indas_ebitda_at_historic_ratio_cr": (
                original_ebitda / ratio
            ),
            "historic_company_mix_cannot_be_ascribed_to_new_winston_project": True,
            "15x_indas_ebitda_multiple_not_15x_cash_ebit_or_fcf_multiple": True,
            "neither_bridge_cell_is_a_expected_profit_or_return_forecast": True,
        },
        "material_unknowns": [
            "WINSTON_ACTUAL_CONSTRUCTION_OPERATIONAL_DATE_AND_APPROVED_LEASE",
            "WINSTON_FITTING_OUT_DEPOSIT_CAPEX_OCCUPANCY_AND_RENT_SCHEDULE",
            "WINSTON_ONLY_INCREMENTAL_CASH_EBIT_REVENUE_AND_FREE_CASH_FLOW",
            "INDAS116_LEASE_LIABILITY_EV_TREATMENT_AND_CASH_ACCOUNTING",
            "CURRENT_NCD_DEBT_OUTSTANDING_INTEREST_COST_AND_CASH_USE",
            "PROPOSED_50CR_NOT_ASSUMED_ISSUED_OR_INTEREST_RATE",
            "AHMEDABAD_PROJECT_CONCENTRATION_AND_CLIENT_LEASE_LOCKIN_MISMATCH",
            "JUPL_110CR_MONETIZATION_NOT_ASSUMED_COMPLETED",
            "CORPORATE_ACTIONS_AND_CURRENT_FULLY_DILUTED_CAPITAL",
        ],
        "winston_realized_income_verified": False,
        "cash_flow_earnings_to_current_valuation_reconciled": False,
        "credit_outlook_equals_equity_buy_recommendation": False,
        "company_completion_probability_published": False,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
