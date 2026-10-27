"""OPEN009: source-period constrained Maharashtra Seamless cash and scheme audit.

This is NOT a prediction, buy signal, or a change to the immutable
HG009 selected/control panel. A demerger issues entitlement shares but is
expressly value neutral as disclosed. Income and portfolio figures are
source-derived as of March, not refreshed October marks.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DATA = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN009_MAHSEAMLES_CASH_DEMERGER_INPUT_20261027.json"
)


def positive(data: dict, key: str, *, allow_zero: bool = False) -> float:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be a number")
    n = float(value)
    if not math.isfinite(n) or n < 0 or (not allow_zero and n == 0):
        raise ValueError(f"{key} invalid financial input")
    return n


def analyze(d: dict) -> dict:
    if d["schema"] != "OPEN009-20261027-MAHSEAMLES-DEMGER-OWNER-CASH-v1":
        raise ValueError("protocol changed")
    if d["scope"] != "POSTHOC_INDEPENDENT_COMPANY_UNDERWRITING_NOT_HG009_ALPHA":
        raise ValueError("research cannot become retroactive HG009 alpha")
    if (d["research_date"], d["price_date"]) != ("2026-10-27", "2026-10-26"):
        raise ValueError("source chronology changed")
    i = d["identity"]
    if (i["symbol"], i["isin"], i["original_hg009_arm"]) != (
        "MAHSEAMLES", "INE271B01025", "SELECTED"
    ):
        raise ValueError("original issuer/experimental identity changed")
    shares = i["shares_at_2026_03_31"]
    if isinstance(shares, bool) or not isinstance(shares, int) or shares != 133999252:
        raise ValueError("actual issuer share denominator changed")
    if i["face_value_inr"] != 5:
        raise ValueError("actual face value should be INR five")
    control = d["controls"]
    if control != {
        "no_change_to_frozen_HG009_selection": True,
        "normalized_parent_owner_FCFE": None,
        "fully_proven_current_intrinsic_value": None,
        "investment_approved": False,
        "capital_authorized": False,
    }:
        raise ValueError("unsupported investment approval or normalized cash")
    evidence = d["source_evidence"]
    if evidence["original_FY26_audited_PDF_bytes_archived"] is not False or (
        evidence["original_FY26_audited_SHA256"] is not None
        or evidence["original_first_observed_UTC"] is not None
    ):
        raise ValueError("original raw custody has not been established")
    scheme = d["scheme"]
    if scheme["original_NSE_PDF"] != (
        "https://nsearchives.nseindia.com/corporate/"
        "MAHSEAMLES_07102026172556_MSLIntimationDemerger.pdf"
    ):
        raise ValueError("original exchange scheme source changed")
    if (scheme["announced"], scheme["appointed_date"]) != (
        "2026-10-07", "2026-10-01"
    ):
        raise ValueError("corporate scheme dates changed")
    if (scheme["MSTL_shares_per_5_MAHSEAMLES"],
        scheme["USL_shares_per_5_MAHSEAMLES"]) != (1, 1):
        raise ValueError("original demger ratios corrupted")
    for k in (
        "company_describes_share_exchange_as_value_neutral",
    ):
        if scheme[k] is not True:
            raise ValueError("value-neutral scheme semantics altered")
    for k in (
        "all_regulatory_NCLT_shareholder_creditor_approvals_received",
        "record_date_announced",
        "legal_effective_and_separate_listing_completed",
    ):
        if scheme[k] is not False:
            raise ValueError("unproven scheme finality asserted")
    turnover = sum(
        positive(scheme, name)
        for name in (
            "Mangaon_MSTL_FY26_operational_turnover_crore",
            "Narketpally_USL_FY26_operational_turnover_crore",
            "remaining_FY26_operational_turnover_crore",
        )
    )
    if turnover != scheme["original_schemed_turnover_total"] or turnover != 4671:
        raise ValueError("scheme business revenue allocation corrupted")

    source = d["fy26_consolidated"]
    if (source["period_end"], source["unit"]) != ("2026-03-31", "INR_CRORE"):
        raise ValueError("mixed accounting period or units")
    quote = positive(d["market"], "NSE_2026_10_26_close_inr")
    if d["market"]["market_price_source"] != (
        "https://eoddata.com/stockquote/NSE/MAHSEAMLES.htm"
    ):
        raise ValueError("quoted price lacks dated original source")
    cap = quote * shares / 10_000_000

    prior = positive(source, "prior_after_tax_CFO")
    cfo = positive(source, "after_tax_CFO")
    pre_wc = positive(source, "pre_working_capital_operating_cash")
    wc = sum(
        positive(source, key, allow_zero=True)
        for key in (
            "inventory_working_capital_release",
            "trade_receivable_working_capital_release",
            "payables_working_capital_release",
        )
    )
    tax = positive(source, "cash_tax_paid")
    if abs(pre_wc + wc - tax - cfo) > 0.00001:
        raise ValueError("original working-capital cash reconciliation failed")
    ppe = positive(source, "selected_PPE_cash_purchases")
    prior_ppe = positive(source, "prior_PPE_cash_purchases")
    pat = positive(source, "parent_attributable_PAT")
    eps = positive(source, "diluted_EPS_inr")
    if abs(pat / (shares / 10_000_000) - eps) > 0.01:
        raise ValueError("FY26 PAT/EPS/share-denominator source mismatch")
    dividend = positive(source, "dividend_paid_crore")
    if abs(dividend / (shares / 10_000_000) - 10) > 0.02:
        raise ValueError("actual cash dividend differs from INR 10/share")
    current_inv = positive(source, "current_investments")
    FVTPL = positive(source, "current_investments_at_FVTPL")
    if FVTPL > current_inv:
        raise ValueError("FVTPL investment greater than all investments")
    cash = (
        positive(source, "cash_equivalents") +
        positive(source, "other_current_bank_balances")
    )
    borrow = (
        positive(source, "gross_borrowing_noncurrent") +
        positive(source, "gross_borrowing_current")
    )
    gross_marked_assets = current_inv + cash
    net_assets_after_named_borrowing = gross_marked_assets - borrow
    if positive(source, "pledged_bonds_from_note_crore") >= current_inv:
        raise ValueError("pledged collateral not reconciled to portfolio")
    q1 = d["q1_FY27"]
    if q1["quarter_end"] != "2026-06-30":
        raise ValueError("Q1 period changed")
    if positive(q1, "previous_year_revenue") <= 0:
        raise ValueError("missing Q1 revenue comparator")

    assumptions = d["assumptions"]
    if assumptions != {
        "current_mark_to_market_current_FVTPL_portfolio_haircuts": [
            0, 0.10, 0.20, 0.30
        ],
        "stress_interpretation": "PORTFOLIO_MARK_ONLY_NOT_EQUITY_RETURN_FORECAST",
        "working_capital_normalization": "ZERO_FY26_POSITIVE_WORKING_CAPITAL_CHANGE_ONLY_AS_STRESS",
        "dividend_repeat_and_total_effective_demerger_uncertain": True,
    }:
        raise ValueError("stress contract changed")
    cases = []
    for factor in assumptions["current_mark_to_market_current_FVTPL_portfolio_haircuts"]:
        markdown = FVTPL * factor
        cases.append({
            "original_FVTPL_haircut_pct": round(factor * 100, 2),
            "loss_on_March_FVTPL_portfolio_crore": round(markdown, 2),
            "gross_current_marked_assets_after_haircut_less_borrowings_crore": round(
                net_assets_after_named_borrowing - markdown, 2
            ),
            "loss_as_pct_Oct26_equity_cap": round(markdown / cap * 100, 2),
            "interpreted_as_stock_price_forecast": False,
        })
    return {
        "symbol": "MAHSEAMLES",
        "as_of": d["research_date"],
        "market_price_date": d["price_date"],
        "market_cap_using_original_share_count_crore": round(cap, 4),
        "fy26_parent_PAT_crore": pat,
        "fy26_diluted_pe": round(quote / eps, 2),
        "dividend_paid_crore": dividend,
        "cash_dividend_inr_per_share": round(dividend / (shares / 10_000_000), 2),
        "historic_dividend_yield_pct": round(dividend / cap * 100, 2),
        "FY26_reported_CFO_after_selected_PPE_crore": round(cfo - ppe, 2),
        "FY26_working_capital_release_crore": round(wc, 2),
        "FY26_stress_excluding_positive_wc_release_after_selected_PPE_crore": round(
            pre_wc - tax - ppe, 2
        ),
        "FY25_CFO_after_selected_PPE_crore": round(prior - prior_ppe, 2),
        "FY26_reported_proxy_yield_pct": round((cfo - ppe) / cap * 100, 2),
        "FY26_working_capital_stress_proxy_yield_pct": round(
            (pre_wc - tax - ppe) / cap * 100, 2
        ),
        "March_current_investments_crore": current_inv,
        "March_FVTPL_portfolio_crore": FVTPL,
        "March_gross_current_assets_investments_cash_crore": round(
            gross_marked_assets, 2
        ),
        "March_marked_assets_less_named_borrowings_crore": round(
            net_assets_after_named_borrowing, 2
        ),
        "reported_at_least_pledged_bonds_crore": source["pledged_bonds_from_note_crore"],
        "Q1_FY27_revenue_YoY_pct": round(
            (positive(q1, "revenue_from_operations") /
             positive(q1, "previous_year_revenue") - 1) * 100, 2
        ),
        "scheme_splits_existing_economic_rights_three_ways": True,
        "scheme_effective_confirmed": False,
        "scheme_creates_free_additional_value": False,
        "investment_market_mark_sensitivities": cases,
        "owner_distributable_cash_verified": False,
        "capital_authorized": False,
        "recommendation": "RESEARCH_ONLY_NO_BUY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DATA)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.input.read_text())), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
