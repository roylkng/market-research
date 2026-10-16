"""P017: ACE two-year original NSE cash-flow bridge, with source custody.

The observed FY26 CFO-minus-PPE increase may reflect a CAPEX spend decline
rather than operating growth. Source is FY25 NSE FY-end CONSOLIDATED "Actuals"
(rupees), not "Lakhs". FY26 is independent retained source at lakh units.

This is an ex-post fundamental review following the Oct-15 first equity
observation, NOT a preregistered market signal or an investment valuation.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p013_cash_bridge import (
    _row_values,
    build_original_fy26_cash_use,
)
from requests.exceptions import RequestException

ID = "HG009-P017-ACE-FY25-FY26-CAPEX-TIMING-AUDIT-v1"
FY25_URL = (
    "https://nsearchives.nseindia.com/corporate/ixbrl/"
    "INTEGRATED_FILING_INDAS_94161_27052025123326_iXBRL_WEB.html"
)
FY25_ISIN = "INE731H01025"
FY25_PERIOD = "2025-03-31"
FIRST_RECEIPT = Path("research/hg009/p017-originals/first-valid-ACE-FY25.json")
ARCHIVE_DIR = Path("research/hg009/p017-originals/by-symbol/ACE")
SOURCE_P013 = Path("research/hg009/hg009-p013-fy26-cash-use-bridge-v1.json")
SOURCE_P015 = Path("research/hg009/hg009-p015-ace-acutaas-hurdles-v1.json")
P013_BLOB = "2b2891b1d5c38a570bd492b4eb822fabf9fd9f36"
P015_BLOB = "bad0a593937ac6132488c6886ddd5a80c50e946e"

# Source: NSE FY25 "INR (in Actuals)" original cash statement, NOT in lakhs.
# Values below are original INR rupees and verified against the retained HTML.
FIELDS = {
    "pbt": ("operating", "profit before tax"),
    "cfo": ("operating", "net cash flows from (used in) operating activities"),
    "ppe_cash_purchase": ("investing", "purchase of property, plant and equipment"),
    "investment_security_bought": (
        "investing",
        "other cash payments to acquire equity or debt instruments of other entities",
    ),
    "investment_security_sold": (
        "investing",
        "other cash receipts from sales of equity or debt instruments of other entities",
    ),
    "net_investing": ("investing", "net cash flows from (used in) investing activities"),
    "net_financing": ("financing", "net cash flows from (used in) financing activities"),
    "cash_begin": (
        "financing", "cash and cash equivalents cash flow statement at beginning of period",
    ),
    "cash_end": (
        "financing", "cash and cash equivalents cash flow statement at end of period",
    ),
    "cash_change": ("financing", "net increase (decrease) in cash and cash equivalents"),
    "lease_paid": ("financing", "payments of lease liabilities"),
    "interest_paid": ("financing", "interest paid"),
    "dividends_paid": ("financing", "dividends paid"),
    "inventory_change": (
        "operating", "adjustments for decrease (increase) in inventories",
    ),
    "receivables_change": (
        "operating", "adjustments for decrease (increase) in trade receivables, current",
    ),
    "payables_change": (
        "operating", "adjustments for increase (decrease) in trade payables, current",
    ),
}
EXPECTED_RUPEES = {
    "pbt": "5491200000",
    "cfo": "4119800000",
    "ppe_cash_purchase": "2210000000",
    "investment_security_bought": "7375900000",
    "investment_security_sold": "4602200000",
    "net_investing": "-3826900000",
    "net_financing": "-289900000",
    "cash_begin": "482100000",
    "cash_end": "488400000",
    "cash_change": "6300000",
    "lease_paid": "5200000",
    "interest_paid": "122000000",
    "dividends_paid": "238000000",
    "inventory_change": "189800000",
    "receivables_change": "-1103200000",
    "payables_change": "1057900000",
}
FX_EFFECT_RUPEES = Decimal("3300000")
RUPEES_PER_CRORE = Decimal("10000000")
CRORE_PRECISION = Decimal("0.0001")


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _load_pinned(root: Path, path: Path, expected_blob: str, signature: str) -> dict:
    raw = (root / path).read_bytes()
    if _git_blob(raw) != expected_blob:
        raise AlphaContractError(f"P017 frozen original research source changed: {path}")
    data = json.loads(raw)
    unsigned = copy.deepcopy(data)
    stated = unsigned.pop(signature, None)
    if stated != digest(unsigned):
        raise AlphaContractError(f"P017 original research source signature invalid: {path}")
    return data


def _crore(rupees: Decimal) -> float:
    if not rupees.is_finite():
        raise AlphaContractError("P017 original cash value not finite")
    return float((rupees / RUPEES_PER_CRORE).quantize(CRORE_PRECISION))


def _original_cash_rows(raw: bytes) -> dict[tuple[str, str], list[Decimal]]:
    # Reuse exact already-regressed P013 section-aware HTML table parsing.
    return _row_values(raw)


def extract_ace_fy25_original(raw: bytes) -> dict[str, Decimal]:
    if not 2000 <= len(raw) <= 3_000_000:
        raise AlphaContractError("P017 NSE original FY25 issuer HTML absent/oversized")
    html = BeautifulSoup(raw, "html.parser")
    text = " ".join(html.get_text(" ", strip=True).split())
    if (
        not re.search(r"\bNSE\s+Symbol\s+ACE\b", text, re.I)
        or FY25_ISIN not in text
        or not re.search(r"\b31[- ]Mar[- ]2025\b", text, re.I)
        or not re.search(r"\bConsolidated\b", text, re.I)
        or not re.search(r"\bAudited\b", text, re.I)
        or not re.search(r"INR\s*\(in\s+Actuals\)", text, re.I)
    ):
        raise AlphaContractError("P017 wrong FY25 issuer, period, basis or currency")
    parsed = _original_cash_rows(raw)
    values = {}
    for key, original in FIELDS.items():
        matched = parsed.get(original, [])
        if len(matched) != 1:
            raise AlphaContractError(f"P017 original FY25 row missing/ambiguous: {key}")
        expected = Decimal(EXPECTED_RUPEES[key])
        if matched[0] != expected:
            raise AlphaContractError(f"P017 changed original FY25 financial cell: {key}")
        values[key] = matched[0]
    if (
        values["cfo"] + values["net_investing"]
        + values["net_financing"] + FX_EFFECT_RUPEES
        != values["cash_change"]
        or values["cash_begin"] + values["cash_change"] != values["cash_end"]
    ):
        raise AlphaContractError("P017 original FY25 consolidated cash flow does not balance")
    return values


def capture_fy25_ace(
    *,
    fetch: Callable[[str], tuple[int, bytes | None]],
    observed_at: datetime,
    root: Path,
) -> dict[str, Any]:
    if observed_at.tzinfo is None:
        raise AlphaContractError("P017 original-source observation needs UTC offset")
    observed = observed_at.astimezone(UTC).isoformat()
    try:
        status, raw = fetch(FY25_URL)
    except (OSError, TimeoutError, RequestException) as exc:
        return {
            "state": "BLOCKED_ORIGINAL_NSE_TRANSPORT",
            "error_type": type(exc).__name__,
            "http_status": None,
            "captured_at_utc": observed,
            "symbol": "ACE",
            "raw_sha256": None,
            "live_capital_allowed": False,
        }
    if status != 200 or raw is None:
        return {
            "state": "BLOCKED_ORIGINAL_NSE_HTTP",
            "http_status": status,
            "captured_at_utc": observed,
            "symbol": "ACE",
            "raw_sha256": None,
            "live_capital_allowed": False,
        }
    try:
        rows = extract_ace_fy25_original(raw)
    except AlphaContractError as exc:
        return {
            "state": "BLOCKED_FY25_ISSUER_OR_FINANCIAL_ROW",
            "http_status": 200,
            "captured_at_utc": observed,
            "symbol": "ACE",
            "error_type": type(exc).__name__,
            "untrusted_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_sha256": None,
            "live_capital_allowed": False,
        }
    sha = hashlib.sha256(raw).hexdigest()
    location = root / ARCHIVE_DIR / f"{sha}.html.gz"
    location.parent.mkdir(parents=True, exist_ok=True)
    compressed = gzip.compress(raw, mtime=0, compresslevel=9)
    if location.exists() and location.read_bytes() != compressed:
        raise AlphaContractError("P017 immutable content-addressed NSE source collision")
    location.write_bytes(compressed)
    receipt = {
        "state": "ORIGINAL_NSE_FY25_CONSOLIDATED_CASHFLOW_REPLAYED",
        "symbol": "ACE",
        "isin": FY25_ISIN,
        "source_url": FY25_URL,
        "reported_unit": "ORIGINAL_INR_ACTUALS_NOT_LAKHS",
        "original_period_end": FY25_PERIOD,
        "observed_at_utc": observed,
        "source_sha256": sha,
        "original_archive_repo_path": str(location.relative_to(root)),
        "cash_flow_rows_verified": len(rows),
        "original_raw_size": len(raw),
        "economic_owner_cash_flow_calculated": False,
        "live_capital_allowed": False,
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def _receipt(root: Path) -> tuple[dict, dict[str, Decimal]]:
    receipt = json.loads((root / FIRST_RECEIPT).read_text(encoding="utf-8"))
    unsigned = copy.deepcopy(receipt)
    signature = unsigned.pop("receipt_sha256", None)
    if signature != digest(unsigned):
        raise AlphaContractError("P017 first captured source receipt hash differs")
    if (
        receipt.get("state") != "ORIGINAL_NSE_FY25_CONSOLIDATED_CASHFLOW_REPLAYED"
        or receipt.get("symbol") != "ACE"
        or receipt.get("isin") != FY25_ISIN
        or receipt.get("source_url") != FY25_URL
        or receipt.get("original_period_end") != FY25_PERIOD
        or receipt.get("reported_unit") != "ORIGINAL_INR_ACTUALS_NOT_LAKHS"
        or receipt.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("P017 first FY25 ACE receipt identity changed")
    path = root / receipt["original_archive_repo_path"]
    if not path.resolve().is_relative_to((root / ARCHIVE_DIR).resolve()):
        raise AlphaContractError("P017 unsafe original source archive path")
    raw = gzip.decompress(path.read_bytes())
    if (
        len(raw) != receipt["original_raw_size"]
        or hashlib.sha256(raw).hexdigest() != receipt["source_sha256"]
    ):
        raise AlphaContractError("P017 retained original NSE FY25 bytes altered")
    return receipt, extract_ace_fy25_original(raw)


def build_ace_fy25_fy26_cash_audit(root: Path) -> dict[str, Any]:
    receipt, fy25 = _receipt(root)
    p013 = _load_pinned(root, SOURCE_P013, P013_BLOB, "report_sha256")
    p015 = _load_pinned(root, SOURCE_P015, P015_BLOB, "packet_sha256")
    # Reparse original FY26 HTML, not just a derived signed summary.
    reproduced_p013 = build_original_fy26_cash_use(root)
    if reproduced_p013 != p013:
        raise AlphaContractError("P017 FY26 original issuer statement replay changed")
    old = [row for row in p013["symbol_records"] if row["symbol"] == "ACE"]
    price = [row for row in p015["two_case_records"] if row["symbol"] == "ACE"]
    if (
        len(old) != 1
        or len(price) != 1
        or old[0]["original_nse_isin"] != FY25_ISIN
        or price[0]["original_isin"] != FY25_ISIN
        or price[0]["dated_market_price_period"] != "2026-10-15"
    ):
        raise AlphaContractError("P017 original ACE comparison identity/date mismatch")
    fy26 = old[0]["original_values_in_inr_crore"]
    pbt25 = _crore(fy25["pbt"])
    cfo25 = _crore(fy25["cfo"])
    ppe25 = _crore(fy25["ppe_cash_purchase"])
    # Extract PBT from the same FIRST-BYTE ATTESTED original FY26 issuer
    # HTML, not from a second mutable or unit-ambiguous summary.
    original_fy26_path = root / old[0]["original_source_path"]
    original_fy26_html = gzip.decompress(original_fy26_path.read_bytes())
    if hashlib.sha256(original_fy26_html).hexdigest() != (
        old[0]["original_nse_full_html_sha256"]
    ):
        raise AlphaContractError("P017 FY26 original ACE bytes changed")
    matched_pbt = _row_values(original_fy26_html).get(
        ("operating", "profit before tax"), []
    )
    if len(matched_pbt) != 1 or matched_pbt[0] != Decimal("55671.00"):
        raise AlphaContractError("P017 FY26 original ACE PBT mismatch")
    # FY26 iXBRL reports in INR LAKHS, unlike FY25 INR ACTUALS.
    pbt26 = float(matched_pbt[0] / Decimal("100"))
    cfo26 = fy26["cfo"]
    ppe26 = fy26["ppe_purchase"]
    proxy25, proxy26 = cfo25 - ppe25, cfo26 - ppe26
    cash_change = cfo26 - cfo25
    ppe_decline = ppe25 - ppe26
    proxy_change = proxy26 - proxy25
    if abs((cash_change + ppe_decline) - proxy_change) > 1e-8:
        raise AlphaContractError("P017 cash-versus-capex improvement does not decompose")
    market = price[0]
    market_cap = market["cross_date_illustrative_basic_market_cap_cr"]
    if market_cap <= 0:
        raise AlphaContractError("P017 no valid dated cross-period equity reference")

    f25 = {k: _crore(v) for k, v in fy25.items()}
    out = {
        "schema_version": 1,
        "research_id": ID,
        "source_review_date": "2026-10-16",
        "source_filing_periods": ["FY25", "FY26"],
        "comparability": "CONSOLIDATED_AUDITED_BOTH_YEARS",
        "fy25_source_original_unit": "INR_ACTUALS",
        "fy26_source_original_unit": "INR_LAKH",
        "first_verified_fy25_original_capture_utc": receipt["observed_at_utc"],
        "fy25_original_source_SHA256": receipt["source_sha256"],
        "fy25_original_receipt_sha256": receipt["receipt_sha256"],
        "fy26_original_bridge_sha256": p013["report_sha256"],
        "market_source_reverse_hurdle_sha256": p015["packet_sha256"],
        "original_company_symbol": "ACE",
        "original_NSE_ISIN": FY25_ISIN,
        "fy25_original_consolidated_cash_cr": f25,
        "fy26_original_consolidated_cash_cr": fy26,
        "fy25_CFO_cr": round(cfo25, 4),
        "fy26_CFO_cr": round(cfo26, 4),
        "fy25_PPE_cash_spend_cr": round(ppe25, 4),
        "fy26_PPE_cash_spend_cr": round(ppe26, 4),
        "fy25_CFO_less_PPE_cr_not_owner_FCF": round(proxy25, 4),
        "fy26_CFO_less_PPE_cr_not_owner_FCF": round(proxy26, 4),
        "fy25_PBT_cr": round(pbt25, 4),
        "fy26_PBT_cr": round(pbt26, 4),
        "CFO_YoY_change_pct": round(100 * (cfo26 / cfo25 - 1), 4),
        "PBT_YoY_change_pct": round(100 * (pbt26 / pbt25 - 1), 4),
        "PPE_spend_YoY_change_pct": round(100 * (ppe26 / ppe25 - 1), 4),
        "CFO_less_PPE_proxy_change_cr": round(proxy_change, 4),
        "CFO_change_component_cr": round(cash_change, 4),
        "PPE_spend_reduction_component_cr": round(ppe_decline, 4),
        "share_of_proxy_improvement_from_reduced_PPE_spend_pct": round(
            ppe_decline / proxy_change * 100, 4
        ),
        "FY26_counterfactual_proxy_holding_FY25_PPE_spend_cr": round(
            cfo26 - ppe25, 4
        ),
        "original_oct15_share_price_inr": market["dated_price_EQ_close_inr"],
        "oct15_cross_date_basic_market_cap_cr_not_current_fd": market_cap,
        "FY25_proxy_yield_vs_cross_date_basic_cap_pct": round(
            100 * proxy25 / market_cap, 4
        ),
        "FY26_proxy_yield_vs_cross_date_basic_cap_pct": round(
            100 * proxy26 / market_cap, 4
        ),
        "FY25_FY26_security_investment_net_purchases_are_operating_capex": False,
        "cash_proxy_growth_is_normalized_owner_cash_growth": False,
        "lower_cash_PPE_spend_is_proof_of_higher_ROIC": False,
        "same_ISIN_proves_October_fully_diluted_shares": False,
        "after_tax_and_corporate_action_total_return_ready": False,
        "probability_weighted_50pct_future_return": None,
        "investment_recommendation_generated": False,
        "capital_eligible": False,
        "live_capital_allowed": False,
    }
    out["report_sha256"] = digest(out)
    return out


def verify_ace_fy25_fy26_cash_audit(packet: dict, root: Path) -> None:
    unsigned = copy.deepcopy(packet)
    signature = unsigned.pop("report_sha256", None)
    if signature != digest(unsigned):
        raise AlphaContractError("P017 cash-audit packet SHA invalid")
    if packet != build_ace_fy25_fy26_cash_audit(root):
        raise AlphaContractError("P017 report cannot replay original NSE sources")
