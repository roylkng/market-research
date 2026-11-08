from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import requests

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_event_bridge import (
    build_workspace,
    finite_contract,
    join_event,
    source_amount,
    timing,
)
from marketlab.company_change_news import setup
from marketlab.company_change_news_review import admit
from marketlab.company_change_semantics import (
    checked_reading,
    main,
    make_payload,
    propose,
    score_events,
    validate_response,
)
from marketlab.company_change_store import EvidenceStore

NOW = '2026-11-08T06:00:00Z'
CONFIG = {'model': 'controlled-test-model', 'url': 'https://model.example/v1/chat/completions'}
TEXT = ('TEST LIMITED received a letter of award for its own scope. '
        'The contract value is USD 26.14 million exclusive of tax. '
        'Work has not yet commenced. Completion is scheduled in May 2027. '
        'The consortium participation does not increase the issuer-specific value.')


def example(store):
    setup(store)
    cap = store.capture(b'original issuer bytes', {'url': 'https://issuer.example/filing.pdf'})
    reading = {'symbol': 'TEST', 'isin': 'INE000A01001', 'url': 'https://issuer.example/filing.pdf',
               'raw_sha256': cap['raw_sha256'], 'capture_id': cap['id'], 'text': TEXT,
               'text_sha256': hashlib.sha256(TEXT.encode()).hexdigest(),
               'known_at': NOW, 'published_at': '2026-11-07T13:32:10Z'}
    reading['reading_sha256'] = canonical_hash(reading)
    store.db.execute('INSERT INTO cc_news_readings VALUES (?,?,?,?,?)',
                     (reading['reading_sha256'], 'candidate', 'recipe', NOW, json.dumps(reading)))
    store.db.commit()
    event = {'category': 'ORDER', 'stage': 'LETTER_OF_AWARD', 'actor_scope': 'ISSUER',
             'interpretation': 'Issuer work award, not proof of recognized earnings or collected cash.',
             'next_check': 'Establish cash margin, investment needs and payment milestones before valuation.',
             'claims': [{'field': field, 'quote': quote} for field, quote in [
                 ('event', 'received a letter of award'), ('actor', 'TEST LIMITED'),
                 ('stage', 'Work has not yet commenced'), ('amount', 'USD 26.14 million exclusive of tax')]]}
    response = {'choices': [{'finish_reason': 'stop', 'message': {
        'content': json.dumps({'status': 'PROPOSED', 'reason': 'An award is reported, commencement is not.', 'events': [event]})}}],
        'model': CONFIG['model'], 'usage': {'prompt_tokens': 500, 'completion_tokens': 150}}
    return reading, event, response


class Response:
    def __init__(self, raw, status=200):
        self.raw, self.status_code = raw, status
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def iter_content(self, size):
        yield self.raw


class Session:
    def __init__(self, raw, status=200, fail=False):
        self.raw, self.status, self.fail, self.calls = raw, status, fail, []
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.fail:
            raise requests.Timeout('private provider details must not be retained')
        return Response(self.raw, self.status)
    def close(self):
        pass


def review_case(store):
    reading, _, response = example(store)
    proposal = validate_response(json.dumps(response).encode(), reading)['proposals'][0]
    return admit(store, [proposal], 'test-source-reviewer')[0]


def scenario(**updates):
    return {'name': 'Illustrative case', 'fx_inr_per_currency_unit': 85,
            'issuer_fraction': 1, 'not_in_baseline_fraction': 1,
            'after_tax_cash_margin': .10, 'additional_capex_crore': 0,
            'working_capital_crore': 0, 'working_capital_recovery_fraction': 1,
            'cash_receipt_months': 12, 'discount_rate': .15, **updates}


def economic_plan(review, **case):
    return {'source_raw_sha256': review['source']['raw_sha256'],
            'amount': {'literal': 'USD 26.14 million', 'amount_scope': 'ISSUER_SCOPE'},
            'scenarios': [scenario(**case)],
            'rationale': 'Hypothetical cash economics for sensitivity, not a forecast or market FX observation.'}


