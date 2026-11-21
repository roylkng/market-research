"""Read-only KRSNAA continuation. INR crore except prices and share counts.

Inputs are manual, page-reviewed transcriptions of signed issuer documents.
This model does not alter CC001 state or any frozen experiment.
"""
from pathlib import Path
import json
import hashlib

HERE = Path(__file__).resolve().parent
PRICE = 511.30
ISSUED_SHARES = 32_438_672
FULL_EXERCISE_SHARES = ISSUED_SHARES + 1_005_607 + 1_621_000

def pv(rate, terminal, dividend=2.0):
    return sum(dividend / (1 + rate) ** t for t in range(1, 6)) + terminal / (1 + rate) ** 5

def irr(terminal, price=PRICE, dividend=2.0):
    lo, hi = -0.99, 4.0
    for _ in range(160):
        middle = (lo + hi) / 2
        if pv(middle, terminal, dividend) > price:
            lo = middle
        else:
            hi = middle
    return (lo + hi) / 2

periods = {
    "fy26": {"cfo":143.098,"ppe_intangible_cash":219.259,"lease_cash":13.954,"interest_cash":26.578},
    "h1fy26": {"cfo":51.874,"ppe_intangible_cash":103.571,"lease_cash":4.550,"interest_cash":12.128},
    "h1fy27": {"cfo":78.796,"ppe_intangible_cash":250.263,"lease_cash":8.137,"interest_cash":29.085},
}
periods["ttm_sep26"] = {k:periods["fy26"][k]+periods["h1fy27"][k]-periods["h1fy26"][k] for k in periods["fy26"]}
for values in periods.values():
    values["cash_after_selected_uses"] = values["cfo"]-values["ppe_intangible_cash"]-values["lease_cash"]-values["interest_cash"]

scenarios=[]
for name,eps,growth,multiple in [("stress",18,.05,12),("working",22,.15,16),("stronger_execution",22,.18,18),("bull",25,.20,20)]:
    terminal = eps*(1+growth)**5*multiple
    scenarios.append({"name":name,"starting_eps":eps,"eps_growth":growth,"terminal_pe":multiple,
                      "terminal_price":terminal,"illustrative_annual_dividend":2.0,
                      "modeled_annual_return":irr(terminal),
                      "entry_value_by_return_preference":{str(r):pv(r,terminal) for r in [.10,.12,.15]}})

cash_capacity_h1 = 133.820 - 11.845 - 29.085 - 8.137
cash_capacity_cost_reserved_annual = 2*(cash_capacity_h1 - 2.670 - .670)
annual_adb_principal_sensitivity = 2*430/13
budget=[]
for maintenance in [60,90,120]:
    for working_capital_absorption in [0,25,50]:
        residual=cash_capacity_cost_reserved_annual-maintenance-working_capital_absorption-annual_adb_principal_sensitivity
        budget.append({"assumed_annual_maintenance":maintenance,
                       "assumed_annual_wc_absorption":working_capital_absorption,
                       "annual_adb_principal_stress":annual_adb_principal_sensitivity,
                       "capacity_remaining_for_growth_capex_other_debt_principal_dividends":residual})

receivable_sensitivity=[]
for cash_mix in [.25,.40,.50]:
    credit_sales=270*(1-cash_mix)
    receivable_sensitivity.append({"assumed_quarter_revenue":270,"assumed_cash_mix":cash_mix,
      "credit_billings":credit_sales,"assumed_total_credit_collections":200,
      "ending_receivables_before_other_movements":474.556+credit_sales-200,
      "total_credit_collections_needed_for_receivables_350":474.556+credit_sales-350})

