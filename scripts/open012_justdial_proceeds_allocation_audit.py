"""OPEN012: Just Dial 2021 equity-use-of-proceeds vs alleged excess-cash valuation.

A direct company annual-report disclosure reports Reliance's 2021 paid-in
capital as temporarily invested pending intended use. This is not a
legally restricted debt claim. Each hypothetical funding reservation is
a zero-probability-free SENSITIVITY, not the actual remaining balance.
Original OPEN007 issuer facts are pinned to their Git blob.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = (
    ROOT / "research/broad-discovery/OPEN012_JUSTDIAL_PREFERENTIAL_CAPITAL_INPUT_20261027.json"
)
BASE = (
    ROOT / "research/broad-discovery/OPEN007_JUSTDIAL_CASH_BRIDGE_INPUT_20261026.json"
)


def finite(v: object, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{name}: expected a financial number")
    result = float(v)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name}: invalid financial amount")
    return result


def baseline(d: dict) -> dict:
    if d["source_baseline_path"] != (
        "research/broad-discovery/OPEN007_JUSTDIAL_CASH_BRIDGE_INPUT_20261026.json"
    ):
        raise ValueError("opening source identity mutated")
    raw = BASE.read_bytes()
    sha = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()
    if sha != d["source_baseline_git_blob_sha"] or sha != (
        "f0650a9c6dac7c22db3432634812e7119c7899a4"
    ):
        raise ValueError("original source blob SHA changed")
    p = json.loads(raw)
    if (p["schema"], p["symbol"], p["isin"]) != (
        "OPEN007-20261026-JUSTDIAL-LIQUID-ASSET-V1",
        "JUSTDIAL", "INE599M01018"
    ):
        raise ValueError("OPEN007 original issuer mismatch")
    if (
        p["q2_date"] != "2026-09-30"
        or p["price_date"] != "2026-10-26"
        or p["unit_source"] != "INR_MILLION"
        or p["capital_authorized"] is not False
        or p["independently_verified_accessible_cash_crore"] is not None
    ):
        raise ValueError("cannot reinterpret original price, unit or permissions")
    return p


def audit(d: dict) -> dict:
    if d["schema"] != "OPEN012-20261027-JUSTDIAL-USE_OF_PROCEEDS_STRESS_V1":
        raise ValueError("source version mismatch")
    if d["record_date"] != "2026-10-27":
        raise ValueError("new discovery date changed")
    if d["reason"] != "RESEARCH_ONLY_FALSIFY_IMMEDIATE_DISTRIBUTABLE_SURPLUS":
        raise ValueError("an invalid trade or prospective objective")
    if (d["source_company"], d["source_isin"]) != (
        "JUSTDIAL", "INE599M01018"
    ):
        raise ValueError("company identity changed")
    limits = d["research_limits"]
    if limits != {
        "no_verified_FY27_unused_preferential_proceeds_balance": True,
        "no_legal_cash_encumbrance_or_liability_inferred": True,
        "no_operating_business_intrinsic_value_estimated": True,
        "no_price_target_or_probabilities": True,
        "no_live_capital": True,
        "no_frozen_H002_H003_HG009_changes": True,
    }:
        raise ValueError("false cash permission, legal restriction or capital gate")
    custody = d["source_custody"]
    if custody != {
        "reliance_2021_original_pdf_visually_checked": True,
        "annual_report_2026_source_text_inspected": True,
        "annual_2026_pdf_raw_bytes_in_git": False,
        "annual_2026_report_first_seen_utc": None,
        "reliance_2021_pdf_sha256_in_git": None,
    }:
        raise ValueError("missing inspection or fabricated source custody")
    fund = d["source_2021_raise"]
    if (
        fund["original_reliance_exchange_pdf"]
        != "https://nsearchives.nseindia.com/corporate/UFR22102021_22102021201739.pdf"
        or fund["original_reliance_pdf_page_index"] != 11
        or fund["source_issuer_FY26_annual_report"]
        != "https://financialfilings.com/filings/just-dial-limited/annual-report/2026/52832446/"
        or fund["transaction_date"] != "2021-09-01"
    ):
        raise ValueError("2021 original source and timing changed")
    if (
        fund["fy26_company_says_funds_pending_utilization_in_funds_or_deposits"] is not True
        or fund["fy26_company_says_no_deviation_from_original_objects"] is not True
        or fund["FY26_original_objects_detailed_text_independently_acquired"] is not False
        or fund["FY27_September_actual_unused_balance_evidenced_in_rupees"] is not None
        or fund["cash_earmarked_legally_restricted_verified"] is not False
    ):
        raise ValueError("unsupported legally frozen FY27 capital conclusion")
    issued = fund["historical_injected_equity_shares"]
    if isinstance(issued, bool) or not isinstance(issued, int) or issued != 21177636:
        raise ValueError("2021 original transaction share count changed")
    issue_price = finite(fund["per_share_subscription_price_inr"], "allotment price")
    original_raise = finite(fund["historical_injection_crore_reported"], "2021 raise")
    if abs(issued * issue_price / 1e7 - original_raise) > 0.01:
        raise ValueError("original issue shares times price mismatch")

    p = baseline(d)
    f = d["accounting"]
    shares = f["issuer_reported_shares_exact"]
    if isinstance(shares, bool) or not isinstance(shares, int) or shares != p["shares_outstanding_exact"]:
        raise ValueError("Q2 share denominator changed")
    price = finite(f["NSE_October26_close_inr"], "October 26 price")
    market = shares * price / 1e7
    if abs(price - p["NSE_close_inr"]) > 0.00001:
        raise ValueError("source share-price drift")
    liquid = sum(
        finite(p[name], name)
        for name in (
            "current_investments_million", "bank_balances_other_million",
            "cash_equivalents_million",
        )
    ) / 10
    liabilities = (
        finite(p["total_assets_million"], "assets")
        - finite(p["total_equity_million"], "equity")
    ) / 10
    if liabilities < 0:
        raise ValueError("invalid balance-sheet liabilities")
    if (
        abs(finite(f["September_30_balance_sheet_current_investments_bank_cash_crore"], "liquid")-liquid) > 0.00001
        or abs(finite(f["September_30_all_reported_book_liabilities_crore"], "claims")-liabilities) > 0.00001
        or abs(finite(f["Q2_reported_operating_EBITDA_crore"], "EBITDA") - p["Q2_operating_ebitda_crore"]) > 0.00001
    ):
        raise ValueError("cannot change original September financial values")
    cash = finite(f["H1_mechanical_selected_cash_crore"], "selected cash")
    if cash != 95.34:
        raise ValueError("half-year illustrative cash flow mutated")
    other = finite(f["Q2_other_income_crore"], "treasury income")
    op_pbt = finite(f["Q2_operating_PBT_crore"], "operating pre-tax income")
    total = finite(f["Q2_total_PBT_crore"], "total pretax profit")
    if abs(op_pbt + other - total) > 0.00001:
        raise ValueError("treasury income is part of PBT, not added on top")
    if not f["all_reported_liabilities_include_deferred_revenue_and_lease_liabilities"]:
        raise ValueError("all liabilities must be counted once")
    if not f["Q1Q2_qtr_income_is_not_equivalent_to_franchise_EBITDA"]:
        raise ValueError("cannot add treasury PBT to business EBITDA")
    net_liquid = liquid - liabilities
    if net_liquid <= 0 or net_liquid < original_raise:
        raise ValueError("historical raise exceeds this illustrative asset cap")
    sensitivity = d["hypothetical_scenarios"]
    if sensitivity != {
        "fraction_historical_raise_not_treated_as_immediately_distributable": [0,0.25,0.5,0.75,1],
        "interpretation": "CONDITIONAL_CAPITAL_DEPLOYMENT_REQUIREMENT_NOT_EVIDENCED_FY27_BALANCE",
        "no_proceeds_ever_deducted_as_financial_debt": True,
    }:
        raise ValueError("unsupported cash earmark sensitivity")
    illustrative_EBITDA_annualized = p["Q2_operating_ebitda_crore"] * 4
    rows = []
    for f in sensitivity["fraction_historical_raise_not_treated_as_immediately_distributable"]:
        assumed_committed = original_raise * f
        amount_potentially_releasable = net_liquid - assumed_committed
        residual = market - amount_potentially_releasable
        rows.append({
            "hypothetical_fraction_of_2021_raise_deployed_elsewhere_pct": round(100*f,2),
            "illustrative_2021_raise_excluded_from_immediate_distribution_crore": round(assumed_committed,2),
            "net_book_liquidity_available_after_hypothetical_allocation_crore": round(amount_potentially_releasable,2),
            "market_residual_business_PLUS_committed_growth_capital_crore": round(residual,2),
            "market_residual_to_annualized_Q2_operating_EBITDA_x": round(residual/illustrative_EBITDA_annualized,2),
            "market_residual_to_twice_H1_selected_cash_x": round(residual/(2*cash),2),
            "legally_restricted_amount_proven": False,
            "is_equity_price_target": False,
        })
    return {
        "name": "JUSTDIAL",
        "as_of": d["record_date"],
        "price_date": p["price_date"],
        "original_2021_injection_crore": original_raise,
        "original_issue_share_count": issued,
        "current_net_book_liquid_after_all_liabilities_crore": round(net_liquid,2),
        "october_26_market_cap_crore": round(market,4),
        "annual_report_does_not_independently_verify_current_2026_09_remaining_balance": True,
        "declared_legally_cash_restricted_amount_crore": None,
        "Q2_other_income_as_pct_total_PBT": round(100*other/total,2),
        "FY26_group_shareholder_dividend_history":"NO_DIVIDEND_AFTER_FY2014_15_TO_FY2025_26",
        "sensitivity_not_a_share_price_or_fair_value_forecast": rows,
        "normalized_parent_owner_cash_crore": None,
        "intrinsic_value_per_share_inr": None,
        "approved_capital": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.input.read_text(encoding="utf-8"))),
                     indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
