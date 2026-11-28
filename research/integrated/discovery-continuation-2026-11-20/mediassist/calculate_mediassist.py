#!/usr/bin/env python3
"""Dated scenario model. INR crore and shares in crore. No data retrieval or policy writes."""
from pathlib import Path
import json
from copy import deepcopy
HERE=Path(__file__).resolve().parent
I=json.loads((HERE/'decision_inputs.json').read_text())

def irr(cfs):
    lo,hi=-0.95,5.0
    def npv(r): return sum(c/(1+r)**t for t,c in enumerate(cfs))
    if npv(lo)*npv(hi)>0: return None
    for _ in range(180):
        mid=(lo+hi)/2
        if npv(mid)>0:lo=mid
        else:hi=mid
    return (lo+hi)/2

def model(case,overrides=None):
    a=I['common_assumptions']; r=I['reported']; s=deepcopy(I['scenarios'][case]); o=overrides or {}
    s.update(o.get('scenario',{}))
    buyback=o.get('buyback',True)
    dilution=o.get('dilution',True)
    options=r['mar26']['option_count']-r['h1_option_exercises']
    shares=(r['issued_shares']-(r['buyback_shares'] if buyback else 0)+(options if dilution else 0))/1e7
    gross=sum(r['sep26'][k] for k in ['cash_equivalents','other_bank_balances','current_investments'])
    deductions={
      'restricted_deposit_proxy':r['mar26']['restricted_current_bank_deposits'],
      'current_tax':r['sep26']['current_tax_liability'],
      'declared_sep_dividend':a['pending_september_dividend_per_share']*r['issued_shares']/1e7,
      'buyback_plus_cost':(r['buyback_cash']+a['buyback_transaction_cost']) if buyback else 0,
      'operating_reserve':s['operating_cash_reserve'],
      'legacy_gratuity_proxy':r['mar26']['defined_benefit_obligation']-r['mar26']['defined_benefit_assets']}
    for k in o.get('release_deductions',[]):deductions[k]=0
    cash=gross-sum(deductions.values())+o.get('additional_initial_cash',0)
    initial_cash=cash
    revenues={k:v*4 for k,v in r['q2_revenue_seed'].items()}
    previous_revenue=sum(revenues.values()); rows=[]; cfs=[-I['price']]
    payout=o.get('payout',a['payout_ratio'])
    taxdep=o.get('tax_dep',a['cash_tax_depreciation_rate'])
    for n in range(1,6):
        revenues={k:v*(1+s['growth'][k]) for k,v in revenues.items()}
        revenue=sum(revenues.values());ebitda=revenue*s['ebitda_margins'][n-1]
        leases=revenue*s['lease_cash_rate'];capex=revenue*s['capex_rate']
        taxable=max(0,ebitda-leases-revenue*taxdep)
        tax=taxable*a['tax_rate']
        wc=(revenue-previous_revenue)*s['incremental_working_capital_rate']
        extra=s['initial_cash_collection_loss'] if n==1 else 0
        group_cash=ebitda-leases-capex-tax-wc-extra
        owner_cash=group_cash*(1-s['minority_leakage_rate'])
        treasury_income=cash*a['cash_treasury_yield_after_tax']
        distributable=owner_cash+treasury_income
        distribution=max(0,distributable*payout)
        cash+=distributable-distribution
        row={'year':n,'revenues':dict(revenues),'revenue':revenue,'ebitda_margin':s['ebitda_margins'][n-1],
             'ebitda':ebitda,'lease_cash':leases,'capex_cash':capex,'cash_tax':tax,'incremental_wc':wc,
             'cash_collection_loss':extra,'owner_operating_cash':owner_cash,'treasury_income':treasury_income,
             'distribution':distribution,'distribution_per_share':distribution/shares,'closing_treasury':cash}
        rows.append(row);cfs.append(distribution/shares);previous_revenue=revenue
    terminal_operating_value=rows[-1]['owner_operating_cash']*s['exit_multiple']
    terminal_equity=terminal_operating_value+cash
    cfs[-1]+=terminal_equity/shares
    return {'case':case,'shares_crore':shares,'remaining_options':options,'initial_gross_current_liquidity':gross,
            'deductions':deductions,'initial_surplus_cash':initial_cash,'assumptions':s,'rows':rows,
            'terminal_operating_value':terminal_operating_value,'terminal_cash':cash,'terminal_equity':terminal_equity,
            'terminal_share_price':terminal_equity/shares,'cashflows_per_share':cfs,'irr':irr(cfs),
            'pv_prices':{str(r):sum(c/(1+r)**n for n,c in enumerate(cfs[1:],1)) for r in [.08,.10,.12,.15]}}

