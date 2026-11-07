from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlab.company_change import ChangeError
from marketlab.company_change_context import build_card, compare_period
from marketlab.company_change_context_quality import (
    attribution_check,
    direct_symbol_change,
    guarded_periods,
    resolve_xml_identity,
)
from marketlab.company_change_store import EvidenceStore

IDENTITY = {"symbol": "NEW", "isin": "INE000A01001", "scope": "CONSOLIDATED"}
NOW = "2026-11-08T00:00:00Z"
REGISTRY = b'Example Limited,OLD,NEW,20-Jul-2026\n'


def period():
    def fact(v):
        return {"value": v, "unit": "INR_crore", "rounding_error": 0.005}
    return {"identity": IDENTITY, "period_start": "2025-04-01", "period_end": "2026-03-31",
            "facts": {"owner_pat": fact(0), "minority_pat": fact(0), "group_pat": fact(100),
                      "revenue": fact(1000), "diluted_eps": {"value": 10, "unit": "INR_per_share"}},
            "source_url": "https://nsearchives.nseindia.com/annual.xml", "raw_sha256": "a" * 64,
            "known_at": "2026-11-07T12:00:00Z", "published_at": "2026-05-01T10:00:00Z"}


def test_inconsistent_attribution_withholds_only_affected_metrics():
    p = period()
    original = copy.deepcopy(p)
    guarded = guarded_periods([p])[0]
    assert guarded['context_quality']['attribution']['status'] == 'FAIL'
    result = compare_period(guarded, guarded)
    assert result['metrics']['owner_pat']['current'] is None
    assert result['metrics']['owner_pat']['reported_growth_fraction'] is None
    assert result['metrics']['group_pat']['current'] == 100
    assert result['metrics']['revenue']['current'] == 1000
    assert p == original
    assert guarded['facts']['owner_pat']['value'] == 0  # raw source not rewritten


def test_bad_annual_attribution_blocks_pe_even_when_eps_positive():
    quote = {'identity': IDENTITY, 'price': 100, 'quoted_at': '2026-11-06T10:00:00Z', 'observed_at': NOW}
    actions = {'start_exclusive': '2026-03-31', 'end_inclusive': '2026-11-08',
               'share_basis_changes_or_unknown_actions': []}
    result = build_card(IDENTITY, [period()], '2026-03-31', quote, actions, NOW)
    assert result['reported_annual_diluted_eps'] == 10
    assert result['price_over_reported_annual_eps'] is None
    assert result['reverse_hurdle_scenarios'] == []
    assert 'reconcile' in result['blockers'][0]


def test_declared_rounding_is_respected_without_invented_tolerance():
    p = period()
    p['facts']['owner_pat']['value'] = 100.01
    assert attribution_check(p)['status'] == 'WITHIN_REPORTED_ROUNDING'
    for fact in p['facts'].values():
        fact.pop('rounding_error', None)
    assert attribution_check(p)['status'] == 'ROUNDING_UNKNOWN'
    assert attribution_check(p)['withheld_fields']
    p['facts']['owner_pat']['value'] = 100
    assert attribution_check(p)['status'] == 'EXACT'
    del p['facts']['minority_pat']
    assert attribution_check(p)['status'] == 'MISSING_INPUT'
    assert not attribution_check(p)['withheld_fields']


@pytest.mark.parametrize('bad', [True, float('nan'), float('inf')])
def test_nonfinite_attribution_rejected(bad):
    p = period()
    p['facts']['owner_pat']['value'] = bad
    with pytest.raises(ChangeError):
        attribution_check(p)


def test_source_claimed_quality_pass_is_recomputed():
    p = period()
    p['context_quality'] = {'withheld_fields': [], 'attribution': {'status': 'PASS'}}
    assert guarded_periods([p])[0]['context_quality']['attribution']['status'] == 'FAIL'


