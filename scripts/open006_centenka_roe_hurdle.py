"""Century Enka OPEN006: test whether book discount compensates for weak ROE.

An analytical earnings-yield identity, NOT a DCF or buy recommendation.
No actual FY27 outcome or later Q2 filing is opened by this code.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN006_CENTENKA_ROE_HURDLE_INPUT_20261026.json"
)


def positive(data: object, label: str) -> float:
    if isinstance(data, bool) or not isinstance(data, (float, int)):
        raise TypeError(f"{label} must be numeric")
    result = float(data)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be finite positive")
    return result


def evaluate(packet: dict) -> dict:
    if packet.get("schema") != "OPEN006-CENTENKA-20261026-ROE-BOOK-FALSIFICATION-v1":
        raise ValueError("input protocol changed")
    if packet.get("type") != "POSTHOC_ECONOMIC_HURDLE_NOT_INVESTMENT_VALUATION":
        raise ValueError("cannot introduce prospective hindsight")
    if packet.get("status") != "OBSERVE_NOT_BUY" or packet.get("capital_authorized") is not False:
        raise ValueError("cannot authorize stock purchases")
    if packet.get("scientific_trials_unchanged") is not True:
        raise ValueError("frozen research mutation")
    if packet.get("price_date") != "2026-10-23" or packet.get("observed_local") != "2026-10-26":
        raise ValueError("dated observation cutoff changed")
    if packet.get("symbol") != "CENTENKA" or packet.get("historical_symbol_isin") != "INE485A01015":
        raise ValueError("exact issuer identity changed")
    source = packet["source_lineage"]
    if not (
        source["original_signed_issuer_presentation"].startswith(
            "https://nsearchives.nseindia.com/corporate/"
        )
        and source["original_pdf_visually_inspected"] is True
        and source["original_bytes_sha256_archived_here"] is None
        and source["actual_first_seen_utc"] is None
    ):
        raise ValueError("original evidence cannot be fabricated or mislabelled")
    original_shares = packet["exact_shares_from_March_2025_annual_report"]
    if not isinstance(original_shares, int) or original_shares <= 0:
        raise ValueError("original share count required")
    if packet["FY26_company_claimed_no_new_securities_issued"] is not True:
        raise ValueError("share count continuity not supported")
    if packet["FY26_statement_basis"] != (
        "consolidated year ended 2026-03-31, amounts INR million/10 = INR crore"
    ):
        raise ValueError("financial data reporting basis changed")
    price = positive(packet["nse_close_inr"], "NSE close")
    annual = packet["annual_data"]
    if set(annual) != {"FY24", "FY25", "FY26"}:
        raise ValueError("three source years required")
    years = []
    for year in ("FY24", "FY25", "FY26"):
        row = annual[year]
        pat = positive(row["group_PAT_crore"], "group PAT")
        book = positive(row["group_closing_equity_crore"], "group closing equity")
        years.append({"year": year, "year_end_ROE_pct": round(pat / book * 100, 4)})
    y26 = annual["FY26"]
    y25 = annual["FY25"]
    price_shares_crore = original_shares / 10_000_000
    market_cap = price * price_shares_crore
    book = positive(y26["group_closing_equity_crore"], "FY26 book")
    profit = positive(y26["group_PAT_crore"], "FY26 PAT")
    p_to_b = market_cap / book
    book_value_share = book / price_shares_crore
    p_to_e = market_cap / profit
    ev = packet["economic_test"]
    if (
        ev["economic_parent_owner_cash_crore"] is not None
        or ev["verified_current_fully_diluted_shares"] is not None
        or ev["intrinsic_equity_value_crore"] is not None
        or ev["investable_entry_price"] is not None
    ):
        raise ValueError("source-unverified owner cash, shares or intrinsic value")
    if ev["abstract_no_growth_full_payout_identity"] != (
        "P=B*(ROE/required_return). Neither a DCF nor a realizable market price; "
        "ignores growth, tax, reinvestment, cash restrictions and cyclicality"
    ):
        raise ValueError("cannot call zero-growth sensitivity a forecast")
    required_returns = ev["required_equity_yields"]
    if required_returns != [0.10, 0.12, 0.15]:
        raise ValueError("analytical hurdle scenarios altered")
    hurdle_rows = []
    for required in required_returns:
        if not 0 < required < 1:
            raise ValueError("invalid required return")
        hurdle_rows.append({
            "required_equity_return_pct": round(required * 100, 2),
            "ROE_required_to_support_dated_price_pct": round(
                p_to_b * required * 100, 3
            ),
            "earnings_capitalization_identity_share_inr": round(
                profit / required / price_shares_crore, 2
            ),
            "identity_share_change_vs_dated_close_pct": round(
                (profit / required / market_cap - 1) * 100, 2
            ),
            "price_target": False,
        })
    rating = packet["external_rating"]
    if rating["date"] != "2026-06-25" or rating["rating"] != "CRISIL A+/Stable":
        raise ValueError("rating citation changed")
    capex = positive(rating["planned_FY27_capex_crore_approx"], "FY27 planned capex")
    accrual = positive(rating["estimated_fy26_operating_cashflow_crore_approx"], "FY26 cash")
    if packet["unresolved"]["FY27_Q2_results_original_verified"] is not False:
        raise ValueError("unknown FY27 results cannot be backfilled")
    return {
        "issuer": packet["symbol"],
        "price_date": packet["price_date"],
        "price_at_last_regular_close_inr": price,
        "reference_shares_from_prior_original_crore": round(price_shares_crore, 7),
        "indicative_equity_market_cap_crore": round(market_cap, 2),
        "fy26_book_per_reference_share_inr": round(book_value_share, 2),
        "price_to_march_book": round(p_to_b, 4),
        "discount_to_march_book_pct": round((1 - p_to_b) * 100, 2),
        "FY26_pat_crore": profit,
        "FY26_earnings_yield_pct": round(100 / p_to_e, 2),
        "years_closing_equity_ROE_pct": years,
        "three_year_closing_ROE_average_pct": round(
            sum(x["year_end_ROE_pct"] for x in years) / len(years), 4
        ),
        "FY26_revenue_change_pct": round(
            (positive(y26["operating_revenue_crore"], "FY26 revenue")
             / positive(y25["operating_revenue_crore"], "FY25 revenue") - 1) * 100, 2
        ),
        "planned_FY27_capex_as_share_of_FY26_approx_operating_cash_pct": round(
            capex / accrual * 100, 2
        ),
        "hypothetical_cash_remaining_if_FY26_approx_cash_repeats_crore": round(
            accrual - capex, 2
        ),
        "analytical_zero_growth_full_distribution_hurdles": hurdle_rows,
        "investment_approved": False,
        "intrinsic_value_verified": False,
        "research_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text(encoding="utf-8"))),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
