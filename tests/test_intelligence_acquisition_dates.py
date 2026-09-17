from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.intelligence_runtime import build_report, collect_source
from marketlab.intelligence_sources import extract_claims
from marketlab.intelligence_store import ResearchStore


def test_unknown_publication_keeps_actual_acquisition_boundary(tmp_path):
    class Transport:
        def fetch(self, url):
            return b'<html>Issuer revenue 10 million</html>', {
                'resolved_url': url, 'observed_at': datetime.now(UTC).isoformat(),
                'content_type': 'text/html', 'status_code': 200}
    spec = {'source_id': 'issuer', 'subject': 'TCS', 'publisher': 'Synthetic issuer',
            'url': 'https://www.tcs.com/test', 'kind': 'html', 'publication_date': None,
            'period_end': '2026-06-30', 'required_markers': ['Issuer'], 'fields': [
                {'concept': 'revenue', 'facet': 'financials', 'unit': 'million',
                 'currency': 'USD', 'basis': 'SYNTHETIC',
                 'pattern': r'revenue (?P<value>\d+) million'}]}
    panel = {'panel_id': 'TEST', 'members': [{'symbol': 'TCS'}]}
    with ResearchStore(tmp_path) as store:
        result = collect_source(store, spec, panel, Transport())
        assert result['status'] == 'DOCUMENT_PARSED'
        evidence = store.records('evidence')[0]
        assert evidence['publication_precision'] == 'UNKNOWN'
        assert evidence['original_document_bytes_retained'] is True
        assert evidence['evidence']['published_at'] == evidence['evidence']['processed_at']
        report = build_report(store, panel, {'sources': [spec]}, as_of='2026-07-01T12:00:00Z')
        assert report['active_evidence_count'] == 0


def test_guidance_gets_future_fiscal_period_not_report_quarter():
    spec = {'period_end': '2026-06-30', 'required_markers': ['Issuer'], 'fields': [
        {'concept': 'guidance_high', 'facet': 'expectations', 'unit': 'percent',
         'currency': 'NA', 'basis': 'MANAGEMENT_GUIDANCE', 'role': 'MANAGEMENT_GUIDANCE',
         'period_end': '2027-03-31', 'pattern': r'guidance (?P<value>\d+)%'}]}
    result = extract_claims('Issuer guidance 3%', spec)
    assert result[0]['period_end'] == '2027-03-31'
    assert result[0]['role'] == 'MANAGEMENT_GUIDANCE'


def test_issuer_extraction_uses_labels_not_the_previous_reported_numbers():
    config = json.loads(Path('registry/company_intelligence_v2.json').read_text())
    spec = next(s for s in config['sources'] if s['source_id'] == 'infy-q1-fy2027-issuer-wire')
    # Synthetic replacement values ensure the parser does not hardcode a result.
    text = ('Infosys July 23, 2026 delivered $9,999 million in Q1 revenues, '
            'year on year growth of 4.2%. Operating margin was at 22.2%. '
            'TCV of large deal wins was $7.7 billion. Revenue growth of 2.0%-4.0%.')
    values = {row['concept']: row for row in extract_claims(text, spec)}
    assert values['revenue_usd_million']['value'] == '9999'
    assert values['fy2027_revenue_guidance_low_pct']['value'] == '2.0'
    assert values['fy2027_revenue_guidance_high_pct']['value'] == '4.0'
    assert values['fy2027_revenue_guidance_high_pct']['period_end'] == '2027-03-31'


def test_page_wrapper_changes_do_not_duplicate_unchanged_company_facts(tmp_path):
    class Transport:
        def __init__(self, marker):
            self.marker = marker

        def fetch(self, url):
            raw = f'<html><script>{self.marker}</script>Issuer revenue 10 million</html>'.encode()
            return raw, {'resolved_url': url, 'observed_at': datetime.now(UTC).isoformat(),
                         'content_type': 'text/html', 'status_code': 200}

    spec = {'source_id': 'issuer', 'subject': 'TCS', 'publisher': 'Synthetic issuer',
            'url': 'https://www.tcs.com/test', 'kind': 'html', 'publication_date': None,
            'period_end': '2026-06-30', 'required_markers': ['Issuer'], 'fields': [
                {'concept': 'revenue', 'facet': 'financials', 'unit': 'million',
                 'currency': 'USD', 'basis': 'SYNTHETIC',
                 'pattern': r'revenue (?P<value>\d+) million'}]}
    panel = {'panel_id': 'TEST', 'members': [{'symbol': 'TCS'}]}
    with ResearchStore(tmp_path) as store:
        first = collect_source(store, spec, panel, Transport('request one'))
        original = store.records('evidence')
        cutoff = datetime.now(UTC).isoformat()
        before = build_report(store, panel, {'sources': [spec]}, as_of=cutoff)
        second = collect_source(store, spec, panel, Transport('request two'))
        assert first['raw_sha256'] != second['raw_sha256']
        assert len(store.records('document')) == 2
        assert len(store.records('attempt')) == 2
        assert len(original) == 1
        assert store.records('evidence') == original
        assert build_report(store, panel, {'sources': [spec]}, as_of=cutoff) == before
