#!/usr/bin/env python3
"""Portable bounded POWERGRID cohort/funding scenarios. Python standard library only.

This is NOT a project-by-project tariff model. All amounts are INR crore except
per-share values. Growth capex includes construction interest. A reference debt
schedule prevents assuming that incremental project earnings have no financing
cost. Actual debt is solved from the cash bridge, and interest on debt above or
below the reference schedule changes earnings. No future loan commitments or
project equity IRRs are asserted by this calculator.
"""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def irr(cash):
    def npv(r):
        return sum(v / (1 + r) ** i for i, v in enumerate(cash))
    lo, hi = -0.95, 2.0
    for _ in range(160):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def price_for_return(dividends, terminal, rate):
    return sum(v / (1 + rate) ** (i + 1) for i, v in enumerate(dividends)) + terminal / (1 + rate) ** len(dividends)


def run(inp, scenario):
    f = inp['facts']
    a = inp['common_assumptions']
    s = scenario
    shares = f['shares_crore']
    debt = f['debt_crore']
    equity = f['book_equity_crore']
    cwip = f['cwip_including_advances_crore']
    w = s['new_tbcb_share']
    debt_fraction = w * a['tbcb_reference_debt_fraction'] + (1 - w) * a['regulated_reference_debt_fraction']
    initial_legacy_reference_debt = debt - cwip * debt_fraction
    reference_debt = debt
    opening_excess = 0.0
    cohorts = []
    rows = []
    cumulative_growth_spend = 0.0
    for y in range(1, 11):
        opening_debt, opening_equity, opening_cwip = debt, equity, cwip
        capex = s['capex_total_including_idc'][y - 1]
        maintenance = s['maintenance_capex'][y - 1]
        growth = capex - maintenance
        commission = min(s['commissioning'][y - 1], opening_cwip + growth)
        cwip += growth - commission
        cumulative_growth_spend += growth
        cohorts.append((y, commission))
        legacy_pat = s['normalized_opening_pat'] * (1 + s['legacy_pat_growth']) ** y
        legacy_da = a['opening_annual_depreciation'] * (1 - s['legacy_depreciation_decline']) ** y
        new_pat, new_da, operating_reference_debt, regulated_pat, tbcb_pat = 0.0, 0.0, 0.0, 0.0, 0.0
        for start, cost in cohorts:
            elapsed_close = y - start + 0.5
            time_active = 0.5 if start == y else 1.0
            elapsed_average = max(0, elapsed_close - time_active / 2)
            remaining_debt = max(0, 1 - elapsed_close / a['new_debt_amortization_years'])
            operating_reference_debt += cost * debt_fraction * remaining_debt
            rpat = cost * (1 - w) * a['regulated_reference_equity_fraction'] * s['regulated_posttax_roe'] * time_active
            # First full-year accounting ROE at 7% reference interest. This is NOT bid/project IRR.
            tpat = cost * w * a['tbcb_reference_equity_fraction'] * s['tbcb_first_year_posttax_roe_at_reference_rate'] * time_active
            tpat -= cost * w * a['tbcb_reference_debt_fraction'] * (s['cash_borrowing_rate'] - a['reference_interest_rate']) * (1 - a['incremental_tax_rate']) * time_active
            # Fixed TBCB operating economics retain interest savings as reference loans amortize.
            tpat += cost * w * a['tbcb_reference_debt_fraction'] * min(elapsed_average / a['new_debt_amortization_years'], 1) * s['cash_borrowing_rate'] * (1 - a['incremental_tax_rate']) * time_active
            regulated_pat += rpat
            tbcb_pat += tpat
            new_pat += rpat + tpat
            new_da += cost * a['new_asset_depreciation_fraction'] * time_active
        legacy_reference_debt = max(0, initial_legacy_reference_debt - a['legacy_reference_principal_per_year'] * y)
        closing_reference_debt = legacy_reference_debt + cwip * debt_fraction + operating_reference_debt
        da = legacy_da + new_da
        normative_pat = legacy_pat + new_pat
        pat = normative_pat
        wc = s['working_capital_cash_use'][y - 1]
        # Fixed-point solution for interest on funding beyond the reference debt schedule.
        for _ in range(200):
            desired_dividend = max(0, s['payout_fraction'] * pat)
            debt_before_dividend = opening_debt + capex + wc - pat - da
            dividend_capacity = (s['debt_to_book_ceiling'] * (opening_equity + pat) - debt_before_dividend) / (1 + s['debt_to_book_ceiling'])
            dividend = min(desired_dividend, max(0, dividend_capacity))
            debt_new = debt_before_dividend + dividend
            excess = debt_new - closing_reference_debt
            financing_adjustment = (opening_excess + excess) / 2 * s['cash_borrowing_rate'] * (1 - a['incremental_tax_rate'])
            pat_new = normative_pat - financing_adjustment
            if abs(pat_new - pat) < 1e-8:
                pat = pat_new
                break
            pat = pat_new
        debt = opening_debt + capex + wc + dividend - pat - da
        equity = opening_equity + pat - dividend
        average_debt = (opening_debt + debt) / 2
        cash_interest = average_debt * s['cash_borrowing_rate']
        idc = (opening_cwip + cwip) / 2 * debt_fraction * s['cash_borrowing_rate']
        idc = min(idc, cash_interest, capex)
        expensed_interest = cash_interest - idc
        construction_cash_ex_idc = capex - idc
        operating_cash_before_interest = pat + da + expensed_interest - wc
        principal = max(0, reference_debt + growth * debt_fraction - closing_reference_debt)
        gross_new_debt = max(0, debt - opening_debt + principal)
        net_cash_bridge = operating_cash_before_interest + gross_new_debt - cash_interest - construction_cash_ex_idc - dividend - principal
        assert abs(net_cash_bridge) < 1e-5, (s['name'], y, net_cash_bridge)
        assert cwip >= -1e-8
        unfunded_under_leverage_ceiling = max(0, debt - s['debt_to_book_ceiling'] * equity)
        rows.append({
            'year': y, 'capex_including_idc': capex, 'maintenance_capex': maintenance,
            'growth_capex_including_idc': growth, 'commissioning': commission,
            'cwip_close': cwip, 'legacy_pat': legacy_pat, 'new_regulated_pat': regulated_pat,
            'new_tbcb_pat': tbcb_pat, 'extra_financing_cost_aftertax': financing_adjustment,
            'pat': pat, 'depreciation': da, 'eps': pat / shares,
            'dividend_cash': dividend, 'dividend_per_share': dividend / shares,
            'desired_dividend_cash': desired_dividend, 'dividend_cut_for_ceiling': desired_dividend - dividend,
            'debt_open': opening_debt, 'debt_close': debt,
            'change_in_gross_borrowings': debt - opening_debt, 'reference_principal_repaid': principal,
            'cash_balance_assumed_constant': f['cash_balance_held_constant'],
            'net_debt_after_all_reported_cash': debt - f['cash_balance_held_constant'],
            'net_debt_after_unrestricted_cash_only': debt - (f['cash_balance_held_constant'] - f['cash_restricted_to_projects']),
            'gross_new_debt': gross_new_debt, 'reference_debt_close': closing_reference_debt,
            'excess_debt_vs_reference': debt - closing_reference_debt,
            'book_equity_close': equity, 'debt_to_book': debt / equity,
            'estimated_cash_interest': cash_interest, 'estimated_capitalized_interest': idc,
            'estimated_expensed_interest': expensed_interest,
            'operating_cash_aftertax_before_cash_interest_proxy': operating_cash_before_interest,
            'construction_cash_excluding_idc': construction_cash_ex_idc,
            'cash_bridge_residual': net_cash_bridge, 'working_capital_cash_use': wc,
            'unfunded_if_leverage_ceiling_binding': unfunded_under_leverage_ceiling,
            'cumulative_growth_spend': cumulative_growth_spend,
            'new_awards_needed_beyond_open_work_cost': max(0, cumulative_growth_spend - (f['work_in_hand_includes_cwip'] - f['cwip_including_advances_crore'])),
        })
        reference_debt = closing_reference_debt
        opening_excess = debt - closing_reference_debt
    summary = {}
    for n in (5, 10):
        dividends = [r['dividend_per_share'] for r in rows[:n]]
        terminal = rows[n - 1]['eps'] * s[f'exit_pe_{n}y']
        cash = [-f['price']] + dividends
        cash[-1] += terminal
        summary[str(n)] = {'terminal_eps': rows[n - 1]['eps'], 'exit_pe': s[f'exit_pe_{n}y'], 'terminal_price': terminal,
                          'dividends_sum': sum(dividends), 'annualized_return': irr(cash),
                          'price_return_map': {str(r): price_for_return(dividends, terminal, r) for r in (0.06, 0.08, 0.10, 0.12)},
                          'return_at_prices': {str(p): irr([-p] + dividends[:-1] + [dividends[-1] + terminal]) for p in (200, 220, 230, 240, 250, 269)},
                          'terminal_debt': rows[n-1]['debt_close'], 'terminal_debt_to_book': rows[n-1]['debt_to_book'],
                          'terminal_cwip': rows[n-1]['cwip_close']}
    return {'name': s['name'], 'summary': summary, 'years': rows,
            'max_debt_to_book': max(r['debt_to_book'] for r in rows),
            'first_year_over_current_220000_borrowing_limit': next((r['year'] for r in rows if r['debt_close'] > 220000), None),
            'funding_gap_max': max(r['unfunded_if_leverage_ceiling_binding'] for r in rows)}


