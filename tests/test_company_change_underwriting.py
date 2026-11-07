from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_financials import extract_financials
from marketlab.company_change_underwriting import (
    analyze_financials,
    build_underwriting,
    entry_sensitivity,
    main,
    reconcile,
    render_underwriting,
)

IDENTITY = {"symbol": "TEST", "isin": "INE000A01001", "scope": "CONSOLIDATED"}
CLOCK = "2026-11-07T12:00:00Z"


def xml(*, currency_ns="http://www.xbrl.org/2003/iso4217", duration_start="2026-04-01", end="2026-09-30"):
    header = f'''<x:xbrl xmlns:x="http://www.xbrl.org/2003/instance" xmlns:t="https://issuer.test/taxonomy" xmlns:money="{currency_ns}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:d="http://xbrl.org/2006/xbrldi">
<x:unit id="R"><x:measure>money:INR</x:measure></x:unit>
<x:unit id="S"><x:divide><x:unitNumerator><x:measure>money:INR</x:measure></x:unitNumerator><x:unitDenominator><x:measure>x:shares</x:measure></x:unitDenominator></x:divide></x:unit>'''
    def ctx(cid, period):
        return f'<x:context id="{cid}"><x:entity><x:identifier scheme="company">TEST</x:identifier></x:entity><x:period>{period}</x:period></x:context>'
    header += ctx("H", f"<x:startDate>{duration_start}</x:startDate><x:endDate>{end}</x:endDate>")
    header += ctx("C", f"<x:instant>{end}</x:instant>")
    header += ctx("O", f"<x:instant>{(date.fromisoformat(duration_start) - timedelta(days=1)).isoformat()}</x:instant>")
    header += '<t:Symbol contextRef="H">TEST</t:Symbol><t:ISIN contextRef="H">INE000A01001</t:ISIN>'
    header += '<t:NatureOfReportStandaloneConsolidated contextRef="H">Consolidated</t:NatureOfReportStandaloneConsolidated>'
    # Flow values are rupees. Display rounding does not scale instance numbers.
    header += '<t:LevelOfRounding contextRef="H">Lakhs</t:LevelOfRounding>'
    dur = {"RevenueFromOperations": 100, "ProfitBeforeTax": 20, "ProfitLossForPeriod": 15,
        "ProfitOrLossAttributableToOwnersOfParent": 12, "ProfitOrLossAttributableToNonControllingInterests": 3,
        "CashFlowsFromUsedInOperatingActivities": 30, "CashFlowsFromUsedInInvestingActivities": -10,
        "CashFlowsFromUsedInFinancingActivities": -5, "EffectOfExchangeRateChangesOnCashAndCashEquivalents": 0,
        "IncreaseDecreaseInCashAndCashEquivalents": 15,
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": 6,
        "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities": 2,
        "PurchaseOfIntangibleAssetsUnderDevelopment": 0}
    ins = {"CashAndCashEquivalents": 35, "CashAndCashEquivalentsCashFlowStatement": 35,
        "BankBalanceOtherThanCashAndCashEquivalents": 80, "BorrowingsCurrent": 20, "BorrowingsNoncurrent": 40,
        "Assets": 200, "Liabilities": 80, "Equity": 120, "EquityAndLiabilities": 200,
        "CurrentAssets": 90, "CurrentLiabilities": 50}
    for context, fields in (("H", dur), ("C", ins), ("O", {"CashAndCashEquivalentsCashFlowStatement": 20})):
        for concept, val in fields.items():
            header += f'<t:{concept} contextRef="{context}" unitRef="R" decimals="-4">{val * 10000000}</t:{concept}>'
    header += '<t:DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="H" unitRef="S" decimals="2">2.50</t:DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations>'
    return (header + "</x:xbrl>").encode()


def document(raw=None):
    return extract_financials(raw or xml(), IDENTITY, CLOCK)


def change(raw, concept, old, new):
    return raw.replace(f'>{old}</t:{concept}>'.encode(), f'>{new}</t:{concept}>'.encode())