def test_prepare_has_no_network_and_no_review_approval(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _, response = example(store)
        session = Session(json.dumps(response).encode())
        result = propose(store, reading, session=session)
        assert result['status'] == 'PREPARED_NOT_EXECUTED'
        assert not result['model_called'] and session.calls == []
        assert store.db.execute("SELECT name FROM sqlite_master WHERE name='cc_news_reviews'").fetchone() is None
        request = json.loads(store.read_blob(result['request_blob_sha256']))
        assert request['payload']['model'] == 'NOT_CONFIGURED'
        assert 'tools' not in request['payload']


def test_one_configured_call_reused_without_repeat_or_financial_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv('CC001_MODEL_API_KEY', 'test-secret-not-for-artifacts')
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _, response = example(store)
        session = Session(json.dumps(response).encode())
        result = propose(store, reading, execute=True, config=CONFIG, session=session)
        assert result['status'] == 'PROPOSED'
        assert result['review_status'] == 'MODEL_PROPOSED_NOT_APPROVED'
        assert len(result['proposals']) == 1
        assert not result['semantic_accuracy_verified']
        again = propose(store, reading, execute=True, config=CONFIG, session=session)
        assert again['reused_attempt'] and len(session.calls) == 1
        assert session.calls[0][1]['allow_redirects'] is False
        assert store.db.execute('SELECT COUNT(*) FROM extractions').fetchone()[0] == 0
        assert 'test-secret' not in json.dumps(result)
        assert 'test-secret' not in store.read_blob(result['request_blob_sha256']).decode()
        for claim in result['proposals'][0]['claims']:
            assert TEXT[claim['start']:claim['end']] == claim['quote']


@pytest.mark.parametrize('fault', ['truncated', 'refusal', 'tool', 'missing_quote', 'ambiguous_quote',
                                  'extra_forecast', 'duplicate_event', 'abstain_events', 'bad_field', 'two_choices'])
def test_bad_provider_responses_fail_without_retry(tmp_path, fault):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _event, response = example(store)
        if fault == 'truncated':
            response['choices'][0]['finish_reason'] = 'length'
        elif fault == 'refusal':
            response['choices'][0]['message']['refusal'] = 'refused'
        elif fault == 'tool':
            response['choices'][0]['message']['tool_calls'] = [{'name': 'buy'}]
        elif fault == 'two_choices':
            response['choices'] *= 2
        else:
            data = json.loads(response['choices'][0]['message']['content'])
            if fault == 'missing_quote':
                data['events'][0]['claims'][0]['quote'] = 'the company has collected all the cash'
            elif fault == 'ambiguous_quote':
                reading['text'] += ' TEST LIMITED'
                reading['text_sha256'] = hashlib.sha256(reading['text'].encode()).hexdigest()
                reading['reading_sha256'] = canonical_hash({k: v for k, v in reading.items() if k != 'reading_sha256'})
            elif fault == 'extra_forecast':
                data['events'][0]['target_price'] = 1000
            elif fault == 'duplicate_event':
                data['events'] *= 2
            elif fault == 'abstain_events':
                data['status'] = 'ABSTAIN'
            else:
                data['events'][0]['claims'][0]['field'] = 'stock_target'
            response['choices'][0]['message']['content'] = json.dumps(data)
        session = Session(json.dumps(response).encode())
        result = propose(store, reading, execute=True, config=CONFIG, session=session)
        assert result['status'] == 'FAILED_NO_AUTOMATIC_RETRY'
        assert propose(store, reading, execute=True, config=CONFIG, session=session)['reused_attempt']
        assert len(session.calls) == 1


def test_timeout_does_not_leak_transport_text_or_rebill(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _, _ = example(store)
        session = Session(b'', fail=True)
        result = propose(store, reading, execute=True, config=CONFIG, session=session)
        assert result['status'] == 'FAILED_NO_AUTOMATIC_RETRY'
        assert 'private provider' not in json.dumps(result)
        assert propose(store, reading, execute=True, config=CONFIG, session=session)['reused_attempt']
        assert len(session.calls) == 1


def test_abstention_is_explicit_and_non_json_text_not_repaired(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _, response = example(store)
        response['choices'][0]['message']['content'] = json.dumps({'status': 'ABSTAIN', 'reason': 'Conflicting evidence.', 'events': []})
        assert validate_response(json.dumps(response).encode(), reading)['status'] == 'ABSTAIN'
        response['choices'][0]['message']['content'] = '```json\n{}\n```'
        with pytest.raises(ValueError):
            validate_response(json.dumps(response).encode(), reading)


def test_no_model_config_fails_before_any_execution(tmp_path, monkeypatch):
    monkeypatch.delenv('CC001_MODEL_URL', raising=False)
    monkeypatch.delenv('CC001_MODEL_NAME', raising=False)
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _, _ = example(store)
        with pytest.raises(ChangeError, match='MODEL_NOT_CONFIGURED'):
            propose(store, reading, execute=True)


def test_source_integrity_clock_and_length_gates(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _, _ = example(store)
        changed = copy.deepcopy(reading)
        changed['text'] += 'tampered'
        with pytest.raises(ChangeError, match='integrity'):
            checked_reading(store, changed)
        store.clock = lambda: '2026-11-07T00:00:00Z'
        with pytest.raises(ChangeError, match='available'):
            checked_reading(store, reading)
        store.clock = lambda: NOW
        reading['text'] = 'x' * 80001
        reading['text_sha256'] = hashlib.sha256(reading['text'].encode()).hexdigest()
        reading['reading_sha256'] = canonical_hash({k:v for k,v in reading.items() if k != 'reading_sha256'})
        with pytest.raises(ChangeError, match='segmentation'):
            checked_reading(store, reading)


@pytest.mark.parametrize('tokens', [0, 8193, True, 1.5])
def test_output_bounds_are_not_silent(tokens):
    with pytest.raises(ChangeError):
        make_payload({}, 'model', tokens)


def test_missing_failed_and_abstaining_documents_stay_in_evaluation_denominator():
    event = {'category':'ORDER','stage':'LETTER_OF_AWARD','actor_scope':'ISSUER'}
    labels = {'provenance':'Synthetic software test, not independent labels',
              'cases': {str(i): [event] for i in range(4)}}
    result = score_events({'0':{'status':'PROPOSED','proposals':[event]},
                           '1':{'status':'ABSTAIN'}, '2':{'status':'FAILED_NO_AUTOMATIC_RETRY'}}, labels)
    assert result['recall'] == .25 and result['precision'] == 1
    assert result['counts']['missing_documents'] == 1
    assert result['counts']['failed_documents'] == 1
    assert result['counts']['abstentions'] == 1
    assert not result['independence_verified']


def test_amount_currency_and_million_crore_conversions(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        review = review_case(store)
        amount = source_amount(review, economic_plan(review)['amount'])
        assert amount['currency'] == 'USD' and amount['amount_units'] == '26140000.00'
        result = finite_contract(amount, scenario())
        assert result['attributed_contract_crore'] == pytest.approx(222.19)
        assert result['after_tax_cash_surplus_before_investment_crore'] == pytest.approx(22.219)
        assert result['finite_incremental_npv_crore'] == pytest.approx(22.219 / 1.15)
        assert result['terminal_value_crore'] == 0 and result['per_share_value'] is None


def test_finite_order_cannot_be_multiplied_by_pe_or_reallocated(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        amount = source_amount(review_case(store), {'literal':'USD 26.14 million','amount_scope':'ISSUER_SCOPE'})
        with pytest.raises(ChangeError, match='unsupported'):
            finite_contract(amount, scenario(exit_pe=15))
        with pytest.raises(ChangeError, match='second time'):
            finite_contract(amount, scenario(issuer_fraction=.5))
        assert finite_contract(amount, scenario(not_in_baseline_fraction=0))['finite_incremental_npv_crore'] == 0
        assert finite_contract(amount, scenario(after_tax_cash_margin=-.1))['finite_incremental_npv_crore'] < 0


def test_working_capital_release_does_not_create_free_money(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        amount = source_amount(review_case(store), {'literal':'USD 26.14 million','amount_scope':'ISSUER_SCOPE'})
        base = finite_contract(amount, scenario())
        locked = finite_contract(amount, scenario(working_capital_crore=20))
        assert locked['finite_incremental_npv_crore'] < base['finite_incremental_npv_crore']
        assert locked['finite_incremental_npv_crore'] == pytest.approx(-20 + (22.219+20)/1.15)
        lost = finite_contract(amount, scenario(working_capital_crore=20,working_capital_recovery_fraction=.5))
        assert lost['finite_incremental_npv_crore'] < locked['finite_incremental_npv_crore']


@pytest.mark.parametrize('change', [{'discount_rate':-1}, {'issuer_fraction':2}, {'cash_receipt_months':-1},
                                   {'after_tax_cash_margin':True}, {'fx_inr_per_currency_unit':float('nan')},
                                   {'additional_capex_crore':-1}])
def test_invalid_cash_scenarios_fail(tmp_path, change):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        amount = source_amount(review_case(store), {'literal':'USD 26.14 million','amount_scope':'ISSUER_SCOPE'})
        with pytest.raises(ChangeError):
            finite_contract(amount, scenario(**change))


def test_pre_event_and_same_day_prices_are_not_post_event_entries(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        review = review_case(store)
        quote = {'session_date':'2026-11-06','quoted_at':None,'observed_at':NOW}
        assert timing(review, quote, NOW)['status'] == 'PRE_EVENT_REFERENCE'
        quote['session_date'] = '2026-11-07'
        assert timing(review, quote, NOW)['status'] == 'DATE_ONLY_TIMING_UNRESOLVED'
        quote['quoted_at'] = '2026-11-07T16:00:00Z'
        assert timing(review, quote, NOW)['status'] == 'PRE_REVIEW_REFERENCE'
        assert not timing(review, quote, NOW)['after_system_review_price']
        with pytest.raises(ChangeError, match='cutoff'):
            timing(review, None, '2026-11-07T10:00:00Z')


def test_order_context_remains_diligence_without_post_event_price(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        review = review_case(store)
        result = join_event(review, None, NOW, economic_plan(review))
        assert result['price_timing']['status'] == 'NO_PRICE'
        assert len(result['finite_contract_scenarios']) == 1
        assert result['decision'] == 'DILIGENCE_ONLY_NO_ENTRY_APPROVED'
        assert result['live_capital_allowed'] is False
        assert result['per_share_effect'] is None
        assert result['dossier_sha256'] == canonical_hash({k:v for k,v in result.items() if k!='dossier_sha256'})


def test_wrong_stage_source_and_amount_do_not_enter_cash_model(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        review = review_case(store)
        plan = economic_plan(review)
        bad = copy.deepcopy(plan)
        bad['source_raw_sha256'] = 'other'
        with pytest.raises(ChangeError):
            join_event(review, None, NOW, bad)
        bad = copy.deepcopy(plan)
        bad['amount']['literal'] = 'USD 26'
        with pytest.raises(ChangeError):
            join_event(review, None, NOW, bad)
        review['stage'] = 'UNRESOLVED'
        review['review_sha256'] = canonical_hash({k:v for k,v in review.items() if k!='review_sha256'})
        with pytest.raises(ChangeError, match='event/stage'):
            join_event(review, None, NOW, plan)


def test_workspace_revalidates_quotes_and_source_bytes(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        review = review_case(store)
        report = build_workspace(store, [economic_plan(review)])
        assert len(report['dossiers']) == 1 and report['unmatched_plan_sources'] == []
        assert store.db.execute('SELECT COUNT(*) FROM extractions').fetchone()[0] == 0
        blob = store.root/'blobs'/review['source']['raw_sha256'][:2]/review['source']['raw_sha256']
        blob.write_bytes(b'changed')
        with pytest.raises(ChangeError, match='integrity'):
            build_workspace(store, [economic_plan(review)])


def test_empty_prepare_cli_needs_no_provider_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('CC001_MODEL_URL', raising=False)
    output = tmp_path/'out/prepared.json'
    assert main(['--workspace',str(tmp_path/'workspace'),'--output',str(output)]) == 0
    assert not json.loads(output.read_text())['execution_requested']
    assert 'count' in capsys.readouterr().out


def test_workflow_is_read_only_and_never_calls_model():
    root = Path(__file__).resolve().parents[1]
    workflow = (root/'.github/workflows/cc001-execution-smoke.yml').read_text()
    assert 'contents: read' in workflow
    assert '--execute' not in workflow
    assert 'push origin' not in workflow
    assert 'company_change_event_bridge' in workflow


@pytest.mark.parametrize('body', [[], None, {'choices':[None]}, {'choices':[{'message':None}]}])
def test_nonobject_provider_envelopes_are_rejected(tmp_path, body):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _, _ = example(store)
        with pytest.raises(ChangeError):
            validate_response(json.dumps(body).encode(), reading)


def test_cli_advances_to_unattempted_readings_without_rebilling(tmp_path, monkeypatch):
    import marketlab.company_change_semantics as module
    root = tmp_path/'workspace'
    with EvidenceStore(root, clock=lambda: NOW) as store:
        reading, _, response = example(store)
        second = copy.deepcopy(reading)
        second['text'] += ' A separate source record follows.'
        second['text_sha256'] = hashlib.sha256(second['text'].encode()).hexdigest()
        capture = store.capture(b'separate original bytes', {'url':'https://issuer.example/second.pdf'})
        second.update(capture_id=capture['id'], raw_sha256=capture['raw_sha256'], url='https://issuer.example/second.pdf')
        second['reading_sha256'] = canonical_hash({k:v for k,v in second.items() if k != 'reading_sha256'})
        store.db.execute('INSERT INTO cc_news_readings VALUES (?,?,?,?,?)',
            (second['reading_sha256'], 'candidate2', 'recipe', NOW, json.dumps(second)))
        store.db.commit()
    client = Session(json.dumps(response).encode())
    monkeypatch.setattr(module, 'model_config', lambda: CONFIG)
    monkeypatch.setattr(module.requests, 'Session', lambda: client)
    ids = []
    for index in range(3):
        out = tmp_path/f'run-{index}.json'
        assert main(['--workspace',str(root),'--output',str(out),'--execute','--limit','1']) == 0
        payload = json.loads(out.read_text())
        ids.extend(r['reading_sha256'] for r in payload['attempts'])
    assert len(client.calls) == 2 and len(set(ids)) == 2
    assert json.loads(out.read_text())['attempts'] == []


def test_same_source_inr_cannot_be_fx_converted_twice():
    amount = {'currency':'INR','amount_units':'10000000','amount_scope':'ISSUER_SCOPE'}
    with pytest.raises(ChangeError, match='converted again'):
        finite_contract(amount, scenario())
    assert finite_contract(amount, scenario(fx_inr_per_currency_unit=1))['attributed_contract_crore'] == 1
