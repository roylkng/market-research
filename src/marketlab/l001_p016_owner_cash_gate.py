"""L001 P016: reject unverified economic owner cash from audited cash tags.

Reuses P015's complete, signed, original-FY26 100-issuer investing taxonomy.
No additional raw-XBRL fact is inferred, no investing components are added,
and no P015 retrospective accounting analysis becomes a prospective signal.
"""

from __future__ import annotations

import copy
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p015_investing_taxonomy import (
    NET_INVESTING_CONCEPT,
    ORIGINAL_CONCEPT,
    PPE_CONCEPT,
)

AUDIT_ID = "L001-P016-ALL100-ECONOMIC-OWNER-CASH-ADMISSION-v1"
AS_OF = "2026-10-19"
P015_PATH = Path("research/l001/l001-p015-investing-cash-taxonomy-100-v1.json")
P015_SHA = "fcceac6870ee20ce238448e9926b317e10c6d859257f43839726b0c9a076cfdd"
P004_SHA = "97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d"

# These are independent REVIEW GATES, not additive investing expenses or
# evidence that the issuer is cheap, fraudulent, or earns a negative IRR.
GATES = (
    "CAPEX_PLUS_INTANGIBLE_PROXY_NONPOSITIVE",
    "PPE_TAG_ZERO_WITH_MATERIAL_NET_INVESTING",
    "LARGE_OTHER_PURCHASE_CASH_CLASSIFICATION_UNRECONCILED",
    "NET_INVESTING_ABSOLUTE_AMOUNT_EXCEEDS_SIMPLE_CFO_MINUS_PPE",
    "MISSING_NET_INVESTING_TAG",
    "NONZERO_INVESTING_NON_PPE_TAGS_REQUIRE_NOTES",
)
MEMO_NAMES = ("SUNTV", "ACE", "OIL", "MAYURUNIQ")


