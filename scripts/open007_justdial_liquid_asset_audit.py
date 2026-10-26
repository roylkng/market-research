"""OPEN007: deterministic Just Dial liquid-asset and residual-franchise sensitivity.

This is retrospective company diligence, not an investment signal, expected
return, buy order or modification to any frozen H002/H003/HG009 study.
Cashflow run rates and portfolio haircuts are illustrative, not forecasts.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN007_JUSTDIAL_CASH_BRIDGE_INPUT_20261026.json"
)


def numeric(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} invalid value")
    return result


def evaluate(p: dict) -> dict:
    if p["schema"] != "OPEN007-20261026-JUSTDIAL-LIQUID-ASSET-V1":
        raise ValueError("unsupported research schema")
    if p["status"] != "POST_HOC_SOURCE_DISCOVERY_NOT_INVESTMENT":
        raise ValueError("cannot promote a post-hoc search into a stock signal")
    if (p["symbol"], p["isin"]) != ("JUSTDIAL", "INE599M01018"):
        raise ValueError("identity mismatch")
    if p["as_of_date"] != "2026-10-26" or p["price_date"] != "2026-10-26":
        raise ValueError("quote or cutoff date is not source verified")
    if p["q2_date"] != "2026-09-30" or p["q2_filing_published"] != "2026-10-19":
        raise ValueError("interim balance-sheet cutoff altered")
    if not p["issuer_has_no_subsidiaries_per_q2_note"]:
        raise ValueError("standalone perimeter cannot be silently consolidated")
    if (p["original_exchange_pdf_bytes_archived"], p["original_pdf_sha256"],
            p["source_first_retrieved_utc"]) != (False, None, None):
        raise ValueError("cannot fabricate original-file custody")
    if (p["independently_verified_accessible_cash_crore"],
            p["normalized_parent_FCFE_crore"],
            p["intrinsic_value_per_share_inr"]) != (None, None, None):
        raise ValueError("unverified realizable cash or valuation")
    if p["no_H002_H003_HG009_retroactive_change"] is not True:
        raise ValueError("frozen investment experiments cannot be rewritten")
    if p["capital_authorized"] is not False:
        raise ValueError("stock purchase cannot be approved")
    if p["FY26_dividend"] != "NONE_DECLARED_AFTER_FY2014_15_UP_TO_FY2025_26":
        raise ValueError("historical no-dividend evidence changed")
    if p["current_portfolio_type"] != (
        "DEBT_MUTUAL_FUNDS_TAX_FREE_BONDS_FVTPL_LEVEL2_FY26_NOTE5"
    ):
        raise ValueError("portfolio instrument type is unverified")
    price = numeric(p["NSE_close_inr"], "price")
    shares = p["shares_outstanding_exact"]
    if isinstance(shares, bool) or not isinstance(shares, int) or shares != 85049032:
        raise ValueError("share denominator mismatch")
    if price <= 0 or p["unit_source"] != "INR_MILLION":
        raise ValueError("price/financial unit mismatch")

    market_cap_cr = shares * price / 10_000_000
    investments = numeric(p["current_investments_million"], "investments") / 10
    bank = numeric(p["bank_balances_other_million"], "bank balances") / 10
    cash = numeric(p["cash_equivalents_million"], "cash") / 10
    gross_liquid = investments + bank + cash
    assets = numeric(p["total_assets_million"], "total assets") / 10
    equity = numeric(p["total_equity_million"], "total equity") / 10
    if assets < equity or assets < gross_liquid:
        raise ValueError("invalid balance-sheet assets/equity relationship")
    all_book_liabilities = assets - equity
    deferred = numeric(p["deferred_revenue_crore"], "deferred revenue")
    if deferred > all_book_liabilities:
        raise ValueError("deferred revenue exceeds book liabilities")
    # The combined book liabilities already include deferred service obligations.
    # They are NOT subtracted a second time anywhere in this sensitivity.
    net_liquid_after_liabilities = gross_liquid - all_book_liabilities
    residual = market_cap_cr - net_liquid_after_liabilities

    q2_ebitda = numeric(p["Q2_operating_ebitda_crore"], "Q2 EBITDA")
    q2_prior = numeric(p["Q2_operating_ebitda_previous_year_crore"], "Q2 prior")
    q2_revenue = numeric(p["Q2_net_revenue_crore"], "Q2 revenue")
    q2_revenue_prior = numeric(p["Q2_net_revenue_previous_year_crore"], "prior rev")
    if min(q2_ebitda, q2_prior, q2_revenue, q2_revenue_prior) <= 0:
        raise ValueError("invalid nonpositive operating denominators")

    h1_cfo = numeric(p["H1_CFO_million"], "H1 CFO") / 10
    h1_prev_cfo = numeric(p["H1_previous_year_CFO_million"], "prior CFO") / 10
    h1_cash_uses = (
        numeric(p["H1_PPE_purchases_million"], "PPE")
        + numeric(p["H1_intangible_purchases_million"], "intangibles")
        + numeric(p["H1_lease_cash_million"], "lease")
    ) / 10
    h1_selected_cash = h1_cfo - h1_cash_uses
    if h1_prev_cfo <= 0 or h1_selected_cash <= 0:
        raise ValueError("cannot compute illustrative cash multiple")
    run_rate = h1_selected_cash * 2
    annual_cfo = numeric(p["FY26_CFO_million"], "FY26 CFO")
    prev_annual_cfo = numeric(p["FY25_CFO_million"], "FY25 CFO")
    if prev_annual_cfo <= 0:
        raise ValueError("invalid annual CFO comparison")

    expected_haircuts = [0, 0.05, 0.10, 0.15, 0.20]
    if p["portfolio_haircut_assumptions"] != expected_haircuts:
        raise ValueError("unauthorized sensitivity assumptions")
    cases = []
    for haircut in expected_haircuts:
        after_loss = gross_liquid * (1 - haircut) - all_book_liabilities
        stressed_residual = market_cap_cr - after_loss
        cases.append({
            "gross_portfolio_haircut_pct": round(haircut * 100, 2),
            "liquid_after_all_liabilities_cr": round(after_loss, 2),
            "residual_market_price_of_business_and_other_assets_cr": round(
                stressed_residual, 2
            ),
            "residual_to_annualized_Q2_ebitda_x": round(
                stressed_residual / (q2_ebitda * 4), 2
            ),
            "residual_to_annualized_selected_H1_cash_x": round(
                stressed_residual / run_rate, 2
            ),
            "forecast_probability": None,
            "capital_approved": False,
        })
    return {
        "symbol": p["symbol"],
        "source_date": p["q2_date"],
        "price_date": p["price_date"],
        "market_cap_exact_share_count_cr": round(market_cap_cr, 4),
        "gross_liquid_book_marks_cr": round(gross_liquid, 2),
        "all_reported_liabilities_book_cr": round(all_book_liabilities, 2),
        "liquid_after_all_reported_liabilities_cr": round(
            net_liquid_after_liabilities, 2
        ),
        "market_implied_residual_franchise_and_other_assets_cr": round(residual, 2),
        "gross_liquid_pct_market_cap": round(gross_liquid / market_cap_cr * 100, 2),
        "portfolio_markdown_to_remove_gross_cash_over_cap_pct": round(
            (gross_liquid - market_cap_cr) / gross_liquid * 100, 2
        ),
        "FY26_CFO_yoy_pct": round((annual_cfo / prev_annual_cfo - 1) * 100, 2),
        "H1_FY27_CFO_yoy_pct": round((h1_cfo / h1_prev_cfo - 1) * 100, 2),
        "Q2_revenue_yoy_pct": round(
            (q2_revenue / q2_revenue_prior - 1) * 100, 2
        ),
        "Q2_operating_EBITDA_yoy_pct": round(
            (q2_ebitda / q2_prior - 1) * 100, 2
        ),
        "illustrative_H1_cash_after_selected_ppe_intangible_lease_cr": round(
            h1_selected_cash, 2
        ),
        "illustrative_annualized_cash_run_rate_cr": round(run_rate, 2),
        "portfolio_stress_scenarios": cases,
        "deferred_revenue_is_not_double_subtracted": True,
        "issuer_minorities_do_not_exist_by_reported_standalone_scope": True,
        "asset_realization_to_minority_shareholders_verified": False,
        "capital_authorized": False,
        "recommendation": "HIGH_PRIORITY_RESEARCH_NO_BUY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text())), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
