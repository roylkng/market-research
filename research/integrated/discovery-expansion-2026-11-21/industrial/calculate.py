#!/usr/bin/env python3
"""PIX funded owner-cash valuation. Python standard library only.

Run: python calculate.py [inputs.json] [outputs.json]
Amounts are INR crore. Shares are crore, so division yields INR/share.
Forecasts are scenarios, not a backtest or probability-weighted prediction.
"""
import copy
import json
import math
import sys
from pathlib import Path


def irr(cashflows):
    def npv(rate):
        return sum(c / (1 + rate) ** i for i, c in enumerate(cashflows))
    lo, hi = -0.95, 5.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(180):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def actuals(d):
    fy, h, old = d['fy2026'], d['h1_2026'], d['h1_2025']
    t = {k: fy[k] + h[k] - old[k]
         for k in ['sales', 'pbt', 'other_income', 'interest', 'da', 'pat', 'cfo', 'capex']}
    t['core_ebit'] = t['pbt'] + t['interest'] - t['other_income'] + fy['fvtpl_loss_in_other_expenses']
    t['core_ebit_margin'] = t['core_ebit'] / t['sales']
    t['core_nopat_at_26pct_tax'] = t['core_ebit'] * .74
    t['core_after_interest_at_26pct_tax'] = (t['core_ebit'] - t['interest']) * .74
    t['reported_eps'] = t['pat'] / d['shares_crore']
    t['core_eps_at_26pct_tax'] = t['core_after_interest_at_26pct_tax'] / d['shares_crore']
    t['reported_pe'] = d['price'] / t['reported_eps']
    t['core_pe_at_26pct_tax'] = d['price'] / t['core_eps_at_26pct_tax']
    t['cash_after_capex_and_interest'] = t['cfo'] - t['capex'] - t['interest']
    t['market_cap'] = d['price'] * d['shares_crore']
    b = d['balance_2026_09_30']
    t['reported_net_cash_excluding_other_bank'] = b['cash_equivalents'] + b['investments_fvtpl'] - b['debt']
    t['operating_working_capital'] = b['inventory'] + b['receivables'] + b['other_current_assets'] - b['trade_payables'] - b['other_financial_current_liabilities'] - b['other_current_liabilities']
    t['operating_working_capital_to_ttm_sales'] = t['operating_working_capital'] / t['sales']
    return t


def run_case(d, s, price=None):
    a = actuals(d)
    b = d['balance_2026_09_30']
    sales = a['sales']
    # Existing liabilities and required operating buffer cannot be counted as
    # owner excess cash. Debt is carried explicitly, not netted at this step.
    opening_excess = b['cash_equivalents'] + b['investments_fvtpl'] * s['portfolio_value_fraction'] - b['legacy_provisions_reserved'] - sales * s['cash_buffer_ratio']
    excess = opening_excess
    debt = b['debt']
    rows = []
    owner_flows = []
    funding_gap = 0.0
    for i, (g, margin) in enumerate(zip(s['growth'], s['ebit_margin']), 1):
        previous_sales = sales
        sales *= 1 + g
        incremental_sales = sales - previous_sales
        ebit = sales * margin
        nopat = ebit * (1 - s['tax'])
        da = sales * s['da_ratio']
        maintenance = sales * s['maintenance_capex_ratio']
        growth_capex = max(0, incremental_sales) * s['growth_capex_per_incremental_sales']
        wc = incremental_sales * s['working_capital_ratio']
        # If the adverse case requires more working capital on all existing
        # sales, fund that catch-up in year one, not only incremental growth.
        wc_catchup = max(0, a['sales'] * s['working_capital_ratio'] - a['operating_working_capital']) if i == 1 else 0.0
        wc += wc_catchup
        buffer = incremental_sales * s['cash_buffer_ratio']
        interest = debt * s['debt_interest_rate']
        funded_cash = nopat - interest * (1 - s['tax']) + da - maintenance - growth_capex - wc - buffer
        treasury_income = max(0, excess) * s['treasury_after_tax_return']
        dividend = max(max(0, funded_cash) * s['dividend_payout_of_funded_cash'],
                       s['dividend_floor_per_share'] * d['shares_crore'])
        repayment = min(debt, d['debt_repayment_by_year'][i-1])
        debt -= repayment
        end_excess = excess + treasury_income + funded_cash - dividend - repayment
        funding_gap = max(funding_gap, max(0, -end_excess))
        rows.append(dict(year=i, revenue=sales, ebit=ebit, nopat=nopat,
                         da=da, maintenance_capex=maintenance,
                         growth_capex=growth_capex, working_capital_investment=wc,
                         working_capital_catchup=wc_catchup,
                         operating_cash_buffer_increase=buffer,
                         interest=interest, funded_owner_cash=funded_cash,
                         dividend=dividend, dividend_per_share=dividend/d['shares_crore'],
                         treasury_income=treasury_income, opening_excess_cash=excess,
                         debt_repayment=repayment,
                         closing_excess_cash=end_excess, debt=debt))
        excess = end_excess
        owner_flows.append(dividend / d['shares_crore'])
    terminal_operation = rows[-1]['nopat'] * s['terminal_nopat_multiple']
    recognized_cash = excess * s['terminal_cash_recognition']
    terminal_equity = terminal_operation + recognized_cash - debt
    terminal_per_share = terminal_equity / d['shares_crore']
    terminal_owner_flows = owner_flows[:]
    terminal_owner_flows[-1] += terminal_per_share
    p = d['price'] if price is None else price
    return dict(opening_excess_cash=opening_excess, years=rows,
                cumulative_funded_owner_cash=sum(x['funded_owner_cash'] for x in rows),
                cumulative_dividends=sum(x['dividend'] for x in rows),
                cumulative_capex=sum(x['maintenance_capex']+x['growth_capex'] for x in rows),
                cumulative_working_capital=sum(x['working_capital_investment'] for x in rows),
                maximum_unfunded_gap=funding_gap,
                terminal_operating_value=terminal_operation,
                terminal_recognized_cash=recognized_cash,
                terminal_equity_value=terminal_equity, terminal_price=terminal_per_share,
                dividends_per_share=owner_flows,
                cashflows_per_share=[-p]+terminal_owner_flows,
                annualized_return=irr([-p]+terminal_owner_flows),
                values_at_required_returns={str(r):sum(c/(1+r)**(i+1) for i,c in enumerate(terminal_owner_flows)) for r in [.08,.10,.11,.12,.14]},
                owner_cash_yield_on_entry_year1=rows[0]['funded_owner_cash']/(p*d['shares_crore']))