def _finite_number(value: object, key: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise AlphaContractError(f"P016 malformed signed source cash amount: {key}")
    return float(value)


def _money_match(left: object, right: object, *, name: str) -> float:
    a = _finite_number(left, name)
    b = _finite_number(right, name)
    if not math.isclose(a, b, rel_tol=0, abs_tol=0.000003):
        raise AlphaContractError(f"P016 source original cash bridge drift: {name}")
    return a


def validate_prior_original_p015(packet: dict[str, Any]) -> None:
    clone = copy.deepcopy(packet)
    stored = clone.pop("report_sha256", None)
    if (
        packet.get("report_id")
        != "L001-P015-FY26-ORIGINAL-100-INVESTING-CASH-TAXONOMY-v1"
        or packet.get("review_date") != AS_OF
        or packet.get("issuer_count") != 100
        or packet.get("original_annual_xml_rehashed") != 100
        or packet.get("original_frozen_p004_report_sha256") != P004_SHA
        or stored != P015_SHA
        or digest(clone) != P015_SHA
        or packet.get("bank_and_media_and_industrial_accounting_not_interchangeable")
        is not True
        or packet.get("live_capital_allowed") is not False
        or packet.get("source_rows_not_added_as_independent_cash_outflows")
        is not True
    ):
        raise AlphaContractError("P016 original 100-issuer signed P015 source changed")
    rows = packet.get("original_tag_inventory_by_company")
    if not isinstance(rows, list) or len(rows) != 100:
        raise AlphaContractError("P016 original 100 cash issuer rows missing")
    seen = set()
    for row in rows:
        symbol, isin = row.get("symbol"), row.get("isin")
        if (
            not isinstance(symbol, str)
            or not isinstance(isin, str)
            or len(isin) != 12
            or (symbol, isin) in seen
            or row.get("sustaining_vs_growth_spending_verified") is not False
            or row.get("capital_eligible") is not False
            or row.get("company_sustainable_owner_cash") is not None
        ):
            raise AlphaContractError("P016 original source identity or owner cash promoted")
        seen.add((symbol, isin))


def _issuer(source: dict[str, Any]) -> dict[str, Any]:
    symbol = source["symbol"]
    cash = _finite_number(source["fy26_reported_cfo_cr"], "CFO")
    ppe = _finite_number(source["fy26_reported_ppe_cash_purchase_cr"], "PPE")
    intangible = _finite_number(
        source["fy26_reported_intangible_cash_purchase_cr"], "intangibles"
    )
    tagged = source["annual_cash_concept_rows"]
    if not isinstance(tagged, list):
        raise AlphaContractError("P016 signed XBRL source concept inventory missing")
    by_concept = {item["source_concept"]: item for item in tagged}
    if len(by_concept) != len(tagged):
        raise AlphaContractError("P016 original annual cash concepts duplicated")
    for tag, value in ((PPE_CONCEPT, ppe), (ORIGINAL_CONCEPT, intangible)):
        if tag not in by_concept:
            raise AlphaContractError(f"P016 original required {symbol} source tag absent")
        _money_match(
            by_concept[tag]["fy26_inr_crore"],
            value,
            name=f"{symbol} {tag}",
        )
    net_source = source["fy26_net_cash_from_investing_cr_if_tagged"]
    if net_source is not None:
        if NET_INVESTING_CONCEPT not in by_concept:
            raise AlphaContractError("P016 missing source cash investing bridge")
        _money_match(
            net_source,
            by_concept[NET_INVESTING_CONCEPT]["fy26_inr_crore"],
            name=f"{symbol} net investing",
        )
    cfo_minus_ppe = round(cash - ppe, 6)
    cfo_less_both = _money_match(
        source["fy26_cfo_less_ppe_intangible_proxy_cr_not_owner_cash"],
        round(cash - ppe - intangible, 6),
        name=f"{symbol} original tagged cash proxy",
    )
    additional = source["nonzero_additional_investing_concepts"]
    if not isinstance(additional, list):
        raise AlphaContractError("P016 source additional investing taxonomy missing")
    if any(
        row.get("fy26_inr_crore") == 0
        or row.get("source_concept") not in by_concept
        for row in additional
    ):
        raise AlphaContractError("P016 zero-template or nonoriginal extra cash item")
    large_other = [
        item for item in source[
            "positive_other_investing_purchase_candidates_needing_notes"
        ]
        if (
            type(item.get("fy26_inr_crore")) in (float, int)
            and item["fy26_inr_crore"] > abs(cfo_minus_ppe)
        )
    ]
    flags = []
    if cfo_less_both <= 0:
        flags.append(GATES[0])
    if ppe == 0 and net_source is not None and abs(net_source) > 0.001:
        flags.append(GATES[1])
    if large_other:
        flags.append(GATES[2])
    if net_source is not None and abs(net_source) > abs(cfo_minus_ppe):
        flags.append(GATES[3])
    if net_source is None:
        flags.append(GATES[4])
    if additional:
        flags.append(GATES[5])
    return {
        "symbol": symbol,
        "isin": source["isin"],
        "original_annual_xml_sha256": source["original_annual_xbrl_sha256"],
        "original_filing_basis": source["original_filing_basis"],
        "original_exchange_published_at_utc": source[
            "original_exchange_published_at_utc"
        ],
        "fy26_cfo_cr_reported": round(cash, 6),
        "fy26_ppe_cash_purchase_cr_reported": round(ppe, 6),
        "fy26_intangible_cash_purchase_cr_reported": round(intangible, 6),
        "fy26_simple_cfo_minus_ppe_cr_not_owner_cash": cfo_minus_ppe,
        "fy26_cfo_minus_ppe_intangibles_cr_not_owner_cash": round(
            cfo_less_both, 6
        ),
        "fy26_net_investing_cr_not_additive_to_cash_spending": net_source,
        "positive_additional_investing_purchase_candidates_over_simple_proxy": [
            {
                "source_concept": item["source_concept"],
                "source_amount_cr_not_verified_recurring": item[
                    "fy26_inr_crore"
                ],
            }
            for item in large_other
        ],
        "other_nonzero_investing_concepts_count": len(additional),
        "economic_cash_review_flags": flags,
        "investments_cash_and_acquisitions_may_overlap_or_net": True,
        "zero_purchase_tag_proves_no_economic_reinvestment": False,
        "all_other_investing_cash_is_maintenance_spending": False,
        "growth_capex_fully_excludable_without_ROIC_test": False,
        "bank_industrial_and_media_owner_cash_comparable": False,
        "normalized_attributable_owner_cash_cr": None,
        "verified_3year_company_price_target_inr": None,
        "verified_3year_expected_total_return": None,
        "capital_eligible": False,
    }


def build_owner_cash_falsification(
    source: dict[str, Any],
) -> dict[str, Any]:
    validate_prior_original_p015(source)
    rows = [
        _issuer(row) for row in source["original_tag_inventory_by_company"]
    ]
    rows.sort(key=lambda row: (row["symbol"], row["isin"]))
    if len(rows) != 100 or len({r["symbol"] for r in rows}) != 100:
        raise AlphaContractError("P016 original 100 issuer denominator changed")
    by_symbol = {row["symbol"]: row for row in rows}
    if not all(name in by_symbol for name in MEMO_NAMES):
        raise AlphaContractError("P016 source original red-team company missing")
    sun = by_symbol["SUNTV"]
    if (
        sun["fy26_cfo_cr_reported"] != 1801.64
        or sun["fy26_ppe_cash_purchase_cr_reported"] != 83.91
        or sun["fy26_intangible_cash_purchase_cr_reported"] != 2130.31
        or sun["fy26_cfo_minus_ppe_intangibles_cr_not_owner_cash"] != -412.58
    ):
        raise AlphaContractError("P016 original SUNTV intangible stress drift")
    oil = by_symbol["OIL"]
    if (
        oil["fy26_ppe_cash_purchase_cr_reported"] != 0
        or oil["fy26_net_investing_cr_not_additive_to_cash_spending"]
        != -10381.37
    ):
        raise AlphaContractError("P016 original OIL PPE missing-category drift")
    count = Counter(
        flag for row in rows for flag in row["economic_cash_review_flags"]
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_id": AUDIT_ID,
        "analysis_date": AS_OF,
        "source_P015_sha256": P015_SHA,
        "original_P004_100_XBRL_report_sha256": P004_SHA,
        "all_original_100_issuer_identities_preserved": True,
        "issuer_count": len(rows),
        "economic_cash_gate_count": len(GATES),
        "economic_cash_gate_names": list(GATES),
        "source_review_gate_counts_overlap": dict(sorted(count.items())),
        "company_cashflow_classification_rows": rows,
        "original_case_illustrations": {
            name: by_symbol[name] for name in MEMO_NAMES
        },
        "prospective_oos_return_labels_not_used_for_selection": True,
        "posthoc_2026_10_19_research_not_Oct15_trading_signal": True,
        "financial_investment_cash_flows_not_assumed_recurring_capex": True,
        "acquisition_cash_flows_not_added_to_PPE_and_net_investing": True,
        "issuer_sustainable_owner_cash_estimated_count": 0,
        "company_expected_return_estimated_count": 0,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def validate_owner_cash_falsification(
    packet: dict[str, Any], *,
    original_p015: dict[str, Any],
) -> None:
    unsigned = copy.deepcopy(packet)
    sha = unsigned.pop("report_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("P016 economic cash diagnostic SHA changed")
    if packet != build_owner_cash_falsification(original_p015):
        raise AlphaContractError("P016 original FY26 investing source replay changed")


def load_original_p015(repo_root: Path) -> dict[str, Any]:
    original = json.loads((repo_root / P015_PATH).read_text(encoding="utf-8"))
    if not isinstance(original, dict):
        raise AlphaContractError("P016 original P015 JSON is not a source report")
    validate_prior_original_p015(original)
    return original