report={
 "assessment_date":"2026-11-19","reference_price_date":"2026-11-18","reference_price":PRICE,
 "identity":{"symbol":"KRSNAA","isin":"INE08LI01020","series":"EQ"},
 "issued_share_reference_date":"2026-03-31, corroborated only to H1 rounded paid-up capital",
 "issued_share_reference":ISSUED_SHARES,"full_exercise_sensitivity_share_count":FULL_EXERCISE_SHARES,
 "market_cap_on_issued_reference":PRICE*ISSUED_SHARES/1e7,
 "full_exercise_not_current_market_cap":PRICE*FULL_EXERCISE_SHARES/1e7,
 "day_volume":104589,"day_turnover_crore":53483724.8/1e7,
 "previous_reference_price":493.60,"previous_reference_date":"2026-11-09",
 "raw_reference_price_change_percent":100*(PRICE/493.6-1),
 "not_executable_or_action_cleared_return":True,
 "reported_ttm_owner_pat":101.431+41.138-44.465,
 "identified_apulki_after_tax_gain_removed":22.241,
 "ttm_owner_pat_less_identified_gain":101.431+41.138-44.465-22.241,
 "full_exercise_conditional_remaining_warrant_proceeds":68.81145,
 "march_options_conditional_exercise_proceeds":32.1529451,
 "cash_periods":periods,
 "h1_cash_capacity_before_wc_and_capex":cash_capacity_h1,
 "cash_capacity_definition":"Pre-WC operating cash less current-tax charge, cash interest and full reported lease cash. No treasury cash added. Not normalized owner FCF.",
 "annualized_capacity_after_full_credit_provision_and_sbc_reserves":cash_capacity_cost_reserved_annual,
 "capacity_limitations":"Doubled H1 diagnostic, not forecast. Reserves retain full pre-tax credit provision and SBC as economic costs. They are not additional historical cash payments. Maintenance and working-capital levels are analyst assumptions. No bank amortization, incremental dilution, future growth capex or dividend is funded automatically.",
 "cash_capacity_budget":budget,
 "receivables":{"march25_net":277.745,"march26_net":295.506,"sep26_net":474.556,
                "march25_considered_good_aged_1_2_years":.282,"march26_considered_good_aged_1_2_years":38.334,
                "march26_considered_good_over_6months":47.383+38.334,
                "march26_share_considered_good_over_6months":(47.383+38.334)/295.506,
                "march26_credit_impaired_provision":7.340},
 "receivables_collection_sensitivity":receivable_sensitivity,
 "collection_sensitivity_warning":"The issuer's 200cr visibility was not explicitly defined as all quarter credit collections. Table applies only IF it were total credit collections. No post-September actual receipt is asserted.",
 "scenarios":scenarios,
 "conditional_year5_parent_profit_on_full_exercise_shares":{"working":22*1.15**5*FULL_EXERCISE_SHARES/1e7,"stronger_execution":22*1.18**5*FULL_EXERCISE_SHARES/1e7},
 "adb_allotment_date":"2026-02-23",
 "adb_first_principal_due_schedule_inference":"2026-08-23, inferred from six-month contractual start. Individual payment not verified.",
 "reverse_growth_working_eps22_terminal16":{str(r):((PRICE-sum(2/(1+r)**t for t in range(1,6)))*(1+r)**5/(22*16))**.2-1 for r in [.10,.12,.15]},
 "decision":"WATCH_EVIDENCE_AT_CURRENT_PRICE",
 "primary_next_check":"Q3 collections and receivable ageing reconciled with supplier payments, maintenance/growth capital and amortizing debt. Same-price stronger execution route remains open.",
 "no_universal_return_hurdle_assumed":True,
 "growth_funding_status":"EPS paths are sensitivities, not independently reconciled financed operating forecasts. The cash-capacity budget states why the higher-growth path is conditional.",
 "equity_valuation_no_double_count":"No second debt subtraction from after-interest EPS. No surplus cash, warrant cash, Apulki value, sale/leaseback proceeds or retained earnings added to terminal equity value. Dividends reduce retained earnings conceptually, but the EPS growth rates have not been certified as fully fundable.",
 "economic_returns_validated":False,
 "verification":{"h1_cash_identity":78.796-86.169+54.552,"reported_cash_increase":47.179,
                 "lease_note_full_cash_fy26":9.955+3.999,"cashflow_lease_fy26":13.954,
                 "critical_pdf_pages_visually_inspected":["h1_fy27.pdf p8","annual_fy26.pdf p219 (printed231)","annual_fy26.pdf p235 (printed247)"]}
}
assert abs(report["verification"]["h1_cash_identity"]-47.179)<1e-9
assert abs(report["verification"]["lease_note_full_cash_fy26"]-13.954)<1e-9
assert abs(periods["ttm_sep26"]["cash_after_selected_uses"]+257.007)<1e-9
(HERE/'krsnaa_calculations_2026-11-19.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({"price":PRICE,"decision":report['decision'],"scenarios":scenarios,"cash_capacity_h1":cash_capacity_h1},indent=2))
