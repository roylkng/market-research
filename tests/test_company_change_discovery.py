from __future__ import annotations

import copy
import html
import json
from datetime import date
from pathlib import Path

import pytest

from marketlab.company_change import ChangeError
from marketlab.company_change_discovery import (
    ARCHIVE_HOSTS,
    candidate,
    coverage,
    discover,
    drain,
    publication_clock,
    retry_failed,
    rows_from_payload,
    security_master,
    selectors_from_document,
)
from marketlab.company_change_store import EvidenceStore

ROOT = Path(__file__).resolve().parents[1]
MASTER = b'SYMBOL,SERIES,ISIN NUMBER\nKRBL,EQ,INE001B01026\nDEMO,BE,INE000A01001\n'
START, END = date(2026, 11, 1), date(2026, 11, 7)
CLOCK = '2026-11-07T10:00:00Z'


def filing():
    return {'symbol': 'KRBL', 'consolidated': 'Consolidated', 'qe_Date': '31-Mar-2026',
            'type': 'Integrated Filing- Financials', 'broadcast_Date': '06-Nov-2026 17:30:00',
            'xbrl': 'https://nsearchives.nseindia.com/test.html'}


class Client:
    INTEGRATED_FILING_ENDPOINT = 'endpoint'

    def __init__(self, financial=None, announcements=None):
        self.financial = [filing()] if financial is None else financial
        self.announcements = [] if announcements is None else announcements
        self.calls = []

    def all_equity_csv(self):
        return MASTER

    def _json_get_with_raw(self, endpoint, *, params):
        self.calls.append(params)
        data = {'data': self.financial}
        return data, json.dumps(data).encode()

    def corporate_announcements_with_raw(self, **kwargs):
        return self.announcements, json.dumps(self.announcements).encode()


@pytest.fixture
def raw_html():
    corpus = json.loads((ROOT / 'data/fixtures/company_change_real_v1.json').read_text())
    return ''.join('<table>' + ''.join('<tr>' + ''.join(
        '<td>' + html.escape(v) + '</td>' for v in r) + '</tr>' for r in t)
        + '</table>' for t in corpus['sources'][1]['tables']).encode()


def test_full_current_master_and_nonsubstitution():
    assert security_master(MASTER) == {'KRBL': 'INE001B01026'}
    with pytest.raises(ChangeError, match='empty'):
        security_master(b'SYMBOL,SERIES,ISIN NUMBER\nDEMO,BE,INE000A01001\n')
    with pytest.raises(ChangeError, match='conflicting'):
        security_master(MASTER + b'KRBL,EQ,INE000A01002\n')


def test_discovery_uses_whole_exchange_not_favorites(tmp_path):
    client = Client()
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        result = discover(store, client, start=START, end=END)
        assert result['accepted_distinct_rows'] == 1
        assert result['errors'] == []
        assert 'symbol' not in client.calls[0]
        assert result['coverage_class'].endswith('NOT_CERTIFIED_CENSUS')
        assert store.read_blob(result['security_master_sha256']) == MASTER
        assert result['current_master_not_historical_membership']
        assert coverage(store)['counts'] == {'PENDING': 1}


def test_repeated_discovery_and_changed_revisions(tmp_path):
    first = filing()
    client = Client(financial=[first, copy.deepcopy(first)])
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        discover(store, client, start=START, end=END)
        discover(store, client, start=START, end=END)
        assert coverage(store)['total_discovered'] == 1
        revised = {**first, 'revised_Date': '07-Nov-2026 10:00:00'}
        client.financial = [revised]
        discover(store, client, start=START, end=END)
        assert coverage(store)['total_discovered'] == 2


def test_revised_clock_not_original_clock():
    row = {**filing(), 'revised_Date': '07-Nov-2026 10:00:00'}
    assert publication_clock(row).isoformat() == '2026-11-07T04:30:00+00:00'


@pytest.mark.parametrize('changes,reason', [
    ({'broadcast_Date': '01-Oct-2026 17:30:00'}, 'OUTSIDE'),
    ({'broadcast_Date': '07-Nov-2026 23:30:00'}, 'FUTURE'),
    ({'symbol': 'UNKNOWN'}, 'CURRENT_EQ'),
    ({'consolidated': ''}, 'ACCOUNTING_SCOPE'),
    ({'xbrl': 'https://evil.test/a.html'}, 'ORIGINAL_URL'),
    ({'xbrl': 'https://nsearchives.nseindia.com/a.html?secret=1'}, 'ORIGINAL_URL'),
    ({'qe_Date': '31-Dec-2026'}, 'FUTURE_REPORTED'),
])
def test_bad_candidates_retained_as_reasons(changes, reason):
    with pytest.raises(ChangeError, match=reason):
        candidate({**filing(), **changes}, security_master(MASTER), START, END, CLOCK, 'financials')


