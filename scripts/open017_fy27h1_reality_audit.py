"""OPEN017: reproduce November 2026 issuer-accounting decision tests.

Four issuer snapshots. This is post-hoc research, not the frozen HG009
or H002/H003 prospective signal/return panel and NEVER a trade engine.
Inputs are observed original NSE XBRL or transcribed signed issuer filings.
No original PDF-byte custody, calibrated probabilities or owner FCFE claimed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FILE = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN017_FY27H1_EARNINGS_CASH_REALITY_20261106.json"
)


def cash(row: dict, field: str, *, allow_negative: bool = False) -> float:
    value = row[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric original evidence")
    numeric = float(value)
    if not math.isfinite(numeric) or (not allow_negative and numeric < 0):
        raise ValueError(f"{field} must be finite and correctly signed")
    return numeric


def r(value: float, places: int = 2) -> float:
    return round(value, places)


def evaluate(d: dict) -> dict:
    if d["schema"] != "OPEN017-20261106-FY27H1-ISSUER-REALITY-v1":
        raise ValueError("research schema changed")
    if (d["observed_as_of"], d["latest_completed_NSE_session"]) != (
        "2026-11-06", "2026-11-05"
    ):
        raise ValueError("as-of/source quote chronology changed")
    if d["study_type"] != "POST_HOC_COMPANY_FUNDAMENTAL_REVIEW_NO_ALPHA_PROMOTION":
        raise ValueError("post-hoc research cannot be prospective alpha")
    if (
        d["original_source_bytes_archived_in_this_change"] is not False
        or d["source_first_retrieved_utc"] is not None
        or d["latest_quotes_are_not_executable_bid_ask"] is not True
    ):
        raise ValueError("original-byte custody or execution proof fabricated")
    if d["guard"] != {
        "original_H002_H003_HG009_signal_identity_and_outcomes_unchanged": True,
        "prospective_alpha_validated": False,
        "independently_underwritten_parent_owner_cash_cases": 0,
        "investments_authorized": 0,
        "unconditional_price_targets_permitted": False,
    }:
        raise ValueError("investment or retrospective alpha promotion forbidden")

    b = d["BLS"]
    if b["isin"] != "INE153T01027" or b["period_end"] != "2026-09-30":
        raise ValueError("BLS identity/financial period")
    if b["source_financial_transcription"] != (
        "https://financialfilings.com/filings/"
        "bls-international-services-ltd/earnings-release/2026/75412654/"
    ):
        raise ValueError("BLS signed source reference changed")
    shares_b = cash(b, "shares_crore_from_reported_paid_up_FV1")
    price_b = cash(b, "NSE_2026_11_05_close")
    if shares_b != 41.1741 or price_b <= 0:
        raise ValueError("BLS issuer shares or quote")
    if abs(
        cash(b, "H1_FY27_parent_PAT_crore")
        + cash(b, "H1_FY27_NCI_PAT_crore")
        - cash(b, "H1_FY27_group_PAT_crore")
    ) > 0.000001:
        raise ValueError("BLS noncontrolling PAT was mistaken for parent")
    b_cap = price_b * shares_b
    b_trailing_pat = (
        cash(b, "FY26_parent_PAT_crore")
        + cash(b, "H1_FY27_parent_PAT_crore")
        - cash(b, "H1_FY26_parent_PAT_crore")
    )
    if b_trailing_pat <= 0:
        raise ValueError("BLS trailing shareholder earnings invalid")
    def bls_selected(horizon: str) -> float:
        return (
            cash(b, f"H1_{horizon}_after_tax_group_CFO_crore")
            - cash(b, f"H1_{horizon}_PPE_intangible_CWIP_cash_crore")
            - cash(b, f"H1_{horizon}_lease_principal_crore")
            - cash(b, f"H1_{horizon}_lease_interest_crore")
            - cash(b, f"H1_{horizon}_finance_interest_paid_crore")
        )

    b_cash = bls_selected("FY27")
    b_cash_prev = bls_selected("FY26")
    if b_cash_prev <= 0:
        raise ValueError("BLS comparative cash denominator invalid")
    b_after_acquisitions = (
        b_cash - cash(b, "H1_FY27_net_cash_business_acquisition_crore")
        - cash(b, "H1_FY27_additional_subsidiary_shares_cash_crore")
    )
    b_parent = (
        cash(b, "H1_FY27_parent_standalone_CFO_crore")
        + cash(b, "H1_FY27_parent_standalone_received_subsidiary_dividends_crore")
        - cash(b, "H1_FY27_parent_standalone_PPE_intangible_CWIP_cash_crore")
        - cash(b, "H1_FY27_parent_standalone_lease_principal_crore")
        - cash(b, "H1_FY27_parent_standalone_lease_interest_crore")
    )
    if b["source_status"] != "ISSUER_SIGNED_RESULT_THIRD_PARTY_TRANSCRIPT_NO_CANONICAL_RAW_SHA":
        raise ValueError("BLS observation tier promoted")

    m = d["INDIAMART"]
    if m["isin"] != "INE933S01016" or m["period_end"] != "2026-09-30":
        raise ValueError("IndiaMART identity or period altered")
    if m["supplier_net_change_method"] != (
        "EXACT_MANAGEMENT_CONCALL_SECONDARY_TRANSCRIPT_NOT_ORIGINAL_BYTE_CONFIRMED"
    ):
        raise ValueError("IndiaMART subscriber evidence upgraded without proof")
    if m["Q2_exact_net_paying_supplier_change_from_concall"] != -615:
        raise ValueError("IndiaMART exact supplier net churn unverified")
    if (
        cash(m, "Q2_FY27_paying_suppliers_approx")
        != 217000
        or cash(m, "Q1_FY27_paying_suppliers_approx") != 218000
    ):
        raise ValueError("IndiaMART rounded subscriber count changed")
    price_m = cash(m, "NSE_2026_11_05_close")
    if price_m <= 0:
        raise ValueError("unverified IndiaMART quote")
    m_cfo = cash(m, "Q2_FY27_group_CFO_crore")
    m_prior_cfo = cash(m, "Q1_FY27_group_CFO_crore")
    if m_prior_cfo <= 0:
        raise ValueError("IndiaMART CFO denominator")
    m_assets_change = (
        cash(m, "Q2_FY27_group_cash_investments_crore")
        - cash(m, "Q1_FY27_group_cash_investments_crore")
    )
    m_price_market_cap = cash(m, "mcap_crore_quote_provider")
    if m_price_market_cap <= 0:
        raise ValueError("IndiaMART cap absent")
    if not m["source_company_signed_press_release_transcription"].startswith(
        "https://financialfilings.com/filings/indiamart-intermesh-limited/"
    ):
        raise ValueError("IndiaMART issuer press evidence absent")

    c = d["CENTENKA"]
    if c["isin"] != "INE485A01015" or c["period_end"] != "2026-09-30":
        raise ValueError("Century Enka ISIN/quarter altered")
    if c["NSE_official_consolidated_xbrl"] != (
        "https://nsearchives.nseindia.com/corporate/ixbrl/"
        "INTEGRATED_FILING_INDAS_205164_27102026211808_iXBRL_WEB.html"
    ):
        raise ValueError("Century Enka original NSE source absent")
    if c["unit"] != "INR_LAKH":
        raise ValueError("Century Enka INR lakh units wrong")
    shares_c = cash(c, "paid_up_equity_share_capital_lakh") / (
        cash(c, "share_face_value_INR") * 100
    )
    price_c = cash(c, "NSE_2026_11_05_close")
    if min(price_c, shares_c) <= 0 or shares_c != 2.185:
        raise ValueError("Century Enka share count/quote")
    c_cfo = cash(c, "H1_FY27_group_after_tax_CFO_lakh", allow_negative=True) / 100
    c_ppe = cash(c, "H1_FY27_group_PPE_cash_purchase_lakh") / 100
    c_q2pat = cash(c, "Q2_FY27_group_profit_lakh") / 100
    c_h1pat = cash(c, "H1_FY27_group_profit_lakh") / 100
    if c_h1pat <= c_q2pat:
        raise ValueError("Century Enka Q1/Q2 PAT period mix")
    c_book = cash(c, "fy26_stale_book_equity_crore")
    if c_book <= 0:
        raise ValueError("Century Enka book source absent")

    a = d["ACUTAAS"]
    if a["isin"] != "INE00FF01025" or a["period_end"] != "2026-09-30":
        raise ValueError("Acutaas issuer or period")
    if a["NSE_official_consolidated_xbrl"] != (
        "https://nsearchives.nseindia.com/corporate/ixbrl/"
        "INTEGRATED_FILING_INDAS_205014_27102026184220_iXBRL_WEB.html"
    ):
        raise ValueError("Acutaas original NSE source absent")
    if a["unit"] != "INR_LAKH":
        raise ValueError("Acutaas unit mismatch")
    a_shares = cash(a, "paid_up_equity_share_capital_lakh") / (
        cash(a, "share_face_value_INR") * 100
    )
    if abs(a_shares - 8.18712) > 0.0000001:
        raise ValueError("Acutaas issued share count differs from source")
    price_a = cash(a, "NSE_2026_11_05_close")
    cap_a = a_shares * price_a
    group_pat_a = cash(a, "H1_FY27_group_PAT_lakh") / 100
    parent_pat_a = cash(a, "H1_FY27_parent_attributable_PAT_lakh") / 100
    nci_a = cash(a, "H1_FY27_noncontrolling_PAT_lakh", allow_negative=True) / 100
    if abs(group_pat_a - parent_pat_a - nci_a) > 0.000001:
        raise ValueError("Acutaas parent/NCI earnings attribution mismatch")
    group_cfo_a = cash(a, "H1_FY27_group_after_tax_CFO_lakh") / 100
    group_ppe_a = cash(a, "H1_FY27_group_PPE_cash_purchase_lakh") / 100
    years = a["conditional_earnings_multiple_horizon_years"]
    exit_pe = cash(a, "conditional_terminal_PE_multiple")
    if years != 3 or exit_pe != 35 or a["conditional_annualized_baseline"] != (
        "H1_FY27_PARENT_PAT_TIMES_TWO_NO_CYCLICAL_NORMALIZATION"
    ):
        raise ValueError("unapproved terminal P/E scenario or source basis")
    baseline_a = 2 * parent_pat_a
    if baseline_a <= 0:
        raise ValueError("Acutaas cannot extrapolate negative PAT")
    runrate_pe_a = cap_a / baseline_a
    break_even_growth = (runrate_pe_a / exit_pe) ** (1 / years) - 1
    required_growth_for_15pct_cagr = (
        (runrate_pe_a * 1.15**years / exit_pe) ** (1 / years) - 1
    )
    return {
        "snapshot_as_of": d["observed_as_of"],
        "source_date_end": "2026-09-30",
        "last_quote_day": d["latest_completed_NSE_session"],
        "capital_approved": False,
        "prospective_alpha_validated": False,
        "owner_cash_verified_cases": 0,
        "BLS": {
            "FY27_Q2_revenue_growth_yoy_pct": r(
                (cash(b, "Q2_FY27_revenue_crore") /
                 cash(b, "Q2_FY26_revenue_crore") - 1) * 100
            ),
            "Q2_EBITDA_margin_change_pp": r(
                cash(b, "Q2_FY27_EBITDA_margin_pct")
                - cash(b, "Q2_FY26_EBITDA_margin_pct")
            ),
            "H1_group_CFO_growth_pct": r(
                (cash(b, "H1_FY27_after_tax_group_CFO_crore") /
                 cash(b, "H1_FY26_after_tax_group_CFO_crore") - 1) * 100
            ),
            "H1_cash_after_selected_capex_leases_interest_cr": r(b_cash, 4),
            "H1_prior_cash_after_selected_capex_leases_interest_cr": r(b_cash_prev, 4),
            "H1_selected_cash_change_pct": r((b_cash / b_cash_prev - 1) * 100),
            "H1_cash_after_additional_acquisitions_cr": r(b_after_acquisitions, 4),
            "standalone_parent_cash_after_selected_including_sub_dividends_cr": r(
                b_parent, 4
            ),
            "standalone_dividend_eliminated_on_group_consolidation": True,
            "trailing_parent_PAT_cr": r(b_trailing_pat, 4),
            "price_to_trailing_parent_PAT_x": r(b_cap / b_trailing_pat),
            "source_underwritten_owner_FCFE_cr": None,
            "investment_decision": "CONTRACT_ACQUISITION_CASH_RESEARCH_ONLY",
        },
        "INDIAMART": {
            "current_approx_paying_suppliers": 217000,
            "management_reported_net_supplier_change": -615,
            "Q2_cash_vs_Q1_change_pct": r((m_cfo / m_prior_cfo - 1) * 100),
            "cash_investments_QoQ_change_cr": m_assets_change,
            "reported_cash_investments_not_owner_cash": True,
            "Q2_reported_group_PAT_cr": cash(m, "quarterly_pat_group_crore"),
            "shareholder_cash_discount_model_verified": False,
            "investment_decision": "SUBSCRIBER_CHURN_BLOCKED",
        },
        "CENTENKA": {
            "H1_operating_cash_cr": r(c_cfo),
            "H1_PPE_cash_cr": r(c_ppe),
            "H1_CFO_less_selected_PPE_cr": r(c_cfo - c_ppe),
            "Q2_PAT_cr": r(c_q2pat),
            "Q1_PAT_implied_cr": r(c_h1pat - c_q2pat),
            "price_to_PRIOR_YEAR_book_x": r(shares_c * price_c / c_book, 3),
            "book_discount_not_equivalent_to_equity_valuation": True,
            "investment_decision": "NEGATIVE_H1_CASH",
        },
        "ACUTAAS": {
            "H1_parent_PAT_cr": r(parent_pat_a, 4),
            "H1_group_CFO_cr": r(group_cfo_a, 4),
            "H1_PPE_cash_cr": r(group_ppe_a, 4),
            "H1_CFO_less_PPE_cr_not_FCFE": r(group_cfo_a - group_ppe_a, 4),
            "H1_cash_after_PPE_as_pct_current_cap": r(
                (group_cfo_a - group_ppe_a) / cap_a * 100
            ),
            "annualized_H1_parent_PAT_cr_NOT_FORECAST": r(baseline_a, 4),
            "implied_quasi_PE_using_annualized_H1_parent_PAT": r(runrate_pe_a, 2),
            "earnings_CAGR_3yr_for_flat_share_value_at_35x_exit_pct": r(
                break_even_growth * 100, 2
            ),
            "earnings_CAGR_3yr_for_15pct_price_CAGR_at_35x_exit_pct": r(
                required_growth_for_15pct_cagr * 100, 2
            ),
            "scenario_probability": None,
            "investment_decision": "GROWTH_PRICED_IN_NOT_BUY",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=FILE)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(data), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