R=I['reported'];ttm={k:R['fy26'][k]+R['h1fy27'][k]-R['h1fy26'][k] for k in R['fy26']}
for p in ['fy26','h1fy26','h1fy27']:
    x=R[p];x['selected_cash_after_capex_lease_interest']=x['cfo']-x['capex']-x['lease_cash']-x['interest_cash_ex_lease']
ttm['selected_cash_after_capex_lease_interest']=ttm['cfo']-ttm['capex']-ttm['lease_cash']-ttm['interest_cash_ex_lease']
ttm['net_working_capital_cash']=ttm['cfo']+ttm['tax_cash']-ttm['pre_wc_cash']
ttm['market_cap']=I['price']*R['issued_shares']/1e7
ttm['reported_pat_multiple']=ttm['market_cap']/ttm['owner_pat']
ttm['fy26_h2_tax_cash']=R['fy26']['tax_cash']-R['h1fy26']['tax_cash']
ttm['reported_pat_less_BTA_deferred_tax_adjustment']=ttm['owner_pat']-R['tax_bta_adjustment_fy26']
out={'identity':I['security'],'reference_date':I['price_date'],'reference_price':I['price'],'reported_periods':R,
     'ttm':ttm,'scenarios':{k:model(k) for k in I['scenarios']},'sensitivity':{}}
for m in [10,12,14,16,18]:out['sensitivity']['working_exit_'+str(m)]=model('working',{'scenario':{'exit_multiple':m}})
for cap in [.035,.045,.055,.065]:out['sensitivity']['working_capex_'+str(cap)]=model('working',{'scenario':{'capex_rate':cap}})
for td in [.02,.04,.06]:out['sensitivity']['working_taxdep_'+str(td)]=model('working',{'tax_dep':td})
out['sensitivity']['working_no_buyback']=model('working',{'buyback':False})
out['sensitivity']['working_no_option_dilution']=model('working',{'dilution':False})
out['sensitivity']['working_released_reserves']=model('working',{'release_deductions':['restricted_deposit_proxy','operating_reserve','legacy_gratuity_proxy']})
out['sensitivity']['working_released_reserves_plus_tax_assets']=model('working',{'release_deductions':['restricted_deposit_proxy','operating_reserve','legacy_gratuity_proxy'],'additional_initial_cash':R['sep26']['income_tax_assets']})
out['sensitivity']['working_no_payout']=model('working',{'payout':0})
out['sensitivity']['working_100pct_payout']=model('working',{'payout':1})
# Proportionate scaling of all operating owner cash, keeping same shareholder distributions/treasury convention.
b=out['scenarios']['working'];n=b['shares_crore'];cash0=b['initial_surplus_cash'];p=I['price'];y=I['common_assumptions']['cash_treasury_yield_after_tax']
def scaled_irr(mult):
    cash=cash0;fs=[-p]
    for row in b['rows']:
        cashflow=row['owner_operating_cash']*mult+cash*y
        paid=cashflow*.5;cash+=cashflow-paid;fs.append(paid/n)
    fs[-1]+=(b['rows'][-1]['owner_operating_cash']*mult*14+cash)/n
    return irr(fs)
requirements={}
for target in [.08,.10,.12,.15]:
    lo,hi=.01,5
    for _ in range(100):
        mid=(lo+hi)/2
        if scaled_irr(mid)<target:lo=mid
        else:hi=mid
    mult=(lo+hi)/2
    requirements[str(target)]={'scale_all_year_cash':mult,'year1_owner_cash':b['rows'][0]['owner_operating_cash']*mult,'year5_owner_cash':b['rows'][-1]['owner_operating_cash']*mult,'scope':'Proportionate cash-path improvement with same14xexit, payouts and openingcash. A reverse sensitivity, not a forecast or required threshold policy.'}
out['reverse_cash_requirements']=requirements
(HERE/'decision_calculations.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'ttm':ttm,'scenarios':{k:{'irr':v['irr'],'y1_owner_cash':v['rows'][0]['owner_operating_cash'],'y5_owner_cash':v['rows'][-1]['owner_operating_cash'],'pv_prices':v['pv_prices'],'terminal_share_price':v['terminal_share_price']} for k,v in out['scenarios'].items()},'sensitivity_irr':{k:v['irr'] for k,v in out['sensitivity'].items()},'reverse':requirements},indent=2))
