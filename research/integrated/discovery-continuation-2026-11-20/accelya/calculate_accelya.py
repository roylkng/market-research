#!/usr/bin/env python3
"""Deterministic cash-funded Accelya scenarios. Standard library only.

Run from any working directory. Writes decision_calculations.json beside this file.
No probabilities, future prices or realized outcomes are manufactured.
"""
from copy import deepcopy
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent


def irr(flows):
    def npv(rate):
        return sum(value / (1 + rate) ** t for t, value in enumerate(flows))
    low, high = -0.95, 3.0
    if npv(low) * npv(high) > 0:
        raise ValueError("IRR not bracketed")
    for _ in range(180):
        mid = (low + high) / 2
        if npv(mid) > 0:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def run_scenario(inputs, assumptions, extra_oneoff=0):
    common = inputs["model_common_assumptions"]
    shares_cr = inputs["shares"] / 1e7
    balance = common["opening_surplus_cash_credited"]
    rows = []
    flows = [-inputs["price_inr"]]
    reserve = common["liquidity_reserve_built_from_future_cash"]
    growth = assumptions["subsequent_revenue_growth"]
    for year in range(1, common["years"] + 1):
        t = year - 1
        revenue = assumptions["year1_revenue"] * (1 + growth) ** t
        ebitda = revenue * assumptions["operating_ebitda_margin"]
        rent = assumptions["recurring_rent_income"]
        leases = assumptions["financing_lease_cash_year1"] * (1 + assumptions["lease_growth"]) ** t
        investment = assumptions["full_ppe_and_software_cash_year1"] * (1 + assumptions["investment_growth"]) ** t
        wc = assumptions["working_capital_and_contract_funding_year1"] * (1 + max(0, growth)) ** t
        depreciation = common["nonlease_tax_depreciation_year1"] * (1 + max(0, growth)) ** t
        tax = max(0, ebitda + rent - leases - depreciation) * common["cash_tax_rate"]
        owner_cash = ebitda + rent - leases - investment - wc - tax
        oneoff = 0
        if year == 1:
            oneoff = common["incremental_gratuity_funding_year1"] + common["epfo_payment_year1"]
            oneoff += assumptions["extra_collection_cash_loss_year1"] + extra_oneoff
        cash_after_oneoff = owner_cash - oneoff
        balance += cash_after_oneoff
        funding_gap = max(0, -balance)
        dividend = max(0, balance - reserve) * common["fraction_of_cash_above_reserve_distributed_each_year"]
        balance -= dividend
        shares_cr *= 1 + common["annual_share_dilution"]
        rows.append({
            "year": year, "revenue": revenue, "operating_ebitda": ebitda,
            "recurring_rent": rent, "financing_lease_cash": leases,
            "nonlease_tax_depreciation_assumption": depreciation, "cash_tax": tax,
            "full_ppe_software_cash": investment, "wc_contract_funding": wc,
            "recurring_owner_cash": owner_cash, "oneoff_funding": oneoff,
            "cash_after_oneoff": cash_after_oneoff, "assumed_cash_distribution": dividend,
            "retained_cash": balance, "shares_crore": shares_cr,
            "distribution_per_share": dividend / shares_cr,
            "recurring_owner_cash_per_share": owner_cash / shares_cr,
            "external_funding_gap": funding_gap
        })
        flows.append(dividend / shares_cr)
    last = rows[-1]
    terminal_business = last["recurring_owner_cash"] * assumptions["terminal_owner_cash_multiple"]
    terminal_surplus_cash = max(0, balance - reserve)
    terminal_equity = terminal_business + terminal_surplus_cash
    flows[-1] += terminal_equity / shares_cr
    return {
        "rows": rows,
        "terminal_business_value": terminal_business,
        "terminal_surplus_cash_counted_once": terminal_surplus_cash,
        "terminal_operating_reserve_excluded": min(reserve, max(0, balance)),
        "terminal_equity_value_per_share_assumption": terminal_equity / shares_cr,
        "shareholder_cash_flows_per_share": flows,
        "annualized_return": irr(flows),
        "funded_without_external_financing": all(row["external_funding_gap"] == 0 for row in rows),
        "comparison_entry_values": {
            f"{rate:.0%}": sum(value / (1 + rate) ** t for t, value in enumerate(flows) if t)
            for rate in (0.08, 0.10, 0.12, 0.15)
        }
    }


