from __future__ import annotations

import runpy
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / 'scripts/cc001_seamec_underwriting.py'))


def test_current_price_scenario_and_entry_hurdle_are_separate():
    s = M['scenario'](100, '.12', 12, '1526.60')
    assert s['terminal_price'] == pytest.approx(2114.81001984)
    assert s['entry_price_meeting_hurdle'] == pytest.approx(1051.43434144)
    assert s['price_cagr_at_reference'] == pytest.approx(.067355814474)
    assert not s['probability_assigned'] and not s['dividends_taxes_costs_included']


def test_generous_scenario_still_misses_fifteen_percent_at_reference():
    s = M['scenario'](115, '.15', 12, '1526.60')
    assert s['entry_price_meeting_hurdle'] == 1380
    assert s['price_cagr_at_reference'] < .15


def test_stress_is_not_a_maximum_loss_or_probability_forecast():
    s = M['scenario'](80, 0, 10, '1526.60')
    assert s['terminal_price'] == 800
    assert s['terminal_value_change_from_reference'] == pytest.approx(-.4759596489)
    assert s['probability_assigned'] is False


def test_pretax_removal_keeps_tax_as_explicit_assumption():
    no_tax = M['earnings_lens']('334.64', '42.43', 25425000, 0)
    partial_tax = M['earnings_lens']('334.64', '42.43', 25425000, '.25')
    assert no_tax == Decimal('292.21') * 10000000 / 25425000
    assert partial_tax > no_tax
    assert float(no_tax) == pytest.approx(114.930186824)
    strict = M['earnings_lens']('334.64', '103.78', 25425000, 0)
    assert float(strict) == pytest.approx(90.800393314)


@pytest.mark.parametrize('v', [True, float('nan'), float('inf'), [], None])
def test_nonfinancial_numbers_rejected(v):
    with pytest.raises((ValueError, TypeError)):
        M['number'](v)


@pytest.mark.parametrize('args', [(0, .1, 12, 100), (100, -1, 12, 100),
                                   (100, .1, 0, 100), (100, .1, 12, 0)])
def test_invalid_scenarios_not_shown(args):
    with pytest.raises(ValueError):
        M['scenario'](*args)


def test_fractional_years_or_boolean_horizon_rejected():
    for years in (True, 1.5, 0, 11):
        with pytest.raises(ValueError):
            M['scenario'](100, .1, 12, 100, years=years)


def test_amount_and_share_denominator_validation():
    for args in [(100, -5, 25425000, 0), (100, 5, 0, 0), (100, 5, 25425000, 1.5)]:
        with pytest.raises(ValueError):
            M['earnings_lens'](*args)


def xml(symbol='SEAMECLTD', duplicate=False, unit='INR'):
    fact = f'<f:RevenueFromOperations contextRef="FourD" unitRef="{unit}" decimals="-5">10000000</f:RevenueFromOperations>'
    return f'''<x:xbrl xmlns:x="http://www.xbrl.org/2003/instance" xmlns:f="urn:test">
<f:Symbol contextRef="OneD">{symbol}</f:Symbol><f:ISIN contextRef="OneD">INE497B01018</f:ISIN>
{fact}{fact if duplicate else ''}</x:xbrl>'''.encode()


def test_exact_issuer_fact_and_units_no_first_value_wins():
    root = M['root_xml'](xml())
    audit = []
    assert M['fact'](root, 'RevenueFromOperations', 'FourD', audit, 'source') == 1
    assert audit[0]['raw_value'] == '10000000'
    for raw in (xml(duplicate=True), xml(unit='USD')):
        with pytest.raises(ValueError):
            M['fact'](M['root_xml'](raw), 'RevenueFromOperations', 'FourD', [], 'source')
    with pytest.raises(ValueError):
        M['root_xml'](xml(symbol='OTHER'))


def test_unsafe_or_oversized_xml_not_parsed():
    for raw in (b'<!DOCTYPE x><x/>', b'<!ENTITY x "test"><x/>', b'x' * 2000001):
        with pytest.raises(ValueError):
            M['root_xml'](raw)


def test_original_pins_and_no_interim_eps_annualization():
    src = (ROOT / 'scripts/cc001_seamec_underwriting.py').read_text()
    assert "annual.pages[210].extract_text()" in src
    assert 'EPS and shares are never added or annualized' in src
    assert len(M['PINS']) == 10
    assert all(len(h) == 64 for h in M['PINS'].values())
    assert 'WAIT_NO_FRESH_PURCHASE_AT_REFERENCE_PRICE' in src
