"""OPEN005: audited parent/group cash bridge and non-admitting tender clock audit.

Run:
    python scripts/open005_indiamart_tender_audit.py

Research only. No unverified owner-cash, forecast, price target or capital
authorization. Original October 15 prospective experiments are unchanged.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN005_INDIAMART_CASH_BLS_TENDER_INPUT_20261026.json"
)


def amount(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field}: numeric audited input required")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{field}: nonfinite or negative audited input")
    return result


def rounded(value: float) -> float:
    return round(value, 4)


def evaluate(packet: dict) -> dict:
    if packet["schema"] != "OPEN005_20261026_INDIAMART_CASH_AND_BLS_TENDER_GATE_V1":
        raise ValueError("snapshot version changed")
    if packet["research_type"] != "POST_HOC_ISSUER_CASH_AND_SCHEDULE_ONLY":
        raise ValueError("cannot relabel post-hoc records as prospective")
    asof = packet["as_of_local"]
    if asof != "2026-10-26T16:50:33+05:30":
        raise ValueError("source-time cutoff may not move without new snapshot")
    time = datetime.fromisoformat(asof)
    if time.tzinfo is None:
        raise ValueError("naive local clock forbidden")
    custody = packet["source_integrity"]
    if custody != {
        "original_issuer_pdf_visually_checked": True,
        "original_pdf_page_consolidated_zero_index": 11,
        "original_pdf_page_standalone_zero_index": 18,
        "raw_original_bytes_in_repository": False,
        "original_pdf_sha256": None,
        "source_first_retrieved_utc": None,
        "source_cutoff_backfill_permitted": False,
    }:
        raise ValueError("raw source custody/backfill misrepresentation")
    frozen = packet["freeze"]
    if frozen != {
        "original_H002_H003_HG009_rules_unchanged": True,
        "investment_authorized": False,
        "parent_owner_fcfe_verified": False,
        "calibrated_expected_stock_return": None,
    }:
        raise ValueError("capital or alpha promoted without evidence")

    company = packet["indiamart"]
    if company["symbol"] != "INDIAMART" or company["isin"] != "INE933S01016":
        raise ValueError("issuer identity mismatch")
    if company["financial_year_end"] != "2026-03-31":
        raise ValueError("audited annual period mismatch")
    if company["next_financial_result_scheduled"] != "2026-10-27":
        raise ValueError("next financial event date changed")
    if company["next_financial_result_published_as_of_cutoff"] is not False:
        raise ValueError("future earnings cannot be backfilled")
    if not company["primary_FY26_original_audited_consolidated_and_standalone_pdf"].startswith(
        "https://nsearchives.nseindia.com/corporate/"
    ):
        raise ValueError("primary official source missing")
    if company["reference_market_cap_observed_at"] != "2026-10-26T12:52:00+05:30":
        raise ValueError("dated equity price observation missing")
    if company["reference_quote_market"] != "BSE":
        raise ValueError("market/source basis changed")
    market_cap = amount(company["reference_market_cap_crore"], "market_cap")
    quote = amount(company["reference_price_inr"], "price")
    if market_cap <= 0 or quote <= 0:
        raise ValueError("invalid positive observed equity reference")
    if company["cash_and_deferred_revenue_are_not_interchangeable"] is not True:
        raise ValueError("contract liabilities must stay separate")
    if company["parent_cash_not_equivalent_to_fully_distributable_cash"] is not True:
        raise ValueError("parent owner cash not proven")

    group = company["fy26_consolidated_crore"]
    parent = company["fy26_parent_standalone_crore"]
    cfo = amount(group["after_tax_operating_cash"], "FY26 consolidated CFO")
    prev = amount(group["after_tax_operating_cash_prior_year"], "FY25 consolidated CFO")
    op_before_wc = amount(
        group["operating_profit_before_working_capital"], "operating before WC"
    )
    prev_op_before_wc = amount(
        group["operating_profit_before_working_capital_prior_year"], "prior before WC"
    )
    liability_cash = amount(
        group["contract_liabilities_cash_inflow"], "change in contract liabilities"
    )
    previous_liability_cash = amount(
        group["contract_liabilities_cash_inflow_prior_year"], "prior contract liabilities"
    )
    capex = amount(
        group["PPE_intangible_and_capital_advance_cash_purchases"], "cash capex"
    )
    leases = amount(
        group["lease_cash_repayment_including_interest"], "lease repayment"
    )
    deferred = amount(
        group["deferred_acquisition_consideration_cash_paid"], "deferred consideration"
    )
    dividend = amount(group["dividends_paid"], "dividends")
    tax = amount(group["income_tax_paid"], "tax")
    cash_generated = amount(group["cash_generated_before_tax"], "before tax")
    if min(cfo, prev, prev_op_before_wc, op_before_wc) <= 0:
        raise ValueError("required positive operating comparisons")
    if abs(cash_generated - tax - cfo) > 0.000001:
        raise ValueError("cash generated minus tax must equal after-tax CFO")

    group_after_selected = cfo - capex - leases
    group_after_acquisition = group_after_selected - deferred
    prior_contract_pace = cfo - (liability_cash - previous_liability_cash)
    no_new_contract_inflow = cfo - liability_cash
    parent_cfo = amount(parent["after_tax_operating_cash"], "parent CFO")
    parent_after_selected = (
        parent_cfo
        - amount(parent["PPE_intangible_cash_and_capital_advance_purchases"], "parent PPE")
        - amount(parent["lease_cash_repayment_including_interest"], "parent lease")
    )
    if abs(amount(parent["dividends_paid"], "parent dividend") - dividend) > 0.001:
        raise ValueError("FY26 original standalone/group equity dividend disagreement")

    q1 = company["latest_issuer_Q1_FY27_reported"]
    if q1["as_of"] != "2026-06-30":
        raise ValueError("Q1 FY27 timestamp changed")
    current_subscribers = amount(q1["paying_suppliers_end_count"], "subscriber count")
    change = q1["paying_suppliers_net_change_count"]
    if not isinstance(change, int) or isinstance(change, bool) or change >= 0:
        raise ValueError("original negative Q1 subscriber addition lost")
    if current_subscribers <= 0 or change != -1850:
        raise ValueError("Q1 supplier observation tampered")
    group_cashlike = amount(
        q1["consolidated_cash_and_investments_crore"], "Q1 group cash-like"
    )
    parent_cashlike = amount(
        q1["standalone_cash_and_investments_crore"], "Q1 parent cash-like"
    )
    future_services = amount(q1["consolidated_deferred_revenue_crore"], "deferred revenue")
    if parent_cashlike > group_cashlike or future_services <= 0:
        raise ValueError("invalid cash/contract obligations")
    finance_sub = company["new_financial_services_subsidiary"]
    if finance_sub["company"] != "IndiaMART Finance Limited":
        raise ValueError("July/August finance-subsidiary source altered")
    if finance_sub["regulatory_and_future_balance_sheet_exposure_unverified"] is not True:
        raise ValueError("financing risk requires new independent proof")

    tender_ids = {
        "2026_MEA_852512_1", "2026_MEA_852578_1",
        "2026_MEA_852518_1", "2026_MEA_853372_1"
    }
    tenders = packet["BLS_tenders"]
    if len(tenders) != 4 or {r["id"] for r in tenders} != tender_ids:
        raise ValueError("BLS original tender identity set changed")
    tender_status = []
    for tender in tenders:
        if (
            tender["bid_open_confirmed"] is not False
            or tender["bidder_names_confirmed"] is not False
            or tender["award_confirmed"] is not False
        ):
            raise ValueError("unverified tender events may not be claimed as confirmed")
        sched = tender["published_opening_local"]
        if sched is None:
            if tender["jurisdiction"] != "Kuwait":
                raise ValueError("scheduled hour unexpectedly absent")
            state = "SCHEDULED_DAY_EXACT_HOUR_UNVERIFIED"
        else:
            when = datetime.fromisoformat(sched)
            if when.tzinfo is None or when.utcoffset() != time.utcoffset():
                raise ValueError("tender time must include source-local IST offset")
            state = (
                "SCHEDULE_HOUR_PASSED_NO_OPENING_PROOF"
                if when <= time else "SCHEDULE_HOUR_NOT_REACHED_NO_OPENING_PROOF"
            )
        tender_status.append({
            "id": tender["id"],
            "jurisdiction": tender["jurisdiction"],
            "opening_scheduled": sched or tender["published_opening_date"],
            "observation_status": state,
            "bidder_identity_verified": False,
            "award_verified": False,
        })
    return {
        "schema": packet["schema"],
        "observation_cutoff_local": asof,
        "return_alpha_verified": False,
        "approved_investments": 0,
        "INDIAMART": {
            "fy26_consolidated_after_tax_cfo_crore": cfo,
            "fy25_consolidated_after_tax_cfo_crore": prev,
            "cfo_growth_pct": rounded((cfo / prev - 1) * 100),
            "before_working_capital_operating_profit_growth_pct": rounded(
                (op_before_wc / prev_op_before_wc - 1) * 100
            ),
            "contract_liability_inflow_share_of_CFO_pct": rounded(
                liability_cash / cfo * 100
            ),
            "FY26_group_selected_use_cash_crore": rounded(group_after_selected),
            "FY26_group_after_selected_deferred_consideration_crore": rounded(
                group_after_acquisition
            ),
            "FY26_group_after_selected_dividends_crore": rounded(
                group_after_acquisition - dividend
            ),
            "FY26_group_selected_use_cash_if_no_contract_liability_increase_crore": rounded(
                no_new_contract_inflow - capex - leases
            ),
            "FY26_group_selected_use_cash_if_FY25_contract_liability_pace_crore": rounded(
                prior_contract_pace - capex - leases
            ),
            "FY26_parent_after_tax_CFO_crore": parent_cfo,
            "parent_share_of_group_CFO_pct": rounded(parent_cfo / cfo * 100),
            "FY26_parent_selected_use_cash_crore": rounded(parent_after_selected),
            "FY26_parent_selected_use_cash_after_common_dividends_crore": rounded(
                parent_after_selected - dividend
            ),
            "reported_group_CFO_selected_use_yield_at_stale_intraday_cap_pct": rounded(
                group_after_selected / market_cap * 100
            ),
            "no_liability_increment_stress_yield_at_intraday_cap_pct": rounded(
                (no_new_contract_inflow - capex - leases) / market_cap * 100
            ),
            "latest_Q1_deferred_revenue_crore": future_services,
            "latest_Q1_cash_investments_crore": group_cashlike,
            "latest_Q1_parent_cash_investments_crore": parent_cashlike,
            "latest_Q1_parent_share_of_group_cash_investments_pct": rounded(
                parent_cashlike / group_cashlike * 100
            ),
            "paying_suppliers_net_change": change,
            "fully_distributable_parent_FCFE_crore": None,
            "unrestricted_parent_cash_crore": None,
            "investment_decision": "RESEARCH_ONLY_FUTURE_SUBSCRIBER_RESULTS_GATE",
        },
        "BLS_tender_status": tender_status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text())), indent=2))


if __name__ == "__main__":
    main()
