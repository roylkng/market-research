#!/usr/bin/env python3
"""Independent Epigral arithmetic and assumption stresses, not a return forecast.

Reads a frozen reviewed-input snapshot and writes only in this review directory.
No author's model or output is changed. Monetary amounts are INR crore.
"""
from copy import deepcopy
from datetime import date
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
INPUT = json.loads((HERE / 'epigral_independent_input_snapshot.json').read_text())


def pv(flows, rate):
    return sum(value / (1 + rate) ** years for years, value in flows)


def solve_return(flows, entry):
    low, high = -0.99, 3.0
    for _ in range(180):
        mid = (low + high) / 2
        if pv(flows, mid) > entry:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def positive_average(start, finish):
    if start >= 0 and finish >= 0:
        return (start + finish) / 2
    if start <= 0 and finish <= 0:
        return 0.0
    if start > 0:
        return start * start / (2 * (start - finish))
    return finish * finish / (2 * (finish - start))


def calculate(scenario, average_debt_interest=False):
    shares_cr = INPUT['shares'] / 10_000_000
    opening = INPUT['initial_net_debt']
    rows, flows = [], []
    for idx, endpoint in enumerate(INPUT['dates']):
        core = scenario['core_sales'][idx]
        downstream = scenario['new_downstream_sales'][idx]
        operating = (core * scenario['core_margin'] +
                     downstream * scenario['new_downstream_margin'] -
                     scenario['cash_leases'][idx])
        outlay = (scenario['capex'][idx] + scenario['working_capital_use'][idx] +
                  (sum(INPUT['one_off_cash_reserves'].values()) if idx == 0 else 0))
        dividend = scenario['dividend_per_share'][idx] * shares_cr
        interest = max(opening, 0) * scenario['interest_rate'] * INPUT['duration_years'][idx]
        for _ in range(100 if average_debt_interest else 1):
            tax = max(operating - scenario['non_rou_depreciation'][idx] - interest, 0) * INPUT['cash_tax_rate']
            cash = operating - interest - tax - outlay
            closing = opening - cash + dividend
            if average_debt_interest:
                interest = (positive_average(opening, closing) *
                            scenario['interest_rate'] * INPUT['duration_years'][idx])
        years = (date.fromisoformat(endpoint) - date.fromisoformat(INPUT['price_date'])).days / 365.25
        rows.append(dict(date=endpoint, revenue=core + downstream,
                         post_lease_ebitda=operating, interest=interest, cash_tax=tax,
                         available_before_dividends=cash, dividends=dividend,
                         opening_net_debt=opening, closing_net_debt=closing))
        flows.append([years, scenario['dividend_per_share'][idx]])
        opening = closing
    ev = rows[-1]['post_lease_ebitda'] * scenario['terminal_post_lease_ebitda_multiple']
    terminal_debt = max(opening, 0)
    terminal_cash = max(-opening, 0)
    equity = ev - terminal_debt + terminal_cash * scenario['terminal_cash_value_fraction']
    terminal_price = max(equity, 0) / shares_cr
    flows[-1][1] += terminal_price
    return dict(rows=rows, terminal_ev=ev, terminal_debt=terminal_debt,
                terminal_cash=terminal_cash, terminal_equity=equity,
                terminal_price=terminal_price,
                pv10=pv(flows, .10), pv12=pv(flows, .12), pv15=pv(flows, .15),
                irr=solve_return(flows, INPUT['price']),
                peak_net_debt=max(row['closing_net_debt'] for row in rows),
                cashflows=flows)


