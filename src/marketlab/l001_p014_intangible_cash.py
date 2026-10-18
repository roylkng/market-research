"""L001 P014: independently replay FY26 cash acquisitions of intangible assets.

This is *not* distributable free cash flow. A zero tagged field does not prove
an issuer has no acquisition, content, R&D or licensing investments elsewhere.
The semantic classification of growth vs sustaining intangible spend is
UNKNOWN for every company until original issuer notes are reconciled.
"""
from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from marketlab.alpha import AlphaContractError, digest

P004_REPORT_SHA = "97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d"
P004_REPORT_ID = "L001-P004-FROZEN-HG009-ALL100-ORIGINAL-REPLAY-v1"
ORIGINAL_CONCEPT = "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"
ORIGINAL_CONTEXT = "FourD"
ORIGINAL_UNIT = "INR"
CUTOFF_UTC = "2026-10-15T13:00:00Z"


def _utc(value: object) -> datetime:
    try:
        stamp = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        stamp = None
    if stamp is None or stamp.utcoffset() != timedelta(0):
        raise AlphaContractError("original annual source UTC timestamp invalid")
    return stamp


def extract_original_intangible_cr(raw: bytes) -> float:
    """One exact annual INR purchase concept, never a guessed name/tag."""
    if not isinstance(raw, bytes) or len(raw) < 100:
        raise AlphaContractError("original financial XBRL raw bytes unavailable")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise AlphaContractError("original financial XML malformed") from exc
    candidates = []
    for element in root.iter():
        if (
            element.tag.rsplit("}", 1)[-1] == ORIGINAL_CONCEPT
            and element.attrib.get("contextRef") == ORIGINAL_CONTEXT
            and element.attrib.get("unitRef") == ORIGINAL_UNIT
        ):
            try:
                value = float(element.text)
            except (ValueError, TypeError) as exc:
                raise AlphaContractError("intangible purchase value nonnumeric") from exc
            if not math.isfinite(value) or value < 0:
                raise AlphaContractError("intangible purchase not nonnegative or finite")
            candidates.append(value)
    if len(candidates) != 1:
        raise AlphaContractError("missing or ambiguous exact annual intangible purchase fact")
    return round(candidates[0] / 1e7, 6)


def audit_original_intangibles(
    original_p004: dict, annual_xml_by_sha: dict[str, bytes],
) -> dict:
    """All 100 source-normalized accounting observations or fail completely."""
    if not isinstance(original_p004, dict):
        raise AlphaContractError("original 100-company accounting source missing")
    expected = original_p004.get("report_sha256")
    if (
        expected != P004_REPORT_SHA
        or digest({
            key: value for key, value in original_p004.items() if key != "report_sha256"
        }) != P004_REPORT_SHA
        or original_p004.get("report_id") != P004_REPORT_ID
        or original_p004.get("company_count") != 100
        or original_p004.get("original_xml_sha256_checked") != 300
        or original_p004.get("original_numeric_xbrl_values_replayed") != 400
        or original_p004.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("original P004 source authenticity changed")
    entries = original_p004.get("source_results")
    if not isinstance(entries, list) or len(entries) != 100:
        raise AlphaContractError("expected exact 100 original company source records")
    original_shas = {
        row["financial_sources"]["annual"]["raw_sha256"] for row in entries
    }
    if not isinstance(annual_xml_by_sha, dict) or set(annual_xml_by_sha) != original_shas:
        raise AlphaContractError("exact original 100 annual XML byte inventory required")
    cutoff = _utc(CUTOFF_UTC)
    symbols = set()
    results = []
    for entry in entries:
        symbol, isin = entry.get("symbol"), entry.get("isin")
        if (
            not isinstance(symbol, str) or not symbol
            or not isinstance(isin, str) or len(isin) != 12
            or (symbol, isin) in symbols
        ):
            raise AlphaContractError("issuer symbol or ISIN invalid/duplicate")
        symbols.add((symbol, isin))
        original = entry["financial_sources"]["annual"]
        sha = original.get("raw_sha256")
        raw = annual_xml_by_sha.get(sha)
        if (
            original.get("period_end") != "2026-03-31"
            or not isinstance(raw, bytes)
            or hashlib.sha256(raw).hexdigest() != sha
            or _utc(original.get("exchange_published_at_utc")) > cutoff
        ):
            raise AlphaContractError("FY26 annual original filing source or timing invalid")
        intangible = extract_original_intangible_cr(raw)
        cfo, ppe = entry.get("fy26_operating_cfo_cr"), entry.get("fy26_ppe_purchase_cr")
        if (
            type(cfo) not in (float, int)
            or type(ppe) not in (float, int)
            or not math.isfinite(cfo) or not math.isfinite(ppe) or ppe < 0
        ):
            raise AlphaContractError("original CFO/PPE source value missing")
        raw_proxy = round(cfo - ppe, 6)
        if abs(raw_proxy - entry["fy26_cfo_less_ppe_cr_not_owner_cash"]) > 0.000002:
            raise AlphaContractError("P004 original CFO/PPE arithmetic drift")
        all_purchases_proxy = round(cfo - ppe - intangible, 6)
        results.append({
            "symbol": symbol, "isin": isin,
            "annual_original_xbrl_sha256": sha,
            "annual_original_source_url": original["original_url"],
            "reported_accounting_scope": original["accounting_basis"],
            "annual_original_published_utc": original["exchange_published_at_utc"],
            "fy26_cfo_cr": cfo,
            "fy26_ppe_purchases_cr": ppe,
            "fy26_intangible_purchases_cr": intangible,
            "fy26_cfo_after_ppe_proxy_cr_not_owner_cash": raw_proxy,
            "fy26_cfo_after_ppe_intangible_purchases_cr_not_owner_cash": all_purchases_proxy,
            "intangible_spend_genuine_source": intangible > 0,
            "zero_intangible_concept_does_not_prove_no_acquisitions": True,
            "maintenance_growth_content_franchise_split_verified": False,
            "unresolved_tax_lease_interest_minority_and_funding_claims": True,
            "realized_equity_returns_evaluated": False,
            "expected_return": None,
            "capital_eligible": False,
        })
    results.sort(key=lambda row: (row["symbol"], row["isin"]))
    positive = [row for row in results if row["fy26_intangible_purchases_cr"] > 0]
    report = {
        "schema_version": 1,
        "report_id": "L001-P014-ORIGINAL-100-FY26-INTANGIBLE-PURCHASES-v1",
        "original_p004_sha256": P004_REPORT_SHA,
        "historical_issuer_count": len(results),
        "annual_xml_sha256_reverified_count": len(results),
        "annual_original_exact_xbrl_intangible_cells_replayed": len(results),
        "positive_tagged_intangible_purchase_count": len(positive),
        "zero_tagged_intangible_purchase_count_not_a_proof_of_none": (
            len(results) - len(positive)
        ),
        "positive_tagged_source_symbols": [
            row["symbol"] for row in positive
        ],
        "sun_tv_original_intangible_cash_purchase_cr": next(
            row["fy26_intangible_purchases_cr"]
            for row in results if row["symbol"] == "SUNTV"
        ),
        "taxonomically_absent_spend_not_filled_with_zero": True,
        "asset_purchase_maint_growth_and_acquisition_semantics_unresolved": True,
        "frozen_hg009_outcome_rule_unchanged": True,
        "new_prediction_or_recommended_trade": False,
        "live_capital_allowed": False,
        "companies": results,
    }
    report["report_sha256"] = digest(report)
    return report
