#!/usr/bin/env python3
"""Deterministic FDC owner-cash and retained-treasury scenarios. Python stdlib only."""
import json, copy
from pathlib import Path
P=Path(__file__).resolve().parent
I=json.loads((P/'decision_inputs.json').read_text())
S=I['security']; C=I['model_common']; B=I['balance_sep26']; R=copy.deepcopy(I['reported'])
for a in R.values():
    a['ebitda_ex_other_before_exceptional']=a['pbt']+a['exceptional']+a['da']+a['finance_cost']-a['other_income']
    a['cash_after_all_capex_finance_and_lease']=a['cfo']-a['capex']-a['finance_cash']-a['lease_cash']
R['TTM']= {k:R['FY26'][k]+R['H1FY27'][k]-R['H1FY26'][k] for k in R['FY26']}
T=R['TTM']; Qpost=(S['shares_pre']-S['buyback_shares'])/1e7; Qpre=S['shares_pre']/1e7

def pv(cfs,r): return sum(v/(1+r)**(j+1) for j,v in enumerate(cfs))
def irr(cfs,price):
    lo,hi=-.95,2
    for _ in range(160):
        mid=(lo+hi)/2
        if pv(cfs,mid)>price:lo=mid
        else:hi=mid
    return (lo+hi)/2

def run(a,buyback=True,ebitda_scale=1,rate_override=None,capex_delta=0,extra_employee_settlement=0):
    q=Qpost if buyback else Qpre
    inv=B['investments_noncurrent']+B['investments_current']
    cash=inv*(1-a['portfolio_haircut'])+B['cash']-C['operating_cash_buffer']-a['claim_buffer']-B['current_tax_liability']
    cash+=sum(I['tax_refund_orders_cr'])*C['refund_credit_fraction']
    if buyback:cash-=S['buyback_shares']*S['buyback_price']/1e7+S['buyback_cost_reserve_cr']
    cash0=cash
    m=T['ebitda_ex_other_before_exceptional']/T['revenue'] if isinstance(a['margin'],str) else a['margin']
    rows=[]
    for j in range(5):
        revenue=T['revenue']*(1+a['revenue_growth'])**(j+1)
        eb=revenue*m*ebitda_scale
        tax=max(0,(eb-C['lease_cash'][j]-C['physical_da'][j]-C['other_financing_cash'])*C['normalized_tax_rate'])
        capex=a['total_capex'][j]+(capex_delta if j==0 else 0)
        core=eb-C['lease_cash'][j]-tax-capex-a['working_capital_use'][j]-C['other_financing_cash']
        tr=cash*(a['treasury_return_after_tax'] if rate_override is None else rate_override)
        dividends=C['dividend_per_share']*q
        extra_settlement=extra_employee_settlement if j==0 else 0
        closing=cash+tr+core-dividends-extra_settlement
        rows.append(dict(year=j+1,revenue=revenue,ebitda=eb,margin=m*ebitda_scale,lease_cash=C['lease_cash'][j],normalized_core_tax=tax,total_capex=capex,working_capital_use=a['working_capital_use'][j],core_owner_cash=core,core_owner_cash_per_share=core/q,opening_treasury=cash,after_tax_treasury_return=tr,dividends=dividends,additional_employee_settlement=extra_settlement,closing_treasury=closing))
        cash=closing
    terminal_core=rows[-1]['core_owner_cash']*a['terminal_core_fcf_multiple']
    terminal=(terminal_core+cash)/q
    cfs=[C['dividend_per_share']]*5;cfs[-1]+=terminal
    return dict(shares_crore=q,starting_credited_financial_assets=cash0,rows=rows,terminal_core_value=terminal_core,terminal_treasury=cash,terminal_price=terminal,cashflows_per_share=cfs,irr_at_reference=irr(cfs,S['price']),reference_pv={str(x):pv(cfs,x) for x in [.08,.10,.12,.15]})

out={'reported_and_ttm':R,'derived':{'pre_buyback_market_cap':Qpre*S['price'],'post_buyback_market_cap_at_same_price':Qpost*S['price'],'ttm_pe_before_buyback':Qpre*S['price']/T['pat'],'ttm_core_profit_at_normalized_tax':(T['pbt']+T['exceptional']-T['other_income'])*.75,'buyback_cash_without_costs':S['buyback_shares']*S['buyback_price']/1e7,'shares_removed_pct':S['buyback_shares']/S['shares_pre']*100},'scenarios':{k:run(a) for k,a in I['scenarios'].items()}}
a=I['scenarios']['working']
out['working_no_buyback']=run(a,False)
out['working_zero_treasury_yield']=run(a,rate_override=0)
out['working_extra_100_capex_year1']=run(a,capex_delta=100)
out['working_additional_employee_settlement_stress']=run(a,extra_employee_settlement=R['FY26']['exceptional'])
out['reverse_valuation']={}
for r in [.08,.10,.12,.15]:
    lo,hi=.5,3
    for _ in range(120):
        mid=(lo+hi)/2;z=run(a,ebitda_scale=mid)
        if pv(z['cashflows_per_share'],r)<S['price']:lo=mid
        else:hi=mid
    z=run(a,ebitda_scale=(lo+hi)/2)
    out['reverse_valuation'][str(r)]={'ebitda_scale':(lo+hi)/2,'margin':z['rows'][0]['margin'],'year1_ebitda':z['rows'][0]['ebitda'],'year5_ebitda':z['rows'][4]['ebitda'],'year5_core_cash':z['rows'][4]['core_owner_cash']}
assert abs(R['FY26']['cash_after_all_capex_finance_and_lease']-1.6995)<1e-8
assert abs(Qpost-16.0410084)<1e-9
assert all(x['terminal_treasury']>0 for x in out['scenarios'].values())
(P/'decision_calculations.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'derived':out['derived'],'scenarios':{k:{'irr':v['irr_at_reference'],'terminal_price':v['terminal_price'],'year1_cash':v['rows'][0]['core_owner_cash'],'year5_cash':v['rows'][-1]['core_owner_cash'],'pv':v['reference_pv']} for k,v in out['scenarios'].items()},'reverse':out['reverse_valuation'],'sensitivity':{k:out[k]['irr_at_reference'] for k in ['working_no_buyback','working_zero_treasury_yield','working_extra_100_capex_year1','working_additional_employee_settlement_stress']}},indent=2))
