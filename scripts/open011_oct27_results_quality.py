"""OPEN011: source-bound Q2FY27 NSE issuer earnings falsification.

A post-hoc investment-diligence comparison; not a share-price predictor.
Q2 investor-call transcription figures, original issuer summary pages and
listed source URLs are NOT the same as a raw-source first-seen receipt.
All financial multiples are illustrative, not after-lease EV or owner FCF.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN011_OCT27_RESULTS_INPUT_20261028.json"
)


def valid_num(value: object, name: str, *, allow_negative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    amount = float(value)
    if not math.isfinite(amount) or (not allow_negative and amount < 0):
        raise ValueError(f"{name}: nonfinite/negative")
    return amount


def original_source_or_report(url: str, key: str) -> None:
    if not isinstance(url, str):
        raise ValueError(f"{key} must have original source")
    result = urlsplit(url)
    if result.scheme != "https" or not result.hostname:
        raise ValueError(f"{key} lacks HTTPS source")


def audit(packet: dict) -> dict:
    if packet["schema"] != "OPEN011_OCT28_POST_RESULTS_EVIDENCE_V1":
        raise ValueError("unexpected report format")
    if (
        packet["purpose"] != "POST_HOC_UNDERWRITING_NOT_HG009_ALPHA"
        or packet["as_of_date"] != "2026-10-28"
        or packet["last_completed_NSE_session"] != "2026-10-28"
    ):
        raise ValueError("source date or research scope illegally altered")
    if (
        packet["raw_pdf_archive_present"] is not False
        or packet["raw_pdf_sha256"] is not None
        or packet["original_first_seen_utc"] is not None
    ):
        raise ValueError("fabricated primary PDF custody")
    if (
        packet["frozen_H002_H003_HG009_unchanged"] is not True
        or packet["live_capital_authorized"] is not False
    ):
        raise ValueError("investment/alpha protocols may not be promoted")
    all_cases = packet["issuer_data"]
    if set(all_cases) != {"INDIAMART", "CENTENKA", "ACUTAAS"}:
        raise ValueError("original three issuer comparison must be preserved")
    for symbol, expected_isin in (
        ("INDIAMART", "INE933S01016"),
        ("CENTENKA", "INE485A01015"),
        ("ACUTAAS", "INE00FF01025"),
    ):
        row = all_cases[symbol]
        if (
            row["symbol"] != symbol
            or row["isin"] != expected_isin
            or row["period_end"] != "2026-09-30"
            or row["released"] != "2026-10-27"
        ):
            raise ValueError("issuer ISIN/period or public-filing date changed")
        if row["owner_FCFE_crore"] is not None:
            raise ValueError("owner FCF cannot be fabricated")

    m = all_cases["INDIAMART"]
    original_source_or_report(m["company_call_transcription"], "INDIAMART transcript")
    original_source_or_report(m["original_BSE_presentation_url_blocked"], "BSE presentation")
    if m["price_date"] != "2026-10-28":
        raise ValueError("fresh IndiaMART price date required")
    if m["cash_balance_period_and_definition_consistency_verified"] is not False:
        raise ValueError("unreconciled June/Sept cash definition must remain blocked")
    if m["wholly_accessible_parent_cash_verified"] is not False:
        raise ValueError("cash is not certified parent-available")
    if m["market_observed_price_is_executable_order"] is not False:
        raise ValueError("dated close is not executable offer")
    if (
        m["paying_suppliers_end_rounded"] != 217000
        or m["paying_suppliers_net_additions"] != -615
        or m["supplier_yoy_pct"] != -2
        or m["business_inquiries_million_rounded"] != 27
        or m["inquiries_yoy_pct"] != -14
    ):
        raise ValueError("operational deterioration cannot be backfilled away")
    if (
        m["case_margins_pct"] != [33, 37]
        or m["cash_available_fractions"] != [0, 0.25, 0.5, 1]
        or m["management_long_run_ebitda_margin_pct"] != 33
    ):
        raise ValueError("unapproved sensitivity assumptions")
    mcap = valid_num(m["approx_market_cap_crore"], "IndiaMART market cap")
    cash = valid_num(m["Q2_cash_treasury_crore_rounded"], "IndiaMART cash")
    revenue = valid_num(m["Q2_revenue_operations_crore_rounded"], "Q2 revenue")
    measured_ebitda = valid_num(m["Q2_EBITDA_crore_rounded"], "Q2 EBITDA")
    if min(mcap, cash, revenue, measured_ebitda) <= 0 or cash >= mcap:
        raise ValueError("IndiaMART fundamental/valuation dimensions invalid")
    if (
        m["Q2_cash_treasury_crore_rounded"] == m["Q1_cash_and_investments_prior_study_crore"]
        or m["Q1_cash_treasury_as_claimed_in_Q2_deck_crore"]
        == m["Q1_cash_and_investments_prior_study_crore"]
    ):
        raise ValueError("reported June cash perimeters need source reconciliation")
    if (
        valid_num(m["Q2_standalone_CFO_crore_rounded"], "parent CFO")
        > valid_num(m["Q2_consolidated_CFO_crore_rounded"], "group CFO")
    ):
        raise ValueError("source statement scope mismatch")
    if m["Q2_P_and_L_other_income_crore_rounded"] != -8:
        raise ValueError("mark-to-market loss from treasury must not be erased")
    margin_stress = []
    for margin in m["case_margins_pct"]:
        annual_ebitda_proxy = revenue * (margin / 100) * 4
        for fraction in m["cash_available_fractions"]:
            cash_after_assumed_access = mcap - cash * fraction
            margin_stress.append({
                "normalized_operating_margin_pct_assumed": margin,
                "fraction_of_treasury_assumed_accessible": fraction,
                "illustrative_annualized_EBITDA_crore": round(annual_ebitda_proxy, 2),
                "equity_cap_less_accessible_cash_crore": round(cash_after_assumed_access, 2),
                "illustrative_cash_adjusted_to_ebitda_multiple": round(
                    cash_after_assumed_access / annual_ebitda_proxy, 2
                ),
                "is_true_enterprise_value": False,
                "is_price_target_or_return_prediction": False,
            })

    c = all_cases["CENTENKA"]
    original_source_or_report(c["original_issuer_pdf_url"], "Century Q2 original")
    if c["original_pdf_download_state"] != "LOCATED_NOT_FETCHED_SIZE_LIMIT_11MB":
        raise ValueError("Century raw original evidence is not independently audited")
    if c["H1_original_CFO_admitted"] is not False:
        raise ValueError("could not verify Century original operating cash")
    q2_rev = valid_num(c["Q2_revenue_operations_crore"], "Century Q2 revenue")
    past_rev = valid_num(c["Q2_previous_year_revenue_crore"], "Century prior revenue")
    q2_ebitda = valid_num(c["Q2_EBITDA_crore"], "Century EBITDA")
    past_ebitda = valid_num(c["Q2_previous_year_EBITDA_crore"], "Century prior EBITDA")
    q2_pat = valid_num(c["Q2_consolidated_PAT_crore"], "Century PAT")
    past_pat = valid_num(c["Q2_previous_year_PAT_crore"], "Century prior PAT")
    q1_ebitda = valid_num(c["Q1_FY27_EBITDA_crore"], "Century Q1 EBITDA")
    q1_pat = valid_num(c["Q1_FY27_PAT_crore"], "Century Q1 PAT")
    if min(past_rev, past_ebitda, past_pat, q1_ebitda, q1_pat) <= 0:
        raise ValueError("Century comparison denominators invalid")

    a = all_cases["ACUTAAS"]
    original_source_or_report(a["issuer_signed_presentation_transcription"], "Acutaas Q2 original")
    if (
        a["operating_revenue_vs_total_income_not_same"] is not True
        or a["cash_after_plant_reinvestment_verified"] is not False
    ):
        raise ValueError("Acutaas recurring revenue/cash cannot be assumed")
    if (
        a["guidance_FY27_EBITDA_margin_low"] != 38
        or a["guidance_FY27_EBITDA_margin_high"] != 40
        or a["guidance_FY27_revenue_growth_pct"] != 30
    ):
        raise ValueError("unregistered Acutaas forecast assumptions")
    acut_rev = valid_num(a["Q2_operating_revenue_crore"], "Acutaas revenue")
    acut_ebitda = valid_num(a["Q2_EBITDA_crore"], "Acutaas EBITDA")
    acut_pat = valid_num(a["Q2_parent_attributable_PAT_crore"], "Acutaas parent PAT")
    acut_cap = valid_num(a["reference_mcap_crore_approx"], "Acutaas quote cap")
    acut_h1_pat = valid_num(a["H1_parent_PAT_crore"], "Acutaas H1 PAT")
    if min(acut_rev, acut_ebitda, acut_pat, acut_cap, acut_h1_pat) <= 0:
        raise ValueError("Acutaas positive denominators missing")
    if (
        a["other_source_total_income_crore"] <= acut_rev
        or a["reference_price_session"] != "2026-10-28"
    ):
        raise ValueError("Acutaas total income differs from revenue basis")

    b = packet["BLS_tender_observation"]
    if (
        b["authenticated_bidder_list_found"] is not False
        or b["authenticated_award_found"] is not False
        or b["schedules_not_awards"] is not True
        or len(set(b["published_tender_ids"])) != 4
    ):
        raise ValueError("government tender opening must not be called award")
    decision = packet["interpretation"]
    if decision["investable_picks"] != 0 or decision["probabilistic_return_estimate"] is not None:
        raise ValueError("invalid stock recommendation or invented probabilities")
    return {
        "as_of": packet["as_of_date"],
        "capital_authorized": False,
        "INDIAMART": {
            "paying_suppliers_rounded": m["paying_suppliers_end_rounded"],
            "actual_quarter_net_supplier_change": -615,
            "unique_business_inquiries_yoy_pct": -14,
            "Q2_CFO_group_crore": m["Q2_consolidated_CFO_crore_rounded"],
            "Q2_CFO_parent_crore": m["Q2_standalone_CFO_crore_rounded"],
            "Q2_group_CFO_share_from_parent_pct": round(
                m["Q2_standalone_CFO_crore_rounded"] /
                m["Q2_consolidated_CFO_crore_rounded"] * 100, 2),
            "reported_margin_pct": round(measured_ebitda / revenue * 100, 2),
            "management_long_run_margin_pct": 33,
            "cash_accounting_perimeter_Q1_to_Q2_reconciled": False,
            "Q1_to_Q2_cash_change_crore": None,
            "full_parent_owner_cash_available": None,
            "cash_adjusted_valuation_sensitivities": margin_stress,
        },
        "CENTENKA": {
            "Q2_revenue_yoy_pct": round((q2_rev / past_rev - 1) * 100, 2),
            "Q2_EBITDA_yoy_pct": round((q2_ebitda / past_ebitda - 1) * 100, 2),
            "Q2_PAT_yoy_pct": round((q2_pat / past_pat - 1) * 100, 2),
            "Q2_EBITDA_margin_pct": round(q2_ebitda / q2_rev * 100, 2),
            "year_ago_EBITDA_margin_pct": round(past_ebitda / past_rev * 100, 2),
            "Q1_to_Q2_EBITDA_change_pct": round((q2_ebitda / q1_ebitda - 1) * 100, 2),
            "Q1_to_Q2_PAT_change_pct": round((q2_pat / q1_pat - 1) * 100, 2),
            "original_cashflow_verified": False,
        },
        "ACUTAAS": {
            "Q2_EBITDA_margin_pct": round(acut_ebitda / acut_rev * 100, 2),
            "mcap_to_Q2_parent_profit_annualized_x": round(acut_cap / (acut_pat * 4), 2),
            "mcap_to_H1_parent_profit_annualized_x": round(acut_cap / (acut_h1_pat * 2), 2),
            "annualized_multiple_is_intrinsic_valuation": False,
            "growth_guidance_company_not_certainty": True,
            "fully_verified_parent_FCFE_crore": None,
        },
        "BLS_tender_award_verified": False,
        "investor_ready_picks": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    opts = parser.parse_args()
    print(json.dumps(audit(json.loads(opts.input.read_text(encoding="utf-8"))),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