def calculate(inputs):
    a = inputs["consolidated_fy26"]
    b = inputs["consolidated_fy25"]
    q = inputs["q1_fy27_september"]
    shares_cr = inputs["shares"] / 1e7
    selected = lambda x: x["cfo"] - x["cash_ppe"] - x["cash_intangible"] - x["lease_principal"] - x["lease_interest"]
    related = lambda x: sum(x["related_billed_receivables"]) + sum(x["related_unbilled_receivables"])
    free_june = a["june_cash"] + a["june_liquid_mutual_funds"] + a["june_other_bank_balances"] - a["unpaid_dividend_earmark"] - a["margin_money_in_other_bank"]
    final_div = inputs["dividends"]["fy26_final_per_share"] * shares_cr
    cases = {name: run_scenario(inputs, assumptions) for name, assumptions in inputs["scenarios"].items()}
    working = inputs["scenarios"]["working"]
    y1_owner = cases["working"]["rows"][0]["recurring_owner_cash"]
    no_compression_multiple = inputs["price_inr"] * shares_cr / y1_owner
    sensitivities = {}
    for name, updates in {
        "exit_14x": {"terminal_owner_cash_multiple": 14},
        "unchanged_current_owner_cash_multiple": {"terminal_owner_cash_multiple": no_compression_multiple},
        "wc_contract_drag_15cr_each_year": {"working_capital_and_contract_funding_year1": 15},
        "lease_cash_12_2379_current_commitment_only": {"financing_lease_cash_year1": a["undiscounted_lease_due_within_one_year"]},
        "zero_incremental_wc_and_contract_funding": {"working_capital_and_contract_funding_year1": 0},
        "joint_optimistic_cash_lease_commitment_zero_wc": {"financing_lease_cash_year1": a["undiscounted_lease_due_within_one_year"], "working_capital_and_contract_funding_year1": 0},
        "flat_revenue": {"subsequent_revenue_growth": 0},
        "margin_31_percent": {"operating_ebitda_margin": 0.31}
    }.items():
        assumptions = deepcopy(working)
        assumptions.update(updates)
        sensitivities[name] = run_scenario(inputs, assumptions)
    for name, updates in {
        "normalized_5cr_wc_low_lease": {"working_capital_and_contract_funding_year1": 5, "financing_lease_cash_year1": a["undiscounted_lease_due_within_one_year"]},
        "zero_wc_low_lease": {"working_capital_and_contract_funding_year1": 0, "financing_lease_cash_year1": a["undiscounted_lease_due_within_one_year"]}
    }.items():
        assumptions = deepcopy(working)
        assumptions.update(updates)
        normalized_owner = run_scenario(inputs, assumptions)["rows"][0]["recurring_owner_cash"]
        recalculated_entry_multiple = inputs["price_inr"] * shares_cr / normalized_owner
        for label, multiple in (("14x_exit", 14), ("unchanged_recalculated_entry_multiple", recalculated_entry_multiple)):
            assumptions["terminal_owner_cash_multiple"] = multiple
            sensitivities[f"joint_{name}_{label}"] = run_scenario(inputs, assumptions)
            sensitivities[f"joint_{name}_{label}"]["entry_normalized_cash_multiple_recalculated"] = recalculated_entry_multiple
    sensitivities["extra_5cr_pf_interest_and_damages"] = run_scenario(inputs, working, extra_oneoff=5)
    historical = {
        "market_cap": inputs["price_inr"] * shares_cr,
        "fy26_selected_owner_cash": selected(a),
        "fy25_selected_owner_cash": selected(b),
        "fy26_selected_cash_per_share": selected(a) / shares_cr,
        "fy26_selected_cash_yield": selected(a) / shares_cr / inputs["price_inr"],
        "fy26_selected_cash_dividend_coverage": selected(a) / a["dividends_paid"],
        "fy25_selected_cash_dividend_coverage": selected(b) / b["dividends_paid"],
        "fy26_cfo_dividend_coverage": a["cfo"] / a["dividends_paid"],
        "fy26_selected_cash_plus_treasury_receipts": selected(a) + a["asset_sale_proceeds"] + a["interest_received"] + a["mutual_fund_dividends_including_reinvestment"],
        "fy26_operating_ebitda": a["revenue"] - a["employee_expense"] - a["other_expense"],
        "fy26_revenue_growth": a["revenue"] / b["revenue_including_other_operating_income"] - 1,
        "management_fee_growth": a["management_fees"] / b["management_fees"] - 1,
        "q1_operating_ebitda": q["revenue"] - q["employee_expense"] - q["other_expense"],
        "q1_operating_ebitda_margin": (q["revenue"] - q["employee_expense"] - q["other_expense"]) / q["revenue"],
        "prior_q1_operating_ebitda_margin": (q["previous_revenue"] - q["previous_employee_expense"] - q["previous_other_expense"]) / q["previous_revenue"],
        "q1_revenue_growth": q["revenue"] / q["previous_revenue"] - 1,
        "q1_pat_growth": q["pat"] / q["previous_pat"] - 1,
        "q1_payroll_growth": q["employee_expense"] / q["previous_employee_expense"] - 1,
        "annualized_q1_revenue_not_forecast": q["revenue"] * 4,
        "declared_fy26_dividend_amount": inputs["dividends"]["fy26_declared_per_share"] * shares_cr,
        "declared_fy26_dividend_yield": inputs["dividends"]["fy26_declared_per_share"] / inputs["price_inr"],
        "june_unencumbered_treasury_upper_bound": free_june,
        "final_dividend_amount_reserved_even_without_payment_receipt": final_div,
        "june_treasury_less_committed_final_dividend_before_any_operating_cash_need": free_june - final_div,
        "fy26_related_services_rendered": sum(a["related_services_rendered"]),
        "fy26_related_services_rendered_revenue_fraction": sum(a["related_services_rendered"]) / a["revenue"],
        "fy26_related_services_received": sum(a["related_services_received"]),
        "fy26_related_billed_unbilled_receivables": related(a),
        "fy25_related_billed_unbilled_receivables": related(b),
        "related_receivable_increase": related(a) - related(b),
        "related_receivables_fraction_of_total": related(a) / a["trade_receivables_including_unbilled"],
        "net_contract_fulfillment_asset_increase": a["contract_fulfillment_asset_current"] + a["contract_fulfillment_asset_noncurrent"] - b["contract_fulfillment_asset_current"] - b["contract_fulfillment_asset_noncurrent"],
        "working_recurring_owner_cash_year1": y1_owner,
        "working_recurring_owner_cash_per_share_year1": y1_owner / shares_cr,
        "working_recurring_owner_cash_yield": y1_owner / shares_cr / inputs["price_inr"],
        "working_current_owner_cash_multiple": no_compression_multiple,
        "working_annual_dividend_80_cash_shortfall": inputs["dividends"]["fy26_declared_per_share"] * shares_cr - y1_owner
    }
    return {"historical_and_normalization": historical, "scenarios": cases,
            "working_sensitivities": sensitivities, "scenario_probabilities": None,
            "future_realized_prices": None, "realized_outcomes": None}


if __name__ == "__main__":
    data = json.loads((HERE / "decision_inputs.json").read_text())
    result = calculate(data)
    assert abs(result["historical_and_normalization"]["fy26_selected_owner_cash"] - 44.4507) < 1e-8
    assert all(c["funded_without_external_financing"] for c in result["scenarios"].values())
    assert data["shares"] == 14926261
    assert result["scenario_probabilities"] is None and result["realized_outcomes"] is None
    (HERE / "decision_calculations.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, case in result["scenarios"].items():
        print(f"{name}: {case['annualized_return']:.4%}, Y1 recurring owner cash {case['rows'][0]['recurring_owner_cash']:.4f}cr, funded={case['funded_without_external_financing']}")