def snapshot(raw):
    sha = hashlib.sha256(raw).hexdigest()
    result = {"as_of": CLOCK, "active": [{**IDENTITY, "kind": "earnings_quality",
        "selector": {"scope": "CONSOLIDATED", "period_start": "2026-04-01", "period_end": "2026-09-30"},
        "extraction_id": "old-extraction", "raw_sha256": sha, "known_at": CLOCK,
        "url": "https://issuer.test/original.xml", "review_status": "ACCEPT"}], "history": [],
        "live_capital_allowed": False, "trained_predictor": False}
    result["snapshot_sha256"] = canonical_hash(result)
    return result


def test_cfo_uses_same_period_group_profit_and_debt_ignores_other_bank_cash():
    result = analyze_financials(document(), "2026-09-30")
    assert result["cfo_crore"] == 30
    assert result["specified_capex_crore"] == 8
    assert result["cfo_less_specified_capex_crore"] == 22
    assert result["cfo_to_group_pat"] == 2  # not 30/12 owner earnings
    assert result["gross_borrowings_crore"] == 60
    assert result["net_borrowings_excluding_leases_crore"] == 25  # do not credit 80 of other bank balances
    assert result["current_ratio"] == 1.8
    assert all(t["status"] == "EXACT" for t in result["checks"])
    assert result["disposition"] == "CASH_COVERED_SPECIFIED_CAPEX"
    assert result["live_capital_allowed"] is False


def test_units_not_display_rounding_and_reported_eps_not_annualized():
    d = document()
    h = d["periods"][0]
    assert h["facts"]["cfo"]["value"] == 30
    assert h["facts"]["diluted_eps"]["value"] == 2.5
    assert h["facts"]["cfo"]["rounding_error"] == 0.0005
    assert "normalized_owner_eps" not in h
    assert d["source_sha256"] == hashlib.sha256(xml()).hexdigest()


@pytest.mark.parametrize("mutation", ["nil", "missing", "negative"])
def test_capex_never_filled_with_zero_or_flipped(mutation):
    raw = xml()
    tag = '<t:PurchaseOfIntangibleAssetsUnderDevelopment contextRef="H" unitRef="R" decimals="-4">0</t:PurchaseOfIntangibleAssetsUnderDevelopment>'
    replacement = '' if mutation == "missing" else tag.replace('>0<', '>-100<') if mutation == "negative" else tag.replace('decimals="-4"', 'decimals="-4" xsi:nil="true"')
    raw = raw.replace(tag.encode(), replacement.encode())
    result = analyze_financials(document(raw), "2026-09-30")
    assert result["specified_capex_crore"] is None
    assert result["cfo_less_specified_capex_crore"] is None


def test_positive_profit_can_coexist_with_negative_cfo():
    raw = change(xml(), "CashFlowsFromUsedInOperatingActivities", 300000000, -300000000)
    r = analyze_financials(document(raw), "2026-09-30")
    assert r["group_pat_crore"] == 15
    assert r["cfo_crore"] == -30
    assert "NEGATIVE_OPERATING_CASH_FLOW" in r["alerts"]
    # Cash reconciliation takes precedence rather than hiding mismatched source figures.
    assert r["disposition"] == "RECONCILE_SOURCE_FIRST"


def test_before_tax_operating_subtotal_is_not_cfo():
    raw = xml().replace(b'CashFlowsFromUsedInOperatingActivities', b'CashFlowsFromUsedInOperations')
    r = analyze_financials(document(raw), "2026-09-30")
    assert r["cfo_crore"] is None
    assert r["cfo_to_group_pat"] is None
    assert r["disposition"] == "CASH_EVIDENCE_INCOMPLETE"


def test_missing_borrowings_component_does_not_default_to_zero():
    raw = xml().replace(b'BorrowingsNoncurrent', b'UnmappedDebt')
    r = analyze_financials(document(raw), "2026-09-30")
    assert r["gross_borrowings_crore"] is None
    assert r["net_borrowings_excluding_leases_crore"] is None