def humnabad(inp):
    h = inp['humnabad_assumptions']
    rows = []
    for cost in h['hypothetical_all_in_costs']:
        revenue = h['quoted_annual_charge'] * h['collection_fraction']
        opex = cost * h['opex_fraction_of_cost']
        da = cost * h['depreciation_fraction']
        interest = cost * h['debt_fraction'] * h['interest_rate']
        principal = cost * h['debt_fraction'] / h['amortization_years']
        pbt = revenue - opex - da - interest
        tax = max(0, pbt) * h['tax_rate']
        pat = pbt - tax
        cash_after_debt = revenue - opex - tax - interest - principal
        rows.append({'hypothetical_cost': cost, 'revenue_if_fully_operating': revenue,
                     'opex': opex, 'depreciation': da, 'cash_interest': interest, 'principal': principal,
                     'pat': pat, 'posttax_first_year_roe': pat / (cost * (1-h['debt_fraction'])),
                     'cash_after_debt_service': cash_after_debt,
                     'debt_service_cover': (revenue - opex - tax) / (interest + principal)})
    # Cost at which first full-year PAT earns 13% on the assumed 20% equity stake.
    target = h['example_first_year_roe']
    max_cost = h['quoted_annual_charge'] * h['collection_fraction'] / (
        h['opex_fraction_of_cost'] + h['depreciation_fraction'] + h['debt_fraction'] * h['interest_rate']
        + target * (1-h['debt_fraction']) / (1-h['tax_rate']))
    return {'interpretation': 'Hypothetical first operating-year sensitivity only, not an actual project cost, bid IRR, lifetime DCF or covenant DSCR.',
            'rows': rows, 'cost_supporting_example_roe': max_cost}


