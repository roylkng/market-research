#!/usr/bin/env python3
"""Epigral: explicit capex, tax, working capital, funding and retained-cash model.

All future inputs are analyst scenarios, not issuer guidance unless labelled in
the companion note. Period one is the remaining FY27 half year estimated from
the latest Sept-2026 balance, not realized post-decision cash. Discount dates are
actual model dates measured from the verified Nov-18 reference price.
"""
from copy import deepcopy
from datetime import date
from pathlib import Path
import csv
import hashlib
import json

HERE = Path(__file__).resolve().parent
INPUT = {
    "classification": "ANALYST_SCENARIO_NOT_RETURN_FORECAST",
    "price": 944.30,
    "price_date": "2026-11-18",
    "symbol": "EPIGRAL",
    "isin": "INE071N01016",
    "series": "EQ",
    "shares": 43141338,
    "share_basis": "Exact FY26 audited and June2026 shareholder count, unchanged rounded September capital. No claim of a fresh November capital audit.",
    "units": "INR crore except share prices and shares",
    "balance_date": "2026-09-30",
    "sales_and_profit_convention": {
        "status": "ANALYST_ALLOCATION_ASSUMPTION_NOT_DISCLOSED_SEGMENT_FORECAST",
        "core_sales": "Gross economic turnover of the existing/expanded upstream and core portfolio, including market-equivalent internal ECH/chlorotoluene transfers when relevant.",
        "new_downstream_sales": "External sales of new downstream output. Its modeled margin is incremental after a market-equivalent charge for captive upstream feedstock.",
        "summed_sales": "Pre-elimination gross turnover proxy, NOT consolidated external revenue. No claim that3550+1000 is a verified product sales bridge.",
        "profit": "Core contribution includes upstream margin on captive material, downstream contribution is after transfer feedstock cost. No automatic subtraction of upstream economic profit merely because delivery is internal.",
        "uncertainty": "No issuer product-level forecast reconciles these allocated sales/margins. The same total EBITDA could require a different product mix. Comparison of summed turnover with management consolidated revenue ambition is not proof of conservatism.",
        "working_capital": "Model charges working capital against the gross growth proxy without a captive-elimination credit. This may overstate funding needs, but no precise external-turnover or incremental-revenue claim is made.",
    },
    "funding_status": {
        "classification": "MODELED_FINANCEABILITY_NOT_VERIFIED_COMMITTED_PROJECT_DRAWDOWNS",
        "description": "Net-debt recurrence assumes facilities can finance the modeled cash deficits and replace scheduled amortization. Rated and proposed facilities are not irrevocable unrestricted project funding.",
        "scheduled_principal_first_two_periods": [57.65,115.28],
        "principal_treatment": "Principal repayment is a financing flow. To preserve model net debt, gross new/refinancing need equals closing net debt minus opening net debt plus scheduled principal, before cashbuffer or optional extra repayment.",
        "later_periods": "Cash sweeps/prepayment and renewed workingcapital access are assumptions. Actual covenants, drawdown conditions and prepayment charges require review before capital deployment.",
    },
    "borrowings": 564.92,
    "cash": 0.86,
    "initial_net_debt": 564.06,
    "cash_tax_rate": 0.2517,
    "one_off_cash_reserves": {
        "derivative_settlement_allowance": 25.0,
        "october_tax_demand_full_amount": 28.11,
        "h1_current_tax_less_cash_tax": 13.98,
        "remaining_renewable_spv_ocd_subscription": 13.81,
    },
    "reserve_caveats": {
        "derivative": "Analyst allowance, not exact Sept current+noncurrent fair value. March derivative liabilities27.71, Sept noncurrent9.24 and current portion not separately published.",
        "tax_demand": "Company contests demand. Full amount assumed paid in first forecast period, no refund benefit.",
        "current_tax": "Timing catch-up allowance57.33-43.35, not assertion all is immediately payable.",
        "spv": "21.25 committed OCD less2.13 FY26 and5.31 H1FY27, equity0.13 already subscribed. Not part of PPE capex assumption.",
    },
    "dates": ["2027-03-31", "2028-03-31", "2029-03-31", "2030-03-31", "2031-03-31", "2032-03-31"],
    "duration_years": [0.5, 1, 1, 1, 1, 1],
    "scenarios": {
        "downside": {
            "core_sales": [1400, 2850, 2850, 2900, 2950, 3000],
            "new_downstream_sales": [0, 0, 50, 120, 220, 300],
            "core_margin": 0.16,
            "new_downstream_margin": 0.10,
            "cash_leases": [4, 8, 9, 9, 10, 10],
            "non_rou_depreciation": [90, 200, 220, 225, 230, 235],
            "capex": [375, 480, 130, 100, 100, 100],
            "working_capital_use": [90, 40, 30, 40, 45, 45],
            "dividend_per_share": [0, 0, 0, 0, 0, 0],
            "interest_rate": 0.105,
            "terminal_post_lease_ebitda_multiple": 5.0,
            "terminal_cash_value_fraction": 1.0,
        },
        "working": {
            "core_sales": [1550, 3300, 3400, 3450, 3500, 3550],
            "new_downstream_sales": [0, 0, 250, 550, 800, 1000],
            "core_margin": 0.21,
            "new_downstream_margin": 0.14,
            "cash_leases": [4, 8, 9, 9, 10, 10],
            "non_rou_depreciation": [90, 200, 220, 225, 230, 235],
            "capex": [312, 400, 75, 85, 90, 95],
            "working_capital_use": [30, 53.757, 63, 63, 54, 45],
            "dividend_per_share": [0, 5, 5, 5, 5, 5],
            "interest_rate": 0.085,
            "terminal_post_lease_ebitda_multiple": 7.0,
            "terminal_cash_value_fraction": 1.0,
        },
        "upside": {
            "core_sales": [1650, 3500, 3650, 3700, 3750, 3800],
            "new_downstream_sales": [0, 0, 450, 850, 1250, 1400],
            "core_margin": 0.23,
            "new_downstream_margin": 0.16,
            "cash_leases": [4, 8, 9, 9, 10, 10],
            "non_rou_depreciation": [90, 200, 220, 225, 230, 235],
            "capex": [312, 400, 85, 95, 105, 115],
            "working_capital_use": [30, 67.771, 102, 76.5, 76.5, 34],
            "dividend_per_share": [0, 5, 5, 5, 5, 5],
            "interest_rate": 0.08,
            "terminal_post_lease_ebitda_multiple": 8.0,
            "terminal_cash_value_fraction": 1.0,
        },
    },
}