def test_rounding_intervals_not_fixed_three_lakh_threshold():
    def fact(value, error):
        return {"decimal_value": str(value), "rounding_error": error}
    assert reconcile("r", [(1, fact(10, .5)), (-1, fact(10.8, .5))])["status"] == "WITHIN_REPORTED_ROUNDING"
    assert reconcile("r", [(1, fact(10, .001)), (-1, fact(10.01, .001))])["status"] == "FAIL"
    assert reconcile("r", [(1, fact(10, None)), (-1, fact(10.01, .001))])["status"] == "ROUNDING_UNKNOWN"
    assert reconcile("r", [(1, None), (-1, fact(10, .001))])["status"] == "MISSING_INPUT"


@pytest.mark.parametrize("field", ["Symbol", "ISIN", "NatureOfReportStandaloneConsolidated"])
def test_wrong_identity_or_scope_fails(field):
    raw = xml()
    old = {"Symbol": "TEST", "ISIN": "INE000A01001", "NatureOfReportStandaloneConsolidated": "Consolidated"}[field]
    raw = raw.replace(f'>{old}</t:{field}>'.encode(), f'>OTHER</t:{field}>'.encode())
    with pytest.raises(ChangeError):
        document(raw)


def test_fake_currency_namespace_is_not_inr():
    with pytest.raises(ChangeError, match="namespace-qualified unit"):
        document(xml(currency_ns="https://attacker.test/currencies"))


def test_entity_context_mismatch_is_not_joined():
    raw = xml().replace(b'<x:context id="C"><x:entity><x:identifier scheme="company">TEST',
                        b'<x:context id="C"><x:entity><x:identifier scheme="company">OTHER')
    r = analyze_financials(document(raw), "2026-09-30")
    assert r["cash_equivalents_crore"] is None


def test_dimensional_subsidiary_or_segment_cash_is_not_group_cash():
    raw = xml().replace(b'<x:context id="C"><x:entity>',
        b'<x:context id="C"><x:scenario><d:explicitMember dimension="t:Segment">t:Child</d:explicitMember></x:scenario><x:entity>')
    r = analyze_financials(document(raw), "2026-09-30")
    assert r["cash_equivalents_crore"] is None


@pytest.mark.parametrize("old,new", [(b'300000000', b'NaN'), (b'300000000', b'3e8'),
    (b'decimals="-4"', b'decimals="-4" scale="5"'), (b'decimals="-4"', b'decimals="bad"'),
    (b'unitRef="R"', b'unitRef="not-there"')])
def test_ambiguous_or_malformed_numbers_fail(old, new):
    with pytest.raises(ChangeError):
        document(xml().replace(old, new))


def test_entities_and_namespace_rebinding_rejected():
    with pytest.raises(ChangeError, match="entities"):
        document(b'<!DOCTYPE x [<!ENTITY e "test">]>' + xml())
    raw = xml().replace(b'<t:Symbol', b'<t:Symbol xmlns:money="https://fake.test/"')
    with pytest.raises(ChangeError, match="rebinding"):
        document(raw)


def test_conflicting_duplicates_fail_instead_of_first_wins():
    raw = xml().replace(b'</x:xbrl>', b'<t:CashFlowsFromUsedInOperatingActivities contextRef="H" unitRef="R" decimals="-4">999</t:CashFlowsFromUsedInOperatingActivities></x:xbrl>')
    with pytest.raises(ChangeError, match="conflicting"):
        document(raw)


def test_source_locator_and_rounding_accuracy_survive():
    f = document()["periods"][0]["facts"]["cfo"]
    assert f["literal"] == '300000000'
    assert f["context_ref"] == 'H'
    assert f["unit_ref"] == 'R'
    assert f["decimals"] == '-4'
    assert f["concept"].endswith('CashFlowsFromUsedInOperatingActivities')


def test_year_ago_absence_does_not_become_growth():
    a = analyze_financials(document(), "2026-09-30")
    assert a["same_source_year_ago"]["revenue"]["growth_fraction"] is None
    assert any('2025-04-01 to 2025-09-30' in gap for gap in a["gaps"])


