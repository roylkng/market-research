"""Narrow, unit-aware original XBRL intake for CC001, separate from frozen parsers."""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, earnings_bridge, finite

NS = 'http://www.xbrl.org/2003/instance'
DIM = 'http://xbrl.org/2006/xbrldi'
NIL = '{http://www.w3.org/2001/XMLSchema-instance}nil'
CONCEPTS = {
    'revenue': ('RevenueFromOperations',),
    'other_income': ('OtherIncome',),
    'pbt': ('ProfitBeforeTax',),
    'pretax_exceptional_items': ('ExceptionalItemsBeforeTax',),
    'tax_expense': ('TaxExpense', 'TotalTaxExpense'),
    'reported_pat': ('ProfitLossForPeriod',),
    'owner_pat': ('ProfitLossAttributableToOwnersOfParent', 'ProfitOrLossAttributableToOwnersOfParent'),
    'noncontrolling_pat': ('ProfitLossAttributableToNonControllingInterests', 'ProfitOrLossAttributableToNonControllingInterests'),
    'basic_eps': ('BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations',),
    'diluted_eps': ('DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations',),
    'paid_up_capital': ('PaidupEquityShareCapital', 'EquityShareCapital', 'PaidUpValueOfEquityShareCapital'),
    'face_value': ('FaceValueOfEquityShareCapital',),
}


def local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def extract_xbrl(raw: bytes, item: dict) -> list[dict]:
    if not raw or len(raw) > 16 * 1024 * 1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ChangeError('unsupported XML size or entity declarations')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ChangeError('invalid XBRL XML') from exc
    if root.tag != f'{{{NS}}}xbrl':
        raise ChangeError('original is not an XBRL instance')
    facts = [node for node in root if node.get('contextRef')]
    symbols = [n for n in facts if local(n.tag) == 'Symbol']
    if not symbols or {n.text for n in symbols} != {item['symbol']}:
        raise ChangeError('XBRL issuer symbol mismatch')
    # Restrict concepts to the same taxonomy as the issuer identity facts.
    namespaces = {n.tag.rsplit('}', 1)[0] for n in symbols}
    if len(namespaces) != 1:
        raise ChangeError('ambiguous XBRL taxonomy')
    prefix = next(iter(namespaces)) + '}'
    facts = [n for n in facts if n.tag.startswith(prefix)]
    isins = {n.text for n in facts if local(n.tag) == 'ISIN'}
    if isins != {item['isin']}:
        raise ChangeError('XBRL issuer ISIN mismatch')
    global_scopes = {str(n.text).strip().upper() for n in facts if local(n.tag) == 'NatureOfReportStandaloneConsolidated'}
    if not global_scopes:
        raise ChangeError('XBRL accounting scope missing')
    units = {}
    for unit in root.findall(f'{{{NS}}}unit'):
        ident = unit.get('id')
        if ident in units:
            raise ChangeError('duplicate XBRL unit identity')
        direct = unit.find(f'{{{NS}}}measure')
        if direct is not None:
            units[ident] = str(direct.text).split(':')[-1]
        else:
            numerator = unit.find(f'.//{{{NS}}}unitNumerator/{{{NS}}}measure')
            denominator = unit.find(f'.//{{{NS}}}unitDenominator/{{{NS}}}measure')
            units[ident] = (str(numerator.text).split(':')[-1] if numerator is not None else None,
                            str(denominator.text).split(':')[-1] if denominator is not None else None)
    records, context_ids = {}, set()
    for context in root.findall(f'{{{NS}}}context'):
        cid = context.get('id')
        if not cid or cid in context_ids:
            raise ChangeError('duplicate or absent XBRL context identity')
        context_ids.add(cid)
        if any(n.tag in {f'{{{DIM}}}explicitMember', f'{{{DIM}}}typedMember'} for n in context.iter()):
            continue
        # Other entity segments are not assumed to be consolidated-company totals.
        segment = context.find(f'{{{NS}}}entity/{{{NS}}}segment')
        scenario = context.find(f'{{{NS}}}scenario')
        if segment is not None or scenario is not None:
            continue
        begin = context.find(f'{{{NS}}}period/{{{NS}}}startDate')
        finish = context.find(f'{{{NS}}}period/{{{NS}}}endDate')
        if begin is None or finish is None:
            continue
        start, end = date.fromisoformat(begin.text), date.fromisoformat(finish.text)
        if start > end:
            raise ChangeError('XBRL reversed duration')
        if end.isoformat() > item['period_end']:
            continue
        scoped = [n for n in facts if n.get('contextRef') == cid]
        scope_values = {str(n.text).strip().upper() for n in scoped if local(n.tag) == 'NatureOfReportStandaloneConsolidated'}
        scope_values = scope_values or global_scopes
        if scope_values != {item['scope']}:
            continue
        extracted = {}
        for metric, names in CONCEPTS.items():
            nodes = [n for n in scoped if local(n.tag) in names and n.get(NIL) not in {'true', '1'}]
            if not nodes:
                continue
            values = []
            for node in nodes:
                unit = units.get(node.get('unitRef'))
                per_share = metric in {'basic_eps', 'diluted_eps', 'face_value'}
                if per_share:
                    if unit not in ('INR', ('INR', 'shares')):
                        raise ChangeError(f'{metric}: unsupported per-share XBRL unit {unit!r}')
                elif unit != 'INR':
                    raise ChangeError(f'{metric}: missing or non-INR XBRL unit {unit!r}')
                if node.get('scale') is not None:
                    raise ChangeError('inline scale is unsupported in an original XBRL instance')
                literal = (node.text or '').strip()
                try:
                    amount = Decimal(literal)
                except InvalidOperation as exc:
                    raise ChangeError('invalid XBRL number') from exc
                value = finite(amount if per_share else amount / Decimal(10_000_000), metric)
                values.append((value, node, literal))
            if len({v for v, _, _ in values}) != 1:
                raise ChangeError(f'conflicting XBRL concept {metric}')
            value, node, literal = values[0]
            extracted[metric] = {'value': value, 'unit': 'INR_per_share' if per_share else 'INR_crore',
                'literal': literal, 'quote': literal,
                'source_locator': {'concept': node.tag, 'context_ref': cid, 'unit_ref': node.get('unitRef')},
                'source_payload_sha256': hashlib.sha256(raw).hexdigest()}
        if not {'revenue', 'reported_pat'} <= extracted.keys():
            continue
        selector = {'period_start': start.isoformat(), 'period_end': end.isoformat(), 'scope': item['scope']}
        key = canonical_hash(selector)
        fingerprint = canonical_hash({k: (v['value'], v['unit']) for k, v in extracted.items()})
        if key in records and records[key]['facts_sha256'] != fingerprint:
            raise ChangeError('conflicting XBRL contexts for identical period and scope')
        warnings = []
        if {'owner_pat', 'noncontrolling_pat', 'reported_pat'} <= extracted.keys():
            residual = extracted['owner_pat']['value'] + extracted['noncontrolling_pat']['value'] - extracted['reported_pat']['value']
            if abs(residual) > max(0.02, abs(extracted['reported_pat']['value']) * 0.001):
                warnings.append('Reported owner plus minority profit does not reconcile with group profit. Review the issuer filing before using attributable earnings.')
        records.setdefault(key, {'selector': selector, 'facts': extracted, 'facts_sha256': fingerprint,
                                 'context_id': cid, 'warnings': warnings,
                                 'bridge': earnings_bridge({'facts': extracted})})
    if not records:
        raise ChangeError('no supported undimensioned XBRL financial context')
    if not any(r['selector']['period_end'] == item['period_end'] for r in records.values()):
        raise ChangeError('XBRL does not contain the declared current reporting period')
    return sorted(records.values(), key=lambda r: (r['selector']['period_end'], r['selector']['period_start']))