def pv(cashflows, rate):
    return sum(c / (1 + rate) ** t for t, c in cashflows)


def irr(cashflows, price):
    lo, hi = -0.99, 3.0
    for _ in range(180):
        mid = (lo + hi) / 2
        if pv(cashflows, mid) > price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def run(s, inp=INPUT):
    shares_cr = inp["shares"] / 1e7
    debt = inp["initial_net_debt"]
    rows, flows = [], []
    for i, end in enumerate(inp["dates"]):
        opening = debt
        revenue = s["core_sales"][i] + s["new_downstream_sales"][i]
        ebitda_before_lease = ((s["core_sales"][i] * s["core_margin"] +
                               s["new_downstream_sales"][i] * s["new_downstream_margin"])
                              *s.get("gross_ebitda_multiplier",1.0))
        cash_leases = s["cash_leases"][i]
        post_lease = ebitda_before_lease - cash_leases
        interest = max(0, opening) * s["interest_rate"] * inp["duration_years"][i]
        pretax = post_lease - s["non_rou_depreciation"][i] - interest
        taxes = max(0, pretax) * inp["cash_tax_rate"]
        capex = s["capex"][i]
        wc = s["working_capital_use"][i]
        one_off = sum(inp["one_off_cash_reserves"].values()) if i == 0 else 0
        available_cash = post_lease - interest - taxes - capex - wc - one_off
        dps = s["dividend_per_share"][i]
        dividends = dps * shares_cr
        debt = opening - available_cash + dividends
        t = (date.fromisoformat(end) - date.fromisoformat(inp["price_date"])).days / 365.25
        flows.append([t, dps])
        scheduled_principal = inp["funding_status"]["scheduled_principal_first_two_periods"][i] if i<2 else None
        replacement_need = max(0,debt-opening+scheduled_principal) if scheduled_principal is not None else None
        rows.append(dict(date=end,discount_years=t,
                         gross_sales_proxy_before_captive_elimination=revenue,
                         consolidated_external_revenue=None,
                         ebitda_before_cash_leases=ebitda_before_lease,
                         cash_leases=cash_leases,post_lease_ebitda=post_lease,
                         opening_net_debt=opening,interest=interest,cash_tax=taxes,
                         capex=capex,working_capital_use=wc,one_off_cash_uses=one_off,
                         cash_after_all_uses_before_dividends=available_cash,
                         dividends=dividends,closing_net_debt=debt,
                         scheduled_principal=scheduled_principal,
                         gross_new_or_replacement_borrowing_before_buffers=replacement_need))
    ev = rows[-1]["post_lease_ebitda"] * s["terminal_post_lease_ebitda_multiple"]
    equity = ev - max(debt,0) + max(-debt,0)*s["terminal_cash_value_fraction"]
    terminal_price = max(equity,0) / shares_cr
    flows[-1][1] += terminal_price
    return {
        "rows": rows, "terminal_enterprise_value": ev, "terminal_equity_value": equity,
        "terminal_share_value": terminal_price, "cashflows_per_share": flows,
        "annualized_scenario_return": irr(flows,inp["price"]),
        "present_value_per_share": {str(h):pv(flows,h) for h in [.10,.12,.15]},
        "highest_net_debt": max(x["closing_net_debt"] for x in rows),
        "terminal_value_share_of_pv_at12": (terminal_price/(1.12)**flows[-1][0])/pv(flows,.12),
    }