def test_same_source_yoy_when_genuinely_present():
    d = document()
    prior = copy.deepcopy(d["periods"][0])
    prior["period_start"], prior["period_end"] = '2025-04-01', '2025-09-30'
    prior["facts"]["revenue"]["decimal_value"] = '80'
    d["periods"].append(prior)
    assert analyze_financials(d, '2026-09-30')["same_source_year_ago"]["revenue"]["growth_fraction"] == .25


def test_snapshot_original_hash_and_no_backdating():
    raw = xml()
    snap = snapshot(raw)
    r = build_underwriting(snap, lambda digest: raw, evaluated_at=CLOCK)
    assert r['counts']['analyzed'] == 1
    assert r['cards'][0]['financial_fact_review'] == 'UNREVIEWED'  # old acceptance does not approve new metrics
    assert r['cards'][0]['entry_case'] is None
    assert r['validated_predictive_edge'] is False
    tampered = copy.deepcopy(snap)
    tampered['active'][0]['symbol'] = 'OTHER'
    with pytest.raises(ChangeError, match='integrity'):
        build_underwriting(tampered, lambda digest: raw, evaluated_at=CLOCK)
    with pytest.raises(ChangeError, match='backdated'):
        build_underwriting(snap, lambda digest: raw, evaluated_at='2026-11-06T00:00:00Z')
    failed = build_underwriting(snap, lambda digest: b'wrong', evaluated_at=CLOCK)
    assert failed['counts']['failed'] == 1


def test_failures_remain_in_denominator_without_erasing_valid_documents():
    raw = xml()
    snap = snapshot(raw)
    second = copy.deepcopy(snap['active'][0])
    second['symbol'], second['isin'], second['raw_sha256'] = 'OTHER', 'INE000A01002', 'a'*64
    snap['active'].append(second)
    snap['snapshot_sha256'] = canonical_hash({k:v for k,v in snap.items() if k!='snapshot_sha256'})
    report = build_underwriting(snap, lambda sha: raw if sha != 'a'*64 else b'unsupported', evaluated_at=CLOCK)
    assert report['counts']['analyzed'] == report['counts']['failed'] == 1
    assert len(report['cards']) == 2


def test_html_escapes_all_source_content():
    r = build_underwriting(snapshot(xml()), lambda digest: xml(), evaluated_at=CLOCK)
    r['cards'][0]['symbol'] = '<script>bad</script>'
    page = render_underwriting(r)
    assert '<script>' not in page
    assert '&lt;script&gt;' in page
    assert 'not an investment recommendation' in page


def test_empty_workspace_cli(tmp_path, capsys):
    output = tmp_path/'out'/'underwriting'
    assert main(['--workspace',str(tmp_path/'workspace'),'--output-prefix',str(output)]) == 0
    report = json.loads(output.with_suffix('.json').read_text())
    assert report['counts']['analyzed'] == 0
    assert output.with_suffix('.html').exists()
    capsys.readouterr()


def test_entry_requires_annual_earnings_and_never_annualizes_halfyear():
    case = {'period_start': '2026-04-01','period_end':'2026-09-30','normalization':{},'shares':{},'specification':{}}
    with pytest.raises(ChangeError, match='annualized'):
        entry_sensitivity(document(), case, CLOCK)


def annual_case():
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root/'data/fixtures/company_change_v1.json').read_text())['valuations'][0]
    spec.update(symbol='TEST',isin='INE000A01001',scope='CONSOLIDATED')
    def evidence(val, unit):
        return {'value':val,'unit':unit,'reviewer':'analyst','reviewed_at':'2026-11-06T11:00:00Z', 'identity':dict(IDENTITY),
                'source_url':'https://issuer.test/notes','evidence_text':f'Value: {val}', 'quote':f'Value: {val}', 'literal':str(val)}
    return {'period_start':'2025-04-01','period_end':'2026-03-31',
            'normalization':{**evidence(2, 'INR_crore_after_tax_owner_adjustment'), 'period_start':'2025-04-01', 'period_end':'2026-03-31'},
            'shares':{**evidence(10000000, 'fully_diluted_shares'), 'effective_at':'2026-11-06T09:00:00Z', 'capital_events_checked_through':'2026-11-06T10:30:00Z'}, 'specification':spec}


