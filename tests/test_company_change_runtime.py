from __future__ import annotations

import copy
import hashlib
import html
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from marketlab.company_change import ChangeError, SourceDocument
from marketlab.company_change_evaluation import score_extraction, validate_dataset
from marketlab.company_change_pipeline import (
    call_extractor,
    check_url,
    document_text,
    economic_features,
    fetch_original,
    ingest,
    main,
    model_config,
    project_html,
    record_decision,
    render_inbox,
    write_outputs,
)
from marketlab.company_change_store import EvidenceStore, loads_unique

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def layout():
    data = json.loads((ROOT / 'data/fixtures/company_change_real_v1.json').read_text())
    tables = data['sources'][1]['tables']
    return ''.join('<table>' + ''.join('<tr>' + ''.join(
        '<td>' + html.escape(v) + '</td>' for v in row) + '</tr>' for row in table)
        + '</table>' for table in tables).encode()


@pytest.fixture
def manifest(tmp_path, layout):
    (tmp_path / 'original.html').write_bytes(layout)
    return {'schema_version': 1, 'allowed_hosts': ['nsearchives.nseindia.com'], 'sources': [{
        'source_id': 'krbl-original', 'url': 'https://nsearchives.nseindia.com/example.html',
        'symbol': 'KRBL', 'isin': 'INE001B01026', 'kind': 'earnings_quality',
        'event_key': 'FY26', 'scope': 'CONSOLIDATED', 'period_start': '2025-04-01',
        'period_end': '2026-03-31', 'format': 'html', 'extractor': 'statement',
        'rights': 'INTERNAL_RESEARCH', 'local_file': 'original.html'}]}


def test_original_bytes_persist_across_processes(tmp_path, manifest, layout):
    root = tmp_path / 'store'
    with EvidenceStore(root) as store:
        first = ingest(manifest, store, base=tmp_path)
        assert not first['failures']
        ident = first['successes'][0]['extraction_id']
        digest = first['successes'][0]['raw_sha256']
        assert store.read_blob(digest) == layout
        assert digest == hashlib.sha256(layout).hexdigest()
        assert first['snapshot']['active'][0]['facts']['revenue']['value'] == 6097.86
    with EvidenceStore(root) as store:
        second = ingest(manifest, store, base=tmp_path)
        assert second['successes'][0]['extraction_id'] == ident
        assert len(second['snapshot']['history']) == 1
        assert store.db.execute('SELECT COUNT(*) FROM captures').fetchone()[0] == 1
        assert store.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 2


def test_revision_keeps_old_bytes_and_invalidates_old_review(tmp_path, manifest, layout):
    with EvidenceStore(tmp_path / 'store') as store:
        first = ingest(manifest, store, base=tmp_path)
        ident = first['successes'][0]['extraction_id']
        store.review(ident, 'reviewer', 'ACCEPT', 'Checked original cells and scope')
        assert len(economic_features(store.snapshot())['rows']) == 1
        (tmp_path / 'original.html').write_bytes(layout.replace(b'6,09,786.00', b'6,09,787.00'))
        second = ingest(manifest, store, base=tmp_path)
        active = second['snapshot']['active'][0]
        assert active['changed'] is True
        assert active['review_status'] == 'UNREVIEWED'
        assert active['supersedes_extraction_id'] == ident
        assert len(second['snapshot']['history']) == 2
        assert economic_features(second['snapshot'])['rows'] == []


def test_point_in_time_snapshot_and_review(tmp_path, manifest):
    clock = ['2026-11-07T10:00:00Z']
    with EvidenceStore(tmp_path / 'store', clock=lambda: clock[0]) as store:
        report = ingest(manifest, store, base=tmp_path)
        identity = report['successes'][0]['extraction_id']
        assert store.snapshot('2026-11-07T09:59:00Z')['active'] == []
        clock[0] = '2026-11-08T10:00:00Z'
        store.review(identity, 'r', 'ACCEPT', 'verified')
        assert store.snapshot('2026-11-07T12:00:00Z')['active'][0]['review_status'] == 'UNREVIEWED'
        assert store.snapshot()['active'][0]['review_status'] == 'ACCEPT'
        exported = economic_features(store.snapshot())['rows'][0]
        assert all(x == '2026-11-08T10:00:00+00:00' for x in exported['known_at'].values())
        assert exported['outcomes_attached'] is False


