"""L001 P015: 100-company original annual XBRL investing cash taxonomy.

Read the *same* immutable P004 annual XBRL source files used by P014. This
inventory never sums investing subcategories as though they were independent:
nested/overlapping net-flow, proceeds, and purchase concepts may double-count
the same transaction. Absence of a tag is NOT proof of zero economic spending.

This is a post-hoc accounting falsification, not pre-October-15 alpha.
"""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p014_intangible_cash import (
    ORIGINAL_CONCEPT,
    P004_REPORT_SHA,
    audit_original_intangibles,
)

REVIEW_ID = "L001-P015-FY26-ORIGINAL-100-INVESTING-CASH-TAXONOMY-v1"
REVIEW_DATE = "2026-10-19"
NET_INVESTING_CONCEPT = "CashFlowsFromUsedInInvestingActivities"
PPE_CONCEPT = "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
CONTEXT = "FourD"
UNIT = "INR"


def _accepted_cash_concept(tag: str) -> bool:
    """Surface exact FY26 investing-cash concepts, not balance sheet accruals."""
    return (
        tag == NET_INVESTING_CONCEPT
        or tag.endswith("ClassifiedAsInvestingActivities")
    )


def _type(tag: str) -> str:
    if tag == NET_INVESTING_CONCEPT:
        return "NET_INVESTING_CASH_NOT_ADDABLE_TO_COMPONENTS"
    if tag == PPE_CONCEPT:
        return "FIXED_ASSET_CASH_PURCHASE"
    if tag == ORIGINAL_CONCEPT:
        return "INTANGIBLE_ASSET_CASH_PURCHASE"
    low = tag.casefold()
    if any(k in low for k in ("acquisitionof", "acquisitionsof", "purchaseofbusiness")):
        return "BUSINESS_OR_INVESTMENT_ACQUISITION_NEEDS_NOTES"
    if any(k in low for k in ("proceedsfrom", "proceedsreceived", "inflow")):
        return "INVESTING_PROCEEDS_OR_INFLOW_NOT_NEGATIVE_CAPEX"
    if any(k in low for k in ("purchaseof", "purchaseto", "paymentsto", "outflow")):
        return "OTHER_INVESTING_PURCHASE_OR_OUTFLOW_REQUIRES_NOTES"
    return "OTHER_INVESTING_COMPONENT_WITH_UNKNOWN_CASH_SEMANTICS"


def source_investing_facts(raw_xml: bytes) -> list[dict[str, Any]]:
    """Catalog exact source FY26 tags without pretending to sum cash outflows."""
    if not isinstance(raw_xml, bytes) or len(raw_xml) < 100:
        raise AlphaContractError("P015 full original XBRL XML required")
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        raise AlphaContractError("P015 malformed annual XBRL XML") from exc
    matches: dict[str, list[float]] = {}
    for item in root.iter():
        tag = item.tag.rsplit("}", 1)[-1]
        if (
            not _accepted_cash_concept(tag)
            or item.attrib.get("contextRef") != CONTEXT
            or item.attrib.get("unitRef") != UNIT
        ):
            continue
        try:
            value = float(item.text)
        except (ValueError, TypeError) as exc:
            raise AlphaContractError(f"P015 nonnumeric original investing concept: {tag}") from exc
        if not math.isfinite(value):
            raise AlphaContractError(f"P015 nonfinite original investing concept: {tag}")
        matches.setdefault(tag, []).append(value)

    result = []
    for tag in sorted(matches):
        values = matches[tag]
        if len(set(values)) != 1:
            raise AlphaContractError(f"P015 conflicting original same-period concept: {tag}")
        result.append({
            "source_concept": tag,
            "context_ref": CONTEXT,
            "unit_ref": UNIT,
            "raw_source_occurrences_same_value": len(values),
            "fy26_inr_crore": round(values[0] / 10_000_000, 6),
            "classification_for_manual_review": _type(tag),
            "may_overlap_or_net_with_other_cash_flow_concepts": True,
            "sum_all_tag_values_as_capex_allowed": False,
        })
    return result


