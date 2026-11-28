#!/usr/bin/env python3
"""MSTC cash ownership and five-year owner-cash sensitivities. INR crore unless per-share.

All retained cash is accounted for. Float principal belongs to counterparties.
Float earnings and returns on assumed own treasury are distinct. No new-platform
revenue, legal receivable recovery or separate joint-venture terminal value is used.
"""
from pathlib import Path
import json
import copy

HERE=Path(__file__).resolve().parent

def irr(cash):
    lo,hi=-0.999,10.0
    for _ in range(200):
        r=(lo+hi)/2
        value=sum(x/(1+r)**t for t,x in enumerate(cash))
        if value>0: lo=r
        else: hi=r
    return (lo+hi)/2

def run(inp,s,price=None):
    f=inp['facts']; a=inp['common_assumptions']
    price=f['price'] if price is None else price
    shares=f['shares_crore']; rev=f['ttm_revenue']; treasury=s['opening_usable_treasury']
    years=[]
    for year in range(1,a['years']+1):
        previous_rev=rev; opening_cash=treasury
        rev*=1+s['revenue_growth']
        pre_wc=rev*s['pre_wc_cash_margin']
        depreciation=rev*a['depreciation_to_sales']
        tax=max(0,pre_wc-depreciation)*a['tax_rate']
        wc=max(0,rev-previous_rev)*s['incremental_wc_to_sales']
        capex=rev*s['all_core_capex_to_sales']
        float_income=s['aftertax_float_income_year1']*(1+s['float_income_growth'])**(year-1)
        core_cash=pre_wc-tax-capex-wc+float_income-f['ttm_cash_interest_paid']
        own_interest=max(0,opening_cash)*a['treasury_interest_rate']*(1-a['tax_rate'])
        platform=s['platform_cash_spend'][year-1]
        legal=s['additional_unreserved_legal_cash_outflow'][year-1]
        available=core_cash+own_interest-platform-legal
        dividend=max(0,available)*s['payout']
        treasury=opening_cash+available-dividend
        funding_gap=max(0,-treasury)
        assert abs(treasury-(opening_cash+core_cash+own_interest-platform-legal-dividend))<1e-8
        years.append({'year':year,'revenue':rev,'pre_wc_cash':pre_wc,'depreciation':depreciation,'normalized_operating_tax':tax,'core_capex':capex,'incremental_working_capital':wc,'float_income_aftertax':float_income,'recurring_core_cash_after_reinvestment':core_cash,'own_treasury_interest_aftertax':own_interest,'platform_spend':platform,'extra_legal_cash_cost':legal,'total_owner_cash_after_all_investment':available,'dividend_cash':dividend,'dividend_per_share':dividend/shares,'treasury_open':opening_cash,'treasury_close':treasury,'unfunded_cash_gap':funding_gap})
    last=years[-1]
    terminal_core=last['recurring_core_cash_after_reinvestment']*s['terminal_core_cash_multiple']
    terminal_cash=treasury*s['terminal_treasury_realization']
    terminal=(terminal_core+terminal_cash)/shares
    dividends=[y['dividend_per_share'] for y in years]
    flows=[-price]+dividends
    flows[-1]+=terminal
    pv=lambda rate:sum(v/(1+rate)**(i+1) for i,v in enumerate(dividends))+terminal/(1+rate)**len(years)
    return {'name':s['name'],'entry_price':price,'annualized_return':irr(flows),'terminal_price':terminal,'terminal_core_value':terminal_core,'terminal_treasury_value':terminal_cash,'terminal_treasury_before_discount':treasury,'total_dividends_per_share':sum(dividends),'total_core_capex':sum(y['core_capex'] for y in years),'total_platform_spend':sum(y['platform_spend'] for y in years),'total_incremental_wc':sum(y['incremental_working_capital'] for y in years),'max_funding_gap':max(y['unfunded_cash_gap'] for y in years),'price_return_map':{str(r):pv(r) for r in [0.06,0.08,0.10,0.12]},'return_at_prices':{str(p):irr([-p]+dividends[:-1]+[dividends[-1]+terminal]) for p in [450,500,550,600,656.55]},'years':years}

def main():
    inp=json.loads((HERE/'inputs.json').read_text()); f=inp['facts']
    own_cash_residual=f['september_cash_and_equivalents']+f['september_other_bank_balances']-f['september_other_current_financial_liabilities']-f['september_borrowings']-f['september_trade_payables']
    core_proxy=f['ttm_pre_working_capital_cash_ex_interest']-f['ttm_actual_cash_tax']-f['ttm_all_ppe_capital_advance_payments']-f['ttm_cash_interest_paid']
    normalized_tax=max(0,f['ttm_pre_working_capital_cash_ex_interest']-f['ttm_revenue']*inp['common_assumptions']['depreciation_to_sales'])*inp['common_assumptions']['tax_rate']
    results={key:run(inp,s) for key,s in inp['scenarios'].items()}
    sensitivities={}
    for name,overrides in {
      'base_without_float_income':{'aftertax_float_income_year1':0},
      'base_no_opening_treasury_credit':{'opening_usable_treasury':0},
      'base_full_treasury_realization':{'terminal_treasury_realization':1},
      'base_growth_12pct':{'revenue_growth':0.12},
      'base_growth_15pct':{'revenue_growth':0.15},
      'base_extra_platform_cost_100':{'platform_cash_spend':[100,50,0,0,0]},
      'base_joint_legal_and_float_stress':{'aftertax_float_income_year1':0,'additional_unreserved_legal_cash_outflow':[100,0,0,0,0],'terminal_core_cash_multiple':12}
    }.items():
        s=copy.deepcopy(inp['scenarios']['base']);s.update(overrides);s['name']=name
        sensitivities[name]=run(inp,s)
    out={'classification':'BOUNDED_CASH_OWNERSHIP_SCENARIOS','historical_bridge':{'market_cap':f['price']*f['shares_crore'],'ttm_pat':f['ttm_pat'],'ttm_reported_pe':f['price']*f['shares_crore']/f['ttm_pat'],'ttm_pre_wc_cash_margin':f['ttm_pre_working_capital_cash_ex_interest']/f['ttm_revenue'],'ttm_core_cash_proxy_before_float_and_own_interest':core_proxy,'normalized_tax_sensitivity':normalized_tax,'normalized_core_cash_at_unchanged_actual_capex':f['ttm_pre_working_capital_cash_ex_interest']-normalized_tax-f['ttm_all_ppe_capital_advance_payments']-f['ttm_cash_interest_paid'],'cash_only_residual_before_other_claims_and_buffers':own_cash_residual},'scenarios':results,'sensitivities':sensitivities}
    (HERE/'outputs.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'historical_bridge':out['historical_bridge'],'scenario_returns':{k:v['annualized_return'] for k,v in results.items()},'base_prices':results['base']['price_return_map'],'sensitivity_returns':{k:v['annualized_return'] for k,v in sensitivities.items()}},indent=2))

if __name__=='__main__':main()
