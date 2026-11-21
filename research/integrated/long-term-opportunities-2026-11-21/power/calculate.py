"""Reproducible arithmetic only, including a distinct profit-reset sensitivity.

This is not a strategy test or a funded forecast. An FY26 profit anchor is a
stress assumption, not a claim that FY26 represents sustainable normal profit.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "inputs.json").read_text())
a, m = data["apar"], data["model"]
shares_crore = a["shares"] / 1e7
market_cap = shares_crore * a["price"]
fy26 = a["historical"][-1]
ttm_pat = fy26["pat"] + a["h1fy27"]["pat"] - a["h1fy26"]["pat"]
ttm_revenue = fy26["revenue"] + a["h1fy27"]["revenue"] - a["h1fy26"]["revenue"]

def cashflows(profit, growth, multiple, years):
    flows = [-a["price"]]
    for year in range(1, years + 1):
        eps = profit * (1 + growth) ** year / (shares_crore * (1 + m["annual_share_dilution"]) ** year)
        flows.append(eps * m["payout"])
    flows[-1] += eps * multiple
    return flows

def npv(flows, rate):
    return sum(value / (1 + rate) ** t for t, value in enumerate(flows))

def irr(flows):
    low, high = -0.95, 3.0
    for _ in range(150):
        mid = (low + high) / 2
        if npv(flows, mid) > 0:
            low = mid
        else:
            high = mid
    return (low + high) / 2

out = {"as_of":data["as_of"], "model_classification":m["classification"], "market_cap_crore":market_cap,
       "ttm_pat_crore":ttm_pat,"ttm_revenue_crore":ttm_revenue,"ttm_eps_on_current_shares":ttm_pat/shares_crore,
       "ttm_pe":market_cap/ttm_pat,"fy26_pe_on_current_shares":market_cap/fy26["pat"],
       "sep26_price_to_book":market_cap/a["h1fy27"]["equity"],"cash_residuals":[],"scenarios":[],"reverse_valuation":[]}
for row in a["historical"][-2:] + [dict(a["h1fy27"], period="H1FY27")]:
    out["cash_residuals"].append({"period":row["period"],"cfo_to_pat":row["cfo"]/row["pat"],
        "after_gross_ppe_interest_and_lease_principal":row["cfo"]-row["ppe_cash_outflow"]-row["interest_paid_financing"]-row["lease_principal"],
        "definition":"Residual before asset-disposal proceeds, dividends, acquisitions and debt principal. All PPE spending is retained, without an invented maintenance/growth split."})
for n in m["horizons"]:
    for s in m["scenarios"]:
        flows = cashflows(s["normalised_start_pat"],s["pat_growth"],s["exit_pe"],n)
        terminal_eps=s["normalised_start_pat"]*(1+s["pat_growth"])**n/(shares_crore*(1+m["annual_share_dilution"])**n)
        out["scenarios"].append(dict(s,years=n,irr=irr(flows),terminal_pat=s["normalised_start_pat"]*(1+s["pat_growth"])**n,
            terminal_price=terminal_eps*s["exit_pe"],cumulative_dividends=sum(flows[1:])-terminal_eps*s["exit_pe"],
            stable_roe_implied_by_retention=s["pat_growth"]/(1-m["payout"]),cashflows_per_share=flows))
    for required in m["required_returns"]:
        for multiple in m["exit_multiples"]:
            low,high=-0.5,1.0
            for _ in range(150):
                growth=(low+high)/2
                if npv(cashflows(m["reverse_start_pat"],growth,multiple,n),required) < 0:
                    low=growth
                else:
                    high=growth
            out["reverse_valuation"].append({"years":n,"required_return":required,"exit_pe":multiple,"required_pat_growth":(low+high)/2})
out["sector_plan"]=[dict(x,implied_capacity_cagr=(x["target"]/x["baseline"])**(1/x["years_for_cagr"])-1) for x in data["sector_plan"]]
pg=data["powergrid"]
out["powergrid_comparator"]={"approx_ttm_eps":pg["fy26_eps"]+pg["h1fy27_eps"]-pg["h1fy26_eps"],
    "approx_ttm_pe":pg["price"]/(pg["fy26_eps"]+pg["h1fy27_eps"]-pg["h1fy26_eps"]),
    "fy26_pe":pg["price"]/pg["fy26_eps"],"price_to_book":pg["price"]/pg["sep26_book_value_per_share"],
    "fy26_announced_dividend_reference_yield":pg["fy26_announced_dividend_per_share"]/pg["price"],
    "caution":"Reported rounded per-share inputs, no modeled project returns, dividend-payment confirmation or full capital-change sweep."}
out["gvtandd_fy26_earnings_multiple_reference"]=data["gvtandd"]["price"]/data["gvtandd"]["fy26_reported_eps"]
(HERE/"calculations.json").write_text(json.dumps(out,indent=2)+"\n")
assert abs(ttm_pat-1377.12)<1e-8
assert abs(market_cap-60044.6442323)<1e-6
assert abs(out["cash_residuals"][1]["after_gross_ppe_interest_and_lease_principal"]+57.86)<1e-8
assert all(abs(npv(s["cashflows_per_share"],s["irr"]))<1e-6 for s in out["scenarios"])
print(json.dumps({"market_cap":market_cap,"ttm_pe":out["ttm_pe"],"scenario_irrs":[[x["name"],x["years"],round(x["irr"]*100,2)] for x in out["scenarios"]],"powergrid":out["powergrid_comparator"]},indent=2))
