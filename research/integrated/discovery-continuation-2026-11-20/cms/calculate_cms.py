"""CMS decision arithmetic. All forecasts are explicit, unweighted scenarios.

Run with Python standard library only. No web requests or external dependencies.
Cash flows are per share and annual from decision date, before investor taxes/costs.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = json.loads((ROOT / "decision_inputs.json").read_text())


def irr(price, cashflows):
    def npv(r):
        return sum(c / (1 + r) ** (i + 1) for i, c in enumerate(cashflows)) - price
    lo, hi = -0.99, 1.0
    while npv(hi) > 0:
        hi *= 2
    for _ in range(160):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def model(s, *, price=None, opening_cash_adjustment=0, cash_credit=1,
          flat_capex=None, extra_customer_finance=0, extra_wc_y1=0,
          upfront_share_cr=0, upfront_option_proceeds=0):
    g = INPUT["global_assumptions"]
    b = INPUT["opening_balance_sheet"]
    price = INPUT["reference_close_inr"] if price is None else price
    opening_cash = (b["cash"] + b["current_investments"] + b["noncurrent_investments"]
                    - b["operating_liquidity_reserve_assumption"]
                    - s["opening_extra_risk_reserve"] + opening_cash_adjustment
                    + upfront_option_proceeds)
    cash = opening_cash
    shares = INPUT["shares_cr_asof_2026_09_30"] + upfront_share_cr
    prior_rev = None
    rows, flows = [], []
    for year in range(1, 6):
        rev = s["revenue_y1"] * (1 + s["revenue_growth"]) ** (year - 1)
        ebitda = rev * s["cash_ebitda_margin"]
        lease_cash = s["lease_cash_y1"] * (1 + s["lease_growth"]) ** (year - 1)
        tax_da = s["tax_depreciation_proxy_y1"] * (1 + s["tax_depreciation_growth"]) ** (year - 1)
        tax = max(0, ebitda - lease_cash - tax_da) * g["tax_rate"]
        capex = (s["cash_capex_y1"] if year == 1 else rev * s["later_capex_to_sales"])
        if flat_capex is not None:
            capex = flat_capex * (1 + s["revenue_growth"]) ** (year - 1)
        wc = (s["wc_y1"] + extra_wc_y1 if year == 1
              else s["incremental_wc_to_sales"] * (rev - prior_rev))
        wc += extra_customer_finance
        owner_cash = ebitda - lease_cash - tax - capex - wc
        div = s["dividend_y1"] * (1 + s["dividend_growth"]) ** (year - 1)
        cash += owner_cash - div
        shares *= 1 + s["annual_share_dilution"]
        flow = div / shares
        flows.append(flow)
        rows.append(dict(year=year,revenue=rev,cash_ebitda=ebitda,lease_cash=lease_cash,
                         cash_tax=tax,tax_da_proxy=tax_da,cash_capex=capex,
                         incremental_working_capital_and_customer_financing=wc,
                         owner_cash_before_dividend=owner_cash,dividends=div,
                         retained_cash=cash,shares_cr=shares,dividend_per_share=flow))
        prior_rev = rev
    # Exit operating value excludes treasury returns. Retained cash is added once.
    terminal_business = rows[-1]["owner_cash_before_dividend"] * s["exit_owner_cash_multiple"]
    terminal_cash = cash * cash_credit
    terminal_share = (terminal_business + terminal_cash) / shares
    flows[-1] += terminal_share
    return dict(opening_available_treasury=opening_cash,years=rows,
                terminal_business_value=terminal_business,terminal_cash_credit=terminal_cash,
                terminal_price=terminal_share,terminal_shares_cr=shares,
                cashflows_per_share=flows,annualized_return=irr(price,flows),
                entry_value_by_return={str(r):sum(c/(1+r)**(i+1) for i,c in enumerate(flows))
                    for r in [.08,.10,.12,.15]},
                minimum_retained_cash=min(r["retained_cash"] for r in rows),
                external_funding_required=any(r["retained_cash"]<0 for r in rows))


def main():
    hist = copy.deepcopy(INPUT["historical"])
    hist["TTM_20260930"] = {key:hist["FY26"][key]-hist["H1FY26"][key]+hist["H1FY27"][key]
                             for key in hist["FY26"]}
    for values in hist.values():
        values["selected_cash_before_customer_finance"] = (values["cfo"]-values["cash_capex"]
            -values["lease_principal"]-values["lease_interest"]-values["other_interest"])
        values["net_customer_financing"] = values["customer_loan_advance"]-values["customer_loan_repaid"]
        values["after_net_customer_financing"] = values["selected_cash_before_customer_finance"]-values["net_customer_financing"]
        values["after_separate_acquisitions"] = values["after_net_customer_financing"]-values["acquisition_cash"]
    n = INPUT["normalization"]
    h1_ebitda = n["h1_pbt"]+n["h1_finance_cost"]+n["h1_da"]-n["h1_other_income"]
    h1_cash_ebitda = h1_ebitda + n["h1_net_esop_cashflow_adjustment"]
    b = INPUT["capex_bridge"]
    asset_additions_proxy = (b["ppe_cwip_intangible_development_closing"]
        -b["ppe_cwip_intangible_development_opening"]+b["h1_nonlease_da"]
        +b["h1_disposal_cash"]-b["h1_disposal_gain"])
    working = INPUT["scenarios"]["working"]
    scenarios={name:model(s) for name,s in INPUT["scenarios"].items()}
    tests={
        "cash_capex_200_then_grows_with_sales":model(working,flat_capex=200),
        "cash_capex_250_then_grows_with_sales":model(working,flat_capex=250),
        "cash_capex_300_then_grows_with_sales":model(working,flat_capex=300),
        "cash_credit_75_percent":model(working,cash_credit=.75),
        "no_opening_treasury_credit":model(working,opening_cash_adjustment=-scenarios["working"]["opening_available_treasury"]),
        "fss_55_remains_payable_one_time":model(working,extra_wc_y1=55),
        "additional_customer_finance_25_every_year":model(working,extra_customer_finance=25),
        "unprovided_disputed_claims_55_46_paid_one_time":model(working,extra_wc_y1=55.46),
        "full_march_option_overhang_gross_exercise_and_proceeds":model(working,
            upfront_share_cr=(6865750+291249)/1e7,
            upfront_option_proceeds=(6865750*308+291249*198)/1e7),
    }
    for exit_m in [8,10,14]:
        s=copy.deepcopy(working);s["exit_owner_cash_multiple"]=exit_m
        tests[f"exit_{exit_m}x"]=model(s)
    for m in [.245,.265]:
        s=copy.deepcopy(working);s["cash_ebitda_margin"]=m
        tests[f"cash_ebitda_margin_{m}"]=model(s)
    s=copy.deepcopy(working);s["revenue_growth"]=0
    tests["no_sales_growth"] = model(s)
    s=copy.deepcopy(working);s["cash_ebitda_margin"]=.245;s["exit_owner_cash_multiple"]=10
    tests["joint_credible_stress_24_5_margin_250_capex_10x_exit_25_financing"] = model(
        s,flat_capex=250,extra_customer_finance=25)
    # Reverse the all-years annual cash capex budget. This is a sensitivity, not guidance.
    reverse={}
    for target in [.08,.10,.12]:
        lo,hi=0,500
        for _ in range(120):
            mid=(lo+hi)/2
            if model(working,flat_capex=mid)["annualized_return"] > target:lo=mid
            else:hi=mid
        reverse[str(target)]=(lo+hi)/2
    annual_bridge = INPUT["fy26_cash_capex_bridge"]
    annual_reconstructed = sum(annual_bridge[k] for k in ["ppe_additions","intangible_additions",
        "cwip_change","intangible_development_change","capital_advances_change","capital_creditor_decline"])
    output=dict(classification="FUNDED_SCENARIO_UNDERWRITING_WITH_UNRESOLVED_CASH_CLASSIFICATION",
        price_date=INPUT["price_date"],reference_close=INPUT["reference_close_inr"])
    output.update(historical=hist,normalization=dict(h1_statutory_ebitda_ex_other_income=h1_ebitda,
        h1_cash_ebitda_ex_other_income_and_net_esop_credit=h1_cash_ebitda,
        h1_cash_ebitda_margin=h1_cash_ebitda/n["h1_revenue"],
        ttm_pat=n["fy26_parent_pat"]+n["h1_parent_pat"]-n["h1fy26_parent_pat"]),
        asset_bridge=dict(gross_asset_addition_proxy=asset_additions_proxy,
            cash_less_asset_addition_proxy=b["h1_cash_capex"]-asset_additions_proxy,
            other_financial_liability_decline=b["march_other_financial_liabilities"]-b["sept_other_financial_liabilities"],
            status="NOT_A_COMPLETE_CAPITAL_CREDITOR_OR_MA_PAYMENT_RECONCILIATION"),
        fy26_cash_capex_bridge=dict(book_capitalizations=annual_bridge["ppe_additions"]+annual_bridge["intangible_additions"],
            reconstructed_cash=annual_reconstructed,reported_cash=annual_bridge["reported_cash_capex"],
            unexplained_residual=annual_bridge["reported_cash_capex"]-annual_reconstructed),
        scenarios=scenarios,sensitivities=tests,
        max_first_year_cash_capex_growing_with_sales_for_return=reverse,
        price_liquidity=dict(shares_cr=INPUT["shares_cr_asof_2026_09_30"],
            market_cap_cr=INPUT["reference_close_inr"]*INPUT["shares_cr_asof_2026_09_30"]),
        prospective_outcome=None,calibrated_probability=None)
    (ROOT/"decision_calculations.json").write_text(json.dumps(output,indent=2)+"\n")
    print(json.dumps({"scenarios":{k:{q:v[q] for q in ["annualized_return","terminal_price","entry_value_by_return","external_funding_required"]}
                                for k,v in scenarios.items()},
                      "sensitivity_returns":{k:v["annualized_return"] for k,v in tests.items()},
                      "reverse_capex":reverse},indent=2))


if __name__=="__main__":
    main()
