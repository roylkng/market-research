from __future__ import annotations

import copy
import json

import pytest

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_decisions import (
    POLICY,
    build_report,
    decision_context,
    load_latest,
    sensitivity,
    trailing_cash,
)
from marketlab.company_change_store import EvidenceStore

NOW = '2026-11-08T00:00:00Z'
ID = {'symbol': 'TEST', 'isin': 'INE000A01001', 'scope': 'CONSOLIDATED'}


def raw_card():
    def period(start, end, revenue, owner, cfo, capex, eps=None):
        facts = {k: {'value': v, 'unit': 'INR_crore', 'rounding_error': 0.00001} for k, v in
                 [('revenue', revenue), ('owner_pat', owner), ('group_pat', owner), ('minority_pat', 0),
                  ('cfo', cfo), ('ppe_purchases', capex), ('intangible_purchases', 0), ('intangible_development', 0)]}
        if eps is not None:
            facts['diluted_eps'] = {'value': eps, 'unit': 'INR_per_share'}
        return {'identity': ID, 'period_start': start, 'period_end': end, 'facts': facts,
                'known_at': '2026-11-07T12:00:00Z', 'published_at': '2026-11-01T10:00:00Z',
                'source_url': 'https://nsearchives.nseindia.com/source.xml', 'raw_sha256': canonical_hash([start, end])}
    return {'identity': ID, 'current_period_end': '2026-09-30', 'as_of': '2026-11-07T13:00:00Z',
            'financial_periods': [period('2025-04-01','2026-03-31',100,10,14,4,5),
                                 period('2026-04-01','2026-09-30',60,6,8,2),
                                 period('2025-04-01','2025-09-30',40,4,4,1)],
            'quote': {'identity': ID, 'price': 70, 'quoted_at': '2026-11-06T10:00:00Z',
                      'observed_at': '2026-11-07T12:00:00Z'},
            'corporate_actions': {'start_exclusive': '2025-03-31', 'end_inclusive': '2026-11-07',
                                 'share_basis_changes_or_unknown_actions': []}, 'retrieval_errors': []}


def test_sensitivity_is_reproducible_and_explicit_not_buy_approval():
    raw = raw_card()
    before = copy.deepcopy(raw)
    result = decision_context(raw, NOW)
    assert raw == before
    assert result['reported_reference_pe'] == 14
    assert result['reported_revenue_growth_yoy'] == .5
    assert result['reported_trailing_cash']['cfo_less_specified_capex_crore'] == 13
    assert not result['buy_approved'] and not result['live_capital_allowed']
    assert len(result['sensitivity']['rows']) == 6
    assert result['category'] == 'FULL_UNDERWRITING_REQUIRED'
    row = next(r for r in result['sensitivity']['rows'] if r['retained_reported_eps_fraction'] == 1 and r['eps_growth_assumption'] == .15)
    assert row['price_consistent_with_hurdle'] == pytest.approx(75)


def test_hurdle_category_does_not_imply_negative_expected_return():
    raw = raw_card()
    raw['quote']['price'] = 200
    result = decision_context(raw, NOW)
    assert result['category'] == 'HURDLE_EXCEEDS_ILLUSTRATIVE_GROWTH_RANGE'
    assert 'forecast' not in result['category']
    assert result['sensitivity']['policy']['classification'].endswith('NOT_FORECASTS')


def test_negative_cash_sends_to_funding_diligence():
    raw = raw_card()
    raw['financial_periods'][0]['facts']['ppe_purchases']['value'] = 40
    result = decision_context(raw, NOW)
    assert result['category'] == 'FUNDING_DILIGENCE'
    assert result['reported_trailing_cash']['cfo_less_specified_capex_crore'] < 0


def test_negative_purchase_sign_never_becomes_extra_cash():
    raw = raw_card()
    raw['financial_periods'][0]['facts']['ppe_purchases']['value'] = -40
    cash = decision_context(raw, NOW)['reported_trailing_cash']
    assert cash['status'] == 'AMBIGUOUS_PURCHASE_SIGN'
    assert cash['cfo_less_specified_capex_crore'] is None


def test_missing_cash_is_unknown_not_zero():
    raw = raw_card()
    del raw['financial_periods'][1]['facts']['cfo']
    assert decision_context(raw, NOW)['reported_trailing_cash']['cfo_less_specified_capex_crore'] is None
    assert trailing_cash({'reported_ttm_flows': None})['status'] == 'MISSING_INPUT'


