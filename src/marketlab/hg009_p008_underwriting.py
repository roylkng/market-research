"""HG009 P008 source-pinned ten-company economic diligence, not stock picks."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

PACKET_ID = "HG009-P008-TEN-SOURCE-BOUND-UNDERWRITING-v1"
DATE = "2026-10-14"
SYMBOLS = (
    "ANANTRAJ", "SAMBHV", "INOXGREEN", "DATAMATICS",
    "ACUTAAS", "ACE", "TRAVELFOOD", "POKARNA",
    "MAYURUNIQ", "PIXTRANS",
)
PINNED = {
    "hg007": ("research/hg007/hg007-p048-direct-catalyst-triage-v1.json",
              "78befaee243fc2f139c984d4bf9627f3e0e847a0"),
    "five": ("research/hg007/hg007-p030-five-case-underwriting-readiness-v1.json",
             "41bea93418f0dbaf8ac024375f99d8c5d1cf0f79"),
    "datamatics": ("research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json",
                   "706c2dd100a49859b5054323baeddc345531fb59"),
    "hundred": ("research/hg009/hg009-d001-100-experimental-companies-v1.json",
                "4ecf75ce934e88c56b5f60b9a5715b4387a49076"),
    "accounting": ("research/hg009/hg009-p003-accounting-quality-redteam-v1.json",
                   "e24f7e164fbaea1ceab7edb86b2c0d980a19a700"),
    "new_fy26": ("registry/hg009_p008_fy26_nse_cash_facts.json",
                 "8f257a6d8787aebf30c67123a056d8fe08d87afd"),
}
GATES = (
    "ORIGINAL_FILING_AND_SEGMENT_DISCLOSURE",
    "RECURRING_REVENUE_AND_PROFIT_QUALITY",
    "CONSOLIDATED_OPERATING_CASH_FLOW",
    "MAINTENANCE_VERSUS_EXPANSION_CAPEX",
    "MULTIYEAR_WORKING_CAPITAL_CYCLE",
    "DEBT_INTEREST_AND_LEASE_OBLIGATIONS",
    "FINANCIAL_ASSETS_CASH_DISTRIBUTABILITY",
    "MINORITY_AND_LISTED_PARENT_OWNERSHIP",
    "CURRENT_FULLY_DILUTED_SHARE_COUNT",
    "LEGAL_CATALYST_DATED_PRICE_ORDER_IMPACT",
)


def _original_git_blob(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
        usedforsecurity=False,
    ).hexdigest()


def load_sources(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    packets, receipts = {}, {}
    for name, (path, expected) in PINNED.items():
        raw = (root / path).read_bytes()
        if _original_git_blob(raw) != expected:
            raise AlphaContractError(f"P008 source {name} is not originally pinned")
        packet = json.loads(raw)
        if not isinstance(packet, dict):
            raise AlphaContractError(f"P008 expected source object {name}")
        packets[name] = packet
        receipts[name] = {
            "path": path,
            "source_git_blob_sha": expected,
            "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return packets, receipts


def _positive(num: object, label: str, *, zero: bool = False) -> float:
    if (
        type(num) not in (float, int) or not math.isfinite(num)
        or (num < 0 if zero else num <= 0)
    ):
        raise AlphaContractError(f"P008 invalid nonnegative original {label}")
    return float(num)


def _fy26_cash(source: dict, isin: str) -> dict:
    if (
        source["isin"] != isin
        or source["reporting_basis"] != "CONSOLIDATED_AUDITED_FY26"
        or source["period_end"] != "2026-03-31"
        or source["statement_currency"] != "INR_LAKH"
        or not source["original_url"].startswith(
            "https://nsearchives.nseindia.com/corporate/ixbrl/"
        )
    ):
        raise AlphaContractError("P008 source date, exchange, or share identity mismatch")
    raw_fields = (
        "pretax_profit", "operating_cfo", "ppe_purchase",
        "financing_lease_principal", "financing_interest_paid",
        "cash_equivalents", "financial_borrowings",
        "current_investments", "noncontrolling_equity",
    )
    raw = {
        key: _positive(
            source[key], label=key,
            zero=key not in ("pretax_profit", "operating_cfo"),
        )
        for key in raw_fields
    }
    pbt, cfo, capex = (
        raw["pretax_profit"] / 100,
        raw["operating_cfo"] / 100,
        raw["ppe_purchase"] / 100,
    )
    lease, interest = (
        raw["financing_lease_principal"] / 100,
        raw["financing_interest_paid"] / 100,
    )
    return {
        "basis": "FY26_CONSOLIDATED_REPORTED_NOT_NORMALIZED",
        "source_url": source["original_url"],
        "period_end": source["period_end"],
        "original_html_bytes_archived": False,
        "original_html_sha256": None,
        "cash_flow_cfo_cr": round(cfo, 4),
        "pbt_cr": round(pbt, 4),
        "cash_ppe_spend_cr": round(capex, 4),
        "lease_principal_financing_cr": round(lease, 4),
        "interest_paid_financing_cr": round(interest, 4),
        "simple_cfo_less_ppe_cr": round(cfo - capex, 4),
        "simple_cfo_less_ppe_and_lease_cr": round(cfo - capex - lease, 4),
        "simple_cfo_less_ppe_lease_interest_cr": round(
            cfo - capex - lease - interest, 4
        ),
        "cfo_over_pbt_not_pat_ratio": round(cfo / pbt, 4),
        "reported_cash_cr_not_verified_excess": round(
            raw["cash_equivalents"] / 100, 4
        ),
        "reported_borrowings_cr_not_current": round(
            raw["financial_borrowings"] / 100, 4
        ),
        "reported_current_investments_cr_not_unrestricted": round(
            raw["current_investments"] / 100, 4
        ),
        "reported_nci_equity_cr_not_shareholder_cash": round(
            raw["noncontrolling_equity"] / 100, 4
        ),
        "maintenance_capex_verified": False,
        "owner_cash_flow_verified": False,
        "after_interest_proxy_assumes_no_operating_cfo_interest_payment": True,
    }


def build_packet(sources: dict[str, dict], receipts: dict[str, dict]) -> dict:
    # Git-blob checks happen at loading. Re-check embedded original packet
    # signatures as well, to reject later in-memory source manipulation.
    for source_key, sig_key in (
        ("hg007", "packet_sha256"),
        ("datamatics", "packet_sha256"),
        ("hundred", "cohort_sha256"),
        ("accounting", "packet_sha256"),
    ):
        signed_source = copy.deepcopy(sources[source_key])
        original = signed_source.pop(sig_key, None)
        if original != digest(signed_source):
            raise AlphaContractError(
                f"P008 tampered original signed source: {source_key}"
            )
    events = sources["hg007"]
    old_cases = {x["symbol"]: x for x in sources["five"]["casework"]}
    hg007 = {x["symbol"]: x for x in events["cases"]}
    selected = {x["symbol"]: x for x in sources["hundred"]["selected"]}
    pilots = sources["accounting"]["original_nse_iXBRL_manual_filing_pilots"]
    audited = {x["symbol"]: x for x in sources["new_fy26"]["numeric_facts"]}
    p049 = sources["datamatics"]
    exact_event_cohort = {
        "ANANTRAJ", "AXITA", "DATAMATICS", "INOXGREEN",
        "SAMBHV", "SANDESH", "SUVIDHAA",
    }
    if set(hg007) != exact_event_cohort:
        raise AlphaContractError("P008 original seven direct identities drifted")
    if (
        events["active_direct_catalyst_count"] != 7
        or len(old_cases) != 5
        or sources["hundred"]["selected_count"] != 100
        or sources["new_fy26"]["original_documents_archived"] is not False
    ):
        raise AlphaContractError("P008 original frozen cohort/sources drifted")
    cases = []
    for name in SYMBOLS:
        source = hg007.get(name) if name in hg007 else selected.get(name)
        if source is None or not isinstance(source.get("isin"), str):
            raise AlphaContractError(f"P008 {name} not in original frozen research")
        isin = source["isin"]
        cash: dict[str, Any] | None = None
        urls = []
        proof = {gate: "MISSING_COMPLETE_ORIGINAL_SOURCE" for gate in GATES}
        missing = list(source.get("missing_original_document_gates", []))
        if name in audited:
            cash = _fy26_cash(audited[name], isin)
            urls = [audited[name]["original_url"]]
            proof[GATES[0]] = "OFFICIAL_AUDITED_NSE_FILING_LOCATED_NOT_ARCHIVED"
            proof[GATES[2]] = "AUDITED_CFO_READ_NOT_OWNER_EARNINGS"
            proof[GATES[3]] = "TOTAL_PPE_READ_MAINTENANCE_SPLIT_UNVERIFIED"
            proof[GATES[5]] = "REPORTED_FINANCING_CASH_AND_BORROWINGS_PARTIAL"
            proof[GATES[7]] = "REPORTED_NCI_EQUITY_NOT_PARENT_ATTRIBUTION"
        if name in old_cases:
            old = old_cases[name]
            if old["portfolio_eligibility_allowed"] is not False:
                raise AlphaContractError("P008 original event cannot be promoted")
            missing += old["necessary_original_document_and_underwriting_gates"]
        if name == "DATAMATICS":
            cash = {
                "basis": "FY26_CONSOLIDATED_REPORTED_NOT_NORMALIZED",
                "source_url": p049["source_page_refs"]["audited_exchange_fy26"]["url"],
                "cash_flow_cfo_cr": p049[
                    "fy26_historical_cash_and_balance_sheet_facts"
                ]["fy26_cfo_inr_crore"],
                "simple_cfo_less_ppe_cr": p049[
                    "fy26_cfo_less_fixed_asset_cash_spending_inr_crore_not_normalized_fcf"
                ],
                "owner_cash_flow_verified": False,
                "original_pdf_bytes_archived": False,
            }
            urls = [cash["source_url"]]
        if name in pilots:
            pilot = pilots[name]
            if pilot["company"] != name:
                raise AlphaContractError("P008 manual NSE company identity conflict")
            if name == "MAYURUNIQ":
                cash = {
                    "basis": "FY26_CONSOLIDATED_REPORTED_NOT_NORMALIZED",
                    "source_url": pilot["source"]["source_url"],
                    "cash_flow_cfo_cr": pilot["fy26_cfo_inr_crore"],
                    "simple_cfo_less_ppe_cr": pilot[
                        "fy26_cfo_less_ppe_purchase_proxy_inr_crore_not_normalized_fcf"
                    ],
                    "owner_cash_flow_verified": False,
                    "original_html_bytes_archived": False,
                }
                urls = [cash["source_url"]]
            elif name == "PIXTRANS":
                cash = {
                    "basis": "Q1FY27_STANDALONE_UNAUDITED_PBT_QUALITY_ONLY",
                    "source_url": pilot["source"]["current_source_url"],
                    "reported_standalone_pbt_cr": pilot[
                        "q1fy27_standalone_reported_pbt_inr_crore"
                    ],
                    "fvtpl_gain_in_reported_pbt_cr": pilot[
                        "q1fy27_fvtpl_nonoperating_included_in_income_inr_crore"
                    ],
                    "pbt_excluding_one_fvtpl_item_cr": pilot[
                        "q1fy27_pbt_excluding_only_investment_fvtpl_inr_crore"
                    ],
                    "operating_cfo_cr": None,
                    "owner_cash_flow_verified": False,
                    "original_html_bytes_archived": False,
                }
                urls = [cash["source_url"], pilot["source"]["prior_source_url"]]
        if name == "POKARNA":
            urls = [sources["new_fy26"]["pokarna"]["original_url"]]
            missing.append("FY26_PDF_VISUAL_CASHFLOW_AND_CAPEX_CONFIRMATION")
        if name in ("TRAVELFOOD", "ACUTAAS"):
            missing += [
                "LEASE_OR_CAPEX_REINVESTMENT_SUSTAINABILITY",
                "RETURNS_ON_INCREMENTAL_INVESTED_CAPITAL",
            ]
        if name == "PIXTRANS":
            missing += ["RECURRING_OPERATING_EARNINGS_EXCLUDING_FVTPL"]
        if cash is not None and proof[GATES[2]] == "MISSING_COMPLETE_ORIGINAL_SOURCE":
            proof[GATES[2]] = "REPORTED_EARNINGS_OR_CFO_PARTIAL_NOT_OWNER_EARNINGS"
        if cash is not None and proof[GATES[0]] == "MISSING_COMPLETE_ORIGINAL_SOURCE":
            proof[GATES[0]] = "FILING_EXCERPT_SEEN_RAW_BYTES_NOT_ARCHIVED"
        cases.append({
            "symbol": name,
            "frozen_isin": isin,
            "source_selection": (
                "HG007_DIRECT_EVENT" if name in hg007 else "HG009_DISCOVERY"
            ),
            "original_filing_urls": urls,
            "reported_financial_hurdle_not_equity_value": cash,
            "ten_proof_gates": proof,
            "missing_verified_source_requirements": sorted(set(missing)),
            "current_parent_fully_diluted_shares_verified": False,
            "current_executable_price_and_depth_verified": False,
            "normalized_owner_cashflow_cr": None,
            "calibrated_scenario_probabilities": None,
            "bear_base_bull_attributable_equity_values": None,
            "current_fair_value_per_share": None,
            "expected_1y_or_3y_net_return": None,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        })
    if len(cases) != 10 or len({x["frozen_isin"] for x in cases}) != 10:
        raise AlphaContractError("P008 ten original source identities not unique")
    out = {
        "schema_version": 1,
        "packet_id": PACKET_ID,
        "as_of_date": DATE,
        "prior_source_git_sha_receipts": receipts,
        "company_count": 10,
        "company_order_predeclared_not_prediction_rank": list(SYMBOLS),
        "original_consolidated_fy26_new_issuer_cash_pilots": 3,
        "ten_proof_fields": list(GATES),
        "cases": cases,
        "new_original_html_pdf_bytes_archived": False,
        "fully_underwritten_equity_valuations_count": 0,
        "verified_completion_probability_count": 0,
        "paper_investment_eligibility_count": 0,
        "shareholder_owner_fcf_normalized_count": 0,
        "no_returns_or_probability_weights_invented": True,
        "live_capital_allowed": False,
    }
    out["packet_sha256"] = digest(out)
    return out


def materialize(root: Path) -> dict:
    sources, receipts = load_sources(root)
    return build_packet(sources, receipts)


def validate_packet(value: dict, root: Path) -> None:
    unsigned = copy.deepcopy(value)
    sha = unsigned.pop("packet_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("P008 research packet SHA altered")
    if value != materialize(root):
        raise AlphaContractError("P008 research packet does not replay sources")
