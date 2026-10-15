"""HG009 P011: independently source-replay PIXTRANS Q1 like-for-like earnings.

FY26 Q1 iXBRL is in INR *actuals*, FY27 Q1 iXBRL is in INR
*lakhs*. This comparison normalizes units and reporting basis using
original SHA-pinned NSE HTML and signed historical acquisition receipts.

Subtracting a current investment mark-to-market gain from FY27 while leaving
all FY26 other income untouched is ASYMMETRIC and cannot be called
normalized operating growth. No future return or shareholder owner FCF
is estimated by this module.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p009_originals import source_specifications

REPORT_ID = "HG009-P011-PIX-Q1-UNITS-AND-OTHER-INCOME-REDTEAM-v1"
SYMBOL = "PIXTRANS"
ISIN = "INE751B01018"
DOCUMENTS = {
    "Q1FY26_STANDALONE": {
        "receipt": (
            "research/hg009/p009-originals/attempts/"
            "38624670429-1-PIXTRANS-Q1FY26_STANDALONE.json"
        ),
        "raw_sha256": (
            "cb6144e127e566ee4c41f908b8b40f1eb768a9b7e12b4a2901f62afc4be28ce3"
        ),
        "receipt_sha256": (
            "3b6caecb65156a1c34f474054eaea020dc9a658d27be8f387c6e242369fe3c83"
        ),
        "source_unit": "INR_ACTUAL",
        "quarter_ended": "2025-06-30",
        "numeric_rows": {
            "revenue": ("Revenue from operations", "1106415000"),
            "other_income": ("Other income", "141867000"),
            "total_income": ("Total income", "1248282000"),
            "total_expenses": ("Total expenses", "938616000"),
            "pbt": ("Total profit before tax", "309666000"),
        },
    },
    "Q1FY27_STANDALONE": {
        "receipt": (
            "research/hg009/p009-originals/attempts/"
            "38624670429-1-PIXTRANS-Q1FY27_STANDALONE.json"
        ),
        "raw_sha256": (
            "24aa596c983d5c6717d2efb4acfbb77afc44be743ae09d2865a83ff0b0e4fe7d"
        ),
        "receipt_sha256": (
            "3723949cd6f9cb933e9f4150d5e9497c8c9bb02b2de128328c6032e5775996c8"
        ),
        "source_unit": "INR_LAKH",
        "quarter_ended": "2026-06-30",
        "numeric_rows": {
            "revenue": ("Revenue from operations", "13,453.20"),
            "other_income": ("Other income", "2,731.12"),
            "total_income": ("Total income", "16,184.32"),
            "total_expenses": ("Total expenses", "10,102.64"),
            "pbt": ("Total profit before tax", "6,081.68"),
        },
        "fvtpl_gain_in_other_income_lakh": "2,529.49",
    },
}


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _money(raw: str) -> Decimal:
    return Decimal(raw.replace(",", "").replace("(", "-").replace(")", ""))


def _in_crore(value: Decimal, unit: str) -> Decimal:
    if unit == "INR_ACTUAL":
        return value / Decimal(10_000_000)
    if unit == "INR_LAKH":
        return value / Decimal(100)
    raise AlphaContractError("P011 original currency-unit mismatch")


def _verified_source(
    repo_root: Path,
    *,
    period: str,
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    pinned = DOCUMENTS[period]
    spec = next(
        (
            s for s in source_specifications(repo_root)
            if s["symbol"] == SYMBOL and s["accounting_period"] == period
        ), None
    )
    if spec is None or spec["isin"] != ISIN:
        raise AlphaContractError("P011 frozen original NSE issuer/period absent")
    receipt = json.loads((repo_root / pinned["receipt"]).read_text("utf-8"))
    unsigned = copy.deepcopy(receipt)
    sig = unsigned.pop("receipt_sha256", None)
    expected_path = (
        "research/hg009/p009-originals/PIXTRANS/"
        f"{pinned['raw_sha256']}.html.gz"
    )
    if (
        sig != pinned["receipt_sha256"]
        or digest(unsigned) != sig
        or receipt.get("state") != "RAW_ARCHIVED_NOT_YET_FINANCIALLY_OR_IDENTITY_VALIDATED"
        or receipt.get("source_url") != spec["source_url"]
        or receipt.get("isin") != ISIN
        or receipt.get("symbol") != SYMBOL
        or receipt.get("raw_sha256") != pinned["raw_sha256"]
        or receipt.get("raw_repo_path") != expected_path
        or receipt.get("http_status") != 200
    ):
        raise AlphaContractError("P011 source or first archived NSE receipt changed")
    try:
        raw = gzip.decompress((repo_root / expected_path).read_bytes())
    except (FileNotFoundError, OSError) as exc:
        raise AlphaContractError("P011 original issuer HTML unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != pinned["raw_sha256"]:
        raise AlphaContractError("P011 original issuer bytes fail SHA")
    return raw, receipt, spec


def _extract_rows(
    html: bytes, *,
    expected: dict[str, Any],
) -> dict[str, Decimal]:
    soup = BeautifulSoup(html, "html.parser")
    header = _normalized(soup.get_text(" ", strip=True))
    if not all(word in header for word in (
        SYMBOL.casefold(), ISIN.casefold(), "standalone", "unaudited",
    )):
        raise AlphaContractError("P011 original NSE issuer/standalone period mismatch")
    if expected["source_unit"] == "INR_ACTUAL":
        if "in actuals" not in header or "30-jun-2025" not in header:
            raise AlphaContractError("P011 prior-year currency/quarter not actuals")
    elif "lakhs" not in header or "30-06-2026" not in header:
        raise AlphaContractError("P011 current-year currency/quarter not lakhs")
    cells = [
        _normalized(row.get_text(" ", strip=True))
        for row in soup.find_all("tr")
    ]
    if len(cells) < 25:
        raise AlphaContractError("P011 NSE source lacks financial rows")
    matched: dict[str, Decimal] = {}
    for key, (label, value) in expected["numeric_rows"].items():
        if not any(
            _normalized(label) in row and value.casefold() in row
            for row in cells
        ):
            raise AlphaContractError(f"P011 missing original reported cell {key}")
        matched[key] = _in_crore(_money(value), expected["source_unit"])
    if matched["total_income"] != (
        matched["revenue"] + matched["other_income"]
    ) or matched["pbt"] != (
        matched["total_income"] - matched["total_expenses"]
    ):
        raise AlphaContractError("P011 original income statement does not reconcile")
    if "fvtpl_gain_in_other_income_lakh" in expected:
        fvtpl = expected["fvtpl_gain_in_other_income_lakh"]
        if "fvtpl" not in header or fvtpl.casefold() not in header:
            raise AlphaContractError("P011 current FVTPL original issuer note missing")
        matched["fvtpl"] = _in_crore(_money(fvtpl), "INR_LAKH")
        if matched["fvtpl"] > matched["other_income"]:
            raise AlphaContractError("P011 FVTPL exceeds total reported other income")
    return matched


def _reported(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.0001")))


def _pct(a: Decimal, b: Decimal) -> float:
    if b <= 0:
        raise AlphaContractError("P011 base denominator must be positive")
    return float(((a / b - 1) * 100).quantize(Decimal("0.01")))


def build_pix_symmetric_income_bridge(root: Path) -> dict[str, Any]:
    numbers: dict[str, dict[str, Decimal]] = {}
    receipts: dict[str, dict[str, Any]] = {}
    for period, document in DOCUMENTS.items():
        raw, receipt, spec = _verified_source(root, period=period)
        numbers[period] = _extract_rows(raw, expected=document)
        receipts[period] = {
            "original_url": spec["source_url"],
            "quarter_ended": document["quarter_ended"],
            "source_display_unit": document["source_unit"],
            "source_sha256": document["raw_sha256"],
            "retained_original_receipt_path": document["receipt"],
            "retained_retrieval_utc": receipt["actual_retrieved_at_utc"],
        }
    prior = numbers["Q1FY26_STANDALONE"]
    current = numbers["Q1FY27_STANDALONE"]
    prior_no_other = prior["pbt"] - prior["other_income"]
    current_no_other = current["pbt"] - current["other_income"]
    current_less_fvtpl = current["pbt"] - current["fvtpl"]
    if (
        prior_no_other <= 0 or current_no_other <= 0
        or current_less_fvtpl <= 0
    ):
        raise AlphaContractError("P011 asymmetric earnings denominator invalid")
    result = {
        "schema_version": 1,
        "analysis_id": REPORT_ID,
        "as_of_research_date": "2026-10-15",
        "issuer": SYMBOL,
        "isin": ISIN,
        "reporting_basis": "STANDALONE_UNAUDITED_QUARTER_COMPARISON",
        "original_unit_discrepancy": (
            "Q1FY26_INR_ACTUALS_VS_Q1FY27_INR_LAKH"
        ),
        "original_source_receipts": receipts,
        "quarter_numbers_recalculated_to_inr_crore": {
            period: {
                metric: _reported(value)
                for metric, value in sorted(rows.items())
            }
            for period, rows in numbers.items()
        },
        "reported_pbt_yoy_pct": _pct(current["pbt"], prior["pbt"]),
        "reported_revenue_yoy_pct": _pct(
            current["revenue"], prior["revenue"]
        ),
        "current_fvtpl_share_of_reported_pbt_pct": float(
            (
                Decimal(100) * current["fvtpl"] / current["pbt"]
            ).quantize(Decimal("0.01"))
        ),
        "current_pbt_less_fvtpl_inr_crore": _reported(current_less_fvtpl),
        "current_other_income_less_fvtpl_inr_crore": _reported(
            current["other_income"] - current["fvtpl"]
        ),
        "asymmetric_current_less_fvtpl_vs_prior_reported_pbt_growth_pct": (
            _pct(current_less_fvtpl, prior["pbt"])
        ),
        "asymmetric_comparison_is_normalized_operating_growth": False,
        "prior_pbt_excluding_all_other_income_cr": _reported(prior_no_other),
        "current_pbt_excluding_all_other_income_cr": _reported(current_no_other),
        "symmetric_pbt_excluding_all_other_income_yoy_pct": _pct(
            current_no_other, prior_no_other
        ),
        "all_other_income_excluded_comparison_is_owner_cash": False,
        "prior_quarter_fvtpl_component_independently_verified": False,
        "consolidated_quarter_earnings_reconciled": False,
        "standalone_to_parent_cash_attribution_verified": False,
        "latest_fully_diluted_parent_shares_verified": False,
        "owner_cashflow_or_financial_asset_realization_verified": False,
        "expected_stock_return": None,
        "investment_recommendation_authorized": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = digest(result)
    return result


def verify_pix_symmetric_income_bridge(report: dict, root: Path) -> None:
    unsigned = copy.deepcopy(report)
    stored = unsigned.pop("packet_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P011 financial bridge signature altered")
    if report != build_pix_symmetric_income_bridge(root):
        raise AlphaContractError("P011 no longer reproduces original issuer statements")
