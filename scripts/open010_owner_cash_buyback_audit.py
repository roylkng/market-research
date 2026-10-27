"""OPEN010: issuer-backed NSE denominator, capital-return and cash-quality audit.

This deliberately does NOT predict stock prices, count buyback proceeds as
future dividends, or promote old disclosures to prospective H-series signals.
SEBI's September post-buyback PA and May NSE audited PDF were visually checked.
Original raw PDF bytes are not archived in this repository.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = (
    ROOT / "research/broad-discovery/OPEN010_REALIZED_CAPITAL_RETURN_INPUT_20261027.json"
)


def n(item: dict, key: str) -> float:
    value = item[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key}: numeric issuer source required")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{key}: invalid numeric issuer source")
    return result


def verify(data: dict) -> dict:
    if data["schema"] != "OPEN010-20261027-REALIZED-CAPITAL-RETURNS-V1":
        raise ValueError("unrecognized source evidence version")
    if data["research_date"] != "2026-10-27" or data["quote_session"] != "2026-10-26":
        raise ValueError("cannot backdate a market session")
    if data["purpose"] != "POSTHOC_BROAD_NSE_COMPANY_UNDERWRITING_NOT_ALPHA":
        raise ValueError("this is not prospective alpha")
    if not data["issuer_pdf_source_visually_verified"]:
        raise ValueError("PDF visual examination missing")
    if (
        data["original_raw_bytes_in_repo"] is not False
        or data["original_raw_first_seen_utc"] is not None
        or data["no_original_H002_H003_HG009_change"] is not True
        or data["no_capital_authorized"] is not True
    ):
        raise ValueError("raw source, backdating or capital promotion prohibited")
    if len(data["candidate_studies"]) != 2:
        raise ValueError("two candidate original study preserved")
    by_symbol = {v["symbol"]: v for v in data["candidate_studies"]}
    if set(by_symbol) != {"GANDHITUBE", "NUCLEUS"}:
        raise ValueError("unexpected issuer in audit")

    g = by_symbol["GANDHITUBE"]
    if g["isin"] != "INE524B01027":
        raise ValueError("Gandhi ISIN mismatch")
    if g["fy26_source_scope"] != "AUDITED_STANDALONE_INR_LAKH":
        raise ValueError("Gandhi annual accounting scope or unit changed")
    if g["fy26_cash_original"] != (
        "https://nsearchives.nseindia.com/corporate/"
        "GANDHITUBE_25052026194543_final_outcome_signed.pdf"
    ):
        raise ValueError("Gandhi original NSE source changed")
    if g["buyback_SEBI_post_advertisement_original"] != (
        "https://www.sebi.gov.in/sebi_data/commondocs/sep-2026/"
        "Gandhi%20Special%20Tubes%20Limited%20-%20PBA_p.pdf"
    ):
        raise ValueError("original SEBI source changed")
    if g["buyback_share_extinguishment_complete_date"] != "2026-09-17":
        raise ValueError("outcome chronology changed")
    if g["company_outstanding_share_count_confirmed_through"] != "2026-09-17":
        raise ValueError("post-buyback legal state changed")
    old_shares = g["pre_buyback_shares"]
    bought = g["buyback_completed_accepted_shares"]
    outstanding = g["post_buyback_shares"]
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (old_shares,bought,outstanding)):
        raise TypeError("share denominator must be integer original evidence")
    if (old_shares,bought,outstanding) != (12152000,868100,11283900):
        raise ValueError("original SEBI completed buyback shares changed")
    if old_shares - bought != outstanding:
        raise ValueError("post-buyback share count not reconciled")
    original_promoter = g["pre_buyback_promoter_shares"]
    post_promoter = g["post_buyback_promoter_shares"]
    if (original_promoter,post_promoter) != (8935257,8090553):
        raise ValueError("promoter class original share counts changed")
    promoter_accepted = original_promoter - post_promoter
    nonpromoter_accepted = bought - promoter_accepted
    if min(promoter_accepted,nonpromoter_accepted) < 0:
        raise ValueError("invalid class acceptance reconciliation")
    if (
        abs(original_promoter / old_shares * 100 - g["pre_buyback_promoter_pct"]) > 0.01
        or abs(post_promoter / outstanding * 100 - g["post_buyback_promoter_pct"]) > 0.01
    ):
        raise ValueError("promoter holdings cannot diverge from original disclosure")
    if g["sustaining_normalized_owner_cash_crore"] is not None:
        raise ValueError("cannot invent owner FCFE")
    if g["capital_distribution_fairness_verified"] is not False:
        raise ValueError("distribution justice cannot be inferred from acceptance")

    price_g = n(g,"price_inr")
    buyback_offer = n(g,"buyback_price_inr")
    if price_g <= 0 or buyback_offer != 900 or g["price_source"] != (
        "https://screener.fincascade.com/company/GANDHITUBE"
    ):
        raise ValueError("dated price or historic offer price not proved")
    mcap_g = outstanding * price_g / 10_000_000
    old_incorrect_cap = old_shares * price_g / 10_000_000
    cfo_g = n(g,"fy26_annual_operating_cash_lakh") / 100
    prior_cfo_g = n(g,"fy25_annual_operating_cash_lakh") / 100
    ppe_g = n(g,"fy26_ppe_cash_lakh") / 100
    lease_g = n(g,"fy26_cash_lease_principal_lakh") / 100
    interest_g = n(g,"fy26_finance_interest_paid_lakh") / 100
    earnings_g = n(g,"fy26_PAT_lakh") / 100
    current_assets_g = sum(
        n(g,k) for k in ("fy26_noncurr_investment_lakh",
                       "fy26_current_investment_lakh",
                       "fy26_cash_equivalent_lakh","fy26_other_bank_lakh")
    ) / 100
    q1_gain = n(g,"fy27_Q1_FVTPL_gain_lakh")
    q1_other = n(g,"fy27_Q1_other_income_lakh")
    q1_pbt = n(g,"fy27_Q1_PBT_lakh")
    if q1_gain > q1_other or q1_other > q1_pbt or q1_pbt == 0:
        raise ValueError("Q1 investment valuation gains cannot exceed parent totals")
    buyback_cr = bought * buyback_offer / 10_000_000
    promoter_cash_cr = promoter_accepted * buyback_offer / 10_000_000
    nonpromoter_cash_cr = nonpromoter_accepted * buyback_offer / 10_000_000

    nuc = by_symbol["NUCLEUS"]
    if (nuc["isin"],nuc["fy26_source_scope"]) != (
        "INE096B01018","AUDITED_CONSOLIDATED_INR_LAKH"
    ):
        raise ValueError("Nucleus ISIN/statement scope mismatch")
    if nuc["fy26_original"] != (
        "https://nsearchives.nseindia.com/corporate/"
        "Nucleus_21052026150516_OUTCOME.pdf"
    ):
        raise ValueError("Nucleus original cash evidence altered")
    if nuc["FY27_Q2_results_board_date"] != "2026-10-31":
        raise ValueError("upcoming financial decision cannot be backfilled")
    if nuc["latest_legal_current_shares_after_FY26_verified"] is not False:
        raise ValueError("must not invent a new 2026 share count")
    if (nuc["noncurrent_investments_accessible_cash_verified"] is not False
        or nuc["noncurrent_other_financial_assets_in_cash_pool_verified"] is not False
        or nuc["normalized_parent_owner_cash_crore"] is not None):
        raise ValueError("noncurrent/foreign parent cash rights unverified")
    shares_n = nuc["shares_original_FY26"]
    if isinstance(shares_n,bool) or not isinstance(shares_n,int) or shares_n != 26325306:
        raise ValueError("Nucleus share denominator not issuer-verified")
    quote_n = n(nuc,"price_inr")
    cap_n = shares_n * quote_n / 10_000_000
    cfo_n = n(nuc,"fy26_cash_operating_lakh") / 100
    cfo_n_prior = n(nuc,"fy25_cash_operating_lakh") / 100
    capital_n = n(nuc,"fy26_cash_PPE_and_intangibles_lakh") / 100
    lease_n = (n(nuc,"fy26_lease_principal_lakh")
               + n(nuc,"fy26_lease_interest_lakh")) / 100
    current_n = sum(
        n(nuc,k) for k in (
            "current_investments_lakh","cash_equivalents_lakh",
            "other_bank_balances_lakh")
    ) / 100
    noncurrent_n = sum(
        n(nuc,k) for k in (
            "noncurrent_investments_lakh","noncurrent_other_financial_assets_lakh")
    ) / 100
    group_debt_and_other_claims = (
        n(nuc,"FY26_total_assets_lakh")-n(nuc,"FY26_total_equity_lakh")
    )/100
    if current_n + noncurrent_n > n(nuc,"FY26_total_assets_lakh")/100:
        raise ValueError("book noncash assets inconsistent")
    q1_pat = n(nuc,"FY27_Q1_PAT_crore")
    prior_q1_pat = n(nuc,"FY26_Q1_PAT_crore")
    if min(q1_pat,prior_q1_pat) <= 0:
        raise ValueError("invalid quarterly profit comparison")
    if nuc["FY25_buyback_cancelled_shares"] != 448018 or (
        n(nuc,"FY25_buyback_at_price_inr") != 1615
    ):
        raise ValueError("historic Nucleus buyback evidence altered")

    controls = data["controls"]
    if controls != {
        "quote_is_last_completed_NSE_session": True,
        "buyback_old_shares_for_marketcap_forbidden": True,
        "prior_buyback_price_not_current_arbitrage": True,
        "FY26_historical_FCF_proxy_not_forecast": True,
        "no_fabricated_original_source_archive": True,
        "no_retrospective_alpha_rank": True,
        "capital_authorized": False,
        "investment_ready_companies": 0,
        "calibrated_return_probabilities": None,
    }:
        raise ValueError("source scoring or trading guard removed")
    return {
        "as_of":data["research_date"],
        "original_portfolios_unchanged":True,
        "capital_authorized":False,
        "GANDHITUBE":{
            "latest_source_verified_shares":outstanding,
            "post_buyback_mcap_crore":round(mcap_g,4),
            "stale_old_share_mcap_crore":round(old_incorrect_cap,4),
            "old_share_denominator_mcap_error_crore":round(
                old_incorrect_cap-mcap_g,4),
            "buyback_gross_paid_crore":round(buyback_cr,5),
            "promoter_group_shares_accepted":promoter_accepted,
            "nonpromoter_shares_accepted":nonpromoter_accepted,
            "promoter_share_of_repurchases_pct":round(
                100*promoter_accepted/bought,4),
            "gross_cash_paid_to_promoters_crore":round(promoter_cash_cr,5),
            "gross_cash_paid_to_nonpromoters_crore":round(nonpromoter_cash_cr,5),
            "fy26_earnings_crore":round(earnings_g,4),
            "fy27_Q1_mtm_in_other_income_crore":round(q1_gain/100,4),
            "fy27_Q1_mtm_gain_as_pct_of_PBT":round(q1_gain/q1_pbt*100,2),
            "fy27_Q1_PBT_ex_only_FVTPL_gain_crore":round((q1_pbt-q1_gain)/100,4),
            "fy26_proforma_earnings_per_new_share_inr":round(
                earnings_g*10_000_000/outstanding,4),
            "historical_earnings_to_new_cap_multiple":round(
                mcap_g/earnings_g,2),
            "fy26_CFO_crore":round(cfo_g,4),
            "fy25_CFO_crore":round(prior_cfo_g,4),
            "fy26_CFO_less_selected_PPE_lease_interest_crore":round(
                cfo_g-ppe_g-lease_g-interest_g,4),
            "historic_cash_proxy_yield_pct":round(
                (cfo_g-ppe_g-lease_g-interest_g)/mcap_g*100,2),
            "March2026_investments_bank_cash_pre_buyback_crore":round(
                current_assets_g,4),
            "must_not_subtract_historic_buyback_from_March_assets_to_claim_Oct_cash":True,
            "company_dividend_repetition_guaranteed":False,
            "next_shareholder_buyback_open":False,
            "parent_cash_rights_and_normalized_FCFE_confirmed":False,
            "investment_recommendation":"WATCH_NOT_BUY",
        },
        "NUCLEUS":{
            "reference_FY26_shares_not_new_Q2_verified":shares_n,
            "reference_equity_cap_crore":round(cap_n,4),
            "fy26_after_tax_CFO_crore":round(cfo_n,4),
            "fy25_after_tax_CFO_crore":round(cfo_n_prior,4),
            "fy26_CFO_change_pct":round((cfo_n/cfo_n_prior-1)*100,2),
            "fy26_CFO_less_PPE_and_lease_crore":round(
                cfo_n-capital_n-lease_n,4),
            "historic_cash_proxy_yield_pct":round(
                (cfo_n-capital_n-lease_n)/cap_n*100,2),
            "march2026_current_cash_investments_crore":round(current_n,4),
            "march2026_noncurrent_financial_assets_not_assumed_liquid_crore":round(
                noncurrent_n,4),
            "all_book_liabilities_crore":round(group_debt_and_other_claims,4),
            "q1_FY27_PAT_change_pct":round((q1_pat/prior_q1_pat-1)*100,2),
            "FY25_buyback_paid_currently_actionable":False,
            "owner_cash_verified":False,
            "investment_recommendation":"WATCH_NOT_BUY"
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(args.input.read_text(encoding="utf-8"))),
                     indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
