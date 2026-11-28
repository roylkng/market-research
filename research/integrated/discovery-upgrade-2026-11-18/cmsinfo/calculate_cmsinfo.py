#!/usr/bin/env python3
"""Reproduce the dated CMSINFO cash bridge. INR crore, unless stated.

Inputs transcribed from issuer statutory consolidated cash flow statements.
These are cash after selected uses, not normalized distributable owner cash.
No company share-price target or investment permission is generated.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
periods = {
    'FY25': {'cfo':482.528, 'ppe_intangible_cash':154.337, 'lease_principal':44.025, 'lease_interest':17.987, 'other_interest':0.210},
    'FY26': {'cfo':389.594, 'ppe_intangible_cash':409.268, 'lease_principal':50.817, 'lease_interest':18.504, 'other_interest':0.975},
    'H1FY26': {'cfo':-116.945, 'ppe_intangible_cash':173.942, 'lease_principal':23.443, 'lease_interest':8.337, 'other_interest':0.324},
    'H1FY27': {'cfo':177.255, 'ppe_intangible_cash':149.442, 'lease_principal':41.774, 'lease_interest':12.036, 'other_interest':0.293},
}
periods['TTM_20260930'] = {k:periods['FY26'][k]-periods['H1FY26'][k]+periods['H1FY27'][k] for k in periods['FY26']}
for p in periods.values():
    p['cash_after_selected_uses'] = p['cfo']-sum(p[k] for k in ['ppe_intangible_cash','lease_principal','lease_interest','other_interest'])
shares_cr = 16.0063
price = 205.35
cap = shares_cr*price
ttm_pat = 303.392-166.932+164.573

def pv(cash, growth, multiple, hurdle):
    annual = [cash*(1+growth)**t for t in range(1,6)]
    return sum(c/(1+hurdle)**t for t,c in enumerate(annual,1)) + annual[-1]*multiple/(1+hurdle)**5

# A reverse scenario, not a claim these assumptions are forecasts or approved hurdles.
reverse = []
for h in [0.10,0.12,0.15]:
    for g in [0.0,0.05,0.08]:
        required = cap/pv(1,g,12,h)
        reverse.append({'required_return':h,'growth':g,'year5_owner_cash_multiple':12,'starting_annual_cash_required_cr':required})
result = {
    'classification':'PRELIMINARY_ORIGINAL_DOCUMENT_CASH_REVIEW_NOT_NORMALIZED_VALUATION',
    'price_date':'2026-11-18','reference_close':price,'shares_cr_last_reported_20260930':shares_cr,
    'market_cap_cr_on_last_reported_shares':cap,'periods':periods,
    'ttm_owner_pat_cr':ttm_pat,'market_cap_to_ttm_pat':cap/ttm_pat,
    'ttm_selected_cash_yield':periods['TTM_20260930']['cash_after_selected_uses']/cap,
    'reverse_cash_scenarios_no_separate_cash_addon':reverse,
    'limitations':['Share denominator is last reported capital, not a fully reconciled post-September diluted count.',
      'Cash measures exclude acquisitions, disposals, treasury income, financing principal changes and shareholder distributions.',
      'Growth presumes incremental investment and working capital have already been funded in the cash number.',
      'Five-year DCF values annual owner-available cash plus year-five cash multiple, not actual promised dividends.',
      'No separate net-cash balance is added and no second lease-liability deduction is made.',
      'Historical cash is seasonal. Neither H1 annualization nor the TTM figure is certified sustainable.',
      'No probability weights, user-approved hurdle, execution assumption, tax or transaction costs.']
}
(ROOT/'cmsinfo_calculations.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'periods':periods,'cap':cap,'pe':cap/ttm_pat,'cash_yield':result['ttm_selected_cash_yield'],'reverse':reverse},indent=2))
