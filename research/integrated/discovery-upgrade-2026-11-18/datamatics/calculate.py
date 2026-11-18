"""Reproducible research arithmetic, 18 November 2026. Not a return forecast.

All financial values are INR crore except explicitly marked prices/shares.
The model values annual cash available to common owners, distributed or
retained at par. Actual dividends are not projected. It adds no net cash.
"""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
inputs = {
    "as_of": "2026-11-18",
    "price_inr": 703.65,
    "shares": 59106389,
    "periods": {
        "FY26": {"cfo": 323.99, "capex": 39.57, "lease_principal": 23.98, "interest_paid": 13.74, "interest_received": 18.45, "dividend_received": 0.24, "cash_tax": 75.67, "current_tax": 78.74, "pnl_tax": 65.14, "group_pat": 194.95, "owner_pat": 194.21, "share_appreciation_rights": 1.86, "operating_before_wc": 380.54, "cash_before_tax": 399.66},
        "H1FY26": {"cfo": 118.01, "capex": 9.64, "lease_principal": 12.61, "interest_paid": 7.04, "interest_received": 10.90, "dividend_received": 0.16, "cash_tax": 36.01, "current_tax": 33.62, "pnl_tax": 30.68, "group_pat": 113.74, "owner_pat": 113.62, "share_appreciation_rights": 0.0, "operating_before_wc": 148.06, "cash_before_tax": 154.02},
        "H1FY27": {"cfo": 190.41, "capex": 37.70, "lease_principal": 18.04, "interest_paid": 6.68, "interest_received": 13.76, "dividend_received": 0.17, "cash_tax": 23.86, "current_tax": 43.25, "pnl_tax": 41.84, "group_pat": 145.94, "owner_pat": 145.76, "share_appreciation_rights": 3.47, "operating_before_wc": 224.49, "cash_before_tax": 214.27, "acquisition_cash": 210.30}
    },
    "tnq": {"first_80_price": 348.12, "final_20_price": 206.80, "fy26_revenue": 338.0946, "fy25_revenue": 296.6243, "fy26_pat": 84.9116, "fy25_pat": 39.6770, "cfo": 113.3942, "capex": 6.0213, "lease_payment": 7.3776, "operating_before_wc": 120.5728, "cash_tax": 28.7248, "wc_receivables_release": 4.6411, "wc_other_assets": -0.5830, "wc_payables": 6.3838, "wc_other_liabilities": 11.1043},
    "balance_20260930": {"noncurrent_investments": 199.80, "current_investments": 468.17, "cash": 137.87, "borrowings_noncurrent": 141.71, "borrowings_current": 107.26, "leases_noncurrent": 35.95, "leases_current": 30.45, "other_bank_balances_not_assumed_free": 15.63, "goodwill": 611.32, "owner_equity": 1670.03},
    "scenario_assumptions": {
        "years": 5,
        "discount_rates": [0.10, 0.12, 0.15],
        "treasury_income_tax_assumption": 0.25,
        "bear": {"starting_owner_cash": 220.0, "growth": 0.0, "terminal_owner_cash_multiple": 10.0},
        "base_operating_only": {"starting_owner_cash": 255.0, "growth": 0.08, "terminal_owner_cash_multiple": 12.0},
        "base": {"starting_owner_cash": 270.0, "growth": 0.08, "terminal_owner_cash_multiple": 12.0},
        "upside": {"starting_owner_cash": 300.0, "growth": 0.12, "terminal_owner_cash_multiple": 15.0},
        "notes": [
            "Annual owner cash is available cash valued as distributed or accumulated at par, not actual dividend guidance.",
            "No net cash or investments are separately added. No new leverage is assumed to fund growth. The operating-only case omits treasury income and rings existing financial assets against debt repayment, with no assumed interest-savings uplift. The270crore working case assumes netfinancing income/cost maintained, which requires enough interest savings or residual investment income after repayment.",
            "All reported capex and lease principal and cash interest are deducted in the starting cash bridge.",
            "Minority-owner adjustment uses observed TTM noncontrolling profit as a provisional reserve, not a verified subsidiary cash attribution.",
            "Growth must be supported by operating expense, capex and working capital within the model. It does not include cost-free future acquisitions.",
            "No calibrated case probabilities. Terminal multiples and growth are analyst assumptions, not facts or issuer guidance.",
            "Treasury income is added after an assumed 25 percent tax even though treasury tax may already be reflected in total current tax. This is a conservative reserve, not precise incremental taxation.",
            "Discount rates show investor return preferences. The user has not specified a universal 15 percent hurdle.",
            "Investor-level capital gains tax, dividend tax and dealing costs are excluded because user tax and execution assumptions are unknown."
        ]
    }
}
shares_crore = inputs["shares"] / 1e7
periods = inputs["periods"]
ttm = {key: periods["FY26"][key] + periods["H1FY27"][key] - periods["H1FY26"][key] for key in periods["FY26"]}
ttm["selected_equity_cash_before_acquisitions"] = ttm["cfo"] - ttm["capex"] - ttm["lease_principal"] - ttm["interest_paid"]
ttm["cash_tax_to_current_tax_reserve"] = ttm["current_tax"] - ttm["cash_tax"]
ttm["nci_profit_proxy_reserve"] = ttm["group_pat"] - ttm["owner_pat"]
ttm["owner_operating_cash_proxy_after_reserves"] = ttm["selected_equity_cash_before_acquisitions"] - ttm["cash_tax_to_current_tax_reserve"] - ttm["nci_profit_proxy_reserve"] - ttm["share_appreciation_rights"]
ttm["estimated_treasury_aftertax_income"] = (ttm["interest_received"] + ttm["dividend_received"]) * (1 - inputs["scenario_assumptions"]["treasury_income_tax_assumption"])
ttm["owner_cash_with_treasury_estimate"] = ttm["owner_operating_cash_proxy_after_reserves"] + ttm["estimated_treasury_aftertax_income"]
ttm["wc_cash_benefit"] = ttm["cash_before_tax"] - ttm["operating_before_wc"]
tnq = inputs["tnq"]
tnq_derived = {
    "total_price": tnq["first_80_price"] + tnq["final_20_price"],
    "post_capex_lease_cash": tnq["cfo"] - tnq["capex"] - tnq["lease_payment"],
    "wc_cash_benefit": tnq["wc_receivables_release"] + tnq["wc_other_assets"] + tnq["wc_payables"] + tnq["wc_other_liabilities"],
    "revenue_growth": tnq["fy26_revenue"] / tnq["fy25_revenue"] - 1,
    "pat_margin": tnq["fy26_pat"] / tnq["fy26_revenue"]
}
tnq_derived["wc_neutral_cash"] = tnq_derived["post_capex_lease_cash"] - tnq_derived["wc_cash_benefit"]
tnq_derived["cash_return_proxy"] = tnq_derived["post_capex_lease_cash"] / tnq_derived["total_price"]
tnq_derived["wc_neutral_cash_return_proxy"] = tnq_derived["wc_neutral_cash"] / tnq_derived["total_price"]
tnq_derived["marginal_final_20_cash_return_proxy"] = tnq_derived["wc_neutral_cash"] * 0.20 / tnq["final_20_price"]
tnq_derived["pat_return_proxy"] = tnq["fy26_pat"] / tnq_derived["total_price"]

