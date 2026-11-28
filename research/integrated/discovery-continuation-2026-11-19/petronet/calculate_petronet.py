"""Bounded Petronet cash/funding and reverse-project-return diagnostic.

This is not a full company valuation. It deliberately leaves a stock target,
expected investment return and success probability uncomputed.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SHARES = 1_500_000_088
PRICE = 325.50
periods = {
    'standalone_fy25': dict(cfo=4397.70,ppe=1451.79,intangibles=5.11,interest=9.55,leases=642.07),
    'standalone_fy26': dict(cfo=4753.06,ppe=2511.84,intangibles=7.26,interest=9.31,leases=690.43),
    'standalone_h1_fy26': dict(cfo=1815.56,ppe=533.24,intangibles=0,interest=5.81,leases=348.50),
    'standalone_h1_fy27': dict(cfo=2914.37,ppe=1685.56,intangibles=.47,interest=5.56,leases=38.64),
    'consolidated_fy26': dict(cfo=4750.04,ppe=2511.84,intangibles=7.26,interest=9.31,leases=690.43),
    'consolidated_h1_fy26': dict(cfo=1813.44,ppe=533.24,intangibles=0,interest=5.81,leases=348.50),
    'consolidated_h1_fy27': dict(cfo=2983.52,ppe=1688.56,intangibles=.52,interest=5.56,leases=35.56),
}
for v in periods.values():
    v['cash_after_selected_uses'] = v['cfo']-v['ppe']-v['intangibles']-v['interest']-v['leases']

def project_cash_required(rate, cost, delay_years=0):
    # Analyst allocation of remaining project budget, NOT issuer payment guidance.
    spending = [(1,cost*.40),(2,cost*.45),(3,cost*.15)]
    pv_cost = sum(c/(1+rate)**t for t,c in spending)
    annuity_factor = sum(1/(1+rate)**t for t in range(4+delay_years,29+delay_years))
    return {'discount_rate':rate,'remaining_cost':cost,'assumed_spending':spending,
            'first_full_cash_year':4+delay_years,'operating_years':25,
            'level_annual_after_tax_project_cash_required':pv_cost/annuity_factor,
            'cash_definition':'After operating costs, cash taxes, sustaining capex and working capital, before financing. No terminal salvage.'}

def main():
    cap = PRICE*SHARES/1e7
    standalone_ttm_pat=3842.67-1656.33+2368.12
    group_ttm_pat=3912.53-1672.18+2393.57
    output={
        'classification':'BOUNDED_PRIMARY_SOURCE_FUNDING_REVIEW_NOT_FULL_COMPANY_UNDERWRITING',
        'decision':'WATCH_CAPITAL_ALLOCATION',
        'identity':{'symbol':'PETRONET','isin':'INE347G01014','series':'EQ'},
        'price':PRICE,'price_date':'2026-11-18','shares':SHARES,
        'share_basis':'FY26 audited exact share count, unchanged rounded September capital, no new November capital audit claimed',
        'market_cap_cr':cap,'periods':periods,
        'standalone_ttm_selected_cash':periods['standalone_fy26']['cash_after_selected_uses']-periods['standalone_h1_fy26']['cash_after_selected_uses']+periods['standalone_h1_fy27']['cash_after_selected_uses'],
        'group_ttm_selected_cash':periods['consolidated_fy26']['cash_after_selected_uses']-periods['consolidated_h1_fy26']['cash_after_selected_uses']+periods['consolidated_h1_fy27']['cash_after_selected_uses'],
        'standalone_ttm_pat':standalone_ttm_pat,'group_ttm_pat':group_ttm_pat,
        'standalone_ttm_pe':cap/standalone_ttm_pat,'group_ttm_pe':cap/group_ttm_pat,
        'h1_parent_current_tax_cash_gap':851.00-643.41,
        'q2_efficiency_gains_share_of_parent_pbt':658/1659.10,
        'september_parent_cash_current_investments_other_bank':2238.37+806.83+9344.43,
        'cash_caveat':'Other bank includes restricted/earmarked balances. March group restriction examples total201.39cr, not a freshly verified September restriction amount. Capital projects also consume these funds.',
        'march_group_known_earmarked_or_lien_bank':29.49+59.90+112.00,
        'september_parent_lease_liability':1448.20+664.86,
        'november_declared_interim_dividend_company_outflow_cr':7*SHARES/1e7,
        'new_buyer_entitlement_to_this_dividend':False,
        'dividend_record_date':'2026-11-06',
        'petrochemical_approved_cost_cr':20685,
        'petrochemical_spent_through_september_management_cr':3300,
        'arithmetic_unspent_petchem_budget_cr':20685-3300,
        'management_remaining_fy27_aggregate_capex_cr':9000-1626,
        'management_fy28_aggregate_capex_cr':9000,
        'committed_undrawn_march_bank_facilities_cr':12000,
        'bank_facility_caveat':'Not a cash asset or equity value. Drawdown creates debt and interest. March undrawn status plus September balance-sheet no borrowings, not independent current bank confirmation.',
        'other_project_reference_budgets_cr':{'third_jetty':2013,'gopalpur':6354.80,'cbg_total_jv':1200,'cbg_company_ownership':.5},
        'project_reverse_hurdles':[project_cash_required(r,17385) for r in [.10,.12,.15]],
        'project_20pct_overrun_one_year_delay_at12':project_cash_required(.12,17385*1.2,1),
        'project_hurdle_limits':'Illustrative remaining-investment decision using 40/45/15 spending allocation. Not full-project IRR, exact approved payment schedule, company price target, cash forecast, or double-counted company funding deficit.',
        'stock_fair_value':None,'stock_expected_return':None,'probability_of_outperformance':None,
        'reason_null':'Normalized recurring regas/trading cash and funded per-share project economics not fully reconciled. A low P/E alone is insufficient.'
    }
    (ROOT/'petronet_calculations_2026-11-19.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in ['periods','project_hurdle_limits']},indent=2))

if __name__=='__main__':
    main()
