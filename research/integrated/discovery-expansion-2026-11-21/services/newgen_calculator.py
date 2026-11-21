#!/usr/bin/env python3
"""Portable standard-library Newgen scenario model. Not a price forecast.

Run: python3 newgen_calculator.py [newgen_inputs.json] [newgen_outputs.json]
Monetary company values and share counts are both in crore, producing INR/share.
"""
import copy
import json
import math
import sys
from pathlib import Path


def irr(cashflows):
    def npv(rate):
        return sum(c / (1 + rate) ** i for i, c in enumerate(cashflows))
    lo, hi = -0.999, 1.0
    while npv(hi) > 0 and hi < 1024:
        hi *= 2
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(160):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def historical(data):
    r = data['reported']
    ttm = {k: r['fy26'][k] + r['h1fy27'][k] - r['h1fy26'][k]
           for k in r['fy26']}
    for period in [r['fy26'], r['h1fy26'], r['h1fy27'], ttm]:
        period['cash_residual'] = period['cfo'] - period['capex'] - period['lease_principal'] - period['lease_interest']
        period['cash_residual_after_cash_share_awards'] = period['cash_residual'] - period.get('share_award_cash', 0.0)
    ttm['core_cash_ebit_before_sbc'] = (ttm['pbt'] + ttm['finance_cost'] + ttm['exceptional_expense']
                                         - ttm['other_income'] + ttm['sbc'])
    ttm['core_cash_ebit_margin_before_sbc'] = ttm['core_cash_ebit_before_sbc'] / ttm['revenue']
    ttm['cash_residual_per_diluted_share'] = ttm['cash_residual'] / data['capital']['model_start_shares_crore']
    ttm['reported_pat_per_legal_issued_share'] = ttm['pat'] / data['capital']['issued_shares_crore']
    ttm['cfo_to_pat'] = ttm['cfo'] / ttm['pat']
    ttm['price_to_actual_cash_residual'] = (data['price_inr'] / ttm['cash_residual_per_diluted_share']
                                           if ttm['cash_residual_per_diluted_share'] > 0 else None)
    return ttm