def value(owner_cash, growth, multiple, rate, years=5):
    annual = [owner_cash * (1 + growth)**year for year in range(1, years + 1)]
    annual_pv = sum(cf / (1 + rate)**year for year, cf in enumerate(annual, 1))
    terminal_pv = annual[-1] * multiple / (1 + rate)**years
    return {"per_share": (annual_pv + terminal_pv) / shares_crore, "equity_value_cr": annual_pv + terminal_pv, "annual_owner_cash_cr": annual, "terminal_pv_share": terminal_pv / (annual_pv + terminal_pv)}

def solve_increasing(fn, target, lo, hi):
    for _ in range(120):
        mid = (lo + hi) / 2
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def implied_return(price, owner_cash=270, growth=0.08, multiple=12):
    return solve_increasing(lambda rate: -value(owner_cash, growth, multiple, rate)["per_share"], -price, -0.49, 1.0)

scenario_values = {}
for name in ("bear", "base_operating_only", "base", "upside"):
    scenario = inputs["scenario_assumptions"][name]
    scenario_values[name] = {str(rate): value(scenario["starting_owner_cash"], scenario["growth"], scenario["terminal_owner_cash_multiple"], rate) for rate in inputs["scenario_assumptions"]["discount_rates"]}
reverse = {}
for rate in inputs["scenario_assumptions"]["discount_rates"]:
    reverse[str(rate)] = {
        "growth_needed_at_owner_cash_270_terminal_12": solve_increasing(lambda growth: value(270, growth, 12, rate)["per_share"], inputs["price_inr"], -0.9, 1.0),
        "starting_cash_needed_at_growth_8_terminal_12": inputs["price_inr"] / value(1, 0.08, 12, rate)["per_share"],
        "terminal_multiple_needed_at_cash_270_growth_8": solve_increasing(lambda multiple: value(270, 0.08, multiple, rate)["per_share"], inputs["price_inr"], 0, 100)
    }
bs = inputs["balance_20260930"]
netcash = bs["noncurrent_investments"] + bs["current_investments"] + bs["cash"] - bs["borrowings_noncurrent"] - bs["borrowings_current"]
derived = {
    "shares_crore": shares_crore,
    "market_cap_cr": shares_crore * inputs["price_inr"] ,
    "ttm": ttm,
    "ttm_owner_eps": ttm["owner_pat"] / shares_crore,
    "reported_ttm_pe": inputs["price_inr"] * shares_crore / ttm["owner_pat"],
    "h1_selected_equity_cash_before_acquisition": periods["H1FY27"]["cfo"] - periods["H1FY27"]["capex"] - periods["H1FY27"]["lease_principal"] - periods["H1FY27"]["interest_paid"],
    "tnq": tnq_derived,
    "net_cash_investments_less_borrowings": netcash,
    "net_cash_investments_less_borrowings_and_leases": netcash - bs["leases_noncurrent"] - bs["leases_current"],
    "current_cash_investments_less_borrowings": netcash - bs["noncurrent_investments"],
    "goodwill_pct_owner_equity": bs["goodwill"] / bs["owner_equity"],
    "scenario_values": scenario_values,
    "base_implied_returns": {str(price): implied_return(price) for price in (703.65, 620.0, 600.0, 590.0)},
    "base_operating_only_implied_returns": {str(price): implied_return(price, 255) for price in (703.65, 620.0, 600.0, 590.0)},
    "reverse_valuation": reverse,
    "sensitivity_owner_cash_10cr_less_base_r12": value(260, .08, 12, .12)["per_share"],
    "sensitivity_terminal_10x_base_r12": value(270, .08, 10, .12)["per_share"],
    "sensitivity_growth_4pct_base_r12": value(270, .04, 12, .12)["per_share"]
}
for filename, data in (("decision_inputs.json", inputs), ("decision_calculations.json", derived)):
    (HERE / filename).write_text(json.dumps(data, indent=2) + "\n")
print(json.dumps(derived, indent=2))
