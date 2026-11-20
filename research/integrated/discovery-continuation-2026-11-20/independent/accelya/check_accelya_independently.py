#!/usr/bin/env python3
"""Independent Accelya cash roll-forward and joint normalization challenge.

Uses an immutable input snapshot, does not import or execute the author's code.
Standard library only. All money is INR crore except shareholder flows in INR.
The output scenarios are assumptions, with no probabilities or realized prices.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def annual_return(cashflows):
    # Solve in log-discount space, independently of the author's rate bisection.
    import math
    left, right = -4.0, 2.0
    for _ in range(160):
        middle = (left + right) / 2
        present = sum(amount * math.exp(-middle * year)
                      for year, amount in enumerate(cashflows))
        if present > 0:
            left = middle
        else:
            right = middle
    return math.expm1((left + right) / 2)


def value_case(data, case, *, terminal=None, reserve=None, starting_cash=0.0):
    common = data['model_common_assumptions']
    share_count_crore = data['shares'] / 10_000_000
    reserve = (common['liquidity_reserve_built_from_future_cash']
               if reserve is None else reserve)
    recurring = []
    owners = [-data['price_inr']]
    retained = starting_cash
    rows = []
    for n in range(common['years']):
        growth_factor = (1 + case['subsequent_revenue_growth']) ** n
        nonnegative_growth_factor = (1 + max(0, case['subsequent_revenue_growth'])) ** n
        sales = case['year1_revenue'] * growth_factor
        operating = sales * case['operating_ebitda_margin'] + case['recurring_rent_income']
        lease = case['financing_lease_cash_year1'] * (1 + case['lease_growth']) ** n
        capex = case['full_ppe_and_software_cash_year1'] * (1 + case['investment_growth']) ** n
        wc = case['working_capital_and_contract_funding_year1'] * nonnegative_growth_factor
        tax_dep = common['nonlease_tax_depreciation_year1'] * nonnegative_growth_factor
        cash_tax = common['cash_tax_rate'] * max(0, operating - lease - tax_dep)
        cash = operating - lease - capex - wc - cash_tax
        recurring.append(cash)
        oneoff = 0
        if n == 0:
            oneoff = (common['incremental_gratuity_funding_year1']
                      + common['epfo_payment_year1']
                      + case['extra_collection_cash_loss_year1'])
        retained += cash - oneoff
        funding_gap = max(0, -retained)
        payout = common['fraction_of_cash_above_reserve_distributed_each_year'] * max(0, retained - reserve)
        retained -= payout
        share_count_crore *= 1 + common['annual_share_dilution']
        owners.append(payout / share_count_crore)
        rows.append({'year': n + 1, 'sales': sales, 'lease_cash': lease,
                     'capex': capex, 'working_capital_and_contract_funding': wc,
                     'cash_tax': cash_tax, 'recurring_owner_cash': cash,
                     'oneoff': oneoff, 'distributed': payout,
                     'retained': retained, 'external_funding_gap': funding_gap})
    entry_multiple = data['price_inr'] * data['shares'] / 10_000_000 / recurring[0]
    if terminal == 'unchanged_recalculated_entry_multiple':
        terminal_multiple = entry_multiple
    elif terminal is not None:
        terminal_multiple = terminal
    else:
        terminal_multiple = case['terminal_owner_cash_multiple']
    terminal_surplus = max(0, retained - reserve)
    terminal_equity = terminal_multiple * recurring[-1] + terminal_surplus
    owners[-1] += terminal_equity / share_count_crore
    return {'annualized_return': annual_return(owners), 'rows': rows,
            'year1_recurring_owner_cash': recurring[0],
            'normalized_entry_owner_cash_multiple': entry_multiple,
            'exit_owner_cash_multiple': terminal_multiple,
            'terminal_surplus_cash': terminal_surplus,
            'terminal_equity_per_share': terminal_equity / share_count_crore,
            'shareholder_cash_flows': owners,
            'comparison_price_at_10pct': sum(x / 1.1 ** t for t, x in enumerate(owners) if t),
            'funded_without_external_financing': all(r['external_funding_gap'] == 0 for r in rows)}


def main():
    data = json.loads((HERE / 'author_inputs_snapshot.json').read_text())
    author = json.loads((HERE / 'author_results_snapshot.json').read_text())
    replicated = {}
    deltas = {}
    for name, case in data['scenarios'].items():
        result = value_case(data, case)
        replicated[name] = result
        deltas[name] = result['annualized_return'] - author['scenarios'][name]['annualized_return']
        assert abs(deltas[name]) < 1e-12
        actual_flows = author['scenarios'][name]['shareholder_cash_flows_per_share']
        assert max(abs(a - b) for a, b in zip(result['shareholder_cash_flows'], actual_flows)) < 1e-8

    base = data['scenarios']['working']
    original_multiple = replicated['working']['normalized_entry_owner_cash_multiple']
    matrices = {}
    # 5 crore is an explicit optimistic normalization hypothesis, not issuer guidance.
    for wc in (15, 5, 0):
        for lease in (18, 14, data['consolidated_fy26']['undiscounted_lease_due_within_one_year']):
            case = dict(base, working_capital_and_contract_funding_year1=wc,
                        financing_lease_cash_year1=lease)
            label = f'wc_{wc:g}_lease_{lease:g}'
            matrices[label] = {}
            for terminal_label, multiple in (
                ('exit_12x', 12), ('exit_14x', 14),
                ('exit_fixed_original_entry_multiple', original_multiple),
                ('exit_unchanged_recalculated_entry_multiple', 'unchanged_recalculated_entry_multiple')):
                matrices[label][terminal_label] = value_case(data, case, terminal=multiple)

    a, b = data['consolidated_fy26'], data['consolidated_fy25']
    selected_cash = lambda x: x['cfo'] - x['cash_ppe'] - x['cash_intangible'] - x['lease_principal'] - x['lease_interest']
    related_receivables = lambda x: sum(x['related_billed_receivables']) + sum(x['related_unbilled_receivables'])
    june_unencumbered = sum(a[k] for k in ('june_cash', 'june_liquid_mutual_funds', 'june_other_bank_balances')) - a['unpaid_dividend_earmark'] - a['margin_money_in_other_bank']
    final_dividend = 35 * data['shares'] / 10_000_000
    contract_fulfillment_increase = (a['contract_fulfillment_asset_current'] + a['contract_fulfillment_asset_noncurrent']
                                   - b['contract_fulfillment_asset_current'] - b['contract_fulfillment_asset_noncurrent'])
    source_checks = []
    for source in json.loads((HERE / 'author_sources_snapshot.json').read_text()):
        path = Path(source['local_original_path'])
        if path.exists():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == source['sha256'], (source['source_id'], 'original hash mismatch')
            source_checks.append({'source_id': source['source_id'], 'local_original_path': str(path),
                                  'sha256': digest, 'original_hash_verified': True})
        else:
            source_checks.append({'source_id': source['source_id'], 'original_hash_verified': False,
                                  'reason': 'Path not available to reviewer'})

    analysis = {
        'fy26_selected_cash': selected_cash(a), 'fy25_selected_cash': selected_cash(b),
        'fy26_selected_cash_dividend_coverage': selected_cash(a) / a['dividends_paid'],
        'fy25_selected_cash_dividend_coverage': selected_cash(b) / b['dividends_paid'],
        'june_unencumbered_treasury': june_unencumbered,
        'committed_final_dividend': final_dividend,
        'june_unencumbered_less_committed_dividend': june_unencumbered - final_dividend,
        'related_revenue_fraction': sum(a['related_services_rendered']) / a['revenue'],
        # Standalone Note33 and revenue Note21, independently read from S1.
        'standalone_related_revenue_including_owned_subsidiary': sum(a['related_services_rendered']) + 65.5315,
        'standalone_related_revenue_fraction_reconciles_brsr': (sum(a['related_services_rendered']) + 65.5315) / 526.5691,
        'related_receivables_fy26': related_receivables(a),
        'related_receivables_fy25': related_receivables(b),
        'related_receivables_growth': related_receivables(a) / related_receivables(b) - 1,
        'related_receivables_fraction_of_total': related_receivables(a) / a['trade_receivables_including_unbilled'],
        'net_contract_fulfillment_asset_increase': contract_fulfillment_increase,
        'year2_base_incremental_sales': base['year1_revenue'] * base['subsequent_revenue_growth'],
        'year2_base_wc_and_contract_funding': base['working_capital_and_contract_funding_year1'] * (1 + base['subsequent_revenue_growth']),
        'capitalized_receivables_contract_assets_fulfillment_less_contract_liabilities': a['trade_receivables_including_unbilled'] + a['contract_asset'] + a['contract_fulfillment_asset_current'] + a['contract_fulfillment_asset_noncurrent'] - 23.2047,
        'incremental_gratuity_funding_recalculated': a['fy27_expected_gratuity_fund_contribution'] - a['ordinary_gratuity_expense_in_fy26_opex'],
        'working_five_year_cumulative_wc': sum(r['working_capital_and_contract_funding'] for r in replicated['working']['rows'])
    }
    revised_inputs = json.loads((HERE / 'revised_author_inputs_snapshot.json').read_text())
    revised_results = json.loads((HERE / 'revised_author_results_snapshot.json').read_text())
    revised_deltas = {}
    for name, case in revised_inputs['scenarios'].items():
        independent = value_case(revised_inputs, case)
        revised_deltas[name] = independent['annualized_return'] - revised_results['scenarios'][name]['annualized_return']
        assert abs(revised_deltas[name]) < 1e-12
    reserve_already_funded_sensitivity = value_case(
        revised_inputs, revised_inputs['scenarios']['working'], terminal=14, starting_cash=20)
    result = {'purpose': 'Independent arithmetic replication and economic-normalization counter-thesis',
              'decision_date': data['decision_date'], 'price_date': data['price_date'],
              'price_inr': data['price_inr'], 'replication_irr_deltas': deltas,
              'revised_replication_irr_deltas': revised_deltas,
              'revised_base_14x_if_20cr_operating_reserve_already_funded_unverified_sensitivity': reserve_already_funded_sensitivity,
              'replicated_scenarios': replicated, 'joint_sensitivities': matrices,
              'historical_independent_calculations': analysis,
              'source_hash_checks': source_checks,
              'scenario_probabilities': None, 'realized_outcomes': None}
    (HERE / 'independent_calculations.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'replication_irr_deltas': deltas, 'historical': analysis,
                      'joint_sensitivities': {
                          key: {basis: {'irr': item['annualized_return'], 'entry_multiple': item['normalized_entry_owner_cash_multiple'],
                                        'exit_multiple': item['exit_owner_cash_multiple'], 'year1_cash': item['year1_recurring_owner_cash']}
                                for basis, item in cases.items()}
                          for key, cases in matrices.items()}}, indent=2))


if __name__ == '__main__':
    main()