def evaluate(data, assumption, price=None):
    ttm = historical(copy.deepcopy(data))
    b = data['balance_20260930']
    revenue = ttm['revenue']
    nwc = (b['net_trade_receivables'] + b['contract_assets'] + b['other_current_assets']
           - b['trade_payables'] - b['deferred_income'] - b['other_current_liabilities']
           - b['other_financial_liabilities'] + b.get('nonoperating_liability_reclassification_to_nwc', 0.0))
    buffer = revenue * assumption['liquidity_buffer_pct_revenue']
    treasury_pool = b.get('verified_treasury_pool', b['cash_equivalents'] + b['other_bank_balances'] + b['current_investments'])
    treasury = (treasury_pool
                - b['all_provisions_reserved'] - b['unclaimed_dividend_exclusion_proxy_fy26']
                - assumption['treasury_haircut'] - buffer - b.get('additional_opening_reserves', 0.0))
    initial = {'revenue': revenue, 'operating_working_capital': nwc,
               'operating_working_capital_to_revenue': nwc / revenue,
               'liquidity_buffer': buffer, 'available_treasury': treasury}
    shares = data['capital']['model_start_shares_crore']
    rows = []
    investor_cf = [-(data['price_inr'] if price is None else price)]
    max_gap = 0.0
    for year in range(1, data['model_conventions']['years'] + 1):
        revenue *= 1 + assumption['revenue_growth']
        shares *= 1 + assumption['annual_new_dilution']
        margin = assumption.get('cash_ebit_margin_path', [assumption['cash_ebit_margin']] * data['model_conventions']['years'])[year - 1]
        cash_ebit = revenue * margin
        cash_tax = max(0.0, cash_ebit) * assumption['cash_tax_rate']
        da = revenue * assumption['da_pct_revenue']
        capex = revenue * assumption['all_capex_pct_revenue']
        lease = revenue * assumption['all_lease_cash_pct_revenue']
        target_nwc = revenue * assumption['operating_wc_pct_revenue']
        change_nwc = target_nwc - nwc
        target_buffer = revenue * assumption['liquidity_buffer_pct_revenue']
        change_buffer = target_buffer - buffer
        extra_loss = assumption['one_time_cash_loss_year1'] if year == 1 else 0.0
        cash_award = revenue * assumption.get('share_award_cash_pct_revenue', 0.0)
        funded_cash = cash_ebit - cash_tax + da - capex - lease - cash_award - change_nwc - change_buffer - extra_loss
        interest = max(0.0, treasury) * assumption['treasury_net_yield']
        cash_for_allocation = funded_cash + interest
        dividend = max(0.0, cash_for_allocation) * assumption['dividend_payout_of_total_available_cash']
        treasury += cash_for_allocation - dividend
        funding_gap = max(0.0, -treasury)
        max_gap = max(max_gap, funding_gap)
        dps = dividend / shares
        investor_cf.append(dps)
        rows.append({'year': year, 'revenue': revenue, 'shares_crore': shares,
                     'cash_ebit_margin_before_sbc': margin, 'cash_ebit_before_sbc': cash_ebit, 'cash_tax': cash_tax,
                     'da_addback': da, 'all_capex': capex, 'all_lease_cash': lease,
                     'operating_working_capital': target_nwc, 'change_operating_working_capital': change_nwc,
                     'required_liquidity_buffer': target_buffer, 'increase_liquidity_buffer': change_buffer,
                     'extra_cash_loss': extra_loss, 'cash_share_award_funding': cash_award, 'funded_operating_cash': funded_cash,
                     'funded_operating_cash_per_share': funded_cash / shares,
                     'treasury_net_income': interest, 'total_dividend': dividend, 'dividend_per_share': dps,
                     'closing_available_treasury': treasury, 'external_funding_gap': funding_gap})
        nwc, buffer = target_nwc, target_buffer
    terminal_operating_value = max(0.0, rows[-1]['funded_operating_cash']) * assumption['terminal_funded_cash_multiple']
    exit_equity = terminal_operating_value + treasury
    exit_price = exit_equity / shares
    investor_cf[-1] += exit_price
    entry = -investor_cf[0]
    result = {'assumptions': assumption, 'initial': initial, 'years': rows,
              'terminal_operating_value': terminal_operating_value, 'terminal_equity_value': exit_equity,
              'exit_price': exit_price, 'dividends_per_share_total': sum(r['dividend_per_share'] for r in rows),
              'investor_cashflows': investor_cf, 'dividend_inclusive_irr': irr(investor_cf),
              'exit_price_cagr': (exit_price / entry) ** (1 / len(rows)) - 1,
              'maximum_external_funding_gap': max_gap,
              'illustrative_entry_values': {str(rate): sum(c / (1 + rate) ** i for i, c in enumerate(investor_cf) if i)
                                           for rate in data['sensitivity']['illustrative_required_returns']}}
    return result


def main():
    here = Path(__file__).resolve().parent
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else here / 'newgen_inputs.json'
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else here / 'newgen_outputs.json'
    data = json.loads(src.read_text())
    result = {'symbol': data['symbol'], 'as_of': data['as_of'], 'price': data['price_inr'],
              'historical_ttm': historical(copy.deepcopy(data)),
              'scenarios': {name: evaluate(data, copy.deepcopy(a)) for name, a in data['scenarios'].items()}}
    result['growth_multiple_sensitivity'] = []
    for growth in data['sensitivity']['base_growth_rates']:
        for multiple in data['sensitivity']['base_exit_multiples']:
            a = copy.deepcopy(data['scenarios']['base'])
            a.update(revenue_growth=growth, terminal_funded_cash_multiple=multiple)
            v = evaluate(data, a)
            result['growth_multiple_sensitivity'].append({'revenue_growth': growth, 'terminal_multiple': multiple,
                                                         'dividend_inclusive_irr': v['dividend_inclusive_irr']})
    result['base_entry_price_sensitivity'] = [{'entry_price': p, 'dividend_inclusive_irr': evaluate(data, copy.deepcopy(data['scenarios']['base']), p)['dividend_inclusive_irr']}
                                              for p in data['sensitivity']['entry_prices']]
    dest.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    for name, s in result['scenarios'].items():
        print(f"{name}: IRR {s['dividend_inclusive_irr']:.2%}, exit INR{s['exit_price']:.2f}, dividends INR{s['dividends_per_share_total']:.2f}, max funding gap INR{s['maximum_external_funding_gap']:.2f}cr")


if __name__ == '__main__':
    main()