def test_blob_tampering_is_detected(tmp_path, manifest):
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
        sha = report['successes'][0]['raw_sha256']
        (store.root / 'blobs' / sha[:2] / sha).write_bytes(b'tampered')
        with pytest.raises(ChangeError, match='integrity'):
            store.snapshot()


def test_database_extraction_tampering_detected(tmp_path, manifest):
    with EvidenceStore(tmp_path / 'store') as store:
        ingest(manifest, store, base=tmp_path)
        row = store.db.execute('SELECT id,result FROM extractions').fetchone()
        data = json.loads(row['result'])
        data['symbol'] = 'FAKE'
        store.db.execute('UPDATE extractions SET result=? WHERE id=?', (json.dumps(data), row['id']))
        store.db.commit()
        with pytest.raises(ChangeError, match='integrity'):
            store.snapshot()


@pytest.mark.parametrize('namespace', ['hypotheses', 'registry', 'experiments', 'prospective', 'hg009', 'ae001'])
def test_protected_namespaces(tmp_path, namespace):
    with pytest.raises(ChangeError, match='frozen'):
        EvidenceStore(tmp_path / namespace)


def test_nested_html_wrappers_are_not_double_counted(layout):
    tables, origins = project_html(b'<table><tr><td>' + layout + b'</td></tr></table>')
    assert len(tables) == 2
    assert origins['1'][3][2]['text'] == '1,52,550.00'


def test_merged_label_preserves_value_column(tmp_path, manifest, layout):
    original = b'<td></td><td>Revenue from operations</td>'
    changed = layout.replace(original, b'<td colspan="2">Revenue from operations</td>')
    (tmp_path / 'original.html').write_bytes(changed)
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
        assert not report['failures']
        value = report['snapshot']['active'][0]['facts']['revenue']
        assert value['value'] == 6097.86
        assert value['original_dom_cell']['text'] == '6,09,786.00'


def test_raw_content_retained_even_on_parse_failure(tmp_path, manifest):
    (tmp_path / 'original.html').write_bytes(b'<html>maintenance unavailable</html>')
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
        assert len(report['failures']) == 1
        assert store.db.execute('SELECT COUNT(*) FROM captures').fetchone()[0] == 1
        assert report['snapshot']['active'] == []


def test_failures_do_not_erase_successes(tmp_path, manifest):
    bad = {**manifest['sources'][0], 'source_id': 'missing', 'local_file': 'not-found.html'}
    manifest['sources'].append(bad)
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
        assert len(report['successes']) == len(report['failures']) == 1


def test_local_path_escape_rejected(tmp_path, manifest):
    manifest['sources'][0]['local_file'] = '../outside.html'
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
        assert 'escapes' in report['failures'][0]['reason']


def test_network_requires_explicit_opt_in(tmp_path, manifest):
    del manifest['sources'][0]['local_file']
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
        assert 'NETWORK_DISABLED' in report['failures'][0]['reason']


@pytest.mark.parametrize('url', ['http://nsearchives.nseindia.com/a', 'https://evil.test/a',
    'https://nsearchives.nseindia.com.evil.test/a', 'https://user:pass@nsearchives.nseindia.com/a',
    'https://nsearchives.nseindia.com:444/a', 'https://nsearchives.nseindia.com/a?token=x'])
def test_source_url_restrictions(url):
    with pytest.raises(ChangeError):
        check_url(url, {'nsearchives.nseindia.com'}, resolve=False)


class Response:
    def __init__(self, raw=b'', status=200, headers=None):
        self.raw, self.status_code, self.headers = raw, status, headers or {}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None
    def raise_for_status(self):
        if self.status_code >= 400:
            raise ChangeError('HTTP error')
    def iter_content(self, size):
        yield self.raw


