from __future__ import annotations

import json
from datetime import date

import pytest

from marketlab.company_change import ChangeError
from marketlab.company_change_discovery import candidate, discover, drain, security_master
from marketlab.company_change_store import EvidenceStore
from marketlab.company_change_xbrl import extract_xbrl


MASTER = b'SYMBOL,SERIES,ISIN NUMBER\nKRBL,EQ,INE001B01026\n'
START, END = date(2026, 11, 1), date(2026, 11, 7)
CLOCK = '2026-11-07T10:00:00Z'


def filing():
    return {'symbol': 'KRBL', 'consolidated': 'Consolidated', 'qe_Date': '31-Mar-2026',
            'type': 'Integrated Filing- Financials', 'broadcast_Date': '06-Nov-2026 17:30:00',
            'xbrl': 'https://nsearchives.nseindia.com/test.xml'}


class Client:
    INTEGRATED_FILING_ENDPOINT = 'endpoint'

    def __init__(self, financial=None):
        self.financial = [filing()] if financial is None else financial

    def all_equity_csv(self):
        return MASTER

    def _json_get_with_raw(self, endpoint, *, params):
        payload = {'data': self.financial}
        return payload, json.dumps(payload).encode()

    def corporate_announcements_with_raw(self, **kwargs):
        return [], b'[]'


def xml():
    return b'''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:x="https://issuer.test/taxonomy" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <xbrli:unit id="rupees"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
    <xbrli:unit id="eps"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unitNumerator><xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>
    <xbrli:context id="annual"><xbrli:entity><xbrli:identifier scheme="test">company</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period></xbrli:context>
    <x:Symbol contextRef="annual">KRBL</x:Symbol><x:ISIN contextRef="annual">INE001B01026</x:ISIN>
    <x:NatureOfReportStandaloneConsolidated contextRef="annual">Consolidated</x:NatureOfReportStandaloneConsolidated>
    <x:LevelOfRounding contextRef="annual">Lakhs</x:LevelOfRounding>
    <x:RevenueFromOperations contextRef="annual" unitRef="rupees" decimals="-5">1000000000</x:RevenueFromOperations>
    <x:ProfitLossForPeriod contextRef="annual" unitRef="rupees">120000000</x:ProfitLossForPeriod>
    <x:ProfitLossAttributableToOwnersOfParent contextRef="annual" unitRef="rupees" xsi:nil="true"/>
    <x:DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="annual" unitRef="eps">12.00</x:DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations>
    </xbrli:xbrl>'''


def item():
    return candidate({**filing(), 'xbrl': 'https://nsearchives.nseindia.com/source.xml'}, security_master(MASTER), START, END, CLOCK, 'financials')


def test_original_units_not_display_rounding():
    record = extract_xbrl(xml(), item())[0]
    assert record['facts']['revenue']['value'] == 100
    assert record['facts']['diluted_eps']['value'] == 12
    assert 'owner_pat' not in record['facts']
    assert record['bridge']['normalized_owner_eps'] is None
    assert record['facts']['revenue']['source_locator']['unit_ref'] == 'rupees'


@pytest.mark.parametrize('old,new', [
    (b'iso4217:INR', b'iso4217:USD'),
    (b'unitRef="rupees"', b'unitRef="missing"'),
    (b'1000000000', b'NaN'),
    (b'>KRBL<', b'>OTHER<'),
    (b'INE001B01026', b'INE000A01001'),
    (b'decimals="-5"', b'decimals="-5" scale="5"'),
])
def test_invalid_original_context_fails(old, new):
    with pytest.raises(ChangeError):
        extract_xbrl(xml().replace(old, new), item())


def test_no_entity_expansion():
    with pytest.raises(ChangeError, match='entities|entity'):
        extract_xbrl(b'<!DOCTYPE x [<!ENTITY t "test">]>' + xml(), item())


def test_xml_queued_and_retained_as_original(tmp_path):
    client = Client(financial=[{**filing(), 'xbrl': 'https://nsearchives.nseindia.com/source.xml'}])
    with EvidenceStore(tmp_path, clock=lambda: CLOCK) as store:
        discover(store, client, start=START, end=END)
        result = drain(store, fetcher=lambda url, hosts: (xml(), url))
        assert not result['failures']
        assert result['successes'][0]['facts'] == 3
        assert store.snapshot()['active'][0]['review_status'] == 'UNREVIEWED'
        assert store.read_blob(result['successes'][0]['raw_sha256']) == xml()


def test_paginated_discovery_and_repeat_detection(tmp_path):
    class Paged(Client):
        def _json_get_with_raw(self, endpoint, *, params):
            import json
            current = {**filing(), 'xbrl': f"https://nsearchives.nseindia.com/page{params['page']}.xml"}
            value = {'data': [current], 'page': params['page'], 'size': 1, 'totalCount': 3}
            return value, json.dumps(value).encode()
    with EvidenceStore(tmp_path / 'first', clock=lambda: CLOCK) as store:
        result = discover(store, Paged(), start=START, end=END)
        assert not result['errors']
        assert result['accepted_distinct_rows'] == 3
    class Repeated(Client):
        def _json_get_with_raw(self, *args, **kwargs):
            import json
            value = {'data': [filing()], 'totalCount': 30}
            return value, json.dumps(value).encode()
    with EvidenceStore(tmp_path / 'repeat', clock=lambda: CLOCK) as store:
        result = discover(store, Repeated(), start=START, end=END)
        assert 'repeated' in result['errors'][0]['reason']


def test_live_taxonomy_owner_alias_and_reconciliation_warning():
    raw = xml().replace(b'ProfitLossAttributableToOwnersOfParent', b'ProfitOrLossAttributableToOwnersOfParent')
    raw = raw.replace(b'unitRef="rupees" xsi:nil="true"/>', b'unitRef="rupees">0</x:ProfitOrLossAttributableToOwnersOfParent>')
    raw = raw.replace(b'</xbrli:xbrl>', b'<x:ProfitOrLossAttributableToNonControllingInterests contextRef="annual" unitRef="rupees">0</x:ProfitOrLossAttributableToNonControllingInterests></xbrli:xbrl>')
    result = extract_xbrl(raw, item())[0]
    assert result['facts']['owner_pat']['value'] == 0
    assert result['warnings']
    assert result['bridge']['normalized_owner_eps'] is None
