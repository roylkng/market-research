from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import requests
import yaml

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_anchor_trial import ENDPOINT, certify, one_attempt, validate_pin
from marketlab.company_change_anchors import catalog, make_payload, output_schema, validate_response
from marketlab.company_change_store import EvidenceStore

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-11-08T08:00:00Z'


def reading(store=None):
    text = '[PAGE 1]\nTEST LIMITED received a letter of award, not recognized revenue.\n'
    text += 'The subsidiary has not started operations. Payment is conditional.\n' * 20
    text += '[PAGE 2]\nThe final paragraph contradicts the stated completion date.\n'
    result = {'symbol': 'TEST', 'isin': 'INE000A01001', 'url': 'https://issuer.example/doc',
              'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
              'raw_sha256': hashlib.sha256(b'original').hexdigest(), 'known_at': NOW,
              'published_at': '2026-11-07T10:00:00Z'}
    if store:
        result['capture_id'] = store.capture(b'original', {'url': result['url']})['id']
    result['reading_sha256'] = canonical_hash(result)
    return result


def output():
    return {'status': 'PROPOSED', 'reason': 'The source reports an award with conditions.',
            'events': [{'category': 'ORDER', 'stage': 'LETTER_OF_AWARD', 'actor_scope': 'ISSUER',
                        'event_evidence': ['b0001'], 'stage_evidence': ['b0001'],
                        'actor_evidence': ['b0001'], 'counterevidence': ['b0002'],
                        'interpretation': 'Reported award, not completed work or recognized earnings.',
                        'next_check': 'Check scope, margins and payment terms before valuing this contract.'}]}


def envelope(value, **extras):
    return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}, **extras}],
                       'usage': {'completion_tokens': 150}}).encode()


def test_full_text_coverage_no_whitespace_or_negation_cleanup():
    r = reading()
    c = catalog(r)
    assert ''.join(b['text'] for b in c['blocks']) == r['text']
    for index, b in enumerate(c['blocks']):
        assert b['text'] == r['text'][b['start']:b['end']]
        assert b['sha256'] == hashlib.sha256(b['text'].encode()).hexdigest()
        if index:
            assert b['start'] == c['blocks'][index-1]['end']
    assert 'not started operations' in ''.join(b['text'] for b in c['blocks'])
    assert c == catalog(r)


def test_same_text_different_security_changes_catalog_identity():
    r = reading()
    old = catalog(r)
    r['isin'] = 'INE000A01002'
    assert catalog(r)['catalog_sha256'] != old['catalog_sha256']
    with pytest.raises(ChangeError, match='another source'):
        validate_response(envelope(output()), r, old)


def test_client_reconstructs_exact_quotes_and_does_not_admit_review():
    r = reading()
    result = validate_response(envelope(output()), r, catalog(r))
    assert result['status'] == 'PROPOSED'
    assert result['review_status'] == 'MODEL_PROPOSED_NOT_APPROVED'
    assert result['semantic_accuracy_verified'] is False
    assert result['evidence_validation_scope'].startswith('EXACT_SOURCE_LOCATION_NOT')
    for claim in result['proposals'][0]['claims']:
        assert claim['quote'] == r['text'][claim['start']:claim['end']]
    assert result['evidence_selections'][0]['counterevidence'] == ['b0002']


@pytest.mark.parametrize('fault', ['unknown', 'missing', 'duplicate', 'offset', 'category',
                                   'too_many', 'short', 'forecast', 'truncated', 'abstain', 'duplicate_event'])
def test_bad_references_and_schema_are_rejected(fault):
    r, value = reading(), output()
    if fault == 'unknown':
        value['events'][0]['actor_evidence'] = ['b9999']
    elif fault == 'missing':
        value['events'][0]['stage_evidence'] = []
    elif fault == 'duplicate':
        value['events'][0]['event_evidence'] *= 2
    elif fault == 'offset':
        value['events'][0]['start'] = 0
    elif fault == 'category':
        value['events'][0]['category'] = []
    elif fault == 'too_many':
        value['events'] *= 3
    elif fault == 'short':
        value['events'][0]['interpretation'] = 'ok'
    elif fault == 'forecast':
        value['target_price'] = 900
    elif fault == 'abstain':
        value['status'] = 'ABSTAIN'
    elif fault == 'duplicate_event':
        value['events'] *= 2
    raw = envelope(value, finish_reason='length') if fault == 'truncated' else envelope(value)
    with pytest.raises(ChangeError):
        validate_response(raw, r, catalog(r))


def test_abstention_valid_but_wrong_semantics_not_certified_by_reference():
    r = reading()
    result = validate_response(envelope({'status': 'ABSTAIN', 'reason': 'Insufficient event evidence.', 'events': []}), r, catalog(r))
    assert result['status'] == 'ABSTAIN' and not result['proposals']
    wrong = output()
    wrong['events'][0]['stage'] = 'COMPLETED'
    parsed = validate_response(envelope(wrong), r, catalog(r))
    # Real IDs do not prove entailment. This is precisely why no automatic approval exists.
    assert parsed['semantic_accuracy_verified'] is False
    assert parsed['review_status'] == 'MODEL_PROPOSED_NOT_APPROVED'


def test_caller_cannot_modify_block_offset_or_quote():
    r, evidence = reading(), catalog(reading())
    evidence['blocks'][0]['start'] = 10
    with pytest.raises(ChangeError, match='changed'):
        validate_response(envelope(output()), r, evidence)