def test_official_direct_alias_and_no_backdating():
    result = direct_symbol_change(REGISTRY, 'OLD', 'NEW', '2026-05-01T10:00:00Z', NOW)
    assert result['effective_date'] == '2026-07-20'
    assert result['source_line'] == 1
    assert result['observed_at'].startswith('2026-11-08')
    with pytest.raises(ChangeError, match='dates'):
        direct_symbol_change(REGISTRY, 'OLD', 'NEW', '2026-08-01T10:00:00Z', NOW)
    with pytest.raises(ChangeError, match='dates'):
        direct_symbol_change(REGISTRY, 'OLD', 'NEW', '2026-05-01T10:00:00Z', '2026-06-01T00:00:00Z')


@pytest.mark.parametrize('raw', [REGISTRY + REGISTRY, b'Example,OLD,OTHER,20-Jul-2026\n',
                               b'Example,OLD,NEW,invalid\n', b'bad,shape\n'])
def test_alias_absence_ambiguity_or_bad_registry_fails(raw):
    with pytest.raises(ChangeError):
        direct_symbol_change(raw, 'OLD', 'NEW', '2026-05-01T10:00:00Z', NOW)


def xml(symbol='OLD', isin='INE000A01001'):
    return f'''<x:xbrl xmlns:x="http://www.xbrl.org/2003/instance" xmlns:c="https://issuer.test/">
<c:Symbol contextRef="x">{symbol}</c:Symbol><c:ISIN contextRef="x">{isin}</c:ISIN></x:xbrl>'''.encode()


def test_identity_resolution_retains_original_and_registry(tmp_path):
    raw = xml()
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        ident, evidence = resolve_xml_identity(raw, IDENTITY, '2026-05-01T10:00:00Z', store,
            fetcher=lambda url, hosts: (REGISTRY, url))
        assert ident['symbol'] == 'OLD'
        assert ident['isin'] == IDENTITY['isin']
        assert evidence['new_symbol'] == 'NEW'
        assert store.read_blob(evidence['registry_sha256']) == REGISTRY
        assert raw == xml()
        assert IDENTITY['symbol'] == 'NEW'


def test_isin_mismatch_never_uses_alias_to_relax_identity(tmp_path):
    calls = []
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store, pytest.raises(ChangeError, match='ISIN'):
        resolve_xml_identity(xml(isin='INE000A01002'), IDENTITY, '2026-05-01T10:00:00Z', store,
                             fetcher=lambda *a: calls.append(a))
    assert calls == []


def test_matching_symbol_needs_no_registry_network_call(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        ident, evidence = resolve_xml_identity(xml(symbol='NEW'), IDENTITY, '2026-05-01T10:00:00Z', store,
                             fetcher=lambda *a: pytest.fail('network should not be called'))
    assert ident == IDENTITY
    assert evidence is None


def test_alias_failure_does_not_mutate_original_document(tmp_path):
    raw = xml()
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store, pytest.raises(ChangeError):
        resolve_xml_identity(raw, IDENTITY, '2026-05-01T10:00:00Z', store,
                             fetcher=lambda url, hosts: (b'Other,AAA,BBB,20-Jul-2026\n', url))
    assert raw == xml()


def test_no_independent_accuracy_or_capital_claim_in_quality_gate():
    check = attribution_check(period())
    assert 'probability' not in check
    assert 'buy' not in json.dumps(check)


def test_decision_workflow_preserves_checkpoint_before_failure():
    p = Path(__file__).resolve().parents[1] / '.github/workflows/cc001-daily-operations.yml'
    text = p.read_text()
    assert 'if ! python -m marketlab.company_change_decisions' in text
    assert text.index('company_change_checkpoint save') < text.index('test "$decision_ok" = true')
    assert text.index('push origin HEAD:refs/heads/cc001-state') < text.index('test "$decision_ok" = true')
    assert '--limit 40' in text and '--limit 3 --output-prefix' in text
    assert "- cron: '47 14 * * *'" in text
