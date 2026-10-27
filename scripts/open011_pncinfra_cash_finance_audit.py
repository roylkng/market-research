"""OPEN011 PNC: audit a spectacular annual-CFO false-positive against debt cash.

Sourced inputs: ORIGINAL pre-existing L001-P016 100-issuer signed source replay;
issuer 19-May signed release, audited consolidated statement transcription,
12-Oct provisional Delhi HC order. No model alpha, order, or live capital.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "research/broad-discovery/OPEN011_PNCINFRA_LEVERED_CASH_INPUT_20261027.json"
PINNED = ROOT / "research/l001/l001-p016-owner-cash-evidence-gates-100-v1.json"
P016_REPORT_SHA = "c74e3ee3f5bb4bae5613c751116b5ccbc66a4e79e04dc23a72c403971c56b39d"
P015_SOURCE_SHA = "fcceac6870ee20ce238448e9926b317e10c6d859257f43839726b0c9a076cfdd"


def value(record: dict, key: str) -> float:
    raw = record[key]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise TypeError(f"{key} is not numeric")
    n = float(raw)
    if not math.isfinite(n):
        raise ValueError(f"{key} nonfinite")
    return n


def r4(v: float) -> float:
    return round(v, 4)


def audit(data: dict, baseline: dict) -> dict:
    if data["schema"] != "OPEN011-20261027-PNCINFRA-CASH-DEBT-CASE-V1":
        raise ValueError("source protocol identity changed")
    if data["evidence_type"] != "POSTHOC_CRITICAL_RESEARCH_NOT_ALPHA":
        raise ValueError("posthoc research cannot become prospective alpha")
    if (data["created_asof_date"], data["price_date"],data["annual_cutoff"]) != (
        "2026-10-27","2026-10-26","2026-03-31"
    ):
        raise ValueError("data/time cutoff altered")
    if (data["symbol"], data["isin"], data["original_HG009_SELECTED_member"]) != (
        "PNCINFRA","INE195J01029",True
    ):
        raise ValueError("original 100-company source identity changed")
    state = data["terminal_gates"]
    if state != {
        "normalized_sustainable_parent_owner_FCFE_cr": None,
        "historical_annual_CFO_minus_PPE_is_owner_earnings": False,
        "parent_shareholder_debt_attribution_verified": False,
        "readable_unencumbered_cash_after_lenders_verified": False,
        "permanent_legal_bidding_eligibility_verified": False,
        "portfolio_entry_authorized": False,
        "calibrated_1_or_3_year_stock_return_probability": None,
    }:
        raise ValueError("false owner cash, investability or live capital state")
    src = data["source_integrity"]
    if src != {
        "original_FY26_company_financial_statement_pdf_raw_bytes_archived_here": False,
        "independently_first_retrieved_at_utc": None,
        "original_signed_press_pdf_visually_checked": True,
        "cashflow_from_original_audited_transcription_and_prior_repo_signed_XML": True,
        "original_cohort_unchanged": True,
    }:
        raise ValueError("raw original custody or historic alpha fabricated")

    s = data["sources"]
    if (s["original_l001_report_id"]
        != "L001-P016-ALL100-ECONOMIC-OWNER-CASH-ADMISSION-v1"
        or s["original_l001_P015_sha256"] != P015_SOURCE_SHA):
        raise ValueError("original L001 source lineage altered")
    if baseline["report_sha256"] != P016_REPORT_SHA:
        raise ValueError("original L001 signed report SHA changed")
    if baseline["source_P015_sha256"] != P015_SOURCE_SHA or baseline["issuer_count"] != 100:
        raise ValueError("original 100-name source lineage changed")
    same = [
        r for r in baseline["company_cashflow_classification_rows"]
        if r["symbol"] == data["symbol"] and r["isin"] == data["isin"]
    ]
    if len(same) != 1:
        raise ValueError("original selected issuer no longer unique")
    row = same[0]
    if row["original_filing_basis"] != "Consolidated":
        raise ValueError("standalone data cannot mix into consolidated")
    if (
        row["original_annual_xml_sha256"] != s["original_exchange_XML_sha256_from_l001"]
        or row["original_exchange_published_at_utc"]
        != s["original_exchange_published_at_utc_from_l001"]
    ):
        raise ValueError("original issuer XML identity/timing changed")

    x = data["FY26_group"]
    if (x["scope"], x["unit"]) != ("CONSOLIDATED","INR_CRORE"):
        raise ValueError("financial statement unit/accounting basis corrupted")
    cfo = value(x,"after_tax_operating_cash_flow")
    ppe = value(x,"cash_PPE_and_intangible_spend")
    if cfo <= 0 or ppe < 0:
        raise ValueError("invalid CFO/PPE")
    if (
        abs(row["fy26_cfo_cr_reported"]-cfo)>0.00001
        or abs(row["fy26_ppe_cash_purchase_cr_reported"]-ppe)>0.00001
        or abs(row["fy26_cfo_minus_ppe_intangibles_cr_not_owner_cash"]-(cfo-ppe))
        > 0.00001
    ):
        raise ValueError("cannot drift from signed original P016 cash")
    if row["capital_eligible"] is not False:
        raise ValueError("original owner cash gate cannot be relaxed")
    releases = {
        name: value(x,name)
        for name in (
            "inventory_working_capital_release",
            "trade_receivables_working_capital_release",
            "other_assets_working_capital_release",
            "other_financial_assets_working_capital_movement",
            "trade_payables_working_capital_movement",
            "other_liabilities_and_provisions_working_capital_movement",
            "other_financial_liabilities_working_capital_movement",
        )
    }
    change_wc = sum(releases.values())
    operating_before_wc = value(x,"cash_operating_before_working_capital")
    tax = value(x,"direct_tax_cash_paid")
    if abs(operating_before_wc+change_wc-tax-cfo)>0.0001:
        raise ValueError("indirect cash flow reconciliation incorrect")
    pre_wc_after_tax = operating_before_wc-tax
    interest = value(x,"cash_financing_interest_paid")
    leases = value(x,"cash_lease_payment_including_interest")
    if min(tax,interest,leases) < 0:
        raise ValueError("negative cash outflow tagging")
    net_investing = value(x,"net_cash_from_investing")
    net_financing = value(x,"net_cash_from_financing")
    if abs(cfo+net_investing+net_financing-value(x,"cash_decrease_total"))>0.0001:
        raise ValueError("net total company cash reconciliation incorrect")

    price = value(data,"nse_price_inr")
    capital_lakh = value(data,"equity_paid_up_capital_lakh_inr")
    fv = value(data,"face_value_inr")
    if min(price,capital_lakh,fv)<=0:
        raise ValueError("invalid share denominator")
    if data["price_source"] != "https://stockanalysis.com/quote/nse/PNCINFRA/market-cap/":
        raise ValueError("market quote source changed")
    shares = capital_lakh*100_000/fv
    mcap = shares*price/10_000_000
    if abs(shares-256_539_000) > 0.001:
        raise ValueError("original reported FY26 shares changed")
    debt = value(x,"current_borrowings")+value(x,"noncurrent_borrowings")
    cash_like = value(x,"other_bank_balances")+value(x,"cash_and_cash_equivalents")
    net_borrow = debt-cash_like
    book = value(x,"book_group_equity")
    Ebitda = value(x,"operating_EBITDA_issuer_press")
    if min(book,Ebitda,debt,cash_like)<=0:
        raise ValueError("financial capital denominators invalid")
    if data["sources"]["original_exchange_published_at_utc_from_l001"] >= data["created_asof_date"]:
        raise ValueError("historical filing not available before discovery")
    no_wc_after_ppe = pre_wc_after_tax-ppe
    conservative_selected = no_wc_after_ppe-interest-leases
    one_off_gain = value(x,"road_asset_sales_one_time_after_tax_gain_in_reported_PAT")
    PAT=value(x,"reported_PAT")
    if one_off_gain >= PAT:
        raise ValueError("unjustified one-time gain exceeds reported PAT")

    legal=data["court_and_catalyst"]
    if (
        legal["legal_order_date"] != "2026-10-12"
        or legal["next_hearing_scheduled"] != "2026-11-26"
        or legal["issuer_FY27_Q2_board_meeting_scheduled"] != "2026-10-28"
        or legal["issuer_FY27_Q2_results_published_asof_research"] is not False
        or legal["permanent_clearance_verified"] is not False
        or legal["interim_debarment_stay_valid_till_next_hearing"] is not True
    ):
        raise ValueError("false event date, results, or court finality")
    if data["risk_stresses"] != {
        "static_hold_debt_receivable_reversal_only": True,
        "cash_finance_interest_and_leases_belong_outside_indirect_CFO": True,
        "fully_unrestricted_other_bank_balances_unproven": True,
        "incremental_tax_interest_capex_after_2026_not_forecast": True,
    }:
        raise ValueError("stress assumptions or debt/cash restrictions removed")
    return {
        "research_id":data["schema"],"market_date":data["price_date"],
        "posthoc_original_sample_member":True,
        "equity_shares_millions":r4(shares/1_000_000),
        "market_cap_crore":r4(mcap),
        "market_cap_to_reported_group_book":r4(mcap/book),
        "group_debt_crore":r4(debt),
        "unverified_bank_and_cash_crore":r4(cash_like),
        "group_net_borrowings_if_all_cash_accessible_crore":r4(net_borrow),
        "illustrative_enterprise_value_crore":r4(mcap+net_borrow),
        "reported_FY26_EV_EBITDA_multiple":round((mcap+net_borrow)/Ebitda,2),
        "CFO_reported_crore":r4(cfo),
        "trade_receivable_cash_release_crore":r4(releases["trade_receivables_working_capital_release"]),
        "trade_receivable_release_pct_of_CFO":round(
            releases["trade_receivables_working_capital_release"]/cfo*100,2
        ),
        "all_wc_releases_net_crore":r4(change_wc),
        "FY26_cash_CFO_less_PPE_crore_NOT_owner_cash":r4(cfo-ppe),
        "before_WC_after_tax_operating_cash_crore":r4(pre_wc_after_tax),
        "after_PPE_before_interest_crore":r4(no_wc_after_ppe),
        "after_PPE_finance_interest_and_leases_crore":r4(conservative_selected),
        "strict_selected_cash_pct_of_cap":round(conservative_selected/mcap*100,2),
        "FY26_actual_cash_change_crore":r4(cfo+net_investing+net_financing),
        "FY26_group_revenue_growth_pct":round(
            (value(x,"revenue_operations")/value(x,"prior_FY_revenue")-1)*100,2
        ),
        "PAT_ex_only_337crore_road_sale_gain_crore":r4(PAT-one_off_gain),
        "P_E_ex_only_asset_monetization_gain_x":round(mcap/(PAT-one_off_gain),2),
        "asset_sale_gain_not_treated_as_recurring":True,
        "court_debarment_stay_is_interim":True,
        "court_next_hearing":legal["next_hearing_scheduled"],
        "Q2_FY27_real_data_available":False,
        "is_stock_selection_alpha":False,
        "is_investment_approved":False,
        "parent_owner_cash_verified":False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=INPUT)
    args=parser.parse_args()
    data=json.loads(args.input.read_text(encoding="utf-8"))
    baseline=json.loads(PINNED.read_text(encoding="utf-8"))
    print(json.dumps(audit(data,baseline),indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
