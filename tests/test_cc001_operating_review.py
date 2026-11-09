from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path

import pytest

from marketlab.company_change import ChangeError, canonical_hash

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / 'scripts/cc001_operating_review.py'))
NOW = '2026-11-10T00:00:00Z'
SOURCE_TIME = '2026-11-08T10:00:00Z'


def seal(report):
    report.pop('report_sha256', None)
    report['report_sha256'] = canonical_hash(report)
    return report


def inputs(n=9):
    business, cash = [], []
    for i in range(n):
        ident = {'symbol': f'COMP{i}', 'isin': f'INE{i:06}01001', 'scope': 'CONSOLIDATED'}
        raw = canonical_hash(['source', i])
        extraction = canonical_hash(['extraction', i])
        business.append({**ident, 'period_end': '2026-09-30', 'flags': [],
            'current': {'raw_sha256': raw, 'extraction_id': extraction, 'known_at': SOURCE_TIME},
            'metrics': {'revenue': {'growth_fraction': .12 if i < 6 else -.1}, 'pbt': {'current': 1}}})
        cash.append({**ident, 'raw_sha256': raw, 'source_url': 'https://issuer.example/source.xml',
            'prior_extraction_id': extraction, 'parsed_at': SOURCE_TIME, 'financial_fact_review': 'UNREVIEWED',
            'analysis': {'period_start': '2026-04-01', 'period_end': '2026-09-30',
                         'disposition': 'CASH_COVERED_SPECIFIED_CAPEX',
                         'cfo_less_specified_capex_crore': 10,
                         'same_source_year_ago': {'revenue': {'growth_fraction': None}}}})
    out = {'business-changes': seal({'as_of': SOURCE_TIME, 'snapshot_sha256': 'clock-a', 'cards': business}),
           'cash-underwriting': seal({'evaluated_at': SOURCE_TIME, 'snapshot_sha256': 'clock-b', 'cards': cash}),
           'decision-context': seal({'as_of': SOURCE_TIME, 'cards': []}),
           'news-inbox': seal({'as_of': SOURCE_TIME, 'failures': [],
                'deferred': [{'reason': 'ACTIVE_STORAGE_HEADROOM_REQUIRED'}],
                'coverage': {'announcements_in_received_queue': 12, 'original_attachments_read': 4,
                             'readings_remaining': 8, 'identity_or_evidence_blocked': 2}}),
           'checkpoint': {'expanded_bytes': 124451387},
           'latest': {'recorded_at': '2026-11-08T10:01:00Z', 'source_commit': 'a' * 40,
                      'run_url': 'https://github.com/owner/repo/actions/runs/1', 'unreviewed': 18,
                      'news_reader_status': 'FAILED', 'news_reader_sha256': None,
                      'business_change_status': 'SUCCESS', 'cash_underwriting_status': 'SUCCESS',
                      'coverage': {'counts': {'EXTRACTED': 9, 'FAILED': 3, 'PENDING': 41}}}}
    links(out)
    return out


def links(value):
    for name, key in [('business-changes', 'business_change_sha256'),
                      ('cash-underwriting', 'cash_underwriting_sha256'),
                      ('decision-context', 'decision_context_sha256')]:
        seal(value[name])
        value['latest'][key] = value[name]['report_sha256']
    seal(value['news-inbox'])
    return value


def record(card, **changes):
    return {'symbol': card['symbol'], 'isin': card['isin'], 'disposition': 'RESEARCH_ONLY',
            'evidence_class': 'HISTORICAL_CARRY_FORWARD_NOT_PROSPECTIVE_ENTRY',
            'case_depth': 'PRELIMINARY_SCREEN', 'decision_published_at': '2026-11-09T10:00:00Z',
            'price_date': '2026-11-09', 'reviewed_source_hashes': [card['raw_sha256']],
            'live_capital_allowed': False, **changes}


def test_explicit_full_denominator_capacity_and_no_skill_claim():
    value = inputs()
    original = copy.deepcopy(value)
    report = M['build'](value, [], NOW)
    assert value == original
    assert report['funnel']['financial_issuers'] == 9
    assert report['funnel']['same_source_yoy_revenue_available_issuers'] == 0
    assert len(report['next_diligence_batch']) == 5
    assert len(report['remaining_candidates']) == 4
    assert sum(report['lane_counts'].values()) == 9
    assert report['capacity_lower_bounds_no_new_arrivals']['financial_processing_runs'] == 2
    assert report['capacity_lower_bounds_no_new_arrivals']['news_processing_runs'] == 2
    assert report['health']['news_storage_blocked'] and report['health']['snapshot_stale']
    assert not report['live_capital_allowed'] and not report['validated_predictive_edge']
    assert all(not c['buy_approved'] for c in report['next_diligence_batch'])


