#!/usr/bin/env python3
"""Entry-price-only sensitivity with frozen per-share cashflows and timing.

Reads adjacent inputs.json and writes adjacent results.json unless overridden.
Uses only Python's standard library. No network or external model execution.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


def periods(case):
    if case['timing_convention'] == 'equal_annual_periods':
        return list(range(len(case['cashflows_per_share'])))
    if case['timing_convention'] == 'actual_days_over_365_25':
        dates = [dt.date.fromisoformat(v) for v in case['dates']]
        return [(v - dates[0]).days / 365.25 for v in dates]
    raise ValueError('Unknown timing convention')


def solve_irr(flows, times):
    assert flows[0] < 0 and all(x >= 0 for x in flows[1:])
    def npv(rate):
        return sum(v / (1 + rate) ** t for v, t in zip(flows, times))
    lo, hi = -0.99, 5.0
    assert npv(lo) > 0 and npv(hi) < 0
    for _ in range(180):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    rate = (lo + hi) / 2
    assert abs(npv(rate)) < 1e-8
    return rate


def calculate(data):
    rows = []
    for case in data['cases']:
        times = periods(case)
        original = case['cashflows_per_share']
        assert original[0] == -case['reference_price']
        assert len(times) == len(original)
        old = solve_irr(original, times)
        assert abs(old - case['published_annualized_return']) < 1e-10, case['id']
        repriced = [-case['observed_price']] + original[1:]
        assert repriced[1:] == original[1:]
        new = solve_irr(repriced, times)
        rows.append({
            'id': case['id'], 'symbol': case['symbol'], 'label': case['label'],
            'reference_price': case['reference_price'],
            'observed_price': case['observed_price'],
            'observed_at_ist': case['observed_at_ist'],
            'price_change_from_model_reference_pct': (case['observed_price'] / case['reference_price'] - 1) * 100,
            'published_annualized_return': case['published_annualized_return'],
            'reproduced_annualized_return': old,
            'repriced_annualized_return': new,
            'return_change_percentage_points': (new - old) * 100,
            'timing_convention': case['timing_convention'],
            'time_periods_years': times,
            'repriced_cashflows_per_share': repriced,
            'source_cashflow_pointer': case['source_cashflow_pointer'],
            'original_rate_reproduced': True,
            'future_cashflows_unchanged': True,
        })
    return {
        'classification': 'ENTRY_PRICE_ONLY_SENSITIVITY_NOT_FORECAST_ROLL_FORWARD',
        'statement': data['statement'],
        'source_repository_commit': data['source_repository_commit'],
        'cashflows_and_timing_frozen': True,
        'all_original_rates_reproduced': True,
        'results': rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=Path(__file__).with_name('inputs.json'))
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('results.json'))
    args = parser.parse_args()
    raw = args.input.read_bytes()
    result = calculate(json.loads(raw))
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    result['calculator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    for row in result['results']:
        print(f"{row['id']}: {100*row['reproduced_annualized_return']:.6f}% -> {100*row['repriced_annualized_return']:.6f}%")


if __name__ == '__main__':
    main()