def audit_investing_taxonomy(
    prior_p004: dict[str, Any],
    original_annual_xml: dict[str, bytes],
) -> dict[str, Any]:
    """Verify all 100 exact historical FY26 filings and P014 cash facts."""
    p014 = audit_original_intangibles(prior_p004, original_annual_xml)
    if (
        prior_p004.get("report_sha256") != P004_REPORT_SHA
        or p014["annual_xml_sha256_reverified_count"] != 100
        or p014["positive_tagged_intangible_purchase_count"] != 17
        or p014["sun_tv_original_intangible_cash_purchase_cr"] != 2130.31
        or p014["live_capital_allowed"] is not False
    ):
        raise AlphaContractError("P015 pinned original 100-P014 source disagrees")
    p014_by = {(r["symbol"], r["isin"]): r for r in p014["companies"]}
    rows = []
    classifications = Counter()
    additional_symbols = []
    missing_net_flow_symbols = []
    large_net_investing_vs_simple_proxy = []
    for original in prior_p004["source_results"]:
        symbol, isin = original["symbol"], original["isin"]
        expected = p014_by.get((symbol, isin))
        if expected is None:
            raise AlphaContractError("P015 original issuer identity missing")
        sha = original["financial_sources"]["annual"]["raw_sha256"]
        raw = original_annual_xml[sha]
        if hashlib.sha256(raw).hexdigest() != sha:
            raise AlphaContractError("P015 original issuer byte hash mismatch")
        tagged = source_investing_facts(raw)
        by = {x["source_concept"]: x["fy26_inr_crore"] for x in tagged}
        ppe = expected["fy26_ppe_purchases_cr"]
        intangible = expected["fy26_intangible_purchases_cr"]
        if (
            by.get(PPE_CONCEPT) != ppe
            or by.get(ORIGINAL_CONCEPT) != intangible
        ):
            raise AlphaContractError(f"P015 original PPE/intangible source drift: {symbol}")
        for item in tagged:
            classifications[item["classification_for_manual_review"]] += 1
        extra = [
            item["source_concept"] for item in tagged
            if item["source_concept"] not in (
                PPE_CONCEPT, ORIGINAL_CONCEPT, NET_INVESTING_CONCEPT
            )
        ]
        if extra:
            additional_symbols.append(symbol)
        net_investing = by.get(NET_INVESTING_CONCEPT)
        if net_investing is None:
            missing_net_flow_symbols.append(symbol)
        # Deliberately exclude the absolute sign of investing cash as a
        # "cost": disposal proceeds/acquisitions change accounting netting.
        if (
            net_investing is not None
            and abs(net_investing) > abs(expected[
                "fy26_cfo_after_ppe_proxy_cr_not_owner_cash"
            ])
        ):
            large_net_investing_vs_simple_proxy.append(symbol)
        rows.append({
            "symbol": symbol,
            "isin": isin,
            "original_annual_xbrl_sha256": sha,
            "original_filing_basis": original["financial_sources"]["annual"][
                "accounting_basis"
            ],
            "original_exchange_published_at_utc": original[
                "financial_sources"
            ]["annual"]["exchange_published_at_utc"],
            "annual_cash_concept_rows": tagged,
            "tagged_investing_concept_count": len(tagged),
            "additional_investing_concept_count": len(extra),
            "additional_investing_concepts": extra,
            "fy26_reported_cfo_cr": expected["fy26_cfo_cr"],
            "fy26_reported_ppe_cash_purchase_cr": ppe,
            "fy26_reported_intangible_cash_purchase_cr": intangible,
            "fy26_net_cash_from_investing_cr_if_tagged": net_investing,
            "fy26_cfo_less_ppe_intangible_proxy_cr_not_owner_cash": expected[
                "fy26_cfo_after_ppe_intangible_purchases_cr_not_owner_cash"
            ],
            "missing_investing_tag_is_not_zero_spending_proof": True,
            "sustaining_vs_growth_spending_verified": False,
            "net_cash_investing_is_not_additive_to_subcategories": True,
            "other_investing_items_are_not_verified_recurrent_spend": True,
            "source_asset_ownership_taxonomy_reconciled": False,
            "company_sustainable_owner_cash": None,
            "company_value": None,
            "capital_eligible": False,
        })
    rows.sort(key=lambda x: (x["symbol"], x["isin"]))
    if len(rows) != 100 or len({(r["symbol"], r["isin"]) for r in rows}) != 100:
        raise AlphaContractError("P015 complete 100-company original identity count broken")

    sun = next(x for x in rows if x["symbol"] == "SUNTV")
    if (
        sun["fy26_reported_cfo_cr"] != 1801.64
        or sun["fy26_reported_ppe_cash_purchase_cr"] != 83.91
        or sun["fy26_reported_intangible_cash_purchase_cr"] != 2130.31
        or sun["fy26_cfo_less_ppe_intangible_proxy_cr_not_owner_cash"] != -412.58
    ):
        raise AlphaContractError("P015 SUNTV material acquisition cash not reproducible")
    payload = {
        "schema_version": 1,
        "report_id": REVIEW_ID,
        "review_date": REVIEW_DATE,
        "original_frozen_p004_report_sha256": P004_REPORT_SHA,
        "embedded_replayed_p014_report_sha256": p014["report_sha256"],
        "issuer_count": 100,
        "original_annual_xml_rehashed": 100,
        "source_investing_classification_occurrences_by_type": dict(
            sorted(classifications.items())
        ),
        "companies_with_additional_investing_concepts": len(additional_symbols),
        "additional_investing_tag_symbols": sorted(additional_symbols),
        "no_explicit_net_investing_tag_symbols": sorted(missing_net_flow_symbols),
        "absolute_net_investing_exceeds_cfo_less_ppe_symbols_descriptive_only": sorted(
            large_net_investing_vs_simple_proxy
        ),
        "original_tag_inventory_by_company": rows,
        "source_rows_not_added_as_independent_cash_outflows": True,
        "empty_tag_not_proof_of_no_cash_investing": True,
        "cashflow_accounting_not_sustainable_owner_earnings": True,
        "bank_and_media_and_industrial_accounting_not_interchangeable": True,
        "analyst_review_required_for_overlap_acquisition_and_disposal": True,
        "method_is_posthoc_source_audit_not_oct15_preregistered_alpha": True,
        "no_expected_stock_returns_or_fair_values": True,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    payload["report_sha256"] = digest(payload)
    return payload
