"""Independent annual cash and tranche-interest reconstruction from a frozen input snapshot.
Does not import the author calculator. No network or writes outside this review folder.
"""
from datetime import date
from pathlib import Path
import json
import copy
D=Path(__file__).resolve().parent
I=json.loads((D/'rsystems_independent_input_snapshot.json').read_text())
F=I['facts']; C=I['common_assumptions']
START=date.fromisoformat(C['forecast_start'])


def irr(flow):
    a,b=-.95,4
    for _ in range(180):
        r=(a+b)/2
        value=sum(v/(1+r)**((d-START).days/365.25) for d,v in flow)
        if value>0:a=r
        else:b=r
    return (a+b)/2


def independent(case,changes=None):
    changes=changes or {};s=copy.deepcopy(I['scenarios'][case]); c=copy.deepcopy(C)
    s.update(changes.get('scenario',{}));c.update(changes.get('common',{}))
    rsu=changes.get('remaining_rsu',F['rsu_authorised_plan_capacity']-F['rsu_shares_issued_2025']-F['rsu_shares_issued_nine_month_2026'])
    stock_claim=max(8*s['novigo_assumed_average_fy26_fy27_ebitda']-400,0)
    shares=(F['issued_shares_sep_2026']+F['velotio_ocrps_one_for_one_shares']+rsu)/1e7+stock_claim/s['novigo_assumed_issue_price']
    bank=F['sep_2026_cash_equivalents']+F['sep_2026_other_bank_balances']-F['sep_dividend_already_paid_october']-F['sep_current_borrowings']-c['other_loan_and_restricted_cash_reserve']-changes.get('legacy_gratuity',0)
    tranches=[(date.fromisoformat(d),F['ncd_face']/6) for d in F['ncd_repayment_dates']]
    sales=c['opening_revenue_run_rate']; amounts=[]; out=[];flows=[(START,-I['price'])]
    for k in range(1,7):
        begin=START.replace(year=START.year+k-1);end=START.replace(year=START.year+k)
        old=sales;sales*=1+(s['first_year_revenue_growth'] if k==1 else s['later_revenue_growth'])
        ebitda=sales*s['cash_ebitda_margin_before_existing_sbc']
        rent=sales*c['cash_lease_rate']; investment=sales*(c['maintenance_capex_rate']+c['growth_capex_rate'])
        working=(sales-old)*c['working_capital_increment_rate']
        if working<0:working*=1-s['working_capital_release_haircut']
        comp=sales*c['new_compensation_cash_rate'] if k>=c['new_compensation_cycle_start_year'] else 0
        # Each equal debt tranche accrues only until its actual maturity.
        interest=sum(v*F['ncd_coupon']*max(0,(min(end,d)-begin).days)/365.25 for d,v in tranches)
        principal=sum(v for d,v in tranches if begin<=d<end)
        tax=max(0,ebitda-rent-comp-interest-sales*c['owned_tax_depreciation_rate']-c['acquisition_amortization_tax_deduction'])*c['cash_tax_rate']
        flow=ebitda-rent-investment-working-comp-interest-tax-(s['one_time_receivable_loss'] if k==1 else 0)
        amounts.append(flow)
        if k==6:break
        available=bank+flow-principal
        paid=min(max(0,(flow-principal)*c['cash_distribution_fraction_after_principal']),max(0,available-c['operating_cash_floor']))
        bank=available-paid
        flows.append((end,paid/shares));out.append({'year':k,'sales':sales,'owner_cash':flow,'interest':interest,'principal':principal,'distribution':paid,'bank':bank})
    terminal_flow=amounts[4] if changes.get('terminal_year5') else amounts[5]
    terminal=(terminal_flow*s['terminal_next_year_cash_multiple']+max(0,bank-c['operating_cash_floor']))/shares
    flows[-1]=(flows[-1][0],flows[-1][1]+terminal)
    return {'irr':irr(flows),'shares':shares*1e7,'terminal_price':terminal,'terminal_owner_cash':terminal_flow,'rows':out,'cashflows':[[str(d),v] for d,v in flows]}

base={k:independent(k) for k in I['scenarios']}
author=json.loads((D/'author_results_snapshot.json').read_text())
checks={}
for k,r in base.items():
    a=author['scenarios'][k]
    checks[k]={'irr_difference':r['irr']-a['xirr'],'terminal_price_difference':r['terminal_price']-a['terminal_price'],'shares_difference':r['shares']-a['fully_diluted_shares'],'max_interest_difference':max(abs(x['interest']-y['cash_interest']) for x,y in zip(r['rows'],a['annual_ledger']))}
    assert abs(checks[k]['irr_difference'])<1e-10
    assert abs(checks[k]['terminal_price_difference'])<1e-8
sensitivity={
 'terminal_year5':independent('base',{'terminal_year5':True}),
 'legacy_gratuity_66_975':independent('base',{'legacy_gratuity':66.975}),
 'actual_fy25_grant_count_less_9m26_issues_proxy':independent('base',{'remaining_rsu':5945625-92376}),
 'margin18_5_futurecomp1_25_year4_and_gratuity':independent('base',{'scenario':{'cash_ebitda_margin_before_existing_sbc':.185},'common':{'new_compensation_cash_rate':.0125,'new_compensation_cycle_start_year':4},'legacy_gratuity':66.975}),
 'favorable_operating_evidence_8pctgrowth_19_5margin':independent('base',{'scenario':{'first_year_revenue_growth':.08,'later_revenue_growth':.08,'cash_ebitda_margin_before_existing_sbc':.195}}),
 'author_base_plus_tax_shield_42_4':independent('base',{'common':{'acquisition_amortization_tax_deduction':42.4}})
}
result={'snapshot_date':'2026-11-20','independent_implementation':True,'replication_checks':checks,'reconstructed_scenarios':base,'sensitivity':sensitivity,'limitations':'Reproduces mathematicalassumptions, notvalidatedfuturecash, taxdeductibility, currentRSUgrantcount or Novigoswapratio. Legacygratuitystress is alternative if150cashflooralreadyearmarkedforthatpurpose, not anautomaticadditionaldoublecharge.'}
(D/'rsystems_independent_calculations.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'checks':checks,'base_irr':{k:v['irr'] for k,v in base.items()},'sensitivity_irr':{k:v['irr'] for k,v in sensitivity.items()}},indent=2))
