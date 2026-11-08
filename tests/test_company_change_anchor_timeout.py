from __future__ import annotations

import hashlib

import requests

from marketlab.company_change import canonical_hash
from marketlab.company_change_anchor_trial import ENDPOINT, one_attempt
from marketlab.company_change_store import EvidenceStore


def test_bounded_cpu_deadline_does_not_enable_automatic_retry(tmp_path, monkeypatch):
    monkeypatch.setenv('CC001_MODEL_URL', ENDPOINT)
    monkeypatch.setenv('CC001_MODEL_NAME', 'local-test')
    monkeypatch.setenv('CC001_ALLOW_LOCAL_MODEL', '1')
    monkeypatch.delenv('CC001_MODEL_API_KEY', raising=False)
    clock = '2026-11-08T08:00:00Z'

    class Session:
        calls = 0
        def post(self, url, **kwargs):
            self.calls += 1
            assert url == ENDPOINT
            assert kwargs['timeout'] == (10, 360)
            assert kwargs['allow_redirects'] is False
            raise requests.ReadTimeout('bounded test timeout')

    with EvidenceStore(tmp_path, clock=lambda: clock) as store:
        capture = store.capture(b'original bytes', {'url': 'https://issuer.example/source'})
        text = 'TEST LIMITED reports a work award, not collected cash. ' * 4
        reading = {'symbol': 'TEST', 'isin': 'INE000A01001', 'url': 'https://issuer.example/source',
                   'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                   'raw_sha256': capture['raw_sha256'], 'capture_id': capture['id'],
                   'known_at': clock, 'published_at': '2026-11-07T10:00:00Z'}
        reading['reading_sha256'] = canonical_hash(reading)
        session = Session()
        result = one_attempt(store, reading, 'local-test', 1024, session=session)
        assert result['status'] == 'FAILED_NO_AUTOMATIC_RETRY'
        assert result['error_type'] == 'ReadTimeout'
        assert one_attempt(store, reading, 'local-test', 1024, session=session)['reused_attempt']
        assert session.calls == 1