def test_mismatched_owner_profit_blocks_ratio_and_false_negative_trailing_profit():
    raw = raw_card()
    raw['financial_periods'][0]['facts']['owner_pat']['value'] = 0
    result = decision_context(raw, NOW)
    assert result['category'] == 'EVIDENCE_BLOCKED'
    assert result['reported_reference_pe'] is None
    assert result['sensitivity'] is None
    assert result['reported_trailing_cash']['cfo_crore'] == 18
    assert any('withheld' in s for s in result['observations'])


def test_wrong_source_or_stale_price_cannot_reuse_cached_ratio():
    raw = raw_card()
    raw['price_over_reported_annual_eps'] = 1
    raw['quote']['quoted_at'] = '2026-01-01T00:00:00Z'
    result = decision_context(raw, NOW)
    assert result['reported_reference_pe'] is None
    assert result['category'] == 'EVIDENCE_BLOCKED'
    assert result['sensitivity'] is None


@pytest.mark.parametrize('fault', ['source_error', 'rejected', 'unsafe_url'])
def test_evidence_failures_not_overridden_by_attractive_price(fault):
    raw = raw_card()
    raw['quote']['price'] = 1
    if fault == 'unsafe_url':
        raw['financial_periods'][0]['source_url'] = 'javascript:alert(1)'
        with pytest.raises(ChangeError):
            decision_context(raw, NOW)
        return
    if fault == 'source_error':
        raw['retrieval_errors'] = [{'stage': 'source', 'reason': 'mismatch'}]
    else:
        raw['anchor_review_status'] = 'REJECT'
    result = decision_context(raw, NOW)
    assert result['category'] == 'EVIDENCE_BLOCKED'
    assert not result['buy_approved']


def test_future_context_does_not_exist_at_earlier_cutoff():
    with pytest.raises(ChangeError, match='observed'):
        decision_context(raw_card(), '2026-11-07T10:00:00Z')


@pytest.mark.parametrize('eps,price', [(0,70),(-1,70),(True,70),(5,0),(5,float('nan'))])
def test_sensitivity_rejects_invalid_numbers(eps,price):
    with pytest.raises(ChangeError):
        sensitivity(eps, price, POLICY)


def test_haircut_cannot_improve_return():
    result = sensitivity(5,70,POLICY)
    for growth in POLICY['eps_growth_scenarios']:
        selected = [r for r in result['rows'] if r['eps_growth_assumption'] == growth]
        assert selected[0]['price_consistent_with_hurdle'] < selected[1]['price_consistent_with_hurdle']
        assert selected[0]['price_cagr_at_observed_price'] < selected[1]['price_cagr_at_observed_price']


def test_latest_context_keeps_a_new_failed_record_instead_of_old_success(tmp_path):
    with EvidenceStore(tmp_path) as store:
        store.db.execute('CREATE TABLE cc_context_runs(id TEXT,known_at TEXT,payload TEXT)')
        old = raw_card()
        new = copy.deepcopy(old)
        new['as_of'] = '2026-11-07T14:00:00Z'
        new['retrieval_errors'] = [{'reason':'mismatch'}]
        for raw in (old,new):
            raw['card_sha256'] = canonical_hash(raw)
            store.db.execute('INSERT INTO cc_context_runs VALUES (?,?,?)',
                             (raw['card_sha256'],raw['as_of'],json.dumps(raw)))
        store.db.commit()
        assert load_latest(store,NOW)[0]['retrieval_errors']
        assert load_latest(store,'2026-11-07T13:30:00Z')[0]['retrieval_errors'] == []


def test_stored_context_tampering_fails(tmp_path):
    with EvidenceStore(tmp_path) as store:
        store.db.execute('CREATE TABLE cc_context_runs(id TEXT,known_at TEXT,payload TEXT)')
        raw = raw_card()
        raw['card_sha256'] = canonical_hash(raw)
        raw['quote']['price'] = 1
        store.db.execute('INSERT INTO cc_context_runs VALUES (?,?,?)',
                         (raw['card_sha256'],raw['as_of'],json.dumps(raw)))
        store.db.commit()
        with pytest.raises(ChangeError,match='integrity'):
            load_latest(store,NOW)


def test_all_output_remains_research_and_alphabetical_input_order():
    report = build_report([raw_card()], NOW)
    assert not report['validated_predictive_edge']
    assert report['counts']['issuers'] == 1
    assert report['report_sha256'] == canonical_hash({k:v for k,v in report.items() if k != 'report_sha256'})
