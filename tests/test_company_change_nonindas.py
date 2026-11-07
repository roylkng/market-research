from __future__ import annotations

from pathlib import Path

from marketlab.company_change import canonical_hash
from marketlab.company_change_discovery import drain, setup_queue
from marketlab.company_change_store import EvidenceStore
from marketlab.company_change_xbrl import extract_xbrl


def nonindas():
    return b'''<x:xbrl xmlns:x="http://www.xbrl.org/2003/instance" xmlns:c="https://issuer.test/taxonomy">
    <x:context id="H1"><x:entity><x:identifier scheme="test">TEST</x:identifier></x:entity><x:period><x:startDate>2026-04-01</x:startDate><x:endDate>2026-09-30</x:endDate></x:period></x:context>
    <x:unit id="R"><x:measure>iso4217:INR</x:measure></x:unit>
    <c:Symbol contextRef="H1">TEST</c:Symbol><c:ISIN contextRef="H1">INE000A01001</c:ISIN>
    <c:NatureOfReportStandaloneConsolidated contextRef="H1">Consolidated</c:NatureOfReportStandaloneConsolidated>
    <c:RevenueFromOperations contextRef="H1" unitRef="R">500000000</c:RevenueFromOperations>
    <c:ProfitLossForPeriodBeforeMinorityInterest contextRef="H1" unitRef="R">100000000</c:ProfitLossForPeriodBeforeMinorityInterest>
    <c:ProfitLossForThePeriod contextRef="H1" unitRef="R">80000000</c:ProfitLossForThePeriod>
    </x:xbrl>'''


def test_nonindas_group_profit_never_uses_after_minority_amount():
    record = extract_xbrl(nonindas(), {'symbol': 'TEST', 'isin': 'INE000A01001', 'scope': 'CONSOLIDATED', 'period_end': '2026-09-30'})[0]
    assert record['facts']['reported_pat']['value'] == 10
    assert record['facts']['revenue']['value'] == 50
    assert 'owner_pat' not in record['facts']
    assert record['bridge']['normalized_owner_eps'] is None
    assert record['facts']['reported_pat']['source_locator']['concept'].endswith('ProfitLossForPeriodBeforeMinorityInterest')


def test_failed_oldest_filing_retries_before_new_backlog(tmp_path):
    import json

    clock = '2026-11-07T10:00:00Z'
    with EvidenceStore(tmp_path, clock=lambda: clock) as store:
        setup_queue(store)
        for i, state, attempts, seen in [(0, 'FAILED', 1, '2026-11-06T10:00:00+00:00'), (1, 'PENDING', 0, clock)]:
            item = {'id': str(i), 'url': f'https://nsearchives.nseindia.com/{i}.xml', 'symbol': 'TEST', 'isin': 'INE000A01001', 'scope': 'CONSOLIDATED', 'period_end': '2026-09-30', 'published_at': seen, 'discovery_row_sha256': canonical_hash(i)}
            store.db.execute('INSERT INTO cc_discovery_queue(id,first_seen,published_at,payload,state,attempts,updated_at) VALUES (?,?,?,?,?,?,?)', (str(i), seen, seen, json.dumps(item), state, attempts, seen))
        store.db.commit()
        urls = []
        def fetch(url, hosts):
            urls.append(url)
            return nonindas(), url
        result = drain(store, limit=1, fetcher=fetch)
        assert not result['failures']
        assert urls == ['https://nsearchives.nseindia.com/0.xml']


def test_parser_fixes_trigger_a_bounded_verification_run():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / '.github/workflows/cc001-daily-operations.yml').read_text()
    assert "- 'src/marketlab/company_change_xbrl.py'" in workflow
    assert "- 'src/marketlab/company_change_discovery.py'" in workflow
    assert '--limit 40' in workflow
