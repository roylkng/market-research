"""GESHIP P001: reproduce dated management-NAV sensitivity, never an investment signal.

Run:
  python scripts/geship_p001_nav_stress.py
  python scripts/geship_p001_nav_stress.py --input path/to/snapshot.json

The residual component is a *balance-sheet identity*, NOT vessel market value.
No backtest, calibrated probabilities, total return or live-capital instruction.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    REPO / "research/company-intelligence/geship-p001-nav-stress-input-20261025.json"
)


def finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def evaluate(payload: dict) -> dict:
    if payload.get("purpose") != "POST_HOC_INVESTMENT_DILIGENCE_NOT_PROSPECTIVE_ALPHA":
        raise ValueError("cannot promote this source into a prospective signal")
    if payload.get("result_status") != "NO_APPROVED_INVESTMENT_NO_PROBABILITIES_NO_CAPITAL":
        raise ValueError("live-capital or approval state is forbidden")
    inputs = payload["inputs"]
    price = finite_number(inputs["price_per_share_inr"], "price")
    nav = finite_number(inputs["reported_consolidated_nav_per_share_inr"], "nav")
    net_cash = finite_number(inputs["reported_consolidated_net_cash_crore"], "net cash")
    capital_lakh = finite_number(inputs["paid_up_share_capital_lakh_inr"], "capital")
    face = finite_number(inputs["face_value_inr"], "face")
    dividend = finite_number(inputs["q1_fy27_interim_dividend_inr"], "dividend")
    if min(price, nav, capital_lakh, face) <= 0 or net_cash < 0 or dividend < 0:
        raise ValueError("invalid nonpositive capital/nav or negative cash/dividend")
    if inputs["price_date"] <= inputs["nav_date"]:
        raise ValueError("market quote and reporting period chronology failed")

    # lakh INR / INR per share / 100 lakh per crore = crore shares.
    shares_crore = capital_lakh / face / 100.0
    cash_per_share = net_cash / shares_crore
    residual = nav - cash_per_share
    if residual <= 0:
        raise ValueError("cannot apply non-cash-component haircut to negative residual")
    if dividend >= nav:
        raise ValueError("dividend exceeds dated NAV")
    scenarios = []
    for spec in payload["stress_scenarios"]:
        haircut = finite_number(spec["residual_noncash_haircut"], "residual haircut")
        cash_haircut = finite_number(spec["net_cash_haircut"], "cash haircut")
        multiple = finite_number(spec["exit_price_to_stressed_nav"], "exit multiple")
        if not (-1 <= haircut <= 1 and 0 <= cash_haircut <= 1 and 0 < multiple <= 2):
            raise ValueError("out-of-range stress assumption")
        stressed_nav = (
            cash_per_share * (1 - cash_haircut)
            + residual * (1 - haircut)
            - dividend
        )
        if stressed_nav < 0:
            raise ValueError("stress implies negative NAV; needs liability model")
        marked_share_price = stressed_nav * multiple
        scenarios.append({
            "name": spec["name"],
            "stressed_nav_per_share": round(stressed_nav, 2),
            "hypothetical_market_price": round(marked_share_price, 2),
            "price_change_vs_dated_close_pct": round((marked_share_price / price - 1) * 100, 2),
            "interpretation": "SENSITIVITY_NOT_FORECAST",
        })
    watch = payload["watch_haircuts"]
    asset_haircut = finite_number(watch["residual_noncash_haircut"], "watch asset haircut")
    cash_haircut = finite_number(watch["net_cash_haircut"], "watch cash haircut")
    safety_margin = finite_number(watch["margin_of_safety_fraction"], "watch margin")
    if not (0 <= asset_haircut <= 1 and 0 <= cash_haircut <= 1 and 0 < safety_margin < 1):
        raise ValueError("invalid watch assumptions")
    watch_nav = (
        cash_per_share * (1 - cash_haircut)
        + residual * (1 - asset_haircut) - dividend
    )
    watch_level = watch_nav * (1 - safety_margin)
    break_even_residual_haircut_if_cash_constant = (nav - dividend - price) / residual
    return {
        "symbol": payload["symbol"],
        "nav_date": inputs["nav_date"],
        "price_date": inputs["price_date"],
        "price_per_share_inr": round(price, 2),
        "company_reported_nav_per_share_inr": round(nav, 2),
        "original_june_denominator_crore_shares": round(shares_crore, 6),
        "june_net_cash_per_share": round(cash_per_share, 2),
        "residual_noncash_component_per_share": round(residual, 2),
        "price_to_reported_nav": round(price / nav, 4),
        "reported_nav_discount_pct": round((1 - price / nav) * 100, 2),
        "break_even_residual_haircut_with_cash_unchanged_pct": round(
            break_even_residual_haircut_if_cash_constant * 100, 2
        ),
        "conditional_research_watch_level_inr": round(watch_level, 2),
        "watch_level_is_trade_instruction": False,
        "scenarios": scenarios,
        "classification": "RESEARCH_ONLY_UNVERIFIED_CURRENT_NAV",
        "capital_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(data), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
