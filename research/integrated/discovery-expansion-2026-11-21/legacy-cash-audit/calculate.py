#!/usr/bin/env python3
"""Narrow audit of published eClerx/CAMS cash-retention conventions.

No new primary operating facts or buy recommendations. The zero-retention
eClerx columns are counterfactual diagnostics, NOT the published model.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def irr(cash):
    lo, hi = -.95, 3
    for _ in range(180):
        r = (lo + hi) / 2
        if sum(v/(1+r)**i for i,v in enumerate(cash)) > 0:
            lo = r
        else:
            hi = r
    return (lo + hi) / 2


def eclerx(d, g, mult, keep):
    cash = [d['starting_selected_cash']*(1+g)**t for t in range(1,6)]
    dividends = [v*d['distribution_fraction']/d['shares_crore'] for v in cash]
    retained = sum(cash)*(1-d['distribution_fraction']) if keep else 0
    terminal = (cash[-1]*mult+d['opening_treasury_credit']+retained)/d['shares_crore']
    flows = [-d['price']]+dividends
    flows[-1] += terminal
    return {'growth':g,'terminal_multiple':mult,'retained_cash_added_at_exit':retained,
            'terminal_price':terminal,'cashflows':flows,'irr':irr(flows),
            'prices_at_returns':{str(r):sum(v/(1+r)**t for t,v in enumerate(flows[1:],1)) for r in [.08,.10,.12]}}


def cams_price(d,g,n,r,multiple):
    shares=d['shares_crore']
    annual=[d['starting_selected_cash']*(1+g)**t/(shares*(1+d['annual_dilution'])**t) for t in range(1,n+1)]
    return d['opening_treasury_credit']/shares+sum(v/(1+r)**t for t,v in enumerate(annual,1))+multiple*annual[-1]/(1+r)**n


def main():
    d=json.loads((HERE/'inputs.json').read_text())
    rows=[]
    for x in d['eclerx']['published_cases']:
        yes=eclerx(d['eclerx'],x['growth'],x['terminal_multiple'],True)
        no=eclerx(d['eclerx'],x['growth'],x['terminal_multiple'],False)
        assert abs(100*yes['irr']-x['published_irr_pct']) < .006
        rows.append({'published_case':x,'published_formula_reproduction':yes,
                     'counterfactual_if_retention_were_omitted':no,
                     'retention_effect_percentage_points':100*(yes['irr']-no['irr'])})
    c=d['cams'];lo,hi=-.5,1
    for _ in range(150):
        g=(lo+hi)/2
        if cams_price(c,g,10,.10,25)>c['price']:hi=g
        else:lo=g
    growth=(lo+hi)/2
    old_mstc=eclerx(d['mstc'],.10,15,False)
    retained_mstc=eclerx(d['mstc'],.10,15,True)
    o={'audit_scope':'Cash-retention treatment only. Source documents are inherited repository artifacts, not newly authenticated financial filings.',
       'finding':'NO_RETENTION_OMISSION_IN_REVIEWED_ECLERX_AND_CAMS_MODELS',
       'eclerx':rows,
       'mstc':{'finding':'AMBIGUOUS_FUNDING_TREATMENT_NOT_AN_IRR_ARITHMETIC_ERROR',
               'original_no_retained_cash_credit_convention':old_mstc,
               'bounded_all_retained_cash_accumulates_without_return':retained_mstc,
               'incremental_irr_percentage_points':100*(retained_mstc['irr']-old_mstc['irr']),
               'limit':'The old note did not say whether retained 50% funds additional growth uses or remains cash. The add-back is valid only if no additional spending consumes it. This is not the new funded MSTC model and is not a normalized forecast.'},
       'cams':{'company_cash_growth_for_10y_10pct_25x':growth,
               'recomputed_price':cams_price(c,growth,10,.10,25),
               'annual_distribution_fraction':1.0,'retained_future_cash_to_add':0,
               'opening_treasury_credit_per_share':c['opening_treasury_credit']/c['shares_crore'],
               'limit':'Reverse valuation assumes future cash is after every reinvestment use. It does not establish that growth can be funded.'},
       'original_files_changed':False,'decision_change':'None from this accounting check alone.'}
    (HERE/'outputs.json').write_text(json.dumps(o,indent=2)+'\n')
    print(json.dumps({'finding':o['finding'],'cams':o['cams'],'mstc':o['mstc'],'eclerx_reproduced_pct':[100*x['published_formula_reproduction']['irr'] for x in rows]},indent=2))


if __name__=='__main__':
    main()