def test_selection_is_deterministic_and_not_input_order_dependent():
    value = inputs()
    first = M['build'](value, [], NOW)['next_diligence_batch']
    value['business-changes']['cards'].reverse()
    value['cash-underwriting']['cards'].reverse()
    second = M['build'](links(value), [], NOW)['next_diligence_batch']
    assert first == second
    assert len({c['isin'] for c in first}) == len(first)


def test_two_clocks_do_not_require_identical_snapshot_hashes():
    value = inputs()
    assert value['business-changes']['snapshot_sha256'] != value['cash-underwriting']['snapshot_sha256']
    assert M['build'](value, [], NOW)['funnel']['financial_issuers'] == 9


@pytest.mark.parametrize('fault', ['hash', 'receipt', 'future_report', 'future_snapshot', 'ambiguous_card', 'unverified_export'])
def test_corrupted_or_unavailable_exports_fail(fault):
    value = inputs()
    if fault == 'hash':
        value['cash-underwriting']['cards'][0]['analysis']['cfo_less_specified_capex_crore'] = 99999
    elif fault == 'receipt':
        value['latest']['cash_underwriting_sha256'] = 'wrong'
    elif fault == 'future_report':
        value['cash-underwriting']['evaluated_at'] = '2026-11-11T00:00:00Z'
        links(value)
    elif fault == 'future_snapshot':
        value['latest']['recorded_at'] = '2026-11-11T00:00:00Z'
    elif fault == 'ambiguous_card':
        value['cash-underwriting']['cards'].append(copy.deepcopy(value['cash-underwriting']['cards'][0]))
        links(value)
    else:
        value['latest']['cash_underwriting_sha256'] = None
    with pytest.raises(ChangeError):
        M['build'](value, [], NOW)


def test_wrong_source_or_missing_quarter_never_creates_a_positive_cue():
    value = inputs()
    value['business-changes']['cards'][0]['current']['raw_sha256'] = 'other'
    value['business-changes']['cards'][1]['current'] = None
    report = M['build'](links(value), [], NOW)
    by = {c['symbol']: c for c in report['next_diligence_batch'] + report['remaining_candidates']}
    for name in ('COMP0', 'COMP1'):
        assert by[name]['lane'] == 'EXPLORATION'
        assert by[name]['sequential_revenue_growth'] is None


def test_exceptional_profit_and_rejected_source_not_promoted_as_clean_cues():
    value = inputs()
    value['business-changes']['cards'][0]['flags'] = ['PRETAX_EXCEPTIONAL_ITEM_PRESENT']
    value['cash-underwriting']['cards'][1]['financial_fact_review'] = 'REJECT'
    report = M['build'](links(value), [], NOW)
    by = {c['symbol']: c for c in report['next_diligence_batch'] + report['remaining_candidates']}
    assert by['COMP0']['lane'] == 'EXPLORATION'
    assert by['COMP1']['lane'] == 'REJECTED_EXTRACTION_REVIEW'
    assert 'COMP1' not in [c['symbol'] for c in report['next_diligence_batch']]
    assert len(by) == 9


def test_consolidated_and_standalone_are_not_double_counted():
    value = inputs()
    duplicate = copy.deepcopy(value['cash-underwriting']['cards'][0])
    duplicate['scope'] = 'STANDALONE'
    value['cash-underwriting']['cards'].append(duplicate)
    report = M['build'](links(value), [], NOW)
    assert report['funnel']['financial_issuers'] == 9
    chosen = next(c for c in report['next_diligence_batch'] + report['remaining_candidates'] if c['symbol'] == 'COMP0')
    assert chosen['scope'] == 'CONSOLIDATED'


def test_previous_case_not_recycled_until_new_filing_and_depth_is_explicit():
    value = inputs()
    first = M['build'](value, [], NOW)['next_diligence_batch'][0]
    old = record(first)
    report = M['build'](value, [old], NOW)
    assert first['symbol'] not in [c['symbol'] for c in report['next_diligence_batch']]
    assert report['funnel']['preliminary_screens'] == 1
    assert report['funnel']['full_underwriting_memos'] == 0
    old['reviewed_source_hashes'] = ['older-source']
    report = M['build'](value, [old], NOW)
    reopened = next(c for c in report['next_diligence_batch'] if c['symbol'] == first['symbol'])
    assert reopened['reopened_for_new_filing']
    assert not reopened['buy_approved']