def test_row_exclusions_and_semantic_queue_remain_in_coverage(tmp_path):
    announcement = {'symbol': 'KRBL', 'an_dt': '06-Nov-2026 17:30:00', 'desc': 'Order award',
                    'attchmntFile': 'https://nsearchives.nseindia.com/order.pdf'}
    client = Client(financial=[filing(), {'broken': True}], announcements=[announcement])
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        result = discover(store, client, start=START, end=END)
        assert len(result['exclusions']) == 1
        assert coverage(store)['counts'] == {'PENDING': 1, 'NEEDS_SEMANTIC_MAPPING': 1}


def test_fetch_and_drain_original_bytes_and_real_periods(tmp_path, raw_html):
    seen = []
    def fetcher(url, hosts):
        assert hosts == ARCHIVE_HOSTS
        seen.append(url)
        return raw_html, url
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        discover(store, Client(), start=START, end=END)
        output = drain(store, limit=3, fetcher=fetcher)
        assert not output['failures']
        assert len(output['successes']) == 2
        assert len(seen) == 1
        assert coverage(store)['counts'] == {'EXTRACTED': 1}
        assert drain(store, limit=3, fetcher=fetcher)['attempted_documents'] == 0
        assert len(store.snapshot()['active']) == 2
        assert all(r['review_status'] == 'UNREVIEWED' for r in store.snapshot()['active'])
        assert store.read_blob(output['successes'][0]['raw_sha256']) == raw_html


def test_failed_intake_budget_no_silent_removal(tmp_path):
    def broken(url, hosts):
        raise ChangeError('network unavailable')
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        discover(store, Client(), start=START, end=END)
        for _ in range(3):
            assert len(drain(store, limit=1, fetcher=broken)['failures']) == 1
        assert drain(store, limit=1, fetcher=broken)['attempted_documents'] == 0
        assert coverage(store)['counts'] == {'FAILED': 1}
        assert retry_failed(store) == 1
        assert drain(store, limit=1, fetcher=broken)['attempted_documents'] == 1


def test_unsupported_format_not_treated_as_extracted(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        discover(store, Client(financial=[{**filing(), 'xbrl': 'https://nsearchives.nseindia.com/a.pdf'}]), start=START, end=END)
        assert coverage(store)['counts'] == {'UNSUPPORTED_FORMAT': 1}
        assert drain(store)['attempted_documents'] == 0


def test_fresh_processing_lease_not_stolen(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        discover(store, Client(), start=START, end=END)
        store.db.execute("UPDATE cc_discovery_queue SET state='PROCESSING'")
        store.db.commit()
        assert drain(store)['attempted_documents'] == 0


def test_discovery_failure_does_not_claim_complete(tmp_path):
    class Broken(Client):
        def _json_get_with_raw(self, *args, **kwargs):
            raise RuntimeError('no response')
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        report = discover(store, Broken(), start=START, end=END)
        assert len(report['errors']) == 1
        assert report['accepted_distinct_rows'] == 0


def test_payload_contract_and_raw_hash_binding(tmp_path):
    with pytest.raises(ChangeError):
        rows_from_payload({'data': 'wrong'})
    class Tampered(Client):
        def _json_get_with_raw(self, *args, **kwargs):
            return {'data': [filing()]}, b'{"data":[]}'
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        result = discover(store, Tampered(), start=START, end=END)
        assert result['accepted_distinct_rows'] == 0
        assert 'bytes' in result['errors'][0]['reason']


def test_selector_requires_discovery_scope(raw_html):
    item = candidate(filing(), security_master(MASTER), START, END, CLOCK, 'financials')
    item['scope'] = 'STANDALONE'
    with pytest.raises(ChangeError, match='matches'):
        selectors_from_document(raw_html, item)


@pytest.mark.parametrize('limit', [0, 101, True, 1.5])
def test_fetch_limits(tmp_path, limit):
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store, pytest.raises(ChangeError, match='budget'):
        drain(store, limit=limit)