class Transport:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_unsafe_redirect_not_followed():
    client = Transport([Response(status=302, headers={'Location': 'https://evil.test/steal'})])
    with pytest.raises(ChangeError, match='allowlist'):
        fetch_original('https://nsearchives.nseindia.com/a', {'nsearchives.nseindia.com'},
                       session=client, resolve=False)
    assert len(client.calls) == 1


def test_response_size_limit():
    client = Transport([Response(headers={'Content-Length': '999999999'})])
    with pytest.raises(ChangeError, match='byte limit'):
        fetch_original('https://nsearchives.nseindia.com/a', {'nsearchives.nseindia.com'},
                       session=client, resolve=False)


def test_explicit_network_fetch_archives_exact_response(tmp_path, manifest, layout):
    del manifest['sources'][0]['local_file']
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path, allow_network=True,
                        fetcher=lambda url, hosts: (layout, url))
        assert report['successes'][0]['origin'] == 'HTTP_RESPONSE_BYTES'
        assert report['successes'][0]['raw_sha256'] == hashlib.sha256(layout).hexdigest()


def test_duplicate_json_keys_and_nan_rejected():
    for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        with pytest.raises(ChangeError):
            loads_unique(raw)


def test_html_scripts_are_not_model_instructions():
    assert document_text(b'<html><script>steal()</script><p>Revenue</p></html>', 'html') == 'Revenue'


def test_pdf_text_path_without_ocr():
    import io

    from pypdf import PdfWriter
    writer, stream = PdfWriter(), io.BytesIO()
    writer.add_blank_page(width=100, height=100)
    writer.write(stream)
    # Empty-page markers are not invented financial facts.
    assert '[PAGE 1]' in document_text(stream.getvalue(), 'pdf')


def test_model_configuration_missing_is_explicit(monkeypatch):
    monkeypatch.delenv('CC001_MODEL_URL', raising=False)
    monkeypatch.delenv('CC001_MODEL_NAME', raising=False)
    with pytest.raises(ChangeError, match='MODEL_NOT_CONFIGURED'):
        model_config()


def test_loopback_model_requires_explicit_permission(monkeypatch):
    monkeypatch.setenv('CC001_MODEL_URL', 'http://127.0.0.1:8000/v1/chat/completions')
    monkeypatch.setenv('CC001_MODEL_NAME', 'test-model')
    monkeypatch.delenv('CC001_ALLOW_LOCAL_MODEL', raising=False)
    with pytest.raises(ChangeError):
        model_config()
    monkeypatch.setenv('CC001_ALLOW_LOCAL_MODEL', '1')
    assert model_config()['model'] == 'test-model'


@pytest.fixture
def model_source():
    source = json.loads((ROOT / 'data/fixtures/company_change_v1.json').read_text())['sources'][0]
    return SourceDocument.from_dict(source)


def model_response(facts, finish='stop'):
    return Response(json.dumps({'choices': [{'finish_reason': finish,
        'message': {'content': json.dumps({'facts': facts})}}],
        'usage': {'total_tokens': 10}}).encode())


def test_model_adapter_verifies_quotes_and_computes_offsets(model_source):
    quote = 'Revenue from operations: INR 1,200 crore'
    client = Transport([model_response([{'field': 'revenue', 'quote': quote, 'literal': 'INR 1,200 crore'}])])
    result, _ = call_extractor(model_source, {'url': 'https://model.test/v1/chat/completions',
                              'model': 'test', 'max_tokens': 100}, session=client)
    fact = result['proposed_facts']['revenue']
    assert model_source.text[fact['start']:fact['end']] == quote
    assert client.calls[0][1]['json']['response_format']['type'] == 'json_schema'
    assert 'tools' not in client.calls[0][1]['json']


@pytest.mark.parametrize('quote,literal', [('made up', 'INR 100 crore'),
    ('Revenue from operations: INR 1,200 crore', 'INR 999 crore'), ('', '')])