def main():
    root = Path(__file__).resolve().parent
    src = Path(sys.argv[1]) if len(sys.argv)>1 else root/'inputs.json'
    dst = Path(sys.argv[2]) if len(sys.argv)>2 else root/'outputs.json'
    d = json.loads(src.read_text())
    o = {'as_of':d['as_of'], 'reference_price':d['price'], 'ttm_actuals':actuals(d),
         'scenarios':{k:run_case(d,s) for k,s in d['scenarios'].items()}}
    o['entry_price_sensitivity'] = {str(p):{k:run_case(d,s,p)['annualized_return'] for k,s in d['scenarios'].items()} for p in [1300,1400,1450,1500,1600,d['price'],1800]}
    o['base_return_sensitivity'] = []
    for growth in [.06,.08,.10,.12]:
        for margin in [.225,.245,.266,.27]:
            s = copy.deepcopy(d['scenarios']['base'])
            s['growth']=[growth]*5
            s['ebit_margin']=[margin]*5
            o['base_return_sensitivity'].append(dict(growth=growth, margin=margin, annualized_return=run_case(d,s)['annualized_return']))
    o['base_terminal_multiple_sensitivity'] = {}
    for multiple in [12,14,16,18,20]:
        s=copy.deepcopy(d['scenarios']['base'])
        s['terminal_nopat_multiple']=multiple
        v=run_case(d,s)
        o['base_terminal_multiple_sensitivity'][str(multiple)] = {
            'annualized_return':v['annualized_return'],
            'terminal_operating_value_to_year5_funded_cash':v['terminal_operating_value']/v['years'][-1]['funded_owner_cash'],
            'value_at_11pct':v['values_at_required_returns']['0.11']}
    o['falsification_cases'] = {}
    for name, changes in {
        'full_treasury_credit': {'portfolio_value_fraction':1.0,'terminal_cash_recognition':1.0},
        'current_margin_persists': {'ebit_margin':[.266]*5},
        'growth_10pct_current_margin': {'growth':[.10]*5,'ebit_margin':[.266]*5},
        'higher_capacity_productivity': {'growth_capex_per_incremental_sales':.25},
    }.items():
        s = copy.deepcopy(d['scenarios']['base'])
        s.update(changes)
        v = run_case(d,s)
        o['falsification_cases'][name] = {'changed_assumptions':changes, 'annualized_return':v['annualized_return'], 'value_at_11pct':v['values_at_required_returns']['0.11']}
    # Arithmetic identities check the economic model, not its predictive merit.
    for c in o['scenarios'].values():
        for row in c['years']:
            expected = row['opening_excess_cash'] + row['treasury_income'] + row['funded_owner_cash'] - row['dividend'] - row['debt_repayment']
            assert math.isclose(expected,row['closing_excess_cash'],abs_tol=1e-8)
        assert math.isclose(sum(c['cashflows_per_share'][i]/(1+c['annualized_return'])**i for i in range(6)),0,abs_tol=1e-7)
        assert c['maximum_unfunded_gap'] == 0
    dst.write_text(json.dumps(o,indent=2)+'\n')
    print(json.dumps({'ttm':o['ttm_actuals'], 'summary':{k:{'annualized_return':v['annualized_return'],'terminal_price':v['terminal_price'],'value_at_11pct':v['values_at_required_returns']['0.11'],'capex':v['cumulative_capex'],'cash_y1':v['years'][0]['funded_owner_cash']} for k,v in o['scenarios'].items()}},indent=2))


if __name__ == '__main__':
    main()
