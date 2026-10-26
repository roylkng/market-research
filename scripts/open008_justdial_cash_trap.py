"""OPEN008: Just Dial capital-retention stress, never an intrinsic-value forecast.

A holder of a tightly controlled, cash-heavy issuer can receive poor returns
even if the portfolio's accounting value exceeds gross equity value. Here
treasury and illustrative business cash are reinvested until the modeled exit.
All assumptions are hypothetical and no portfolio or trade is authorized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "research/broad-discovery/OPEN008_JUSTDIAL_CASH_TRAP_INPUT_20261026.json"


def positive_num(value: object, name: str, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise TypeError(f"{name} must be a number")
    v = float(value)
    if not math.isfinite(v) or (v < 0 if allow_zero else v <= 0):
        raise ValueError(f"{name} must be finite and positive")
    return v


def pinned_financials(meta: dict) -> tuple[float, float, float]:
    path = ROOT / meta["source_baseline_path"]
    if path.resolve() != (
        ROOT / "research/broad-discovery/OPEN007_JUSTDIAL_CASH_BRIDGE_INPUT_20261026.json"
    ).resolve():
        raise ValueError("original source file changed")
    raw = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\\0" + raw).hexdigest()
    if blob != meta["source_baseline_git_blob_sha"]:
        raise ValueError("original source Git blob SHA mismatched")
    p = json.loads(raw)
    if p["symbol"] != "JUSTDIAL" or p["isin"] != "INE599M01018":
        raise ValueError("issuer mismatch")
    if not p["issuer_has_no_subsidiaries_per_q2_note"]:
        raise ValueError("original source perimeter changed")
    shares = p["shares_outstanding_exact"]
    price = positive_num(p["NSE_close_inr"], "share price")
    if isinstance(shares, bool) or shares != 85049032:
        raise ValueError("original share denominator changed")
    market_cap = round(shares * price / 10_000_000, 4)
    gross_liquid = sum(
        positive_num(p[k], k)
        for k in ("current_investments_million", "bank_balances_other_million",
                  "cash_equivalents_million")
    ) / 10
    claims = (
        positive_num(p["total_assets_million"], "total assets")
        - positive_num(p["total_equity_million"], "book equity")
    ) / 10
    net_liquid = round(gross_liquid - claims, 2)
    annual_selected_cash = round(
        (positive_num(p["H1_CFO_million"], "half-year CFO")
         - positive_num(p["H1_PPE_purchases_million"], "PPE")
         - positive_num(p["H1_intangible_purchases_million"], "intangible")
         - positive_num(p["H1_lease_cash_million"], "lease")) / 10 * 2, 2
    )
    for key, obtained in (
        ("source_market_cap_crore", market_cap),
        ("source_net_liquid_after_all_book_liabilities_crore", net_liquid),
        ("source_illustrative_selected_operating_cash_run_rate_crore", annual_selected_cash),
    ):
        declared = positive_num(meta[key], key)
        if abs(declared - obtained) > 0.000001:
            raise ValueError(f"{key} inconsistent with original packet")
    return market_cap, net_liquid, annual_selected_cash


def evaluate(meta: dict) -> dict:
    if meta["schema"] != "OPEN008-20261026-JUSTDIAL-CAPITAL-ACCESS-V1":
        raise ValueError("wrong protocol")
    if meta["date"] != "2026-10-26":
        raise ValueError("observation chronology changed")
    if meta["source_type"] != "CONDITIONAL_THESIS_FALSIFICATION_NOT_INVESTMENT":
        raise ValueError("cannot promote to investment signal")
    if meta["historical_dividends_since_fy2014_15"] != "NONE_IN_FY2015_FY2026":
        raise ValueError("historical dividends cannot be fabricated")
    if meta["historical_five_year_buyback_issuer_note"] != "NONE_IN_LAST_FIVE_YEARS_TO_FY2026":
        raise ValueError("historical repurchase note changed")
    if meta["controlling_shareholder"] != "RELIANCE_RETAIL_VENTURES_PROMOTER_GROUP":
        raise ValueError("controller identity changed")
    if meta["reported_promoter_group_2026_sep_pct"] != 74.14:
        raise ValueError("reported holding changed")
    if meta["promotion_prohibited"] != {
        "historical_h002_h003_hg009_retroactive_change": False,
        "source_raw_bytes_archived": False,
        "source_first_retrieved_utc": None,
        "investment_approved": False,
        "calibrated_scenario_probabilities": None,
        "target_price_recommendation": None,
    }:
        raise ValueError("false original custody, forecast or capital authorization")
    market, netliq, c = pinned_financials(meta)
    studies = meta["scenarios"]
    labels = [s["name"] for s in studies]
    if len(studies) != 8 or len(set(labels)) != 8:
        raise ValueError("missing or duplicate scenarios")

    results = []
    for row in studies:
        n = row["years_without_common_shareholder_distribution"]
        if isinstance(n, bool) or not isinstance(n, int) or n < 0 or n > 10:
            raise ValueError("unsupported cash-trap holding period")
        r = positive_num(row["illustrative_net_treasury_yield"], "portfolio yield", True)
        k = positive_num(row["illustrative_equity_hurdle"], "equity hurdle")
        g = positive_num(row["illustrative_cash_generation_growth"], "growth", True)
        multiple = positive_num(row["terminal_franchise_cash_multiple"], "exit multiple")
        if max(r, g) > 0.25 or k > 0.3 or not (2 <= multiple <= 12):
            raise ValueError("out-of-range uncalibrated assumptions")
        terminal_treasury = netliq * (1 + r) ** n
        retained_operating_cash = sum(
            c * (1 + g) ** (year - 1) * (1 + r) ** (n - year)
            for year in range(1, n + 1)
        )
        ending_annual_cash = c * (1 + g) ** n
        hypothetical_business_exit = ending_annual_cash * multiple
        discounted_total = (
            terminal_treasury + retained_operating_cash + hypothetical_business_exit
        ) / (1 + k) ** n
        results.append({
            "name": row["name"],
            "hypothetical_no_distribution_years": n,
            "assumed_treasury_net_yield_pct": round(r * 100, 2),
            "assumed_shareholder_discount_pct": round(k * 100, 2),
            "assumed_cash_growth_pct": round(g * 100, 2),
            "assumed_terminal_business_cash_multiple": multiple,
            "discounted_hypothetical_equity_value_cr": round(discounted_total, 2),
            "relative_to_observed_market_cap_pct": round(
                (discounted_total / market - 1) * 100, 2
            ),
            "research_only_not_value_forecast": True,
            "capital_authorized": False,
        })
    return {
        "source_market_cap_cr": market,
        "illustrative_net_liquid_before_restrictions_cr": netliq,
        "annualized_selected_cash_not_owner_fcfe_cr": c,
        "scenarios": results,
        "probability_weighted_equity_value": None,
        "forecast_return": None,
        "capital_authorized": False,
        "decision": "CASH_TRAP_MAY_ERASE_APPARENT_DISCOUNT_NO_BUY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text(encoding="utf-8"))),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