def test_model_hallucinations_rejected(model_source, quote, literal):
    client = Transport([model_response([{'field': 'revenue', 'quote': quote, 'literal': literal}])])
    with pytest.raises(ChangeError):
        call_extractor(model_source, {'url': 'https://model.test/v1/chat/completions',
                       'model': 'test', 'max_tokens': 100}, session=client)


def test_model_truncation_not_retried(model_source):
    client = Transport([model_response([], finish='length')])
    with pytest.raises(ChangeError, match='incomplete'):
        call_extractor(model_source, {'url': 'https://model.test/v1/chat/completions',
                       'model': 'test', 'max_tokens': 100}, session=client)
    assert len(client.calls) == 1


def test_decision_and_reviews_remain_research_only(tmp_path, manifest):
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
        spec = {k: manifest['sources'][0][k] for k in ('symbol', 'isin', 'scope', 'event_key')}
        card = record_decision(store, spec)
        assert card['disposition'] == 'WAIT'
        assert card['live_capital_allowed'] is False
        store.review(report['successes'][0]['extraction_id'], 'r', 'ACCEPT', 'scope verified')
        assert record_decision(store, spec)['disposition'] == 'WAIT'  # normalization still unknown
        with pytest.raises(ChangeError):
            store.decision({'live_capital_allowed': True})


def test_cli_render_and_feature_export(tmp_path, manifest, capsys):
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    root = tmp_path / 'store'
    assert main([str(path), '--workspace', str(root)]) == 0
    assert len(list((root / 'reports').glob('*.html'))) == 1
    assert main(['--workspace', str(root), '--export-features']) == 0
    capsys.readouterr()


def test_output_serialization_and_escaping(tmp_path, manifest):
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
        report['failures'] = [{'source_id': '<script>x</script>', 'reason': '<img>'}]
        page = render_inbox(report)
        assert '<script>' not in page
        assert '&lt;script&gt;' in page
        paths = write_outputs(store, report)
        assert write_outputs(store, report) == paths


def gold_from_report(report):
    r = report['snapshot']['active'][0]
    return {'schema_version': 1, 'label_provenance': 'Synthetic test labels, not independent accuracy',
            'cases': [{'source_id': r['source_id'], 'raw_sha256': r['raw_sha256'], 'selector': r['selector'],
                       'facts': {k: {'value': v['value'], 'unit': v['unit'], 'absolute_tolerance': 1e-6}
                                 for k, v in r['facts'].items()}}]}


def test_extraction_scores_abstention_errors_and_extra_fields(tmp_path, manifest):
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
    gold = gold_from_report(report)
    perfect = score_extraction(report, gold)
    assert perfect['precision'] == perfect['recall'] == 1
    assert perfect['independent_labelling_verified'] is False
    modified = copy.deepcopy(report)
    facts = modified['snapshot']['active'][0]['facts']
    del facts['revenue']
    facts['owner_pat']['value'] *= 10
    facts['extra'] = {'value': 1, 'unit': 'INR_crore'}
    scored = score_extraction(modified, gold)
    assert scored['counts']['abstained'] == 1
    assert scored['counts']['wrong'] == 1
    assert scored['counts']['unexpected'] == 1
    assert report['snapshot']['active'][0]['facts']['owner_pat']['value'] == 648.04


def test_missing_document_counts_as_abstention(tmp_path, manifest):
    with EvidenceStore(tmp_path / 'store') as store:
        report = ingest(manifest, store, base=tmp_path)
    gold = gold_from_report(report)
    report['snapshot']['active'] = []
    result = score_extraction(report, gold)
    assert result['counts']['documents_missing'] == 1
    assert result['recall'] == 0
    assert result['precision'] is None


