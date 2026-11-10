from __future__ import annotations

import runpy
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / 'scripts/cc001_krsnaa_underwriting.py'))


def test_base_case_price_and_return_hurdle_are_separate():
    r = M['valuation'](22, '.15', 16, '493.60', annual_dividend=2)
    assert r['entry_price_for_hurdle_ex_dividends'] == 352
    assert r['price_cagr'] == pytest.approx(.07480911995)
    assert r['required_starting_eps_at_reference'] == 30.85
    assert r['required_growth_at_reference'] == pytest.approx(.230451040517)
    assert r['entry_price_for_hurdle_with_flat_dividend'] == pytest.approx(358.704310196)
    assert r['probability_assigned'] is False


def test_stronger_and_bull_cases_are_not_the_base_case():
    stronger = M['valuation'](22, '.18', 18, '493.60')
    bull = M['valuation'](25, '.20', 20, '493.60')
    assert stronger['entry_price_for_hurdle_ex_dividends'] == pytest.approx(450.41829334)
    assert stronger['price_cagr'] < .15 < bull['price_cagr']
    assert not bull['probability_assigned']


def test_reverse_hurdle_equation_is_invertible():
    r = M['valuation'](22, '.15', 16, '493.60')
    check = M['valuation'](22, r['required_growth_at_reference'], 16, '493.60')
    assert check['price_cagr'] == pytest.approx(.15)


@pytest.mark.parametrize('value', [True, [], {}, None])
def test_invalid_numeric_types_rejected(value):
    with pytest.raises(TypeError):
        M['number'](value)


@pytest.mark.parametrize('value', ['bad', 'NaN', 'Infinity', float('nan')])
def test_nonfinite_or_invalid_numbers_rejected(value):
    with pytest.raises(ValueError):
        M['number'](value)


@pytest.mark.parametrize('args', [(0, .15, 16, 493.6), (22, -1, 16, 493.6),
                                 (22, .15, 0, 493.6), (22, .15, 16, 0)])
def test_invalid_price_scenarios_do_not_render(args):
    with pytest.raises(ValueError):
        M['valuation'](*args)


def test_boolean_horizon_and_unsupported_dividend_rejected():
    with pytest.raises(ValueError):
        M['valuation'](22, '.15', 16, 493.6, years=True)
    with pytest.raises(ValueError):
        M['valuation'](22, '.15', 16, 493.6, annual_dividend=30)


def test_warrant_cash_is_not_counted_twice_or_assumed_exercised():
    r = M['warrant_math'](1621000, 566, '22.93715', '22.937')
    assert r['total_if_exercised_crore'] == pytest.approx(91.7486)
    assert r['conditional_balance_crore'] == pytest.approx(68.81145)
    assert r['additional_upfront_cash_to_add'] == 0
    assert not r['balance_is_received_or_guaranteed']


@pytest.mark.parametrize('args', [(1621000, 566, 91.7486, 22.937),
                                 (1621000, 566, 22.93715, 0), (1.5, 566, 1, 1),
                                 (1621000, -1, 22.93715, 22.937)])
def test_warrant_wrong_funding_and_fractional_shares_rejected(args):
    with pytest.raises(ValueError):
        M['warrant_math'](*args)


def raw_xml(symbol='KRSNAA', unit='INR', duplicate=False):
    f = f'<f:RevenueFromOperations contextRef="FourD" unitRef="{unit}">10000000</f:RevenueFromOperations>'
    return f'<x:xbrl xmlns:x="http://www.xbrl.org/2003/instance" xmlns:f="urn:test"><f:Symbol>{symbol}</f:Symbol><f:ISIN>INE08LI01020</f:ISIN>{f}{f if duplicate else ""}</x:xbrl>'.encode()


def test_xml_exact_identity_units_and_duplicates_are_checked():
    r = M['root_xml'](raw_xml())
    audit = []
    assert M['fact'](r, 'RevenueFromOperations', 'FourD', audit, 'test') == Decimal(1)
    assert audit[0]['raw_inr'] == '10000000'
    for raw in (raw_xml(unit='USD'), raw_xml(duplicate=True)):
        with pytest.raises(ValueError):
            M['fact'](M['root_xml'](raw), 'RevenueFromOperations', 'FourD', [], 'test')
    with pytest.raises(ValueError):
        M['root_xml'](raw_xml(symbol='OTHER'))


def test_unsafe_xml_and_missing_scope_fail():
    for raw in (b'<!DOCTYPE x><x/>', b'<!ENTITY x "x"><x/>', b'a' * 2000001):
        with pytest.raises(ValueError):
            M['root_xml'](raw)
    with pytest.raises(ValueError, match='scope'):
        M['period'](M['root_xml'](raw_xml()), 'FourD', '2025-04-01', '2026-03-31', [], 'test')


def test_retained_sources_and_no_prospective_fill_or_model_call():
    assert len(M['PINS']) == 14
    assert all(len(v) == 64 for v in M['PINS'].values())
    source = (ROOT / 'scripts/cc001_krsnaa_underwriting.py').read_text()
    assert 'actual_current_diluted_denominator_certified' in source
    assert 'WAIT_NO_FRESH_PURCHASE_AT_REFERENCE_PRICE' in source
    assert 'ASSISTED_UNDERWRITING_NOT_PROSPECTIVE_PAPER_ENTRY' in source
    assert 'reviewed' in source


def test_gain_removal_and_full_exercise_are_arithmetic_not_interim_eps_annualization():
    pat = Decimal('101.431') + Decimal('41.138') - Decimal('44.465')
    normal = pat - Decimal('22.241')
    shares = Decimal(32438672)
    full = shares + 1005607 + 1621000
    assert float(pat) == pytest.approx(98.104)
    assert float(normal * 10000000 / shares) == pytest.approx(23.3865923981)
    assert float(normal * 10000000 / full) == pytest.approx(21.6347914984)
    assert int(full) == 35065279


def test_price_identity_and_date_must_match_dated_case(tmp_path):
    with pytest.raises(ValueError, match='9 November'):
        M['verify_price'](tmp_path, {'identity': M['IDENTITY'], 'session_date': '2026-11-10'})


def test_completed_case_preserves_original_screen_and_disables_resume():
    import hashlib
    import json

    records = json.loads((ROOT / 'research/operations/carried-forward-decisions.json').read_text())
    assert len({(r['symbol'], r['isin']) for r in records}) == len(records) == 4
    rec = next(r for r in records if r['symbol'] == 'KRSNAA')
    assert rec['case_depth'] == 'FULL_UNDERWRITING' and rec['disposition'] == 'WAIT'
    assert rec['resume_underwriting'] is False and rec['workflow_state'] == 'DATED_WAIT'
    assert rec['decision_published_at'] == '2026-11-10T05:40:15Z'
    assert rec['price_date'] == '2026-11-09' and rec['reference_price_inr'] == 493.6
    assert rec['prospective_entry_price'] is None and not rec['live_capital_allowed']
    old = rec['prior_research_records'][0]
    digest = hashlib.sha256(json.dumps(old, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert digest == '3179149f3d98bbffdd96174c72d41eda846ef8099d6fe433700c95abef5bdb59'
    assert old['case_depth'] == 'PRELIMINARY_SCREEN' and old['resume_underwriting'] is True
