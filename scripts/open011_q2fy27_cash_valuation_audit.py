"""OPEN011: reproducible, source-scoped Q2 FY27 cash and valuation hurdles.

This is independent, retrospective issuer underwriting and not an H-series
prospective alpha model. Conditional reverse returns are not price forecasts.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN011_Q2FY27_EVIDENCE_INPUT_20261029.json"
)


def amount(value: object, name: str, *, allow_negative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or (number < 0 and not allow_negative):
        raise ValueError(f"{name} must be finite and valid")
    return number


def pct(a: float, b: float) -> float:
    if b <= 0:
        raise ValueError("invalid percentage denominator")
    return round((a / b - 1) * 100, 2)


def evaluate(p: dict) -> dict:
    if p["schema"] != "OPEN011_20261029_FY27_Q2_ORIGINAL_DISCLOSURE_CHALLENGE_V1":
        raise ValueError("frozen review schema changed")
    if p["as_of_IST"] != "2026-10-29" or p["market_price_date"] != "2026-10-29":
        raise ValueError("source observation clock changed")
    if p["experiment"] != "INDEPENDENT_POST_HOC_UNDERWRITING_NO_H002_H003_HG009_BACKFILL":
        raise ValueError("cannot promote post-hoc research to original alpha")
    if p["source_limits"] != {
        "all_three_signed_issuer_publications_retrieved_or_transcribed": True,
        "original_issuer_PDF_bytes_archived_in_repo": False,
        "canonical_first_observed_UTC": None,
        "canonical_original_file_SHA256": None,
        "official_exchange_closing_auction_price_verified": False,
    }:
        raise ValueError("unverified source custody or exchange quote promoted")
    if p["capital_permissions"] != {
        "approved_buys": 0,
        "capital_authorized": False,
        "parent_owner_FCFE_fully_underwritten_count": 0,
        "calibrated_outcome_probabilities": None,
    }:
        raise ValueError("research must remain not trade approved")
    records = p["issuer_records"]
    if len(records) != 3 or {v["symbol"] for v in records} != {
        "ACUTAAS", "INDIAMART", "CENTENKA"
    }:
        raise ValueError("three exact original issuer identities required")
    data = {v["symbol"]: v for v in records}
    expected_isins = {
        "ACUTAAS": "INE00FF01025",
        "INDIAMART": "INE933S01016",
        "CENTENKA": "INE485A01015",
    }
    for symbol, r in data.items():
        if r["isin"] != expected_isins[symbol]:
            raise ValueError(f"{symbol}: wrong ISIN")
        if r["q2_release_date"] != "2026-10-27":
            raise ValueError("report date must not be backdated")
        if r["reporting_period_end"] != "2026-09-30":
            raise ValueError("financial period mismatch")
        if "2026-10-29" not in r["quote_observation"]:
            raise ValueError("delayed quote label must be retained")
        if r["underwritten_intrinsic_value"] is not None:
            raise ValueError("unverified intrinsic value")
        if r["parent_owner_distributable_cash"] is not None:
            raise ValueError("unverified parent owner cash")
        if amount(r["quote_inr"], "quoted share price") <= 0:
            raise ValueError("invalid delayed quote")

    a = data["ACUTAAS"]
    if a["reported_unit_sales_profit"] != "INR_MILLION" or (
        a["reported_unit_cashflow"] != "INR_LAKH"
    ):
        raise ValueError("different Acutaas source units must not be mixed")
    if a["original_exchange_press_pdf"] != (
        "https://nsearchives.nseindia.com/corporate/"
        "AMIORG_27102026125648_PressrealeaseSigned.pdf"
    ):
        raise ValueError("Acutaas original NSE issuer document changed")
    if (a["original_issuer_mirror_cash_page_zero_index"],
        a["original_issuer_mirror_notes_page_zero_index"]) != (9, 10):
        raise ValueError("cash and minority disclosure pages unverified")
    a_shares = amount(a["asof_paid_up_equity_capital_lakh"], "share capital")
    face = amount(a["asof_share_face_value_inr"], "face value")
    if face != 5:
        raise ValueError("Acutaas paid-up share face value changed")
    # INR lakh / INR per share -> count shares, not crore shares.
    share_count = round(a_shares * 100_000 / face)
    if share_count != 81_871_200:
        raise ValueError("Acutaas issuer share-capital denominator altered")
    a_cap = share_count * amount(a["quote_inr"], "Acutaas price") / 10_000_000
    group_profit = amount(a["h1_consolidated_PAT_lakh"], "group PAT")
    parent_profit = amount(a["h1_parent_profit_lakh"], "parent PAT")
    nci_profit = amount(
        a["h1_noncontrolling_profit_lakh"], "NCI PAT", allow_negative=True
    )
    if abs(parent_profit + nci_profit - group_profit) > 0.005:
        raise ValueError("group and minority profit identity failed")
    cfo = amount(a["h1_CFO_lakh"], "H1 CFO") / 100
    old_cfo = amount(a["h1_prior_CFO_lakh"], "prior H1 CFO") / 100
    capex = amount(a["h1_PPE_intangible_CWIP_cash_lakh"], "H1 capex") / 100
    old_capex = amount(
        a["h1_prior_PPE_intangible_CWIP_cash_lakh"], "prior H1 capex"
    ) / 100
    inventory_absorption = amount(
        a["h1_inventory_cash_adjustment_lakh"],
        "cash inventory", allow_negative=True
    ) / 100
    if inventory_absorption >= 0:
        raise ValueError("original inventory absorption sign must not be inverted")
    diluted_h1 = amount(a["h1_diluted_eps_inr"], "reported H1 diluted EPS")
    if abs(diluted_h1 - 24.28) > 0.001:
        raise ValueError("Acutaas consolidated H1 diluted EPS changed")
    q2_revenue_yoy = pct(
        amount(a["q2_revenue_million"], "Q2 revenue"),
        amount(a["q2_prior_revenue_million"], "prior Q2 revenue"),
    )
    q2_ebitda_yoy = pct(
        amount(a["q2_ebitda_million"], "Q2 EBITDA"),
        amount(a["q2_prior_ebitda_million"], "prior Q2 EBITDA"),
    )
    assumptions = a["reverse_assumptions"]
    if assumptions != {
        "annualized_H1_diluted_EPS_only_as_sensitivity": True,
        "gross_required_equity_return_pct": 12,
        "years": 10,
        "terminal_PE": 30,
        "dividend_dilution_taxes_and_costs_modeled": False,
    }:
        raise ValueError("reverse-expectations assumptions changed")
    # NOT a forecast or normalized EPS: double current H1 diluted EPS only
    # to illustrate the terminal-growth hurdle implicit in the quote.
    eps_proxy = diluted_h1 * 2
    required_future_eps = (
        a["quote_inr"] * (1 + assumptions["gross_required_equity_return_pct"] / 100)
        ** assumptions["years"] / assumptions["terminal_PE"]
    )
    implied_eps_cagr = (
        (required_future_eps / eps_proxy) ** (1 / assumptions["years"]) - 1
    ) * 100
    if a["indichem_south_korea_stake_fraction"] != 0.75 or (
        a["indichem_production_status_asof_sep"]
        != "TRIAL_RUNS_NOT_COMMERCIAL_SALES_PROVEN"
    ):
        raise ValueError("Korean ownership or commercial state misrepresented")
    if a["enchem_reorganization_2026_10_17"] != (
        "EXISTING_SUBSIDIARY_TO_DIRECT_PARENT_HOLDING_NOT_EXTERNAL_ACQUISITION"
    ):
        raise ValueError("internal Enchem transfer misrepresented")
    acutaas = {
        "H1_consolidated_CFO_cr": round(cfo, 4),
        "H1_previous_CFO_cr": round(old_cfo, 4),
        "H1_CFO_growth_pct": pct(cfo, old_cfo),
        "H1_cash_PPE_intangible_CWIP_cr": round(capex, 4),
        "H1_cash_after_selected_PPE_cr": round(cfo - capex, 4),
        "prior_H1_cash_after_selected_PPE_cr": round(old_cfo - old_capex, 4),
        "inventory_cash_absorption_cr": round(inventory_absorption, 4),
        "H1_parent_PAT_cr": round(parent_profit / 100, 4),
        "H1_noncontrolling_PAT_cr": round(nci_profit / 100, 4),
        "H1_group_PAT_cr": round(group_profit / 100, 4),
        "Q2_revenue_growth_pct": q2_revenue_yoy,
        "Q2_EBITDA_growth_pct": q2_ebitda_yoy,
        "reference_issued_shares": share_count,
        "reference_equity_market_cap_cr": round(a_cap, 4),
        "annualized_H1_diluted_EPS_proxy_inr": round(eps_proxy, 2),
        "price_to_annualized_H1_diluted_EPS_proxy": round(a["quote_inr"] / eps_proxy, 2),
        "annualized_selected_cash_as_pct_of_market_cap": round(
            2 * (cfo - capex) / a_cap * 100, 2
        ),
        "ten_year_EPS_CAGR_required_for_hypothetical_12pct_gross_return_with_terminal_30PE_pct": round(
            implied_eps_cagr, 2
        ),
        "required_growth_is_forecast": False,
        "Korean_75pct_owned_plant_in_trials": True,
        "investment_decision": "VALUATION_GATE_FAILED_NO_BUY",
    }

    b = data["INDIAMART"]
    if "financialreports.eu" not in b["original_issuer_press_reproduced_pdf"] or (
        b["press_metrics_zero_index_page"] != 3
    ):
        raise ValueError("IndiaMART signed issuer metrics source missing")
    if b["h1_audited_after_tax_CFO_cr_exact"] is not None or (
        b["latest_fully_diluted_share_count"] is not None
    ):
        raise ValueError("unreconciled H1 operating cash/share capital invented")
    if b["supplier_exact_sequential_decrease_from_call_transcript"] != -615:
        raise ValueError("transcript source supplier delta changed")
    if b["q2_paying_suppliers_rounded"] != 217000 or (
        b["q1_paying_suppliers_rounded"] != 218000
    ):
        raise ValueError("issuer reported rounded supplier count changed")
    if b["other_market_vendor_close_inr"] < b["quote_inr"]:
        raise ValueError("quote-source disagreement not preserved")
    india = {
        "Q2_revenue_growth_pct": pct(
            amount(b["q2_group_revenue_crore"], "IndiaMART revenue"),
            amount(b["q2_prior_group_revenue_crore"], "IndiaMART prior revenue")
        ),
        "reported_Q2_operating_cash_cr": b["q2_CFO_management_reported_crore"],
        "reported_Q1_operating_cash_cr": b["q2_q1_CFO_management_reported_crore"],
        "Q2_operating_cash_qoq_pct": pct(
            amount(b["q2_CFO_management_reported_crore"], "Q2 operating cash"),
            amount(b["q2_q1_CFO_management_reported_crore"], "Q1 operating cash")
        ),
        "q2_cash_investments_cr": b["q2_cash_and_investments_crore"],
        "cash_investments_change_qoq_cr": round(
            b["q2_cash_and_investments_crore"]
            - b["q1_cash_and_investments_crore"], 2
        ),
        "q2_parent_fraction_of_group_marked_cash_pct": round(
            b["q2_parent_cash_and_investments_crore"]
            / b["q2_cash_and_investments_crore"] * 100, 2
        ),
        "paid_suppliers_reported_end_rounded": b["q2_paying_suppliers_rounded"],
        "paid_supplier_exact_sequential_change_call_only": -615,
        "exact_delta_not_derived_from_rounded_217k_218k": True,
        "company_reported_deferred_revenue_cr": b["q2_deferred_revenue_crore"],
        "audited_H1_CFO_cr": None,
        "fully_diluted_issuer_shares": None,
        "investment_decision": "RETAIN_WATCH_SUBSCRIBER_RENEWALS_UNDER_REVIEW",
    }

    c = data["CENTENKA"]
    if c["q2_investor_explanation_date"] != "2026-10-28" or not (
        c["Q1_issuer_explicit_early_inventory_cost_tailwind"]
    ):
        raise ValueError("Century issuer Q1 inventory explanation source missing")
    if c["h1_issuer_actual_after_tax_CFO_cr"] is not None:
        raise ValueError("Century H1 source CFO not yet validated")
    if c["reference_FY26_basic_shares_crore"] != 2.185:
        raise ValueError("Century FY26 share reference changed")
    if (c["normalized_margin_company_low_pct"],
        c["normalized_margin_company_high_pct"]) != (7, 10):
        raise ValueError("Century conditional margin band mutated")
    c_cap = c["quote_inr"] * c["reference_FY26_basic_shares_crore"]
    if (c["q2_group_PAT_crore"] <= 0
        or c["q1_group_PAT_crore"] <= 0):
        raise ValueError("positive quarter earnings required for simple sensitivity")
    century = {
        "Q2_revenue_yoy_pct": pct(
            c["q2_group_revenue_crore"], c["q2_prior_group_revenue_crore"]
        ),
        "Q2_EBITDA_qoq_pct": pct(
            c["q2_EBITDA_crore"], c["q1_EBITDA_crore"]
        ),
        "Q2_PAT_qoq_pct": pct(
            c["q2_group_PAT_crore"], c["q1_group_PAT_crore"]
        ),
        "reported_Q2_EBITDA_margin_pct": c["q2_issuer_EBITDA_margin_pct"],
        "reported_Q1_EBITDA_margin_pct": c["q1_issuer_EBITDA_margin_pct"],
        "source_issuer_Q1_low_cost_opening_inventory_windfall": True,
        "reference_market_cap_cr": round(c_cap, 4),
        "reference_Sept_equity_book_price_ratio": round(
            c_cap / c["FY27_H1_close_equity_crore"], 4
        ),
        "P_to_annualized_Q2_PAT_illustration": round(
            c_cap / (c["q2_group_PAT_crore"] * 4), 2
        ),
        "P_to_annualized_H1_PAT_illustration": round(
            c_cap / ((c["q2_group_PAT_crore"] + c["q1_group_PAT_crore"]) * 2), 2
        ),
        "annualization_is_stable_earnings_estimate": False,
        "issuer_cashflow_verified": False,
        "investment_decision": "HOLD_MARGIN_CYCLICALITY_UNDER_REVIEW",
    }
    upcoming = p["next_decisive_events"]
    if upcoming != [
        {"name": "Crizac Q2/H1 results", "date": "2026-10-30",
         "confirmed_published_asof": False},
        {"name": "BLS Canada MEA bid opening", "date": "2026-11-02",
         "confirmed_award_asof": False},
    ]:
        raise ValueError("future event/award fabrication")
    return {
        "schema": p["schema"],
        "analysed_on": p["as_of_IST"],
        "source_bytes_pinned": False,
        "exchange_auction_price_verified": False,
        "approved_positions": 0,
        "original_HG009_H002_H003_frozen": True,
        "ACUTAAS": acutaas,
        "INDIAMART": india,
        "CENTENKA": century,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text(encoding="utf-8"))),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