def persist_xbrl(store, raw: bytes, item: dict, final_url: str) -> list[dict]:
    records = extract_xbrl(raw, item)
    recipe = canonical_hash({'xml_code': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                             'base_code': hashlib.sha256(Path(__file__).with_name('company_change.py').read_bytes()).hexdigest()})
    outputs = []
    for record in records:
        selector = record['selector']
        source_id = 'xbrl-' + item['id'] + '-' + selector['period_start'] + '-' + selector['period_end']
        identity = {'symbol': item['symbol'], 'isin': item['isin'], 'scope': selector['scope'],
                    'kind': 'earnings_quality', 'event_key': selector['period_start'] + '/' + selector['period_end']}
        capture = store.capture(raw, {'source_id': source_id, 'url': item['url'], 'selector': selector,
            'origin': 'HTTP_RESPONSE_BYTES', 'final_url': final_url,
            'discovery_row_sha256': item['discovery_row_sha256'], 'published_at': item['published_at']})
        cached = store.cached(capture['id'], recipe)
        result = cached or store.record_extraction(capture, recipe, {
            **{k: item[k] for k in ('symbol', 'isin', 'url')}, 'kind': 'earnings_quality',
            'source_id': source_id, 'identity': identity, 'selector': selector,
            'facts': record['facts'], 'facts_sha256': record['facts_sha256'], 'bridge': record['bridge'],
            'warnings': record['warnings'],
            'requires_review': True, 'evidence_mode': 'HISTORICAL_RECONSTRUCTION', 'source_document': None,
            'blockers': ['Reported XBRL values require semantic and accounting review.',
                         'Sustainable owner earnings and current diluted shares are not automatically established.']})
        outputs.append({'source_id': source_id, 'extraction_id': result['extraction_id'],
            'symbol': item['symbol'], 'raw_sha256': capture['raw_sha256'],
            'facts': len(result['facts']), 'selector': selector, 'origin': 'HTTP_RESPONSE_BYTES'})
    return outputs
