from __future__ import annotations

from marketlab.company_change_store import EvidenceStore


def test_old_source_retry_cannot_replace_newer_revision(tmp_path):
    clock = ['2026-11-07T10:00:00Z']
    with EvidenceStore(tmp_path, clock=lambda: clock[0]) as store:
        identity = {'symbol': 'TEST', 'event_key': 'Q1'}
        newer = store.capture(b'new', {'published_at': '2026-11-06T10:00:00Z'})
        newest = store.record_extraction(newer, 'recipe', {'identity': identity, 'facts_sha256': 'new'})
        clock[0] = '2026-11-07T11:00:00Z'
        older = store.capture(b'old', {'published_at': '2026-11-05T10:00:00Z'})
        store.record_extraction(older, 'recipe', {'identity': identity, 'facts_sha256': 'old'})
        snapshot = store.snapshot()
        assert snapshot['active'][0]['extraction_id'] == newest['extraction_id']
        assert snapshot['history'][-1]['older_source_observed_late']
        assert len(snapshot['history']) == 2
        assert store.snapshot('2026-11-07T09:00:00Z')['active'] == []