def test_explicit_evidence_binds_annual_owner_earnings_and_fully_diluted_shares():
    d = document(xml(duration_start='2025-04-01',end='2026-03-31'))
    case = annual_case()
    result = entry_sensitivity(d, case, CLOCK)
    assert result['base_owner_eps'] == 10
    assert result['live_capital_allowed'] is False
    assert result['disposition'] == 'ANALYST_SCENARIO_NOT_INVESTMENT_APPROVAL'


@pytest.mark.parametrize('fault', ['value','future','scope','missing','unit'])
def test_bad_valuation_evidence_is_not_promoted(fault):
    d = document(xml(duration_start='2025-04-01',end='2026-03-31'))
    c = annual_case()
    if fault=='value': c['shares']['value'] = 123
    if fault=='future': c['shares']['reviewed_at'] = '2027-01-01T00:00:00Z'
    if fault=='scope': c['specification']['scope'] = 'STANDALONE'
    if fault=='missing': del c['normalization']['quote']
    if fault=='unit': c['normalization']['unit'] = 'INR_crore_before_tax'
    with pytest.raises(ChangeError):
        entry_sensitivity(d, c, CLOCK)


@pytest.mark.parametrize("fault", ["old_shares", "wrong_period", "wrong_entity", "fractional_shares"])
def test_normalization_and_shares_are_date_and_issuer_bound(fault):
    d = document(xml(duration_start="2025-04-01", end="2026-03-31"))
    c = annual_case()
    if fault == "old_shares":
        c["shares"]["capital_events_checked_through"] = "2026-11-06T09:30:00Z"
    elif fault == "wrong_period":
        c["normalization"]["period_end"] = "2025-03-31"
    elif fault == "wrong_entity":
        c["normalization"]["identity"]["symbol"] = "OTHER"
    else:
        c["shares"].update(value=1.5, literal="1.5", quote="Value: 1.5", evidence_text="Value: 1.5")
    with pytest.raises(ChangeError):
        entry_sensitivity(d, c, CLOCK)


def test_wrong_owner_attribution_blocks_valuation_even_with_signed_adjustments():
    raw = change(xml(duration_start="2025-04-01", end="2026-03-31"), "ProfitOrLossAttributableToOwnersOfParent", 120000000, 100000000)
    with pytest.raises(ChangeError, match="attribution"):
        entry_sensitivity(document(raw), annual_case(), CLOCK)


def test_no_ignored_entry_cases():
    c = annual_case()
    c["specification"]["symbol"] = "OTHER"
    with pytest.raises(ChangeError, match="no matching"):
        build_underwriting(snapshot(xml()), lambda sha: xml(), evaluated_at=CLOCK, entry_cases=[c])


def test_cash_export_failure_cannot_skip_source_checkpoint():
    import yaml

    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root/'.github/workflows/cc001-daily-operations.yml').read_text())
    steps = workflow['jobs']['refresh-research-workspace']['steps']
    command = next(s['run'] for s in steps if s.get('name') == 'Export research desk and checkpoint durable state')
    assert 'if ! python -m marketlab.company_change_underwriting' in command
    assert command.index('company_change_checkpoint save') < command.index('test "$underwriting_ok" = true')
    assert command.index('push origin HEAD:refs/heads/cc001-state') < command.index('test "$underwriting_ok" = true')
    assert "'cash_underwriting_status': 'SUCCESS' if underwriting else 'FAILED'" in command
    assert '--limit 40' in next(s['run'] for s in steps if s.get('id') == 'intake')
    upload = next(s for s in steps if s.get('uses') == 'actions/upload-artifact@v4')
    assert 'cash-underwriting.json' in upload['with']['path']


def test_underwriting_same_snapshot_is_deterministic_without_source_writes():
    raw = xml()
    before = snapshot(raw)
    original = copy.deepcopy(before)
    a = build_underwriting(before, lambda sha: raw, evaluated_at=CLOCK)
    b = build_underwriting(before, lambda sha: raw, evaluated_at=CLOCK)
    assert a == b
    assert before == original
    assert a['report_sha256'] == canonical_hash({k:v for k,v in a.items() if k!='report_sha256'})
