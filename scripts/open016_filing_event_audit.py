"""OPEN016: fail-closed, source-pinned post-hoc NSE/BSE research replay.

Standalone receivables are not substituted for consolidated CFO.
The Oct30 Crizac NSE after-close filing cannot explain the Oct30 close
as a retrospectively tradable reaction. Signed PDF text was transcribed
through market mirrors and original issuer URL located, NOT archived/visually
read here because issuer PDF is ~12MB and source fetch hit size restrictions.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / (
    "research/broad-discovery/OPEN016_Q2_DISCOVERY_INPUT_20261030.json"
)


def measure(record: dict, field: str, *, allow_negative: bool = False) -> float:
    value = record[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be issuer-sourced numeric")
    if not math.isfinite(value) or (not allow_negative and value < 0):
        raise ValueError(f"{field} invalid original numeric")
    return float(value)


def pct(new: float, old: float) -> float:
    if old <= 0:
        raise ValueError("comparative cannot be zero or negative")
    return (new / old - 1) * 100


def replay(packet: dict) -> dict:
    if packet["schema"] != "OPEN016-20261030-RESEARCH-ONLY-v1":
        raise ValueError("unsupported source packet")
    if packet["observed_local"] != "2026-10-30T19:09:24+05:30":
        raise ValueError("point-in-time original observation changed")
    if packet["study_type"] != (
        "POST_HOC_FILING_DISCOVERY_UNRELATED_TO_FROZEN_H002_H003_HG009"
    ):
        raise ValueError("frozen selection leakage prohibited")
    if (packet["raw_issuer_pdf_bytes_archived"] is not False
        or packet["original_issuer_filing_located"] is not True
        or packet["original_issuer_pdf_visually_inspected"] is not False
        or packet["source_tier"] != (
            "SIGNED_ISSUER_TEXT_REPRODUCED_BY_EXCHANGE_MIRRORS_AND_ISSUER_REPORT_INDEX_ONLY"
        )
        or packet["future_prediction_or_live_capital"] is not False):
        raise ValueError("cannot overclaim original issuer document access or signal")
    if set(packet["studies"]) != {"CRIZAC", "OSWALPUMPS"}:
        raise ValueError("source universe unexpectedly changed")
    guards = packet["safety_gates"]
    if set(guards) != {
        "no_trade", "no_buy_recommendations",
        "no_quote_after_issuer_release_claimed_for_CRIZAC",
        "no_legacy_cohort_mutation",
        "no_sustainable_owner_cash_inferred_from_group_CFO",
        "no_earned_profit_from_gross_order",
        "no_cash_bank_assets_inferred_as_unrestricted",
        "no_certainty_or_return_probabilities", "no_simulated_raw_pdf_sha"
    } or any(v is not True for v in guards.values()):
        raise ValueError("required anti-investment-promotion gate failed")

    c = packet["studies"]["CRIZAC"]
    if (
        c["isin"] != "INE0S4R01014"
        or c["event_date"] != "2026-10-30"
        or c["statement_scope"] != "UNAUDITED_LIMITED_REVIEW_CONSOLIDATED_INR_LAKH"
        or c["quarter_ended"] != "2026-09-30"
        or c["period_h1_ended"] != "2026-09-30"
        or c["source_NSE_named_attachment"] is not None
        or c["source_issuer_original_url"] != (
            "https://www.crizac.com/investors_file/stock-exchange-intimation/"
            "FY26-27/outcome-of-the-bm-for-quarter-ended-september-30-2026.pdf"
        )
        or c["source_released_time"] != "2026-10-30T16:57:00+05:30"
        or c["source_released_clock_basis"] != (
            "third_party_mirror_publication_time_not_primary_exchange_legal_release"
        )
        or c["price_clock"] != "2026-10-30T15:29:00+05:30"
        or c["q2_meeting_end_local"] != "2026-10-30T16:40:00+05:30"
    ):
        raise ValueError("Crizac issuer, session, source or clock mismatch")
    if any(c[k] is not False for k in (
        "current_free_cash_at_parent_verified", "subscription_UK_loss_cause_verified",
        "ownership_and_acquisition_dilution_full_verified", "value_ready"
    )):
        raise ValueError("Crizac cannot be promoted with missing disclosures")
    shares_c = c["share_count_from_dividend_consistency"]
    if (
        isinstance(shares_c, bool) or not isinstance(shares_c, int)
        or shares_c != 174982500 or c["share_FV_INR"] != 2
        or c["interim_dividend_per_share_inr"] != 4
        or c["dividend_record_date"] != "2026-11-06"
        or c["dividend_payment_deadline"] != "2026-11-27"
    ):
        raise ValueError("issuer share denominator or dividend changed")
    crizac_cash = measure(c, "h1_after_tax_operating_cash_lakh") / 100
    crizac_pat = measure(c, "h1_PAT_lakh") / 100
    crizac_mcap = shares_c * measure(c, "price_nse_close_2026_10_30_inr") / 1e7
    crizac_dividend_total = shares_c * 4 / 1e7
    h1_tax_asset = measure(c, "h1_UK_deferred_tax_asset_recognition_lakh") / 100
    if measure(c, "two_overseas_subs_q2_PAT_lakh", allow_negative=True) >= 0:
        raise ValueError("overseas subset loss reclassified")
    if measure(c, "two_overseas_subs_h1_PAT_lakh", allow_negative=True) >= 0:
        raise ValueError("overseas H1 subset loss reclassified")
    if measure(c, "quarter_lower_depreciation_due_method_change_lakh") >= (
        measure(c, "q2_PAT_lakh")
    ):
        raise ValueError("depreciation accounting estimate inconsistent")
    fy26_pat = measure(c,"FY26_PAT_consolidated_lakh")/100
    prior_h1_pat = measure(c,"h1_prior_PAT_lakh")/100
    ttm_pat = fy26_pat + crizac_pat - prior_h1_pat
    if min(ttm_pat-h1_tax_asset,crizac_mcap) <= 0:
        raise ValueError("invalid trailing reference / tax sensitivity")

    o = packet["studies"]["OSWALPUMPS"]
    if (
        o["isin"] != "INE0BYP01024"
        or o["event_date"] != "2026-10-30"
        or o["order_awarding_company"] != (
            "Maharashtra State Electricity Distribution Company Limited"
        )
        or o["source_exchange_pdf_uuid"] != (
            "0e6cb910-22f6-4fb8-93e4-f050c5fdb5fc.pdf"
        )
        or o["source_annual_transcribed"] != (
            "https://financialfilings.com/filings/oswal-pumps-limited/"
            "annual-report/2026/59465028/"
        )
        or o["price_close_date"] != "2026-10-29"
        or o["award_notice_timestamp"] != "2026-10-30T12:02:00+05:30"
        or o["order_execution_days"] != "60_FROM_WORK_ORDER_OR_NOTICE_TO_PROCEED"
        or o["order_service_years"] != 5
        or o["order_solar_pumps"] != 10000
        or o["FY26_standalone_receivables_hypothecated"] is not True
    ):
        raise ValueError("Oswal source scope, time or contract changed")
    if any(o[k] is not False for k in (
        "award_GST_exclusion_verified","cash_collected_on_new_order",
        "award_net_margin_verified","full_contract_order_terms_verified",
        "owner_parent_cash_verified","value_ready"
    )):
        raise ValueError("Oswal gross contract cannot be owner earnings")
    if measure(o,"FY26_CONSOLIDATED_after_tax_CFO_million",allow_negative=True) >= 0:
        raise ValueError("negative operating cash flow concealed")
    if measure(o,"FY25_CONSOLIDATED_after_tax_CFO_million",allow_negative=True) >= 0:
        raise ValueError("negative prior cash flow concealed")
    if (
        measure(o,"FY26_CONSOLIDATED_PPE_cash_outflow_million") <= 0
        or measure(o,"FY26_CONSOLIDATED_PAT_million") <= 0
    ):
        raise ValueError("capex or earnings line misunderstood")
    if measure(o,"FY26_standalone_trade_receivables_million") <= (
        measure(o,"FY25_standalone_trade_receivables_million")
    ):
        raise ValueError("receivables did not reconcile")
    annual_net_rcv = measure(o,"FY26_standalone_trade_receivables_million") / 10
    old_net_rcv = measure(o,"FY25_standalone_trade_receivables_million") / 10
    cap_o = measure(o,"approx_mcap_2026_10_29_crore")
    order_incl_GST = measure(o,"order_amount_including_GST_crore")
    annual_profit_o=measure(o,"FY26_CONSOLIDATED_PAT_million") / 10
    annual_cfo_o=measure(o,"FY26_CONSOLIDATED_after_tax_CFO_million",
                         allow_negative=True) / 10
    annual_capex_o=measure(o,"FY26_CONSOLIDATED_PPE_cash_outflow_million") / 10
    q1profit_o=measure(o,"Q1FY27_CONSOLIDATED_PAT_crore")
    prior_q1profit_o=measure(o,"Q1FY26_CONSOLIDATED_PAT_crore")
    # This is not a terminal price or FY27 profit forecast.
    q1_annualised_simple = q1profit_o * 4
    return {
        "evidence_level": packet["source_tier"],
        "historical_cohorts_untouched":True,
        "capital_authorized":False,
        "Crizac":{
            "observation_session":"2026-10-30",
            "q2_revenue_yoy_pct":round(pct(
                measure(c,"q2_revenue_lakh"),measure(c,"q2_revenue_prior_lakh")),2),
            "q2_revenue_qoq_pct":round(pct(
                measure(c,"q2_revenue_lakh"),measure(c,"q1_revenue_lakh")),2),
            "q2_PBT_yoy_pct":round(pct(
                measure(c,"q2_PBT_lakh"),measure(c,"q2_prior_PBT_lakh")),2),
            "q2_PAT_yoy_pct":round(pct(
                measure(c,"q2_PAT_lakh"),measure(c,"q2_prior_PAT_lakh")),2),
            "h1_revenue_yoy_pct":round(pct(
                measure(c,"h1_revenue_lakh"),measure(c,"h1_prior_revenue_lakh")),2),
            "h1_PAT_yoy_pct":round(pct(
                measure(c,"h1_PAT_lakh"),measure(c,"h1_prior_PAT_lakh")),2),
            "h1_CFO_crore_not_owner_FCFE":round(crizac_cash,4),
            "h1_UK_deferred_tax_asset_crore":round(h1_tax_asset,4),
            "h1_UK_DTA_as_pct_H1_PAT":round(100*h1_tax_asset/crizac_pat,2),
            "q2_effective_tax_rate_pct":round(100*(1-measure(c,"q2_PAT_lakh")/measure(c,"q2_PBT_lakh")),2),
            "prior_q2_effective_tax_rate_pct":round(100*(1-measure(c,"q2_prior_PAT_lakh")/measure(c,"q2_prior_PBT_lakh")),2),
            "reference_shares":shares_c,
            "reference_close_market_cap_crore":round(crizac_mcap,4),
            "reference_trailing_PAT_crore":round(ttm_pat,4),
            "reference_P_E_x":round(crizac_mcap/ttm_pat,2),
            "mechanical_P_E_ex_H1_DTA_x_NOT_FORECAST":round(
                crizac_mcap/(ttm_pat-h1_tax_asset),2),
            "interim_dividend_total_crore":round(crizac_dividend_total,4),
            "new_dividend_pct_of_H1_CFO":round(crizac_dividend_total/crizac_cash*100,2),
            "price_preceded_disclosure":True,
            "opportunity_status":"THESIS_NEGATIVE_RESEARCH_ONLY"
        },
        "OswalPumps":{
            "source_event_date":"2026-10-30",
            "reference_market_cap_29oct_crore":cap_o,
            "award_gross_including_GST_crore":order_incl_GST,
            "award_gross_pct_prior_equity_cap":round(100*order_incl_GST/cap_o,2),
            "FY26_group_PAT_crore":round(annual_profit_o,4),
            "FY26_group_CFO_crore":round(annual_cfo_o,4),
            "FY26_group_PPE_cash_outflow_crore":round(annual_capex_o,4),
            "FY26_selected_CFO_after_PPE_crore_NOT_FCFE":round(
                annual_cfo_o-annual_capex_o,4),
            "FY26_standalone_trade_receivables_crore":round(annual_net_rcv,4),
            "FY25_standalone_trade_receivables_crore":round(old_net_rcv,4),
            "FY26_standalone_trade_receivables_growth_pct":round(
                pct(annual_net_rcv,old_net_rcv),2),
            "FY26_group_CFO_over_PAT_pct":round(100*annual_cfo_o/annual_profit_o,2),
            "FY26_unspent_IPO_cash_earmarked_crore":round(
                measure(o,"FY26_unspent_IPO_cash_earmarked_million")/10,4),
            "Q1FY27_PAT_yoy_pct":round(
                pct(q1profit_o,prior_q1profit_o),2),
            "Q1FY27_margin_vs_yearago_pp":round(
                measure(o,"Q1FY27_CONSOLIDATED_operating_margin_pct")-
                measure(o,"Q1FY26_CONSOLIDATED_operating_margin_pct"),2),
            "FY26_historical_E_P_multiple":round(cap_o/annual_profit_o,2),
            "Q1_annualised_PAT_multiple_HYPOTHETICAL_NOT_ESTIMATE":round(
                cap_o/q1_annualised_simple,2),
            "ten_pct_recovery_impairment_pretax_crore":round(
                annual_net_rcv*.1,4),
            "ten_pct_recovery_impairment_pct_cap":round(
                annual_net_rcv*.1/cap_o*100,2),
            "order_recognized_as_revenue":False,
            "real_earned_order_margin_and_parent_owner_cash":False,
            "opportunity_status":"NEW_ORDER_BUT_CASH_TRAP_RESEARCH_ONLY"
        }
    }


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,default=SOURCE)
    args=ap.parse_args()
    print(json.dumps(replay(json.loads(args.input.read_text(encoding="utf-8"))),
                     indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