def abc_inputs():
    features, labels = [], []
    for day in range(12):
        for n in range(3):
            decision = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day)
            ident = f'{day}-{n}'
            features.append({'id': ident, 'symbol': f'DEMO{n}', 'isin': f'INE000A0100{n}',
                'decision_at': decision.isoformat(), 'entry_at': (decision + timedelta(hours=1)).isoformat(),
                'horizon_sessions': 1, 'features': {'value': day + n, 'sentiment': n - 1,
                                                 'economic_delta': n * day},
                'known_at': {k: decision.isoformat() for k in ('value', 'sentiment', 'economic_delta')},
                'cost_bps': 25, 'cost_known_at': decision.isoformat()})
            exit_at = decision + timedelta(days=2)
            labels.append({'id': ident, 'exit_at': exit_at.isoformat(),
                'available_at': (exit_at + timedelta(hours=2)).isoformat(),
                'target_excess_return': .01 * n + .002 * day})
    spec = {'feature_groups': {'baseline': ['value'], 'sentiment': ['sentiment'], 'events': ['economic_delta']},
        'folds': [{'test_start': '2026-01-09T00:00:00Z', 'test_end': '2026-01-12T23:00:00Z'}],
        'l2': 1., 'minimum_training_rows': 6, 'as_of': '2026-02-01T00:00:00Z'}
    return {'features': features, 'labels': labels, 'evidence_class': 'SYNTHETIC_TEST'}, spec


def test_abc_clock_contract_without_model_training():
    data, spec = abc_inputs()
    rows, labels, groups = validate_dataset(data, spec)
    assert len(rows) == len(labels) == 36
    assert set(groups) == {'baseline', 'sentiment', 'events'}


@pytest.mark.parametrize('fault', ['future_feature', 'future_label', 'future_cost', 'overlap', 'duplicate'])
def test_abc_rejects_leakage(fault):
    data, spec = abc_inputs()
    if fault == 'future_feature':
        data['features'][0]['known_at']['value'] = '2027-01-01T00:00:00Z'
    elif fault == 'future_label':
        data['labels'][0]['available_at'] = '2027-01-01T00:00:00Z'
    elif fault == 'future_cost':
        data['features'][0]['cost_known_at'] = '2027-01-01T00:00:00Z'
    elif fault == 'overlap':
        spec['folds'].append(copy.deepcopy(spec['folds'][0]))
    else:
        data['features'].append(copy.deepcopy(data['features'][0]))
    with pytest.raises(ChangeError):
        validate_dataset(data, spec)


def test_abc_runtime_reuses_existing_fitter_and_identical_test_rows():
    from marketlab.company_change_evaluation import run_abc
    data, spec = abc_inputs()
    result = run_abc(data, spec)
    assert len(result['models']) == 3
    assert len(result['predictions']) == 36
    sets = [{r['id'] for r in result['predictions'] if r['arm'] == arm} for arm in ('A', 'B', 'C')]
    assert sets[0] == sets[1] == sets[2]
    assert result['validated_predictive_edge'] is False
    # Labels on Jan 7/8 are still immature at the Jan 9 cutoff.
    assert all(int(i.split('-')[0]) <= 5 for m in result['models'] for i in m['training_ids'])


def test_abc_runtime_test_targets_cannot_change_predictions():
    from marketlab.company_change_evaluation import run_abc
    data, spec = abc_inputs()
    before = run_abc(data, spec)
    for label in data['labels']:
        if int(label['id'].split('-')[0]) >= 8:
            label['target_excess_return'] = 99
    after = run_abc(data, spec)
    assert [r['prediction'] for r in before['predictions']] == [r['prediction'] for r in after['predictions']]
    assert before['metrics']['A']['mse'] != after['metrics']['A']['mse']


def test_abc_runtime_frozen_prediction_needs_no_target_and_checks_hash():
    from marketlab.company_change_evaluation import predict_frozen, run_abc
    data, spec = abc_inputs()
    model = run_abc(data, spec)['models'][0]
    row = {'symbol': 'DEMO', 'isin': 'INE000A01001', 'decision_at': '2027-01-01T00:00:00Z',
           'features': {'value': 10}, 'known_at': {'value': '2026-01-01T00:00:00Z'}}
    result = predict_frozen(model, [row])
    assert len(result) == 1
    assert 'target' not in result[0]
    model['model']['intercept'] = 123
    with pytest.raises(ChangeError, match='integrity'):
        predict_frozen(model, [row])
