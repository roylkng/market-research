"""Dated SEAMEC underwriting arithmetic from retained originals.

This is one assisted case, not a return predictor. No forecasts are fitted and no
broker or production research state is touched. Scenario parameters are assumptions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

D = Decimal
CRORE = D(10_000_000)
X = '{http://www.xbrl.org/2003/instance}'
IDENTITY = {'symbol': 'SEAMECLTD', 'isin': 'INE497B01018', 'scope': 'CONSOLIDATED'}
PINS = {
    'annual_fy26': '12f9f4f5b7606e1aa730b070f73aace10144d483c79297b9d28af96ce49c53f1',
    'board_results_20261103': 'f8bae1ce88fc53f8bc87dbdc5d0daf511eb43b795443d16b3c7278453b6fd518',
    'h1fy27_xml': '23e945063cbd3304cc37cbb69919cd2269e9500ee122b448ebeca42e90be119f',
    'h1fy26_xml': '3ad8d274ec58cda4cbca45a23a917c438c9e3aefe24a9294d5463df803c0f03d',
    'fy26_xml': 'd4541871c6725b54f2850fcf970a0c785da571eaf7be9d42b6322f9c61c61b2f',
    'fy25_xml': 'c4187502a85881fc6d249a6abb617c3d27fd4c706862128a7e15359625adba66',
    'q1fy27_xml': '30ea4377ae131dc7b212875a2223a2c0850041264d07ad000dc573d1f40fba1a',
    'commencement_20261108': '0b1c76766b979e338ec9840e47af37586dd517851e74155282848a64633b1c5d',
    'anant_takeover': '799a2c83486c2b35253baed84784934a867b7c71c9c9c3654fc11b43a7ca1d84',
    'anant_charter': 'b4aaad97665446965ce806f969fa227b2d4f1019212a2ffe9923983712b3157a',
}
TAGS = {
    'revenue': 'RevenueFromOperations',
    'other_income': 'OtherIncome',
    'pbt_before_exception': 'ProfitBeforeExceptionalItemsAndTax',
    'exceptional_gain': 'ExceptionalItemsBeforeTax',
    'pbt': 'ProfitBeforeTax',
    'owner_pat': 'ProfitOrLossAttributableToOwnersOfParent',
    'group_pat': 'ProfitLossForPeriod',
    'finance_cost': 'FinanceCosts',
    'depreciation': 'DepreciationDepletionAndAmortisationExpense',
    'tax': 'TaxExpense',
}


def canon(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('numeric value required')
    result = D(str(value))
    if not result.is_finite():
        raise ValueError('nonfinite input')
    return result


def scenario(eps, growth, multiple, price, years=5, hurdle='0.15'):
    eps, growth, multiple, price, hurdle = map(number, (eps, growth, multiple, price, hurdle))
    if (eps <= 0 or price <= 0 or not 1 <= multiple <= 100 or not D('-0.99') < growth <= 1
            or type(years) is not int or not 1 <= years <= 10 or not 0 <= hurdle <= 1):
        raise ValueError('scenario outside bounds')
    future = eps * (1 + growth) ** years * multiple
    return {'starting_eps': float(eps), 'annual_eps_growth': float(growth),
            'exit_pe': float(multiple), 'years': years, 'price_return_hurdle': float(hurdle),
            'terminal_price': float(future),
            'price_cagr_at_reference': math.pow(float(future / price), 1 / years) - 1,
            'entry_price_meeting_hurdle': float(future / (1 + hurdle) ** years),
            'required_eps_growth_at_reference': math.pow(float(price * (1 + hurdle) ** years / (eps * multiple)), 1 / years) - 1,
            'terminal_value_change_from_reference': float(future / price - 1),
            'dividends_taxes_costs_included': False, 'probability_assigned': False}


def earnings_lens(owner_pat, removed_pretax, shares, assumed_tax_benefit):
    pat, removed, shares, tax = map(number, (owner_pat, removed_pretax, shares, assumed_tax_benefit))
    if shares <= 0 or removed < 0 or not 0 <= tax <= 1:
        raise ValueError('invalid earnings sensitivity')
    return (pat - removed * (1 - tax)) * CRORE / shares


def root_xml(raw):
    if len(raw) > 2_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unsupported XML')
    root = ElementTree.fromstring(raw)
    for field, expected in [('Symbol', 'SEAMECLTD'), ('ISIN', 'INE497B01018')]:
        values = {n.text for n in root if n.tag.rsplit('}', 1)[-1] == field}
        if values != {expected}:
            raise ValueError('issuer identity mismatch')
    return root


def text_fact(root, tag, context):
    nodes = [n for n in root if n.tag.rsplit('}', 1)[-1] == tag and n.get('contextRef') == context]
    if len(nodes) != 1 or nodes[0].text is None:
        raise ValueError(f'exact fact unavailable: {context}/{tag}')
    return nodes[0]


def fact(root, tag, context, records, source):
    node = text_fact(root, tag, context)
    if node.get('unitRef') != 'INR':
        raise ValueError('not INR monetary evidence')
    value = number(node.text) / CRORE
    records.append({'source': source, 'tag': tag, 'context': context,
                    'raw_value': node.text, 'unit': 'INR', 'crore': str(value),
                    'source_decimals': node.get('decimals')})
    return value


def period(root, context, start, end, records, source):
    context_node = root.find(f"{X}context[@id='{context}']")
    if (context_node is None or context_node.find(f'{X}period/{X}startDate').text != start
            or context_node.find(f'{X}period/{X}endDate').text != end
            or context_node.find(f'{X}scenario') is not None
            or text_fact(root, 'NatureOfReportStandaloneConsolidated', context).text != 'Consolidated'):
        raise ValueError('period or accounting scope mismatch')
    result = {k: fact(root, t, context, records, source) for k, t in TAGS.items()}
    result['operating_ebitda_ex_other_income'] = (result['pbt_before_exception'] - result['other_income']
                                               + result['finance_cost'] + result['depreciation'])
    if abs(result['pbt_before_exception'] + result['exceptional_gain'] - result['pbt']) > D('.02'):
        raise ValueError('PBT bridge fails disclosed rounding')
    return result


def verify_price(workspace, quote):
    if quote['identity'] != IDENTITY or quote['session_date'] != '2026-11-09':
        raise ValueError('case requires exact dated price identity')
    raw = (workspace / 'blobs' / quote['raw_sha256'][:2] / quote['raw_sha256']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != quote['raw_sha256']:
        raise ValueError('price source hash mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.namelist() != ['BhavCopy_NSE_CM_0_0_0_20261109_F_0000.csv']:
            raise ValueError('price archive member mismatch')
        csv_raw = archive.read(archive.namelist()[0])
    if hashlib.sha256(csv_raw).hexdigest() != quote['csv_sha256']:
        raise ValueError('price CSV hash mismatch')
    rows = [r for r in csv.DictReader(io.StringIO(csv_raw.decode('utf-8-sig')))
            if r['TckrSymb'] == 'SEAMECLTD' and r['SctySrs'] == 'EQ']
    if len(rows) != 1 or any(rows[0][k] != v for k, v in {
        'TradDt': '2026-11-09', 'ISIN': IDENTITY['isin'], 'Sgmt': 'CM', 'Src': 'NSE', 'FinInstrmTp': 'STK'
    }.items()) or number(rows[0]['ClsPric']) != number(quote['price']):
        raise ValueError('price row mismatch')
    return rows[0]


def build(workspace):
    manifest = json.loads((workspace / 'capture-manifest.json').read_text())
    if canon({k: v for k, v in manifest.items() if k != 'report_sha256'}) != manifest.get('report_sha256'):
        raise ValueError('capture manifest hash mismatch')
    by_name = {s['name']: s for s in manifest['sources']}
    if len(by_name) != len(manifest['sources']):
        raise ValueError('duplicate source name')
    raw = {}
    for name, expected in PINS.items():
        source = by_name[name]
        content = (workspace / source['path']).read_bytes()
        if source['sha256'] != expected or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError('original filing changed: ' + name)
        raw[name] = content
    # Read the original audited EPS note, not rounded capital or a generated summary.
    annual = PdfReader(io.BytesIO(raw['annual_fy26']))
    eps_note = annual.pages[210].extract_text()
    capital_note = annual.pages[195].extract_text()
    found = re.search(r'Weighted average number of equity shares outstanding.*?25,425,000', eps_note, re.DOTALL)
    if not found or '25,425,000' not in capital_note or '98.87' not in eps_note:
        raise ValueError('exact audited share evidence unavailable')
    shares = D('25425000')
    quote = manifest['quote']
    price_row = verify_price(workspace, quote)
    price = number(quote['price'])
    records, periods = [], {}
    specs = [
        ('FY25', 'fy25_xml', 'FourD', '2024-04-01', '2025-03-31'),
        ('FY26', 'fy26_xml', 'FourD', '2025-04-01', '2026-03-31'),
        ('H1FY26', 'h1fy26_xml', 'FourD', '2025-04-01', '2025-09-30'),
        ('H1FY27', 'h1fy27_xml', 'FourD', '2026-04-01', '2026-09-30'),
        ('Q1FY27', 'q1fy27_xml', 'OneD', '2026-04-01', '2026-06-30'),
        ('Q2FY27', 'h1fy27_xml', 'OneD', '2026-07-01', '2026-09-30'),
    ]
    roots = {s: root_xml(raw[s]) for s in {x[1] for x in specs}}
    for label, source, context, start, end in specs:
        periods[label] = period(roots[source], context, start, end, records, source)
    # Same additive flow identity only. EPS and shares are never added or annualized.
    ttm = {k: periods['FY26'][k] + periods['H1FY27'][k] - periods['H1FY26'][k] for k in periods['FY26']}
    current = roots['h1fy27_xml']
    def cf(tag):
        return fact(current, tag, 'FourD', records, 'h1fy27_xml')
    cfo = cf('CashFlowsFromUsedInOperatingActivities')
    wc = sum(cf(t) for t in ('AdjustmentsForDecreaseIncreaseInInventories',
        'AdjustmentsForDecreaseIncreaseInTradeReceivablesCurrent',
        'AdjustmentsForIncreaseDecreaseInTradePayablesCurrent'))
    # The provisions line is explicitly read from the original statement page 12.
    result_text = PdfReader(io.BytesIO(raw['board_results_20261103'])).pages[11].extract_text()
    if 'Increase in provision' not in result_text or '32,074' not in result_text:
        raise ValueError('cash statement provenance unavailable')
    wc += D('.05')
    cash = {'cfo': cfo, 'net_working_capital_contribution_including_provisions': wc,
            'cfo_without_those_movements_not_normalized_fcf': cfo - wc,
            'specified_cash_ppe_purchases': cf('PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'),
            'cash_interest_in_financing': cf('InterestPaidClassifiedAsFinancingActivities'),
            'cash_lease_payments': cf('PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities')}
    cash['after_specified_purchases_interest_leases'] = cfo - cash['specified_cash_ppe_purchases'] - cash['cash_interest_in_financing'] - cash['cash_lease_payments']
    cash['same_before_working_capital_movements'] = cash['after_specified_purchases_interest_leases'] - wc
    lenses = []
    for name, removed in [('Remove vessel-sale gain only', ttm['exceptional_gain']),
                          ('Remove gain and all other income', ttm['exceptional_gain'] + ttm['other_income'])]:
        for tax in (D('0'), D('.25')):
            eps = earnings_lens(ttm['owner_pat'], removed, shares, tax)
            lenses.append({'label': name, 'pretax_removed_crore': float(removed),
                           'assumed_tax_benefit_fraction': float(tax), 'eps': float(eps),
                           'reference_pe': float(price / eps),
                           'scope': 'SENSITIVITY_NOT_VERIFIED_NORMALIZED_OWNER_EARNINGS'})
    cases = [dict(name=n, **scenario(e, g, m, price)) for n, e, g, m in (
        ('Stress', 80, 0, 10), ('Conservative base', 100, '.12', 12),
        ('Optimistic', 120, '.18', 15), ('Generous cross-check', 115, '.15', 12))]
    mcap = price * shares / CRORE
    order = []
    for fx in (85, 100):
        npv = D('26.14') * D(1_000_000) * fx / CRORE * D('.10') / D('1.15')
        order.append({'hypothetical_usdinr': fx, 'after_tax_cash_margin': .10,
                      'receipt_months': 12, 'discount_rate': .15, 'additional_funding_crore': 0,
                      'fully_incremental_assumed': True, 'finite_npv_crore': float(npv),
                      'reference_per_share': float(npv * CRORE / shares),
                      'equity_value_fraction': float(npv / mcap)})
    report = {'case': 'SEAMEC-20261109', 'reference_date': quote['session_date'],
        'source_capture_completed_at': manifest['observed_at'],
        'decision': 'WAIT_NO_FRESH_PURCHASE_AT_REFERENCE_PRICE',
        'decision_basis': 'Assisted underwriting judgment, not a calibrated forecast or trade instruction.',
        'price': quote, 'price_row': price_row, 'reference_share_count': int(shares),
        'shares_evidence': {'source': 'annual_fy26', 'pdf_pages': [196, 197, 211],
            'printed_pages': [194, 195, 209], 'basis_date': '2026-03-31',
            'basis': 'Audited outstanding and basic/diluted weighted shares, not inferred from rounded capital.',
            'current_dilution_note': 'Carried forward reference denominator. Subsequent full dilution not independently certified.'},
        'reference_market_cap_crore': float(mcap), 'reported_ttm_eps': float(ttm['owner_pat'] * CRORE / shares),
        'reported_ttm_pe': float(price / (ttm['owner_pat'] * CRORE / shares)),
        'periods_crore': {p: {k: str(v) for k, v in values.items()} for p, values in periods.items()},
        'reported_ttm_crore': {k: str(v) for k, v in ttm.items()},
        'ttm_basis': 'FY26 + H1FY27 - H1FY26. Cross-document reported flows, not restatement-certified.',
        'q2_exception_share_of_pbt': float(periods['Q2FY27']['exceptional_gain'] / periods['Q2FY27']['pbt']),
        'q2_pbt_ex_exception_and_other_income_crore': float(periods['Q2FY27']['pbt_before_exception'] - periods['Q2FY27']['other_income']),
        'h1_cash_crore': {k: str(v) for k, v in cash.items()},
        'earnings_sensitivities': lenses, 'valuation_scenarios': cases, 'finite_order_sensitivity': order,
        'source_assertions': {
            'princess': '8 November filing confirms departure from Mumbai at 07:06 to commence PRP-X. Not proof of accepted billable work or collected cash.',
            'anant': 'Taken over from HAL on 14 October. Chartered back to HAL for ONGC IMR, about USD55m over1225 days, excluding GST. Related-party transaction. Onhire filing says21 October22:00.',
            'tax': 'Annual policy applies tonnage-based taxation to shipping income, not a universal25% corporate tax on all earnings.',
            'cash_reconciliation': 'Q2/H1 results note reports42.43cr exceptional sale gain. H1 cash-flow statement shows27.31cr gain-on-fixed-assets adjustment. The15.12cr difference is not reconciled here.',
            'deposit_restrictions': 'FY26 annual note16 identifies UAE term deposits pledged against overdraft facilities. Do not assume all bank balances are freely distributable.'},
        'external_primary_reference': {'publisher': 'CRISIL Ratings', 'date': '2026-10-13',
            'url': 'https://www.crisil.com/mnt/winshare/Ratings/RatingList/RatingDocs/SeamecLimited_October%2013_%202026_RR_406092.html',
            'finding': 'A+/Stable andA1 reaffirmed. Expects expansion to move net cash to net debt. Forecasts are agency assessments, not realized balances.'},
        'next_decisive_evidence': [
            'Post-Anant debt, cash restrictions and total financing cost rather than the September snapshot.',
            'Recurring per-share earnings after vessel sale, financing effects and ordinary maintenance, without double counting the PRP-X order.',
            'Billable deployment, charter cash collection and reconciliation of the sale-gain cash-flow adjustment.',
            'A dated price at or below a justified hurdle threshold, with share dilution and liquidity rechecked.'],
        'fact_records': records, 'sources': manifest['sources'], 'source_capture_errors': manifest['errors'],
        'live_capital_allowed': False, 'model_called': False,
        'limits': ['Scenarios are analyst assumptions, not probabilities or price targets.',
                   'Other income contains recurring interest as well as variable items. Removing all of it is a stricter sensitivity, not an accounting correction.',
                   'The0% and25% tax benefits are hypothetical removal assumptions, not the actual tax on the sale.',
                   'Five-year outcomes exclude dividends, taxes, costs, dilution and execution slippage.',
                   'Working-capital-stripped cash less full purchases is not normalized maintenance free cash flow.',
                   'No surplus cash is added separately to an earnings valuation that already contains its income.']}
    report['report_sha256'] = canon(report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('decision', 'reported_ttm_eps', 'reported_ttm_pe', 'reference_market_cap_crore', 'report_sha256')}))
