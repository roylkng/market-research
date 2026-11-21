"""Reproduce the signed cash bridge and the explicitly unfunded expectations map.

Run: python calculate.py
No market downloads or assumptions are silently refreshed.
"""
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parent
i = json.loads((ROOT / "model_inputs.json").read_text())
p = i["periods"]
ttm = {k: p["FY26"][k] - p["H1FY26"][k] + p["H1FY27"][k] for k in p["FY26"]}
periods = {**p, "TTM_to_2026_09": ttm}
bridges = {}
for name, row in periods.items():
    after_leases = row["CFO"] - row["lease_principal"] - row["lease_interest"]
    after_capex = after_leases - row["capex"]
    bridges[name] = {
        **row,
        "CFO_after_full_lease_cash": after_leases,
        "cash_after_all_actual_capex": after_capex,
        "economic_cash_after_all_capex_and_SBC": after_capex - row["SBC"],
    }
shares = i["shares_crore_approx"]
price = i["price_inr"]
eps = ttm["PAT"] / shares
market_cap = price * shares
pe = price / eps
gross_options = i["fy26_options_outstanding"] + i["h1_fy27_options_granted"] - i["h1_fy27_options_exercised"]
gross_option_shares = shares + gross_options / 1e7
cases = []
reverse = []
v = i["reverse_valuation"]
for years in v["horizons_years"]:
    for growth in v["annual_eps_growth_assumptions"]:
        terminal_eps = eps * (1 + growth) ** years
        for multiple in v["terminal_pe_assumptions"]:
            terminal_price = terminal_eps * multiple
            cases.append({"years": years, "eps_cagr": growth, "exit_pe": multiple,
                          "terminal_eps": terminal_eps, "terminal_price": terminal_price,
                          "price_cagr_excluding_dividends": (terminal_price / price) ** (1 / years) - 1})
    for return_axis in v["price_cagr_axes_for_reverse"]:
        for multiple in v["terminal_pe_assumptions"]:
            reverse.append({"years": years, "price_cagr_axis": return_axis, "exit_pe": multiple,
                            "required_eps_cagr": (1 + return_axis) * (pe / multiple) ** (1 / years) - 1})
cash = i["h1_fy27_cash_semantics"]
assert math.isclose(cash["signed_lease_principal"] + cash["signed_finance_costs_paid"], cash["ixbrl_aggregate_lease_payments"], abs_tol=1e-8)
assert math.isclose(bridges["TTM_to_2026_09"]["cash_after_all_actual_capex"],
                    bridges["FY26"]["cash_after_all_actual_capex"] - bridges["H1FY26"]["cash_after_all_actual_capex"] + bridges["H1FY27"]["cash_after_all_actual_capex"], abs_tol=1e-8)
assert i["isin"] == "INE043W01024" and i["price_date"] == "2026-11-20"
result = {
    "units": "INR crore except per-share rupees, multiples and fractional rates",
    "model_type": v["model_type"],
    "market_cap": market_cap,
    "ttm_eps_using_approx_issued_shares": eps,
    "ttm_pe": pe,
    "price_sales": market_cap / ttm["revenue"],
    "h1_weighted_diluted_shares_implied_by_rounded_eps_crore": p["H1FY27"]["PAT"] / i["h1_fy27_diluted_eps_inr"],
    "gross_option_sensitivity": {"options_before_unknown_lapses": gross_options,
                                  "shares_crore": gross_option_shares,
                                  "market_cap_without_option_exercise_cash_credit": price * gross_option_shares,
                                  "pe": price * gross_option_shares / ttm["PAT"],
                                  "is_verified_current_fully_diluted_share_count": False},
    "cash_bridges": bridges,
    "price_scenarios": cases,
    "required_eps_growth": reverse,
    "no_probability_assigned": True,
    "validation": "Signed cash-flow line semantics and TTM bridge reconcile. This does not validate future EPS growth."
}
(ROOT / "model_outputs.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ["model_type", "market_cap", "ttm_pe", "price_sales", "gross_option_sensitivity"]}, indent=2))
