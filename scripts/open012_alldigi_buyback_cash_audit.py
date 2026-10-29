"""OPEN012 original-issuer Oct 29 buyback: cash, ownership and causal-clock audit.

This model is NOT an actionable tender arbitrage, recommendation, capital order,
or prediction. Board terms were released AFTER the 15:29 observed share price.
Only future fully signed approval/letter and post-event executable quotes could
make any investment decision implementable.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN012_ALLDIGI_BUYBACK_CASH_INPUT_20261029.json"
)


def numeric(value: object, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{key} invalid amount")
    return result


def verify(packet: dict) -> dict:
    if packet["schema"] != "OPEN012-20261029-ALLDIGI-POSTCLOSE-CORPORATE-DECISION-V1":
        raise ValueError("original source protocol altered")
    if packet["scope"] != "ISSUER_ORIGINAL_SOURCE_POSTHOC_VALUATION_NO_INVESTMENT":
        raise ValueError("cannot relabel outcome as prospective alpha")
    issuer = packet["company"]
    if (issuer["symbol"], issuer["isin"], issuer["asof"]) != (
        "ALLDIGI", "INE835G01018", "2026-10-29"
    ):
        raise ValueError("original issuer identity or observation date changed")
    if (issuer["q2_statement_end"], issuer["finance_statement_units"]) != (
        "2026-09-30", "INR_LAKH"
    ):
        raise ValueError("source reporting period or units changed")
    if issuer["issuer_original_signed_pdf"] != (
        "https://www.alldigitech.com/wp-content/uploads/2026/10/"
        "SEFiling_BMOutcome_29102026.pdf"
    ):
        raise ValueError("signed issuer original lost")
    if issuer["issuer_original_pdf_pages"] != {
        "outcome": 0, "buyback_shareholding": 13,
        "consolidated_earnings": 8, "consolidated_balance": 9,
        "consolidated_cash": 10
    }:
        raise ValueError("visual audited page locators changed")

    observed = packet["observation"]
    if observed["quote_day"] != "2026-10-29" or (
        observed["quote_provider"]
        != "https://dhan.co/stocks/allsec-technologies-ltd-share-price/"
    ):
        raise ValueError("unverifiable quoted market price")
    quote_time = datetime.fromisoformat(observed["quote_observation_IST"])
    board_end = datetime.fromisoformat(observed["meeting_concluded_IST"])
    if quote_time.tzinfo is None or board_end.tzinfo is None:
        raise ValueError("missing observation timezone")
    if quote_time >= board_end or (
        board_end != datetime.fromisoformat("2026-10-29T17:35:00+05:30")
    ):
        raise ValueError("cannot execute a newly priced buyback before disclosure")
    if (observed["quote_is_after_completed_board_buyback_price_disclosure"] is not False
        or observed["actual_original_publication_UTC"] is not None
        or observed["official_NSE_postdisclosure_tradable_quote"] is not None):
        raise ValueError("unobserved postdisclosure quote or event clock fabricated")
    quote = numeric(observed["delayed_quote_inr"], "quote")
    if quote <= 0:
        raise ValueError("invalid price")

    b = packet["buyback"]
    if b["board_approval_date"] != "2026-10-29" or (
        b["offer_method"] != "TENDER_PROPORTIONATE_NOT_OPEN_MARKET"
        or b["source_is_approved_board_decision_not_just_agenda"] is not True
    ):
        raise ValueError("buyback source decision/route altered")
    shares = b["issuer_existing_shares_at_2026_09_30"]
    promoter_shares = b["issuer_pre_buyback_promoter_shares"]
    maxshares = b["max_shares"]
    if any(
        isinstance(x, bool) or not isinstance(x, int)
        for x in (shares, promoter_shares, maxshares)
    ):
        raise TypeError("share counts must be exact integers")
    if (shares, promoter_shares, maxshares) != (15238326, 11182912, 480000):
        raise ValueError("original company share/repurchase denominator changed")
    offer = numeric(b["price_inr"], "offer price")
    cap_cr = numeric(b["max_gross_crore"], "cap")
    if offer != 1000 or cap_cr != 48 or (
        abs(maxshares * offer / 10_000_000 - cap_cr) > 1e-7
    ):
        raise ValueError("published authorized cash cap and repurchase count diverge")
    if b["promoter_explicit_intention_to_participate"] is not True:
        raise ValueError("promoter intention missing")
    if any(
        b[k] is not False for k in (
            "shareholder_special_resolution_approved", "record_date_set",
            "letter_of_offer_published", "offer_completed",
            "allocation_results_known"
        )
    ):
        raise ValueError("legal effectiveness or acceptance not yet proved")
    custody = packet["evidence_custody"]
    if custody != {
        "signed_original_public_issuer_PDF_visually_reviewed": True,
        "pdf_first_observed_UTC": None,
        "original_raw_bytes_in_repository": False,
        "pdf_sha256_archive": None,
    }:
        raise ValueError("unsupported source file custody asserted")
    controls = packet["controls"]
    if controls != {
        "h002_h003_hg009_original_decisions_unchanged": True,
        "company_eligible_for_live_investment": False,
        "issuer_sustainable_parent_owner_FCFE_crore": None,
        "profit_catalyst_calibrated_probabilities": None,
        "trading_order_created": False,
    }:
        raise ValueError("trade/forecast or trial promotion forbidden")

    h1 = packet["h1_group"]
    fields = (
        "CFO_2026_lakh", "CFO_2025_lakh",
        "PPE_intangible_CWIP_cash_2026_lakh",
        "PPE_intangible_CWIP_cash_2025_lakh",
        "lease_principal_paid_2026_lakh",
        "lease_principal_paid_2025_lakh",
        "lease_interest_paid_2026_lakh",
        "lease_interest_paid_2025_lakh",
        "shareholder_cash_dividends_paid_2026_lakh",
        "shareholder_cash_dividends_paid_2025_lakh",
        "cash_equivalents_sep2026_lakh",
        "current_investments_sep2026_lakh",
        "other_bank_balances_sep2026_lakh",
        "noncurrent_lease_liabilities_sep2026_lakh",
        "current_lease_liabilities_sep2026_lakh",
        "reported_total_book_liabilities_sep2026_lakh",
        "reported_total_book_equity_sep2026_lakh",
        "Q2_group_revenue_sep2026_lakh", "Q2_group_revenue_sep2025_lakh",
        "Q2_group_PAT_sep2026_lakh", "Q2_group_PAT_sep2025_lakh",
        "FY27H1_group_PAT_lakh",
        "FY27H1_standalone_parent_dividend_from_Philippines_sub_lakh"
    )
    for field in fields:
        numeric(h1[field], field)
    if h1["FY27H1_standalone_parent_dividend_from_Philippines_sub_lakh"] != 1847:
        raise ValueError("standalone subsidiary cash cannot be added to consolidated")
    latest_operating = h1["CFO_2026_lakh"]/100
    prev_operating = h1["CFO_2025_lakh"]/100
    current_after = (
        h1["CFO_2026_lakh"]
        - h1["PPE_intangible_CWIP_cash_2026_lakh"]
        - h1["lease_principal_paid_2026_lakh"]
        - h1["lease_interest_paid_2026_lakh"]
    ) / 100
    previous_after = (
        h1["CFO_2025_lakh"]
        - h1["PPE_intangible_CWIP_cash_2025_lakh"]
        - h1["lease_principal_paid_2025_lakh"]
        - h1["lease_interest_paid_2025_lakh"]
    ) / 100
    dividends = h1["shareholder_cash_dividends_paid_2026_lakh"] / 100
    cashlike = sum(
        h1[k] for k in (
            "cash_equivalents_sep2026_lakh",
            "current_investments_sep2026_lakh",
            "other_bank_balances_sep2026_lakh"
        )
    ) / 100
    lease_obligations = (
        h1["noncurrent_lease_liabilities_sep2026_lakh"]
        + h1["current_lease_liabilities_sep2026_lakh"]
    ) / 100
    equitycap = shares * quote / 10_000_000
    original_premium = offer / quote - 1
    fraction = maxshares / shares
    if packet["scenarios"] != {
        "historical_shareholder_tender_acceptance_fraction": [
            0, 0.01, 0.0315, 0.05, 0.10
        ],
        "interpretation": "GROSS_SENSITIVITY_NOT_AFTERCOST_RETURN_OR_FILLED_TENDER",
        "postdisclosure_share_price_unknown": True,
        "underlying_equity_after_payout_price_unknown": True,
    }:
        raise ValueError("acceptance probabilities cannot be invented")
    scenarios = []
    for rate in packet["scenarios"]["historical_shareholder_tender_acceptance_fraction"]:
        scenarios.append({
            "hypothetical_share_acceptance_pct": round(rate * 100, 2),
            "gross_accepted_share_offer_premium_effect_pct": round(
                rate * original_premium * 100, 4
            ),
            "is_total_portfolio_return": False,
            "afterclose_buy_available_at_observed_quote": False,
            "probability": None,
        })
    return {
        "schema": packet["schema"],
        "as_of": issuer["asof"],
        "issuer_exact_shares": shares,
        "promoter_percentage": round(promoter_shares / shares * 100, 4),
        "market_equity_at_preannouncement_quote_crore": round(equitycap, 4),
        "board_buyback_max_gross_crore": cap_cr,
        "maximum_buyback_fraction_pct": round(fraction * 100, 4),
        "nominal_offer_premium_to_earlier_quote_pct": round(original_premium * 100, 2),
        "buyback_size_to_earlier_market_cap_pct": round(cap_cr / equitycap * 100, 2),
        "new_approved_board_price_available_for_executable_trade_at_prior_quote": False,
        "shareholder_approval_pending": True,
        "record_date_unpublished": True,
        "H1_FY27_consolidated_after_tax_CFO_crore": latest_operating,
        "H1_FY26_consolidated_after_tax_CFO_crore": prev_operating,
        "H1_CFO_growth_pct": round(
            (latest_operating / prev_operating - 1) * 100, 2
        ),
        "H1_FY27_cash_after_selected_PPE_lease_crore": round(current_after, 2),
        "H1_FY26_cash_after_selected_PPE_lease_crore": round(previous_after, 2),
        "H1_FY27_cash_dividend_paid_crore": dividends,
        "H1_cash_after_selected_PPE_lease_less_dividends_crore": round(
            current_after - dividends, 2
        ),
        "annualized_H1_selected_cash_yield_at_preannouncement_market_cap_pct": round(
            current_after * 2 / equitycap * 100, 2
        ),
        "consolidated_current_investments_cash_and_other_bank_crore": round(cashlike, 2),
        "consolidated_current_and_noncurrent_lease_liabilities_crore": round(
            lease_obligations, 2
        ),
        "financial_asset_marks_less_lease_claims_crore": round(
            cashlike - lease_obligations, 2
        ),
        "H1_group_net_PAT_crore": h1["FY27H1_group_PAT_lakh"] / 100,
        "Q2_revenue_yoy_pct": round(
            (h1["Q2_group_revenue_sep2026_lakh"] /
             h1["Q2_group_revenue_sep2025_lakh"] - 1) * 100, 2
        ),
        "Q2_group_PAT_yoy_pct": round(
            (h1["Q2_group_PAT_sep2026_lakh"] /
             h1["Q2_group_PAT_sep2025_lakh"] - 1) * 100, 2
        ),
        "hypothetical_gross_tender_sensitivities": scenarios,
        "parent_owner_cash_verified": False,
        "approved_investments": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=SOURCE)
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(args.input.read_text(encoding="utf-8"))),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