def main():
    result = {k:run(v) for k,v in INPUT["scenarios"].items()}
    sensitivity = []
    for multiple in [5,6,7,8]:
        for cash_fraction in [0.5,0.75,1.0]:
            s=deepcopy(INPUT["scenarios"]["working"])
            s["terminal_post_lease_ebitda_multiple"]=multiple
            s["terminal_cash_value_fraction"]=cash_fraction
            r=run(s)
            sensitivity.append(dict(exit_multiple=multiple,cash_value_fraction=cash_fraction,
                pv12=r["present_value_per_share"]["0.12"],irr=r["annualized_scenario_return"]))
    reverse=[]
    for hurdle in [.10,.12,.15]:
        lo,hi=.05,.40
        for _ in range(100):
            m=(lo+hi)/2
            s=deepcopy(INPUT["scenarios"]["working"])
            s["core_margin"]=m
            r=run(s)
            if r["present_value_per_share"][str(hurdle)]<INPUT["price"]:lo=m
            else:hi=m
        reverse.append(dict(hurdle=hurdle,required_constant_core_margin=(lo+hi)/2,
            fixed_other_assumptions="working trajectory, new14%, exit7x, full retained cash value"))
    no_growth=deepcopy(INPUT["scenarios"]["working"])
    no_growth.update(core_sales=[1450,2900,2900,2900,2900,2900],
                     new_downstream_sales=[0,0,0,0,0,0],working_capital_use=[30,20,20,20,20,20],
                     terminal_post_lease_ebitda_multiple=7)
    result["paid_for_expansion_but_no_incremental_revenue"]=run(no_growth)
    entry_sensitivity=[]
    for entry in [800,850,875,900,944.30,1000]:
        for fraction in [0.75,1.0]:
            s=deepcopy(INPUT["scenarios"]["working"])
            s["terminal_cash_value_fraction"]=fraction
            r=run(s)
            entry_sensitivity.append(dict(entry=entry,cash_value_fraction=fraction,
                irr=irr(r["cashflows_per_share"],entry)))
    overrun=deepcopy(INPUT["scenarios"]["working"])
    overrun["capex"][1]+=150
    result["working_with_150cr_extra_capex"]=run(overrun)
    softer_contribution=deepcopy(INPUT["scenarios"]["working"])
    softer_contribution["gross_ebitda_multiplier"]=0.90
    result["working_with_10pct_lower_aggregate_gross_ebitda"]=run(softer_contribution)
    softer_downstream=deepcopy(INPUT["scenarios"]["working"])
    softer_downstream["new_downstream_margin"]=0.10
    result["working_with_downstream_margin_10pct"]=run(softer_downstream)
    accounting={
        "market_cap":INPUT["price"]*INPUT["shares"]/1e7,
        "h1_owner_pat":164.82,"h1_cash_tax":43.35,"h1_current_tax":57.33,
        "h1_owner_cash_after_selected_uses":140.84-87.97-24.16-3.98,
        "h1_owner_cash_after_selected_uses_and_spv":140.84-87.97-24.16-3.98-5.31,
        "fy26_cash_after_selected_uses":435.53-394.15-48.69-5.87,
        "fy26_after_selected_uses_and_preference_dividend":435.53-394.15-48.69-5.87-3.24,
        "fy25_cash_after_selected_uses":440.56-194.69-65.94-2.36,
        "h1prior_cash_after_selected_uses":267.31-235.68-24.10-2.68,
        "ttm_cash_after_selected_uses":(435.53-267.31+140.84)-(394.15-235.68+87.97)-(48.69-24.10+24.16)-(5.87-2.68+3.98),
        "ttm_owner_pat":331.97-211.91+164.82,
        "ttm_reported_pe":INPUT["price"]*INPUT["shares"]/1e7/(331.97-211.91+164.82),
        "h1_doubled_eps_multiple":944.30/(38.2*2),
        "h1_working_capital_use":137.18,
        "h1_working_capital_neutral_after_current_tax_cash_finance_leases_and_maintenance_estimate":321.37-57.33-24.16-3.98-22.5,
        "maintenance_estimate_basis":"Issuer1.5%annual grossblock, analyst3000cr grossblock andhalfyear. Notreportedmaintenancecash.",
        "caveat":"Selected cash proxies exclude disposals, treasuryrealizations, acquisition costs, debtprincipal andequitydividends. They are not normalized distributable FCF."
    }
    (HERE/'epigral_model_inputs.json').write_text(json.dumps(INPUT,indent=2)+'\n')
    output=dict(accounting=accounting,scenarios=result,sensitivity=sensitivity,reverse_margin=reverse,
                entry_sensitivity=entry_sensitivity)
    (HERE/'epigral_calculations.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({"accounting":accounting,"summary":{k:{x:v[x] for x in ["annualized_scenario_return","present_value_per_share","terminal_share_value","highest_net_debt"]} for k,v in result.items()},"sensitivity":sensitivity,"reverse_margin":reverse},indent=2))


if __name__ == '__main__':
    main()
