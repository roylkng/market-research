#!/usr/bin/env python3
"""Reproduce NRAIL cash bridge and explicit project/funding scenarios. No network or ledger writes."""
import copy,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
I=json.loads((HERE/'decision_inputs.json').read_text())
SH=I['shares']/1e7

def irr(price, flows):
    lo,hi=-0.9999,10.0
    def npv(r): return sum(c/(1+r)**(t+1) for t,c in enumerate(flows))-price
    assert npv(lo)>0 and npv(hi)<0
    for _ in range(200):
        mid=(lo+hi)/2
        if npv(mid)>0:lo=mid
        else:hi=mid
    return (lo+hi)/2

def model(s):
    d=I['balance_sep26']['gross_borrowings']
    cash_credit=I['balance_sep26']['cash']+I['balance_sep26']['current_investments']*I['model']['current_investment_credit']
    div=I['model']['annual_dividend_per_share']*SH
    rows=[]
    for j in range(I['model']['horizon_years']):
        e=s['old_ebitda'][j]+s['new_ebitda'][j]-s['lease_cash'][j]
        dn=d
        for _ in range(200):
            interest=s['cash_funding_rate']*(d+dn)/2
            tax=max(0,e-s['physical_depreciation'][j]-interest)*I['model']['tax_rate']
            cash_before_project=e-interest-tax-s['maintenance_capex'][j]-s['incremental_working_capital'][j]
            dn=d-cash_before_project+s['project_capex'][j]+div
        assert abs(dn-(d-cash_before_project+s['project_capex'][j]+div))<1e-8
        rows.append({'year':j+1,'gross_debt_open':d,'existing_ebitda':s['old_ebitda'][j],'new_ebitda':s['new_ebitda'][j],'postlease_ebitda':e,'lease_cash':s['lease_cash'][j],'physical_depreciation':s['physical_depreciation'][j],'cash_interest':interest,'normalized_cash_tax':tax,'maintenance_capex':s['maintenance_capex'][j],'incremental_working_capital':s['incremental_working_capital'][j],'project_capex':s['project_capex'][j],'cash_before_project':cash_before_project,'dividend':div,'gross_debt_close':dn})
        d=dn
    terminal_ev=e*s['terminal_ev_postlease_ebitda']
    terminal_eq=max(0,terminal_ev-d+cash_credit)
    terminal_price=terminal_eq/SH
    flows=[I['model']['annual_dividend_per_share']]*5
    flows[-1]+=terminal_price
    return {'annual_rows':rows,'future_project_capex':sum(s['project_capex']),'credited_cash_and_investments':cash_credit,'terminal_ev':terminal_ev,'terminal_gross_debt':d,'terminal_net_debt':d-cash_credit,'terminal_equity':terminal_eq,'terminal_price':terminal_price,'five_year_irr_at_reference':irr(I['price_inr'],flows),'pv_per_share':{str(r):sum(c/(1+r)**(t+1) for t,c in enumerate(flows)) for r in [0.10,0.12,0.15]},'reference_price':I['price_inr']}

out={'units':I['units'],'price':I['price_inr'],'shares_crore':SH,'market_cap':I['price_inr']*SH}
cr=copy.deepcopy(I['cash_rows'])
cr['TTM_Sep26']={k:cr['FY26'][k]-cr['H1FY26'][k]+cr['H1FY27'][k] for k in cr['FY26']}
for v in cr.values():v['cash_after_all_capex_interest_and_total_lease']=v['cfo']-v['capex']-v['nonlease_interest_cash']-v['total_lease_cash']
out['cash_bridge']=cr
out['mechanical_ttm_pe']=out['market_cap']/cr['TTM_Sep26']['pat']
out['mechanical_doubled_h1_pe']=out['market_cap']/(2*cr['H1FY27']['pat'])
out['gross_debt_increase_h1']=I['balance_sep26']['gross_borrowings']-I['balance_mar26']['gross_borrowings']
h=I['h1fy27'];out['h1_ebitda_ex_other_income']=h['pbt']+h['pnl_finance_cost']+h['depreciation']-h['other_income']
out['h1_inventory_plus_receivables_absorption']=h['inventory_cash_absorption']+h['receivables_cash_absorption']
out['scenarios']={k:model(v) for k,v in I['model']['scenarios'].items()}
base=I['model']['scenarios']['working'];sens=[]
for spend in [1100,1250,1375]:
    b=copy.deepcopy(base);b['project_capex']=[x*spend/1250 for x in b['project_capex']];r=model(b)
    sens.append({'remaining_noninterest_project_spend':spend,'irr':r['five_year_irr_at_reference'],'pv12':r['pv_per_share']['0.12']})
out['capex_overlap_sensitivity']=sens
rev=[]
for target in [0.10,0.12,0.15]:
    lo,hi=0.,1000.
    for _ in range(120):
        mid=(lo+hi)/2;b=copy.deepcopy(base);b['new_ebitda'][-1]=mid
        if model(b)['five_year_irr_at_reference']<target:lo=mid
        else:hi=mid
    rev.append({'target_irr':target,'required_new_plant_year5_ebitda':(lo+hi)/2,'interpretation':'One-factor EBITDA sensitivity with fixed working capital, maintenance and depreciation. A margin-change case, not a free higher-volume case.'})
out['reverse_new_plant_ebitda']=rev
stress=copy.deepcopy(base);stress['incremental_working_capital'][0]+=50
r=model(stress);out['supplier_finance_runoff_50_once']={'irr':r['five_year_irr_at_reference'],'pv12':r['pv_per_share']['0.12'],'reason':'FY26 bill/vendor-finance acceptances95.2579. A50 runoff is charged once in working capital, not also as debt.'}
out['limitations']=['Not calibrated forecasts or probabilities','Normalized economic cash tax uses full modeled cash interest as deduction and physical depreciation, not a company tax-return forecast','Future interest-capex decomposition unresolved and sensitivity explicit','Total-lease cash included once. No additional lease-debt subtraction under postlease valuation','Borrowing/refinancing assumed available, not verified financial closure','No investor tax, trading costs, fill or position-size model','September balances held as latest disclosed initial state despite November price','Dividends modeled at2 yearly, not promised','No noncurrent investments, other bank balances, asset-sale proceeds or separate project residual value added','All project cash retained in debt bridge, not distributed again']
(HERE/'decision_calculations.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['market_cap','mechanical_ttm_pe','mechanical_doubled_h1_pe','gross_debt_increase_h1','h1_ebitda_ex_other_income']},indent=2))
for k,v in out['scenarios'].items():print(k,{a:v[a] for a in ['terminal_price','terminal_net_debt','five_year_irr_at_reference','pv_per_share']})
print('reverse',rev)
