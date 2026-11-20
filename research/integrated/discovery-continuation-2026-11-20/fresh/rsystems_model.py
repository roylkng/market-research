#!/usr/bin/env python3
"""Dated funded owner-cash model. INR crore except per-share amounts.

No packages, no network and no external inputs. No statistical probability claim.
Run from any directory. Writes only adjacent rsystems_model_results.json.
"""
import copy
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = json.loads((ROOT / 'rsystems_inputs.json').read_text())


def cash_residual(period):
    return period['cfo'] - period['ppe_capex'] - period['intangible_capex'] - period['lease_cash'] - period['interest_cash']


def xnpv(rate, payments):
    start = payments[0][0]
    return sum(amount / (1 + rate) ** ((date - start).days / 365.25) for date, amount in payments)


def xirr(payments):
    low, high = -0.99, 5.0
    assert xnpv(low, payments) > 0 and xnpv(high, payments) < 0
    for _ in range(160):
        mid = (low + high) / 2
        if xnpv(mid, payments) > 0:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def calc(name, scenario_overrides=None, common_overrides=None, price=None):
    f = INPUT['facts']
    c = copy.deepcopy(INPUT['common_assumptions'])
    s = copy.deepcopy(INPUT['scenarios'][name])
    c.update(common_overrides or {})
    s.update(scenario_overrides or {})
    price = INPUT['price'] if price is None else price
    start = dt.date.fromisoformat(c['forecast_start'])
    paydates = [dt.date.fromisoformat(x) for x in f['ncd_repayment_dates']]
    plan_remaining = f['rsu_authorised_plan_capacity'] - f['rsu_shares_issued_2025'] - f['rsu_shares_issued_nine_month_2026']
    pre_novigo_shares = f['issued_shares_sep_2026'] + f['velotio_ocrps_one_for_one_shares'] + plan_remaining
    earnout_value = max(0.0, f['novigo_earnout_ebitda_multiple'] * s['novigo_assumed_average_fy26_fy27_ebitda'] - f['novigo_upfront_consideration'])
    novigo_shares = earnout_value * 1e7 / s['novigo_assumed_issue_price']
    shares = pre_novigo_shares + novigo_shares
    shares_crore = shares / 1e7
    cash = f['sep_2026_cash_equivalents'] + f['sep_2026_other_bank_balances'] - f['sep_dividend_already_paid_october'] - f['sep_current_borrowings'] - c['other_loan_and_restricted_cash_reserve']
    opening_cash = cash
    revenue = c['opening_revenue_run_rate']
    debt = f['ncd_face']
    schedule_payment = debt / len(paydates)
    payments = [(start, -price)]
    rows = []

    for year in range(1, c['years'] + 2):
        begin = start.replace(year=start.year + year - 1)
        end = start.replace(year=start.year + year)
        prior_revenue = revenue
        growth = s['first_year_revenue_growth'] if year == 1 else s['later_revenue_growth']
        revenue = prior_revenue * (1 + growth)
        ebitda = revenue * s['cash_ebitda_margin_before_existing_sbc']
        lease = revenue * c['cash_lease_rate']
        maintenance = revenue * c['maintenance_capex_rate']
        growth_capex = revenue * c['growth_capex_rate']
        wc = (revenue - prior_revenue) * c['working_capital_increment_rate']
        if wc < 0:
            wc *= 1 - s['working_capital_release_haircut']
        cash_comp = revenue * c['new_compensation_cash_rate'] if year >= c['new_compensation_cycle_start_year'] else 0.0
        one_time = s['one_time_receivable_loss'] if year == 1 else 0.0
        principal = 0.0
        interest = 0.0
        last = begin
        opening_debt = debt
        for date in paydates:
            if begin <= date < end:
                interest += debt * f['ncd_coupon'] * (date - last).days / 365.25
                debt -= schedule_payment
                principal += schedule_payment
                last = date
        interest += debt * f['ncd_coupon'] * (end - last).days / 365.25
        debt = max(0.0, debt)
        owned_tax_dep = revenue * c['owned_tax_depreciation_rate']
        taxable = max(0.0, ebitda - lease - cash_comp - interest - owned_tax_dep - c['acquisition_amortization_tax_deduction'])
        cash_tax = taxable * c['cash_tax_rate']
        owner_cash = ebitda - lease - maintenance - growth_capex - wc - cash_comp - interest - cash_tax - one_time
        if year > c['years']:
            terminal_next_owner_cash = owner_cash
            break
        pre_distribution_cash = cash + owner_cash - principal
        desired_distribution = max(0.0, (owner_cash - principal) * c['cash_distribution_fraction_after_principal'])
        distribution = min(desired_distribution, max(0.0, pre_distribution_cash - c['operating_cash_floor']))
        cash = pre_distribution_cash - distribution
        rows.append({
            'year':year, 'date':str(end), 'revenue':revenue, 'cash_ebitda_before_existing_sbc':ebitda,
            'cash_lease':lease, 'maintenance_capex':maintenance, 'growth_capex':growth_capex,
            'working_capital_investment':wc, 'future_compensation_cash_equivalent':cash_comp,
            'one_time_receivable_loss':one_time, 'debt_open':opening_debt,
            'cash_interest':interest, 'cash_tax':cash_tax, 'owner_cash_before_debt_principal':owner_cash,
            'debt_principal':principal, 'debt_close':debt, 'distribution':distribution,
            'distribution_per_share':distribution / shares_crore, 'closing_cash':cash,
            'funding_gap_to_operating_floor':max(0.0, c['operating_cash_floor'] - cash)
        })
        payments.append((end, distribution / shares_crore))

    terminal_capitalized_cash = terminal_next_owner_cash if c['terminal_cash_basis'] == 'next_year' else rows[-1]['owner_cash_before_debt_principal']
    terminal_business_equity = terminal_capitalized_cash * s['terminal_next_year_cash_multiple']
    terminal_excess_cash = max(0.0, rows[-1]['closing_cash'] - c['operating_cash_floor'])
    # Owner cash is AFTER interest and principal was already funded in the cash ledger.
    # Debt has fully matured, and recurring lease cash is already deducted.
    assert abs(rows[-1]['debt_close']) < 1e-8
    terminal_equity = terminal_business_equity + terminal_excess_cash
    terminal_price = terminal_equity / shares_crore
    payments[-1] = (payments[-1][0], payments[-1][1] + terminal_price)
    for row in rows:
        assert row['closing_cash'] >= c['operating_cash_floor'] - 1e-7
    assert abs(sum(r['debt_principal'] for r in rows) - f['ncd_face']) < 1e-7
    # Payouts reduce company cash, so no cash is credited twice.
    ledger_end = opening_cash + sum(r['owner_cash_before_debt_principal'] - r['debt_principal'] - r['distribution'] for r in rows)
    assert abs(ledger_end - rows[-1]['closing_cash']) < 1e-7
    values = {str(rate):sum(amount / (1 + rate) ** ((date - start).days / 365.25) for date, amount in payments[1:]) for rate in [0.0, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16]}
    return {
        'scenario':name, 'price':price, 'assumptions':s, 'common_assumptions':c,
        'existing_plan_remaining_share_ceiling':plan_remaining,
        'pre_novigo_diluted_shares':pre_novigo_shares,
        'novigo_assumed_stock_consideration':earnout_value,
        'novigo_assumed_incremental_shares':novigo_shares,
        'fully_diluted_shares':shares, 'opening_cash_after_reserves':opening_cash,
        'annual_ledger':rows, 'terminal_next_year_owner_cash':terminal_next_owner_cash,
        'terminal_capitalized_owner_cash':terminal_capitalized_cash,
        'terminal_cash_basis':c['terminal_cash_basis'],
        'terminal_business_equity':terminal_business_equity, 'terminal_excess_cash':terminal_excess_cash,
        'terminal_price':terminal_price, 'total_dividends_per_share':sum(r['distribution_per_share'] for r in rows),
        'xirr':xirr(payments), 'present_value_by_illustrative_rate':values,
        'cashflows_per_share':[[str(date),amount] for date,amount in payments],
        'max_funding_gap':max(r['funding_gap_to_operating_floor'] for r in rows)
    }


