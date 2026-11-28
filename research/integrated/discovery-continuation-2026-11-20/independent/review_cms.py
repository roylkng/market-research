"""Separate CMS cash/valuation implementation, never imports the analyst calculator."""
from pathlib import Path
import json
import copy

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / 'cms_input_snapshot.json').read_text())
reported = json.loads((HERE.parent / 'cms/decision_calculations.json').read_text())


def present_value(flows, discount):
    return sum(amount * (1 + discount) ** -period for period, amount in enumerate(flows, 1))


def yield_from_flows(flows):
    low, high = -.95, 2
    for _ in range(140):
        guess = (low + high) / 2
        if present_value(flows, guess) > data['reference_close_inr']:
            low = guess
        else:
            high = guess
    return (low + high) / 2


def reconstruct(assumptions, consistent_capex=None, extra_finance=0, cash_credit=1):
    balance = data['opening_balance_sheet']
    reserve = (balance['cash'] + balance['current_investments'] + balance['noncurrent_investments']
               - balance['operating_liquidity_reserve_assumption'] - assumptions['opening_extra_risk_reserve'])
    equity_count = data['shares_cr_asof_2026_09_30']
    rows, flows = [], []
    preceding_sales = None
    for n in range(5):
        sales = assumptions['revenue_y1'] * (1 + assumptions['revenue_growth']) ** n
        operating_profit = assumptions['cash_ebitda_margin'] * sales
        occupancy_cash = assumptions['lease_cash_y1'] * (1 + assumptions['lease_growth']) ** n
        allowance = assumptions['tax_depreciation_proxy_y1'] * (1 + assumptions['tax_depreciation_growth']) ** n
        tax = max(0, operating_profit - occupancy_cash - allowance) * data['global_assumptions']['tax_rate']
        investment = assumptions['cash_capex_y1'] if n == 0 else assumptions['later_capex_to_sales'] * sales
        if consistent_capex is not None:
            investment = consistent_capex * (1 + assumptions['revenue_growth']) ** n
        working_capital = assumptions['wc_y1'] if n == 0 else (sales - preceding_sales) * assumptions['incremental_wc_to_sales']
        working_capital += extra_finance
        owner_money = operating_profit - occupancy_cash - tax - investment - working_capital
        payout = assumptions['dividend_y1'] * (1 + assumptions['dividend_growth']) ** n
        reserve += owner_money - payout
        equity_count *= 1 + assumptions['annual_share_dilution']
        flows.append(payout / equity_count)
        rows.append({'period':n+1, 'owner_cash':owner_money, 'cash_balance':reserve, 'shares_cr':equity_count})
        preceding_sales = sales
    terminal = (owner_money * assumptions['exit_owner_cash_multiple'] + reserve * cash_credit) / equity_count
    flows[-1] += terminal
    return {'irr':yield_from_flows(flows), 'terminal_price':terminal, 'cashflows':flows, 'rows':rows,
            'pv_12_percent':present_value(flows, .12), 'minimum_cash':min(r['cash_balance'] for r in rows)}


comparisons = {}
for name, inputs in data['scenarios'].items():
    result = reconstruct(inputs)
    expected = reported['scenarios'][name]
    differences = {
        'irr':abs(result['irr'] - expected['annualized_return']),
        'terminal_price':abs(result['terminal_price'] - expected['terminal_price']),
        'cashflows':max(abs(a-b) for a,b in zip(result['cashflows'],expected['cashflows_per_share'])),
        'owner_cash':max(abs(r['owner_cash']-e['owner_cash_before_dividend']) for r,e in zip(result['rows'],expected['years']))
    }
    assert max(differences.values()) < 1e-8, (name, differences)
    comparisons[name] = {'result':result, 'absolute_differences':differences}

working = data['scenarios']['working']
stress = copy.deepcopy(working)
stress.update(cash_ebitda_margin=.245, exit_owner_cash_multiple=10)
checks = {
    'consistent_200_capex_then_sales_growth':reconstruct(working,consistent_capex=200),
    'joint_stress_245margin_250capex_10xexit_25finance':reconstruct(stress,consistent_capex=250,extra_finance=25),
    '75percent_terminal_cash_credit':reconstruct(working,cash_credit=.75)
}
hist = data['historical']
ttm = {k:hist['FY26'][k]+hist['H1FY27'][k]-hist['H1FY26'][k] for k in hist['FY26']}
residual = ttm['cfo']-ttm['cash_capex']-ttm['lease_principal']-ttm['lease_interest']-ttm['other_interest']-ttm['customer_loan_advance']+ttm['customer_loan_repaid']
assert abs(residual-143.802)<1e-8
out = {
    'scope':'Separate arithmetic reproduction with explicit adverse scenarios, not prospective validation',
    'all_three_scenarios_reproduced':True,
    'scenarios':comparisons,
    'challenges':checks,
    'ttm_selected_cash_after_net_customer_financing_cr':residual,
    'material_interpretations':[
        'The 12.5% working case requires first-year ₹200cr capex, then 6.5% of sales. Keeping ₹200cr growing with sales gives 10.8%.',
        'Existing and future full lease cash is charged. Do not subtract the entire lease balance again at exit.',
        'Opening free treasury excludes the operating reserve and loan book. Retained cash is credited only once.',
        'The March option exercise test is a sensitivity. Existing options and future grants are not independently forecast.',
        'Combining customer financing with operating cash neutralizes a presentation benefit. It must not be claimed as verified customer cash collection.',
        'Cash capex around ₹250cr instead of ₹200cr materially weakens the case. No arbitrary 15% hurdle is needed to identify that risk.'
    ],
    'not_verified':['Future capex mix and amounts','Recoverability of aged receivables','Terminal market multiple','Independent customer corroboration','Investment outperformance']
}
(HERE/'cms_independent_review.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'scenario_irrs':{k:v['result']['irr'] for k,v in comparisons.items()},'challenge_irrs':{k:v['irr'] for k,v in checks.items()},'cash_residual_cr':residual},indent=2))