@pytest.mark.parametrize('fault', ['BUY', 'future', 'capital', 'duplicate', 'prospective'])
def test_old_case_cannot_be_turned_into_live_trade_or_new_forecast(fault):
    value = inputs()
    rec = record(value['cash-underwriting']['cards'][0])
    if fault == 'BUY':
        rec['disposition'] = 'BUY'
    elif fault == 'future':
        rec['decision_published_at'] = '2026-11-11T00:00:00Z'
    elif fault == 'capital':
        rec['live_capital_allowed'] = True
    elif fault == 'prospective':
        rec['evidence_class'] = 'PROSPECTIVE'
    records = [rec, rec] if fault == 'duplicate' else [rec]
    with pytest.raises(ChangeError):
        M['build'](value, records, NOW)


def test_output_cannot_overwrite_source_reports(tmp_path):
    with pytest.raises(ChangeError, match='outside'):
        M['main'](['--reports', str(tmp_path), '--decisions', 'unused.json',
                   '--output-prefix', str(tmp_path / 'latest')])


def test_cash_boolean_or_infinite_growth_does_not_qualify():
    assert not M['positive'](True)
    assert not M['positive'](float('inf'))
    assert not M['positive'](None)


def test_cli_offline_inputs_unchanged_and_html_escapes(tmp_path):
    source = tmp_path / 'inputs'
    source.mkdir()
    value = inputs()
    value['cash-underwriting']['cards'][0]['symbol'] = '<script>COMP0</script>'
    links(value)
    for name in M['FILES']:
        (source / (name + '.json')).write_text(json.dumps(value[name]))
    decisions = tmp_path / 'decisions.json'
    decisions.write_text('[]')
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    output = tmp_path / 'out/review'
    assert M['main'](['--reports', str(source), '--decisions', str(decisions),
                      '--output-prefix', str(output), '--as-of', NOW]) == 0
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}
    page = output.with_suffix('.html').read_text()
    assert '<script>COMP0</script>' not in page
    result = json.loads(output.with_suffix('.json').read_text())
    assert result['report_sha256'] == canonical_hash({k: v for k, v in result.items() if k != 'report_sha256'})


def test_workflow_does_not_trade_fetch_models_or_mutate_production():
    text = (ROOT / '.github/workflows/cc001-operating-review.yml').read_text()
    assert 'contents: read' in text
    assert 'schedule:' not in text
    assert 'push origin' not in text
    assert 'company_change_semantics' not in text
    assert 'FETCH_HEAD' in text


def test_failed_lane_with_retained_old_hash_cannot_seed_new_diligence():
    value = inputs()
    value['latest']['cash_underwriting_status'] = 'FAILED'
    with pytest.raises(ChangeError, match='successful'):
        M['build'](value, [], NOW)


def test_exploration_reservation_cannot_be_filled_with_more_growth_cues():
    value = inputs()
    report = M['build'](value, [], NOW)
    picked = report['next_diligence_batch']
    assert sum(c['lane'] == 'CASH_SUPPORTED_SEQUENTIAL_CUE' for c in picked) == 3
    assert sum(c['lane'] != 'CASH_SUPPORTED_SEQUENTIAL_CUE' for c in picked) == 2


def test_unfinished_screen_is_resumed_not_mistaken_for_a_closed_case():
    value = inputs()
    card = value['cash-underwriting']['cards'][8]
    legacy = record(card, resume_underwriting=True)
    report = M['build'](value, [legacy], NOW)
    batch = report['next_diligence_batch']
    assert len(batch) == 5
    assert batch[0]['symbol'] == card['symbol']
    assert batch[0]['existing_company_memo'] and batch[0]['resume_underwriting']
    assert sum(c['lane'] == 'CASH_SUPPORTED_SEQUENTIAL_CUE' for c in batch) == 2
    assert report['funnel']['explicit_unfinished_cases'] == 1
    assert not batch[0]['buy_approved']


def test_resume_marker_cannot_turn_a_full_memo_into_a_false_open_screen():
    value = inputs()
    legacy = record(value['cash-underwriting']['cards'][0], resume_underwriting=True, case_depth='FULL_UNDERWRITING')
    with pytest.raises(ChangeError, match='unfinished preliminary'):
        M['build'](value, [legacy], NOW)