def main():
    f = INPUT['facts']
    hist = {p:cash_residual(f[p]) for p in ['cy2025','h1_2025','h1_2026']}
    hist['ttm_june_2026_cash_before_principal_dividends_existing_dilution'] = hist['cy2025'] + hist['h1_2026'] - hist['h1_2025']
    hist['h1_2026_annualized_same_basis'] = hist['h1_2026'] * 2
    scenarios = {name:calc(name) for name in INPUT['scenarios']}
    sensitivity_defs = [
        ('base_margin_18_5pct', {'cash_ebitda_margin_before_existing_sbc':0.185}, {}),
        ('base_margin_17pct', {'cash_ebitda_margin_before_existing_sbc':0.17}, {}),
        ('base_growth_3pct', {'first_year_revenue_growth':0.03,'later_revenue_growth':0.03}, {}),
        ('base_terminal_10x', {'terminal_next_year_cash_multiple':10.0}, {}),
        ('base_terminal_12x_year5_cash', {}, {'terminal_cash_basis':'year5'}),
        ('base_novigo_issue_at_200', {'novigo_assumed_issue_price':200.0}, {}),
        ('base_novigo_average_105', {'novigo_assumed_average_fy26_fy27_ebitda':105.0}, {}),
        ('base_future_compensation_1_25pct_year4', {}, {'new_compensation_cash_rate':0.0125,'new_compensation_cycle_start_year':4}),
        ('base_capex_2pct', {}, {'maintenance_capex_rate':0.017}),
        ('base_wc_22pct', {}, {'working_capital_increment_rate':0.22}),
        ('base_payout_zero', {}, {'cash_distribution_fraction_after_principal':0.0}),
        ('base_payout_all', {}, {'cash_distribution_fraction_after_principal':1.0}),
        ('base_cash_floor_250', {}, {'operating_cash_floor':250.0}),
        ('base_reserve_legacy_gratuity_66_975', {}, {'other_loan_and_restricted_cash_reserve':68.975}),
        ('base_tax_amortization_shield_42_4', {}, {'acquisition_amortization_tax_deduction':42.4}),
        ('same_price_evidence_route', {'first_year_revenue_growth':0.08,'later_revenue_growth':0.08,'cash_ebitda_margin_before_existing_sbc':0.195,'novigo_assumed_average_fy26_fy27_ebitda':85.0}, {}),
        ('joint_moderate_stress', {'first_year_revenue_growth':0.03,'later_revenue_growth':0.03,'cash_ebitda_margin_before_existing_sbc':0.175,'terminal_next_year_cash_multiple':10.0,'novigo_assumed_issue_price':200.0}, {'new_compensation_cash_rate':0.0125,'new_compensation_cycle_start_year':4})
    ]
    sensitivity = {}
    for label,s,c in sensitivity_defs:
        result = calc('base',s,c)
        sensitivity[label] = {k:result[k] for k in ['xirr','terminal_price','total_dividends_per_share','fully_diluted_shares','max_funding_gap']}
    entry = {str(p):{name:calc(name,price=p)['xirr'] for name in INPUT['scenarios']} for p in [180,200,210,220,230,242.5,260]}
    result = {'model_version':'1.0','analysis_date':INPUT['analysis_date'],'historical_cash_bridge':hist,'scenarios':scenarios,'sensitivity':sensitivity,'entry_price_sensitivity':entry,'scenario_probabilities':None,'benchmark_outcomes':None,'out_of_sample_validation':False}
    (ROOT / 'rsystems_model_results.json').write_text(json.dumps(result,indent=2) + '\n')
    print(json.dumps({'historical_cash_bridge':hist,'scenarios':{n:{k:r[k] for k in ['xirr','terminal_price','total_dividends_per_share','fully_diluted_shares','max_funding_gap']} for n,r in scenarios.items()},'sensitivity':sensitivity,'entry_price_sensitivity':entry},indent=2))


if __name__ == '__main__':
    main()
