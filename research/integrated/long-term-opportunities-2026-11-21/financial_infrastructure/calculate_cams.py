#!/usr/bin/env python3
"""CAMS cash bridge and reverse valuation, as observed on 21 November 2026.

This is an expectations calculation, not a fully funded operating forecast.
All financial-statement inputs are INR crore. Shares are crore shares.
Run from any directory. No external dependencies or network requests.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUTS = {
    "price_date": "2026-11-20",
    "price": 724.65,
    "isin": "INE596I01020",
    "share_count_date": "2026-09-30",
    "shares_march_2026": 247_984_498,
    "shares_issued_h1fy27": 433_880,
    "fy26": {
        "revenue": 1516.2490, "owner_pat": 476.0057,
        "cfo": 584.2614, "cash_before_wc_before_tax": 705.5942,
        "cash_tax": 164.0401, "all_ppe_software_capex": 140.5483,
        "lease_principal": 33.2211, "lease_interest": 6.9391,
        "borrowing_interest": 0.0193, "cash_dividends": 304.5274,
        "sbc_added_back_in_cfo": 13.2012,
    },
    "fy25": {
        "revenue": 1422.4833, "owner_pat": 470.1938,
        "cfo": 477.4214, "cash_before_wc_before_tax": 661.7096,
        "cash_tax": 145.9360, "all_ppe_software_capex": 118.3786,
        "lease_principal": 28.1206, "lease_interest": 8.4450,
        "borrowing_interest": 0.0, "cash_dividends": 344.8622,
        "sbc_added_back_in_cfo": 14.7251,
    },
    "h1fy26": {
        "revenue": 730.8898, "owner_pat": 224.0336,
        "cfo": 324.3426, "cash_before_wc_before_tax": 335.5455,
        "cash_tax": 82.5036, "all_ppe_software_capex": 52.9560,
        "lease_principal": 15.7959, "lease_interest": 3.7552,
        "borrowing_interest": 0.0, "cash_dividends": 148.4243,
        "sbc_added_back_in_cfo": 8.4660,
    },
    "h1fy27": {
        "revenue": 809.4952, "owner_pat": 259.5081,
        "cfo": 253.6140, "cash_before_wc_before_tax": 382.9172,
        "cash_tax": 84.6684, "all_ppe_software_capex": 73.7459,
        "lease_principal": 17.0722, "lease_interest": 2.8579,
        "borrowing_interest": 0.0134, "cash_dividends": 161.3562,
        "sbc_added_back_in_cfo": 3.9050,
        "subsidiary_acquisition_cash": 18.6816, "joint_venture_cash": 3.5000,
    },
    "september_treasury": {
        "cash_equivalents": 4.4685,
        "current_investments": 471.3827,
        "other_bank_balances": 399.2459,
        "current_borrowing": 0.2436,
        "lease_liabilities": 58.9244,
        "november_dividend_per_share": 3.25,
        "november_dividend_record_date": "2026-11-13",
    },
    "reverse_valuation_assumptions": {
        "normalized_starting_cash": 400.0,
        "provisional_opening_treasury_credit": 650.0,
        "annual_share_dilution": 0.005,
        "horizons_years": [5, 10],
        "illustrative_annual_returns": [0.08, 0.10, 0.12],
        "terminal_cash_multiples": [20, 25, 30],
        "cash_distribution_fraction": 1.0,
        "cash_growth_is_after_all_future_reinvestment": True,
    },
}


def cash_bridge(p):
    investments = p["all_ppe_software_capex"]
    financing = p["lease_principal"] + p["lease_interest"] + p["borrowing_interest"]
    zero_wc_cfo = p["cash_before_wc_before_tax"] - p["cash_tax"]
    return {
        **p,
        "selected_cash_after_all_capex_leases": p["cfo"] - investments - financing,
        "cash_before_wc_after_tax_all_capex_leases": zero_wc_cfo - investments - financing,
        "working_capital_cash_effect": p["cfo"] - zero_wc_cfo,
    }


SHARES = (INPUTS["shares_march_2026"] + INPUTS["shares_issued_h1fy27"]) / 10_000_000


def price_for_growth(starting_cash, growth, years, annual_return, terminal_multiple):
    a = INPUTS["reverse_valuation_assumptions"]
    treasury_per_share = a["provisional_opening_treasury_credit"] / SHARES
    annual_claims = [starting_cash * (1 + growth) ** t /
                     (SHARES * (1 + a["annual_share_dilution"]) ** t)
                     for t in range(1, years + 1)]
    pv_distributions = sum(c / (1 + annual_return) ** t
                           for t, c in enumerate(annual_claims, 1))
    pv_terminal = terminal_multiple * annual_claims[-1] / (1 + annual_return) ** years
    return treasury_per_share + pv_distributions + pv_terminal


def growth_for_price(starting_cash, years, annual_return, terminal_multiple):
    lo, hi = -0.5, 1.0
    for _ in range(120):
        mid = (lo + hi) / 2
        if price_for_growth(starting_cash, mid, years, annual_return, terminal_multiple) > INPUTS["price"]:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def run():
    periods = {k: cash_bridge(INPUTS[k]) for k in ["fy25", "fy26", "h1fy26", "h1fy27"]}
    ttm = {k: INPUTS["fy26"][k] - INPUTS["h1fy26"][k] + INPUTS["h1fy27"][k]
           for k in INPUTS["fy26"]}
    periods["ttm_september_2026"] = cash_bridge(ttm)
    t = periods["ttm_september_2026"]
    mcap = SHARES * INPUTS["price"]
    observed_cash = t["selected_cash_after_all_capex_leases"]
    a = INPUTS["reverse_valuation_assumptions"]
    reverse = []
    for f in [observed_cash, a["normalized_starting_cash"]]:
        for n in a["horizons_years"]:
            for mult in a["terminal_cash_multiples"]:
                for r in a["illustrative_annual_returns"]:
                    g = growth_for_price(f, n, r, mult)
                    reverse.append({"starting_cash": f, "years": n,
                                    "illustrative_annual_return": r,
                                    "terminal_cash_multiple": mult,
                                    "required_company_cash_growth": g,
                                    "required_cash_per_share_growth": (1 + g) / (1 + a["annual_share_dilution"]) - 1,
                                    "required_terminal_company_cash": f * (1 + g) ** n,
                                    "recomputed_price": price_for_growth(f, g, n, r, mult)})
    sensitivity = [{"annual_company_cash_growth": g, "terminal_cash_multiple": mult,
                    "illustrative_annual_return": 0.10, "years": 10,
                    "price_consistent_with_assumptions": price_for_growth(400, g, 10, 0.10, mult)}
                   for g in [0.08, 0.10, 0.12, 0.15] for mult in [20, 25, 30]]
    business_cases = []
    for name, aum, fee, other_mf, non_mf in [
            ("weak_market", 0.06, -0.03, 0.04, 0.12),
            ("steady", 0.12, -0.03, 0.08, 0.18),
            ("strong", 0.14, -0.03, 0.10, 0.20),
            ("very_strong", 0.17, -0.02, 0.12, 0.25)]:
        asset_growth = (1 + aum) * (1 + fee) - 1
        business_cases.append({"case": name, "aum_growth": aum, "fee_yield_change": fee,
                               "mf_asset_revenue_growth": asset_growth,
                               "mf_other_growth": other_mf, "non_mf_growth": non_mf,
                               "weighted_total_revenue_growth": 0.74 * asset_growth + 0.12 * other_mf + 0.14 * non_mf})
    treasury = INPUTS["september_treasury"]
    result = {
        "model_type": "REVERSE_VALUATION_NOT_FULLY_FUNDED_FORECAST",
        "as_of": "2026-11-21", "inputs": INPUTS, "periods": periods,
        "identity_and_valuation": {
            "september_issued_shares_crore": SHARES, "market_cap_cr": mcap,
            "ttm_owner_pat_over_current_issued_shares": t["owner_pat"] / SHARES,
            "indicative_pe_current_issued_share_basis": mcap / t["owner_pat"],
            "rolling_reported_diluted_eps": 19.13 - 9.00 + 10.41,
            "approximate_pe_rolling_reported_diluted_eps": INPUTS["price"] / (19.13 - 9.00 + 10.41),
            "observed_selected_cash_per_share": observed_cash / SHARES,
            "observed_selected_cash_yield": observed_cash / mcap,
            "zero_wc_cash_yield_diagnostic": t["cash_before_wc_after_tax_all_capex_leases"] / mcap,
            "gross_treasury_cr": treasury["cash_equivalents"] + treasury["current_investments"] + treasury["other_bank_balances"],
            "november_dividend_committed_before_price_date_cr": treasury["november_dividend_per_share"] * SHARES,
        },
        "reverse_valuation": reverse, "price_sensitivity": sensitivity,
        "business_growth_mechanism_scenarios_not_forecasts": business_cases,
        "industry": {"aum_oct2016_lakh_cr": 16.29, "aum_oct2026_lakh_cr": 83.39,
                     "ten_year_multiple": 83.39 / 16.29,
                     "ten_year_aum_cagr": (83.39 / 16.29) ** 0.1 - 1},
        "history": {"owner_pat_fy22_cr": 286.9469, "owner_pat_fy26_cr": 476.0057,
                    "four_elapsed_year_pat_cagr": (476.0057 / 286.9469) ** 0.25 - 1,
                    "split_adjusted_eps_fy22": 11.75, "split_adjusted_eps_fy26": 19.23,
                    "four_elapsed_year_eps_cagr": (19.23 / 11.75) ** 0.25 - 1},
        "comparison": {
            "CAMS": {"official_close": 724.65, "rolling_diluted_eps": 20.54, "approximate_pe": 724.65 / 20.54},
            "KFINTECH": {"official_close": 934.90, "rolling_diluted_eps": 19.81 - 9.83 + 10.12,
                         "approximate_pe": 934.90 / (19.81 - 9.83 + 10.12),
                         "h1fy27_selected_cash_cr": (2333.74 - 171.92 - 419.14 - 102.37 - 26.59) / 10,
                         "h1fy26_selected_cash_cr": (1808.13 - 222.39 - 212.44 - 69.32 - 18.85) / 10},
            "CDSL": {"official_close": 1430.00, "rolling_diluted_eps": 21.82 - 11.61 + 13.94,
                     "approximate_pe": 1430.00 / (21.82 - 11.61 + 13.94)},
        },
        "limitations": [
            "Current issued share count is verified to 30 September, not independently to 20 November. A 0.5% annual dilution allowance is an assumption.",
            "Reported CFO includes SBC add-back. Share dilution is modeled instead of also deducting the same SBC amount as cash. No future option exercise proceeds are credited.",
            "Zero working-capital movement is a diagnostic, not a sustainable funded-growth assumption.",
            "All PPE and software capex is retained. Acquisitions and joint venture investments are separate capital-allocation uses, not included in recurring selected cash.",
            "INR650cr treasury credit is provisional. It is below INR875.10cr gross treasury and allows for the already-earned dividend, buffers and other claims. It is not an audited free-cash number.",
            "Annual future cash is assumed distributable only after all future reinvestment and taxes. Growth feasibility is not established by this reverse calculation.",
            "Opening treasury is credited once. All modeled annual owner cash is distributed and is not added again to terminal cash.",
            "Lease payments are deducted annually. The entire lease liability is not also subtracted from opening equity value.",
            "Terminal multiple, discount rate and growth assumptions are sensitivities, not forecasts or a universal hurdle.",
            "Rolling rounded reported EPS sums are approximate because weighted share counts can differ between periods.",
        ],
    }
    (HERE / "decision_calculations.json").write_text(json.dumps(result, indent=2) + "\n")
    (HERE / "decision_inputs.json").write_text(json.dumps(INPUTS, indent=2) + "\n")
    # Integrity checks verify identities, not investment outcomes.
    assert abs(t["selected_cash_after_all_capex_leases"] - 311.6227) < 1e-6
    assert abs(t["cash_before_wc_after_tax_all_capex_leases"] - 384.8509) < 1e-6
    assert abs(SHARES - 24.8418378) < 1e-9
    assert all(abs(row["recomputed_price"] - INPUTS["price"]) < 1e-8 for row in reverse)
    print(json.dumps({"ttm_selected_cash_cr": observed_cash,
                      "ttm_cash_before_wc_cr": t["cash_before_wc_after_tax_all_capex_leases"],
                      "market_cap_cr": mcap,
                      "reverse_case_normalized_10y_10pct_25x": [x for x in reverse if x["starting_cash"] == 400 and x["years"] == 10 and x["illustrative_annual_return"] == 0.10 and x["terminal_cash_multiple"] == 25][0]}, indent=2))


if __name__ == "__main__":
    run()