def main():
    inp = json.loads((HERE / 'inputs.json').read_text())
    results = {k: run(inp, v) for k, v in inp['scenarios'].items()}
    base = inp['scenarios']['base']
    sensitivities = {}
    for key, changes in {
        'opening_pat_reported_ttm': {'normalized_opening_pat': inp['facts']['reported_ttm_pat']},
        'tbcb_roe_10pct': {'tbcb_first_year_posttax_roe_at_reference_rate': 0.10},
        'tbcb_roe_16pct': {'tbcb_first_year_posttax_roe_at_reference_rate': 0.16},
        'borrowing_rate_plus_1pct': {'cash_borrowing_rate': 0.08},
        'commissioning_one_year_slower': {'commissioning': [15000] + base['commissioning'][:-1]},
        'working_capital_use_2000_per_year': {'working_capital_cash_use': [2000]*10},
        'sustaining_capex_5000_with_total_spend_plus_2000': {'maintenance_capex': [5000]*10,
            'capex_total_including_idc': [c + 2000 for c in base['capex_total_including_idc']]},
    }.items():
        mod = copy.deepcopy(base)
        mod.update(changes)
        mod['name'] = key
        out = run(inp, mod)
        sensitivities[key] = {'summary': out['summary'], 'max_debt_to_book': out['max_debt_to_book'], 'funding_gap_max': out['funding_gap_max']}
    result = {'classification': 'BOUNDED_FUNDING_SCENARIOS_NOT_FULLY_COMMITTED_FORECAST', 'facts': inp['facts'], 'scenarios': results,
              'sensitivities': sensitivities, 'humnabad': humnabad(inp)}
    (HERE / 'outputs.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v['summary'] for k, v in results.items()}, indent=2))


if __name__ == '__main__':
    main()