def main():
    working = INPUT['scenarios']['working']
    all_cases = {name: calculate(scenario) for name, scenario in INPUT['scenarios'].items()}
    all_cases['working_average_debt_interest'] = calculate(working, True)
    for margin in [.18, .19, .20]:
        altered = deepcopy(working)
        altered['core_margin'] = margin
        all_cases[f'working_core_margin_{margin:.2f}'] = calculate(altered)
    altered = deepcopy(working)
    altered['working_capital_use'][1] += 100
    all_cases['working_extra_100cr_wc_once_fy28'] = calculate(altered)
    altered = deepcopy(working)
    altered['capex'][1] += 150
    all_cases['working_extra_150cr_capex_fy28'] = calculate(altered)
    altered = deepcopy(working)
    altered['new_downstream_sales'] = [x * .75 for x in altered['new_downstream_sales']]
    all_cases['working_new_downstream_sales_25pct_lower'] = calculate(altered)
    altered = deepcopy(working)
    altered['capex'] = [312, 400, 100, 115, 130, 150]
    all_cases['working_later_capex_100_115_130_150'] = calculate(altered)
    previous_tax_reserve = INPUT['one_off_cash_reserves']['h1_current_tax_less_cash_tax']
    INPUT['one_off_cash_reserves']['h1_current_tax_less_cash_tax'] = 25.30
    all_cases['working_pay_full_september_current_tax_liability'] = calculate(working)
    INPUT['one_off_cash_reserves']['h1_current_tax_less_cash_tax'] = previous_tax_reserve
    baseline = all_cases['working']
    principal = [2 * (14.58 + 14.24), 4 * (14.58 + 14.24)]
    gross_funding = []
    for idx, amount in enumerate(principal):
        row = baseline['rows'][idx]
        net_change = row['closing_net_debt'] - row['opening_net_debt']
        gross_funding.append(dict(period_end=row['date'], indicative_existing_term_principal=amount,
                                  modeled_net_debt_change=net_change,
                                  gross_replacement_and_incremental_funding=amount + net_change,
                                  caveat='Assumes unchanged cash and no asset-sale proceeds or equity. This is not a verified loan draw schedule.'))
    terminal = baseline['rows'][-1]
    terminal_cash_after_uses = terminal['available_before_dividends']
    reviewer_checks = dict(
        working_pv12_price_headroom=baseline['pv12'] - INPUT['price'],
        working_pv12_price_headroom_fraction=baseline['pv12'] / INPUT['price'] - 1,
        first_year_duration=(date.fromisoformat(INPUT['dates'][0]) - date.fromisoformat(INPUT['price_date'])).days / 365.25,
        final_year_duration=(date.fromisoformat(INPUT['dates'][-1]) - date.fromisoformat(INPUT['price_date'])).days / 365.25,
        working_terminal_post_lease_ev_multiple=working['terminal_post_lease_ebitda_multiple'],
        terminal_after_tax_capex_wc_cash_to_ev=terminal_cash_after_uses / baseline['terminal_ev'],
        terminal_cash_yield_if_maintenance_equals_235_depreciation=(terminal_cash_after_uses - (235 - 95)) / baseline['terminal_ev'],
        current_tax_catchup=57.33 - 43.35,
        renewable_ocd_remaining=21.25 - 2.13 - 5.31,
        original_derivative_total_march=15.40 + 12.31,
        first_period_extra_reserves=sum(INPUT['one_off_cash_reserves'].values()),
        ttm_pat=331.97 - 211.91 + 164.82,
        h1_selected_cash=140.84 - 87.97 - 24.16 - 3.98,
        h1_selected_cash_after_spv=140.84 - 87.97 - 24.16 - 3.98 - 5.31,
        h1_cashflow_identity=140.84 - 97.23 - 47.77,
        ttm_selected_cash=(435.53 - 267.31 + 140.84) - (394.15 - 235.68 + 87.97) - (48.69 - 24.10 + 24.16) - (5.87 - 2.68 + 3.98),
    )
    output = dict(classification='INDEPENDENT_REVIEW_AND_ASSUMPTION_STRESSES_NOT_A_FORECAST',
                  reviewed_input_sha256=hashlib.sha256((HERE / 'epigral_independent_input_snapshot.json').read_bytes()).hexdigest(),
                  verdict='AGREE_WITH_WATCH_PRICE_WITH_EXPLICIT_FUNDING_AND_REVENUE_CONVENTION_CAVEATS',
                  direct_double_count_found=False,
                  checks=reviewer_checks, gross_funding=gross_funding, cases=all_cases,
                  stress_caveats={
                      'downstream_sales': '25% lower new downstream sales is a business stress, not an accounting correction for captive feedstock. Working capital is unchanged, deliberately conservative.',
                      'maintenance': 'Higher later capex is a stress, not a demonstrated recurring replacement requirement. Operating repair expenses remain in margins.',
                      'average_interest': 'Assumes linear within-period debt movement and is a sensitivity, not a precise daily financing schedule.',
                      'terminal_cash': 'Already accumulated after investments, taxes and dividends. It is counted once in terminal equity and never simultaneously paid out as FCF.'})
    (HERE / 'epigral_independent_calculations.json').write_text(json.dumps(output, indent=2) + '\n')
    compact = {name: {key: case[key] for key in ['pv12','irr','peak_net_debt','terminal_cash']} for name, case in all_cases.items()}
    summary = dict(
        research_date='2026-11-19', company='EPIGRAL', reference_price=INPUT['price'],
        price_date=INPUT['price_date'], verdict=output['verdict'],
        original_scenarios_reproduced_exactly=['downside','working','upside'],
        direct_double_count_found=False,
        reviewed_input_sha256=output['reviewed_input_sha256'],
        material_findings=[
            'Net debt, dividends and retained cash reconcile without direct double counting.',
            'The remaining 312cr and FY28 400cr capex envelopes are used once, not added to a separate 600cr program.',
            'H2 FY27 needs about 235.25cr and FY28 74.86cr gross incremental/replacement funding under the working assumptions. This is modeled financing, not verified committed drawdowns.',
            'Captive ECH/chlorotoluene requires an explicit external revenue versus internal transfer convention. This is not proof of EBITDA overstatement.',
            'Working PV at12 exceeds current price by0.24%. Margin and exit-multiple assumptions matter more than rounding or interest timing.',
            'The 13.98cr tax timing reserve is not the entire25.30cr September current tax liability. Full liability cash stress is reported separately.',
            '7x is an analyst multiple, not a verified historical floor or a promised market valuation.'
        ],
        gross_funding=gross_funding, checks=reviewer_checks, scenarios=compact,
        reviewer_files=['independent_review.md','review_epigral.py','epigral_independent_input_snapshot.json','epigral_independent_calculations.json'],
        author_files_modified=False)
    (HERE / 'independent_review.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(dict(checks=reviewer_checks, gross_funding=gross_funding, cases=compact), indent=2))


if __name__ == '__main__':
    main()