def test_visible_schema_bounded_refs_and_no_expected_labels_or_case_names():
    r = reading()
    payload, evidence = make_payload(r, 'model')
    schema = output_schema(evidence)
    assert json.dumps(schema, sort_keys=True) in payload['messages'][0]['content']
    assert schema['properties']['events']['maxItems'] == 2
    source = json.loads(payload['messages'][1]['content'])
    assert set(source) == {'source', 'untrusted_blocks'}
    assert ''.join(b['text'] for b in source['untrusted_blocks']) == r['text']
    assert all(s not in payload['messages'][0]['content'] for s in ['SEAMEC','DHRUV','VIKRAN','PRESTIGE'])
    assert 'tools' not in payload


@pytest.mark.parametrize('value', [True, 0, 2049, 1.2])
def test_token_limits(value):
    with pytest.raises(ChangeError):
        make_payload(reading(), 'model', value)


def test_modified_or_oversized_source_not_silently_truncated():
    r = reading()
    r['text'] += 'changed'
    with pytest.raises(ChangeError, match='hash'):
        catalog(r)
    r['text'] = 'x' * 80001
    with pytest.raises(ChangeError, match='segmentation'):
        catalog(r)


class Response:
    status_code = 200
    def __init__(self, raw):
        self.raw = raw
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def iter_content(self, n):
        yield self.raw


class Session:
    def __init__(self, raw, fail=False):
        self.raw, self.fail, self.calls = raw, fail, 0
    def post(self, url, **kwargs):
        self.calls += 1
        assert url == ENDPOINT and kwargs['allow_redirects'] is False
        assert 'Authorization' not in str(kwargs)
        if self.fail:
            raise requests.Timeout('sensitive transport details')
        return Response(self.raw)


def local_config(monkeypatch):
    monkeypatch.setenv('CC001_MODEL_URL', ENDPOINT)
    monkeypatch.setenv('CC001_ALLOW_LOCAL_MODEL', '1')
    monkeypatch.setenv('CC001_MODEL_NAME', 'model')
    monkeypatch.delenv('CC001_MODEL_API_KEY', raising=False)


def test_real_attempt_contract_is_idempotent_and_has_no_review_side_effects(tmp_path, monkeypatch):
    local_config(monkeypatch)
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        r = reading(store)
        session = Session(envelope(output()))
        result = one_attempt(store, r, 'model', 1024, session=session)
        assert result['status'] == 'PROPOSED'
        assert result['generation']['completion_tokens'] == 150
        assert one_attempt(store, r, 'model', 1024, session=session)['reused_attempt']
        assert session.calls == 1
        assert store.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0] == 0
        req = json.loads(store.read_blob(result['request_blob_sha256']))
        assert req['catalog'] == catalog(r)


def test_network_failure_retained_without_retry_or_transport_text_leak(tmp_path, monkeypatch):
    local_config(monkeypatch)
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        r, s = reading(store), Session(b'', fail=True)
        result = one_attempt(store, r, 'model', 1024, session=s)
        assert result['status'] == 'FAILED_NO_AUTOMATIC_RETRY'
        assert 'sensitive' not in str(result)
        assert one_attempt(store, r, 'model', 1024, session=s)['reused_attempt']
        assert s.calls == 1


def test_credential_and_remote_endpoint_are_blocked(tmp_path, monkeypatch):
    local_config(monkeypatch)
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        r = reading(store)
        monkeypatch.setenv('CC001_MODEL_API_KEY','do-not-send')
        with pytest.raises(ChangeError, match='credential'):
            one_attempt(store, r, 'model', 1024)
        monkeypatch.delenv('CC001_MODEL_API_KEY')
        monkeypatch.setenv('CC001_MODEL_URL','https://example.test/v1/chat/completions')
        with pytest.raises(ChangeError, match='loopback'):
            one_attempt(store, r, 'model', 1024)


def test_pins_require_official_revisions_and_hashes(tmp_path):
    pin = json.loads((ROOT/'data/cc001/anchored-model-trial.json').read_text())
    validate_pin(pin)
    bad = copy.deepcopy(pin)
    bad['models']['large']['revision'] = 'main'
    with pytest.raises(ChangeError):
        validate_pin(bad)
    spec = pin['models']['small']['files'][0]
    model = tmp_path/spec['filename']
    model.write_bytes(b'test weights')
    spec['sha256'] = hashlib.sha256(model.read_bytes()).hexdigest()
    binary = tmp_path/'server'
    binary.write_bytes(b'test binary')
    c = certify(pin,'small',tmp_path,binary,pin['runtime_commit'],NOW)
    assert c['weights'][0]['bytes'] == len(b'test weights')
    model.write_bytes(b'changed weights')
    with pytest.raises(ChangeError, match='content'):
        certify(pin,'small',tmp_path,binary,pin['runtime_commit'],NOW)


def test_matrix_read_only_full_denominator_and_no_production_changes():
    text = (ROOT/'.github/workflows/cc001-anchored-model-trial.yml').read_text()
    workflow = yaml.safe_load(text)
    assert workflow['permissions'] == {'contents':'read'}
    assert workflow['jobs']['compare-model']['strategy']['matrix']['model'] == ['small','large']
    assert 'schedule:' not in text and 'push origin' not in text
    assert 'sha256sum --check' in text
    assert 'cases_with_generated_tokens' in text and 'production_model_approved' in text
    assert 'unset CC001_MODEL_API_KEY' in text
