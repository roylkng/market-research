"""Dated, source-pinned KRSNAA underwriting. Scenarios are assumptions, not forecasts.

This case reads retained originals only. It never writes production research,
accepts model facts, places orders or turns a historical close into a paper fill.
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
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

D = Decimal
CRORE = D(10_000_000)
X = '{http://www.xbrl.org/2003/instance}'
IDENTITY = {'symbol': 'KRSNAA', 'isin': 'INE08LI01020', 'scope': 'CONSOLIDATED'}
PINS = {
    'annual_fy26': 'dd45961fd84c1e74fc7a970f99e6dad7a5905b0e54e905213031790c8610a8f8',
    'h1fy27_results': '6733fffe826e7fbaa17ac12ba568704e69639f73340e3cb844945a6b1dd8007b',
    'h1fy27_presentation': '8bfdc8ee32081dec82e4c0471923c84b2f70054300bb31c46f112e42b6d4cba4',
    'h1fy27_transcript': '7aa67d42e6664bc926ebe1a059d24fa9977ab5e94caa47caa5da5a0e9bcb6487',
    'h1fy27_xml': '6390b2d760447563ce52711231c5d4053d8fbe9e5040af4f50a3c9c894f3d2ed',
    'h1fy26_xml': '1f2d88781c8c18f9fb24f5d2cf777b7325962d20d44eaaaab8aab75bf7c0532f',
    'fy26_xml': '23cd273250f4fdf5e5ca8f507758e2bf093bc4c6e607b39ffe54359605b6ae96',
    'fy25_xml': '5c5a3b9458ecce50a6deefa78c67a5becf0f7e54959546fc611abc1acdee0383',
    'q1fy27_xml': 'a63e594405a63d9ebfeb0dd26714872cfe3a39c2d1320b0abb351c2c2717dacf',
    'delhi_project': '73c0d6461e65624b2b84fbc27433fe16a005f06fe22198cdd2990bf019b12af6',
    'tax_appeal_20260909': '97937bdc018d72f971f2b9427bc82af08f95fc8270af31c759401c9315e983c1',
    'discovered_01': '6fdc87fe8b386e1c34f92c31aeae876ac58764725a707dd3f9324417a0df7b44',
    'discovered_02': '994103a9bec0ea6d2d5623ab3e28040018eec303b9fcef47ba1b7add113addd5',
    'discovered_03': '776efd2c1769d71b5bf413d34c57570819c03e8e2880edf2beadeb6cc5ffa64f',
}
TAGS = {
    'revenue': 'RevenueFromOperations', 'other_income': 'OtherIncome',
    'pbt_before_associate': 'ProfitBeforeTax', 'owner_pat': 'ProfitOrLossAttributableToOwnersOfParent',
    'group_pat': 'ProfitLossForPeriod', 'minority_pat': 'ProfitOrLossAttributableToNonControllingInterests',
    'finance_cost': 'FinanceCosts', 'depreciation': 'DepreciationDepletionAndAmortisationExpense',
    'tax': 'TaxExpense', 'associate_profit': 'ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod',
}
CASH_TAGS = {
    'cfo': 'CashFlowsFromUsedInOperatingActivities',
    'cash_generated_before_tax': 'CashFlowsFromUsedInOperations',
    'cash_taxes': 'IncomeTaxesPaidRefundClassifiedAsOperatingActivities',
    'ppe_purchases': 'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities',
    'ppe_sales': 'ProceedsFromSalesOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities',
    # The original cash statement identifies this taxonomy slot as bank-deposit liquidation.
    'deposit_liquidation': 'CashReceiptsFromRepaymentOfAdvancesAndLoansMadeToOtherPartiesClassifiedAsInvestingActivities',
    'interest_received': 'InterestReceivedClassifiedAsInvestingActivities',
    'net_investing': 'CashFlowsFromUsedInInvestingActivities',
    'warrant_receipts': 'ProceedsFromIssuingOtherEquityInstruments',
    'short_borrowings_net': 'ProceedsFromBorrowingsClassifiedAsFinancingActivities',
    'long_borrowing_repayment_net': 'RepaymentsOfBorrowingsClassifiedAsFinancingActivities',
    'lease_payments_as_presented': 'PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities',
    'interest_paid': 'InterestPaidClassifiedAsFinancingActivities',
    'net_financing': 'CashFlowsFromUsedInFinancingActivities',
    'cash_change': 'IncreaseDecreaseInCashAndCashEquivalents',
    'receivables_movement': 'AdjustmentsForDecreaseIncreaseInTradeReceivablesCurrent',
    'payables_movement': 'AdjustmentsForIncreaseDecreaseInTradePayablesCurrent',
}
WC_TAGS = [
    'AdjustmentsForDecreaseIncreaseInInventories', 'AdjustmentsForDecreaseIncreaseInTradeReceivablesCurrent',
    'AdjustmentsForDecreaseIncreaseInTradeReceivablesNoncurrent', 'AdjustmentsForDecreaseIncreaseInOtherCurrentAssets',
    'AdjustmentsForDecreaseIncreaseInOtherNoncurrentAssets', 'AdjustmentsForOtherFinancialAssetsNoncurrent',
    'AdjustmentsForOtherFinancialAssetsCurrent', 'AdjustmentsForIncreaseDecreaseInTradePayablesCurrent',
    'AdjustmentsForIncreaseDecreaseInTradePayablesNoncurrent', 'AdjustmentsForIncreaseDecreaseInOtherCurrentLiabilities',
    'AdjustmentsForIncreaseDecreaseInOtherNoncurrentLiabilities', 'AdjustmentsForProvisionsCurrent',
    'AdjustmentsForProvisionsNoncurrent', 'AdjustmentsForOtherFinancialLiabilitiesCurrent',
    'AdjustmentsForOtherFinancialLiabilitiesNoncurrent',
]


def canon(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise TypeError('numeric input required')
    try:
        out = D(str(value))
    except InvalidOperation as exc:
        raise ValueError('invalid number') from exc
    if not out.is_finite():
        raise ValueError('nonfinite input')
    return out


def valuation(eps, growth, multiple, price, years=5, hurdle='.15', annual_dividend=0):
    eps, growth, multiple, price, hurdle, dividend = map(number, (eps, growth, multiple, price, hurdle, annual_dividend))
    if (eps <= 0 or price <= 0 or not D('-.99') < growth <= 1 or not 1 <= multiple <= 100
            or type(years) is not int or not 1 <= years <= 10 or not 0 <= hurdle <= 1 or not 0 <= dividend <= eps):
        raise ValueError('valuation assumption outside bounds')
    terminal = eps * (1 + growth) ** years * multiple
    pv_dividends = sum(dividend / (1 + hurdle) ** t for t in range(1, years + 1))
    return {'starting_eps': float(eps), 'annual_eps_growth': float(growth), 'exit_pe': float(multiple),
            'years': years, 'hurdle': float(hurdle), 'terminal_price': float(terminal),
            'price_cagr': math.pow(float(terminal / price), 1 / years) - 1,
            'entry_price_for_hurdle_ex_dividends': float(terminal / (1 + hurdle) ** years),
            'entry_price_for_hurdle_with_flat_dividend': float(terminal / (1 + hurdle) ** years + pv_dividends),
            'assumed_flat_annual_dividend': float(dividend),
            'required_growth_at_reference': math.pow(float(price / (eps * multiple)), 1 / years) * float(1 + hurdle) - 1,
            'required_starting_eps_at_reference': float(price / multiple * ((1 + hurdle) / (1 + growth)) ** years),
            'terminal_price_change': float(terminal / price - 1), 'probability_assigned': False,
            'taxes_costs_slippage_included': False}


def warrant_math(count, issue_price, upfront, already_reported, tolerance='.001'):
    count, price, paid, reported, tol = map(number, (count, issue_price, upfront, already_reported, tolerance))
    if count != int(count) or count <= 0 or price <= 0 or paid < 0 or reported < 0 or tol < 0:
        raise ValueError('invalid warrant inputs')
    total = count * price / CRORE
    if abs(paid - total / 4) > tol or abs(paid - reported) > tol:
        raise ValueError('warrant cash does not reconcile to original statement rounding')
    return {'potential_shares': int(count), 'issue_price': float(price), 'total_if_exercised_crore': float(total),
            'upfront_received_crore': float(paid), 'already_in_h1_statement_crore': float(reported),
            'additional_upfront_cash_to_add': 0, 'conditional_balance_crore': float(total - paid),
            'remaining_cash_per_warrant': float((total - paid) * CRORE / count),
            'balance_is_received_or_guaranteed': False}


def root_xml(raw):
    if len(raw) > 2_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unsupported XML')
    root = ElementTree.fromstring(raw)
    for key, expected in [('Symbol', 'KRSNAA'), ('ISIN', 'INE08LI01020')]:
        if {n.text for n in root if n.tag.rsplit('}', 1)[-1] == key} != {expected}:
            raise ValueError('issuer identity mismatch')
    return root


def node(root, tag, context):
    values = [n for n in root if n.tag.rsplit('}', 1)[-1] == tag and n.get('contextRef') == context]
    if len(values) != 1 or values[0].text is None:
        raise ValueError(f'one exact fact required: {context}/{tag}')
    return values[0]


def fact(root, tag, context, audit, source):
    n = node(root, tag, context)
    if n.get('unitRef') != 'INR':
        raise ValueError('not an INR monetary fact')
    value = number(n.text) / CRORE
    audit.append({'source': source, 'tag': tag, 'context': context, 'raw_inr': n.text,
                  'crore': str(value), 'decimals': n.get('decimals')})
    return value


def period(root, context, start, end, audit, source):
    c = root.find(f"{X}context[@id='{context}']")
    if (c is None or c.findtext(f'{X}period/{X}startDate') != start
            or c.findtext(f'{X}period/{X}endDate') != end or c.find(f'{X}scenario') is not None
            or node(root, 'NatureOfReportStandaloneConsolidated', context).text != 'Consolidated'):
        raise ValueError('wrong reporting period or scope')
    out = {key: fact(root, tag, context, audit, source) for key, tag in TAGS.items()}
    if abs(out['group_pat'] - out['owner_pat'] - out['minority_pat']) > D('.002'):
        raise ValueError('parent/minority attribution mismatch')
    if abs(out['pbt_before_associate'] - out['tax'] + out['associate_profit'] - out['group_pat']) > D('.002'):
        raise ValueError('profit and tax bridge mismatch')
    out['operating_ebitda_after_csr_esop'] = out['pbt_before_associate'] - out['other_income'] + out['finance_cost'] + out['depreciation']
    return out


def verify_price(workspace, quote):
    if quote.get('identity') != IDENTITY or quote.get('session_date') != '2026-11-09':
        raise ValueError('dated case requires the exact 9 November reference')
    sha = quote['raw_sha256']
    if not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('invalid price digest')
    raw = (workspace / 'blobs' / sha[:2] / sha).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('price archive hash mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.namelist() != ['BhavCopy_NSE_CM_0_0_0_20261109_F_0000.csv']:
            raise ValueError('wrong price archive member')
        csv_raw = archive.read(archive.namelist()[0])
    if hashlib.sha256(csv_raw).hexdigest() != quote['csv_sha256']:
        raise ValueError('price CSV hash mismatch')
    matches = [r for r in csv.DictReader(io.StringIO(csv_raw.decode('utf-8-sig')))
               if r['TckrSymb'] == 'KRSNAA' and r['SctySrs'] == 'EQ']
    if len(matches) != 1 or any(matches[0][k] != v for k, v in {
            'ISIN': IDENTITY['isin'], 'Sgmt': 'CM', 'Src': 'NSE', 'FinInstrmTp': 'STK', 'TradDt': '2026-11-09'}.items()):
        raise ValueError('exact security/market/session row missing')
    if number(matches[0]['ClsPric']) != number(quote['price']) or number(matches[0]['TtlTradgVol']) <= 0:
        raise ValueError('price or volume mismatch')
    return matches[0]


def build(workspace):
    manifest = json.loads((workspace / 'capture-manifest.json').read_text())
    if canon({k: v for k, v in manifest.items() if k != 'report_sha256'}) != manifest.get('report_sha256'):
        raise ValueError('capture manifest integrity failure')
    completed = datetime.fromisoformat(manifest['observed_at'])
    if completed.tzinfo is None:
        raise ValueError('capture clock must include timezone')
    for source in manifest['sources']:
        observed = datetime.fromisoformat(source['observed_at'])
        if observed.tzinfo is None or observed > completed:
            raise ValueError('source observed after capture completion')
    if datetime.fromisoformat(manifest['quote']['observed_at']) > completed:
        raise ValueError('price observed after capture completion')
    by_name = {s['name']: s for s in manifest['sources']}
    if len(by_name) != len(manifest['sources']):
        raise ValueError('duplicate original source identity')
    raw = {}
    for name, digest in PINS.items():
        source = by_name[name]
        path = (workspace / source['path']).resolve()
        if not path.is_relative_to(workspace.resolve()) or path.is_symlink():
            raise ValueError('unsafe original source path')
        content = path.read_bytes()
        if source['sha256'] != digest or hashlib.sha256(content).hexdigest() != digest:
            raise ValueError('pinned original changed: ' + name)
        raw[name] = content
    pdf = {}
    evidence = []
    def page(name, number_):
        if name not in pdf:
            pdf[name] = PdfReader(io.BytesIO(raw[name]))
        return pdf[name].pages[number_ - 1].extract_text() or ''
    def reviewed(name, page_no, literal, label, value):
        text = page(name, page_no)
        if literal not in text:
            raise ValueError('reviewed original passage unavailable: ' + label)
        start = text.index(literal)
        evidence.append({'source': name, 'pdf_page': page_no, 'label': label, 'value': value,
                         'quote': literal, 'start': start, 'end': start + len(literal),
                         'method': 'ASSISTED_TRANSCRIPTION_FROM_RENDERED_ORIGINAL_NOT_INDEPENDENT_LABEL'})
        return number(value)
    gain = reviewed('annual_fy26', 217, '222.41 million', 'Apulki remeasurement gain after deferred tax, INR million', '222.41') / 10
    shares = reviewed('annual_fy26', 221, '3,24,38,672 Equity Shares', 'Issued March shares, count', '32438672')
    options = sum(reviewed('annual_fy26', 233, q, 'Outstanding ESOP reference count ' + q, value)
                  for q, value in [('6,24,135', '624135'), ('1,55,956', '155956'), ('2,25,516', '225516')])
    warrants = reviewed('discovered_02', 1, '16,21,000', 'October warrants, count', '1621000')
    issue_price = reviewed('discovered_02', 1, '566/', 'Warrant total issue price, INR', '566')
    upfront = reviewed('discovered_02', 1, '22,93,71,500/', 'Warrant upfront INR', '229371500') / CRORE
    full_shares = shares + options + warrants
    annual_restricted = reviewed('annual_fy26', 220, '666.81 mn', 'March pledged deposits, INR million', '666.81') / 10
    adb_face = reviewed('annual_fy26', 223, '4,30,00,00,000', 'ADB debenture face INR', '4300000000') / CRORE
    reviewed('annual_fy26', 223, '7.79% per annum', 'ADB coupon fraction', '.0779')
    reviewed('annual_fy26', 223, 'thirteen (13) equal instalments', 'Scheduled principal instalments', '13')
    reviewed('delhi_project', 2, 'extendable by up to five years', 'Delhi optional extension, years', '5')
    reviewed('delhi_project', 2, 'concession period of ten years', 'Delhi base concession, years', '10')
    reviewed('discovered_01', 1, 'up to ₹120 crore', 'Approved equipment sale ceiling, INR crore', '120')
    roots = {name: root_xml(content) for name, content in raw.items() if name.endswith('_xml')}
    audit, periods = [], {}
    for label, source, context, start, end in [
        ('FY25', 'fy25_xml', 'FourD', '2024-04-01', '2025-03-31'),
        ('FY26', 'fy26_xml', 'FourD', '2025-04-01', '2026-03-31'),
        ('H1FY26', 'h1fy26_xml', 'FourD', '2025-04-01', '2025-09-30'),
        ('H1FY27', 'h1fy27_xml', 'FourD', '2026-04-01', '2026-09-30'),
        ('Q2FY27', 'h1fy27_xml', 'OneD', '2026-07-01', '2026-09-30'),
    ]:
        periods[label] = period(roots[source], context, start, end, audit, source)
    ttm = {k: periods['FY26'][k] + periods['H1FY27'][k] - periods['H1FY26'][k] for k in TAGS}
    ttm['owner_pat_less_identified_gain'] = ttm['owner_pat'] - gain
    current = roots['h1fy27_xml']
    cash = {key: fact(current, tag, 'FourD', audit, 'h1fy27_xml') for key, tag in CASH_TAGS.items()}
    cash['net_working_capital_movement'] = sum(fact(current, tag, 'FourD', audit, 'h1fy27_xml') for tag in WC_TAGS)
    cash['operating_cash_before_wc_and_tax'] = cash['cash_generated_before_tax'] - cash['net_working_capital_movement']
    cash['cfo_less_gross_purchases'] = cash['cfo'] - cash['ppe_purchases']
    cash['cfo_without_payables_change_sensitivity'] = cash['cfo'] - cash['payables_movement']
    for left, right in [
        (cash['net_investing'], -cash['ppe_purchases'] + cash['ppe_sales'] + cash['deposit_liquidation'] + cash['interest_received']),
        (cash['net_financing'], cash['warrant_receipts'] + cash['short_borrowings_net'] - cash['long_borrowing_repayment_net'] - cash['lease_payments_as_presented'] - cash['interest_paid']),
        (cash['cash_change'], cash['cfo'] + cash['net_investing'] + cash['net_financing']),
        (cash['cfo'], cash['cash_generated_before_tax'] - cash['cash_taxes']),
    ]:
        if abs(left - right) > D('.002'):
            raise ValueError('cash flow bridge failed')
    for key in ('cfo', 'ppe_purchases'):
        annual = fact(roots['fy26_xml'], CASH_TAGS[key], 'FourD', audit, 'fy26_xml')
        prior = fact(roots['h1fy26_xml'], CASH_TAGS[key], 'FourD', audit, 'h1fy26_xml')
        cash['ttm_' + key] = annual + cash[key] - prior
    cash['ttm_cfo_less_gross_purchases'] = cash['ttm_cfo'] - cash['ttm_ppe_purchases']
    balance = {}
    for label, source in [('March', 'fy26_xml'), ('September', 'h1fy27_xml')]:
        r = roots[source]
        balance[label] = {k: fact(r, tag, 'OneI', audit, source) for k, tag in {
            'receivables': 'TradeReceivablesCurrent', 'payables': 'TradePayablesCurrent',
            'cash': 'CashAndCashEquivalents', 'other_current_bank_balances': 'BankBalanceOtherThanCashAndCashEquivalents',
            'xml_borrowings_noncurrent_including_leases': 'BorrowingsNoncurrent',
            'xml_borrowings_current_including_leases': 'BorrowingsCurrent'}.items()}
    for label, values in {'March': ('4371.44', '533.61', '311.49', '126.63'),
                          'September': ('4027.95', '1565.46', '245.77', '125.14')}.items():
        # Source-pinned, visually reviewed PDF row values. The XML combines debt and leases.
        for value in values:
            reviewed('h1fy27_presentation', 11, f'{number(value):,.2f}',
                     label + ' balance-sheet row, INR million', value)
        b = balance[label]
        b['borrowing_ex_leases'] = (number(values[0]) + number(values[1])) / 10
        b['leases'] = (number(values[2]) + number(values[3])) / 10
        b['borrowing_and_leases'] = b['xml_borrowings_noncurrent_including_leases'] + b['xml_borrowings_current_including_leases']
        if abs(b['borrowing_ex_leases'] + b['leases'] - b['borrowing_and_leases']) > D('.003'):
            raise ValueError('PDF debt versus XML lease-inclusive total mismatch')
        b['cash_plus_current_deposits_not_free_cash'] = b['cash'] + b['other_current_bank_balances']
    warrant = warrant_math(warrants, issue_price, upfront, cash['warrant_receipts'])
    quote = manifest['quote']
    price_row = verify_price(workspace, quote)
    price = number(quote['price'])
    normal = ttm['owner_pat_less_identified_gain']
    option_cash = sum(D(n) * p for n, p in ((624135, 225), (155956, 350), (225516, 561))) / CRORE
    conditional_new_cash = option_cash + number(warrant['conditional_balance_crore'])
    assumed_interest_saving = conditional_new_cash * D('.08') * D('.75')
    earnings = {'reported_ttm_owner_pat_crore': float(ttm['owner_pat']),
        'identified_net_gain_removed_crore': float(gain), 'gain_removed_owner_pat_crore': float(normal),
        'reported_ttm_eps_reference': float(ttm['owner_pat'] * CRORE / shares),
        'gain_removed_eps_reference': float(normal * CRORE / shares),
        'gain_removed_eps_fully_exercised_sensitivity': float(normal * CRORE / full_shares),
        'reported_reference_pe': float(price / (ttm['owner_pat'] * CRORE / shares)),
        'gain_removed_reference_pe': float(price / (normal * CRORE / shares)),
        'gain_removed_full_exercise_pe': float(price / (normal * CRORE / full_shares)),
        'full_exercise_plus_hypothetical_debt_saving_eps': float((normal + assumed_interest_saving) * CRORE / full_shares),
        'fully_normalized_owner_earnings_verified': False}
    cases = [dict(name=name, **valuation(e, g, mult, price, annual_dividend=2))
             for name, e, g, mult in [('Stress', 18, '.05', 12), ('Conservative base', 22, '.15', 16),
                                      ('Stronger execution', 22, '.18', 18), ('Bull', 25, '.20', 20)]]
    report = {'case': 'KRSNAA-20261110', 'evidence_class': 'ASSISTED_UNDERWRITING_NOT_PROSPECTIVE_PAPER_ENTRY',
        'decision': 'WAIT_NO_FRESH_PURCHASE_AT_REFERENCE_PRICE', 'reference_date': '2026-11-09',
        'source_capture_completed_at': manifest['observed_at'], 'price': quote, 'price_row': price_row,
        'reference_shares': int(shares), 'reference_market_cap_crore': float(price * shares / CRORE),
        'dilution': {'audited_march_issued_shares': int(shares), 'audited_march_outstanding_esop_options': int(options),
                    'october_warrant_shares': int(warrants), 'fully_exercised_reference_count': int(full_shares),
                    'full_exercise_increase_fraction': float(full_shares / shares - 1),
                    'actual_current_diluted_denominator_certified': False,
                    'potential_option_cash_crore': float(option_cash),
                    'conditional_unreceived_warrant_and_option_cash_crore': float(conditional_new_cash),
                    'funding_offset_sensitivity': {'assumed_debt_cost': .08, 'assumed_tax_rate': .25,
                        'all_new_proceeds_assumed_used_to_reduce_debt': True,
                        'incremental_after_tax_saving_crore': float(assumed_interest_saving),
                        'status': 'HYPOTHETICAL_NOT_RECEIVED_OR_COMMITTED'}},
        'earnings': earnings, 'periods_crore': {k: {a: str(v) for a, v in p.items()} for k, p in periods.items()},
        'reported_ttm_crore': {k: str(v) for k, v in ttm.items()},
        'h1_cash_crore': {k: str(v) for k, v in cash.items()},
        'balance_crore': {k: {a: str(v) for a, v in p.items()} for k, p in balance.items()},
        'h1_yoy': {k: float(periods['H1FY27'][k] / periods['H1FY26'][k] - 1)
                   for k in ('revenue', 'owner_pat', 'finance_cost', 'operating_ebitda_after_csr_esop')},
        'h1_after_csr_esop_ebitda_margin': float(periods['H1FY27']['operating_ebitda_after_csr_esop'] / periods['H1FY27']['revenue']),
        'prior_h1_after_csr_esop_ebitda_margin': float(periods['H1FY26']['operating_ebitda_after_csr_esop'] / periods['H1FY26']['revenue']),
        'warrants': warrant, 'march_pledged_deposits_crore': float(annual_restricted),
        'adb': {'face_value_crore': float(adb_face), 'coupon_fraction': .0779, 'tenor_years': 7,
                'scheduled_equal_instalments': 13, 'principal_per_scheduled_instalment_crore': float(adb_face / 13),
                'interpretation': 'Amortizing facility, not a seven-year principal holiday. Actual current repayment status not inferred.'},
        'valuation_scenarios': cases, 'xml_fact_audit': audit, 'pdf_evidence': evidence,
        'sources': manifest['sources'], 'capture_errors': manifest['errors'], 'model_called': False,
        'live_capital_allowed': False, 'buy_approved': False,
        'limits': [
            'The WAIT is an assisted judgment, not a learned return forecast or sell instruction for an existing holding.',
            'Only the explicitly identified after-tax Apulki gain is removed. Other income, ordinary maintenance, future credit loss and funding remain material.',
            'The full-exercise denominator is a sensitivity using March options and October warrants, not a current diluted-EPS audit. Exercise proceeds are not free value. A separate 8%-debt-cost/25%-tax saving case illustrates a possible offset, not a forecast.',
            'Gross cash purchases include expansion and advances. The CFO gap is a financing requirement diagnostic, not verified maintenance free cash flow.',
            'Current cash and deposits exclude some noncurrent deposits and include restricted balances. No free-cash or fully reconciled net-debt claim is made.',
            'The half-year statement already includes the warrant upfront receipt, even though formal allotment followed in October. Exact receipt date is not established here. No cash is added twice.',
            'Future warrant exercise, up-to-120-crore equipment monetization and 200-crore Q3 collections are not assumed realized.',
            'Delhi has ten years from commercial operation plus an optional five-year extension, not fifteen guaranteed revenue years. Award value depends on actual test volumes.',
            'Exit multiples and EPS paths are business-risk sensitivities, not verified peer fair values. No probabilities are assigned.',
            'The tax appeal has multiple orders and rectification amounts. The stated 62.69-crore aggregate is not a reconciled maximum possible liability.',
            'No terminal-value cash bonus or separate Apulki valuation is added to the earnings scenarios. Dividends are a separate flat illustrative sensitivity.',
            'The 9 November close is a historical reference observed on 10 November, not an executable post-research fill.'],
        'reopen_conditions': [
            'Reported Q3 collections and ending receivables support management expectations without an offsetting overdue-payables buildup.',
            'New sites show repeatable utilization and post-financing earnings improvement, not only revenue growth.',
            'Debt service, vendor balances, restricted cash, asset-sale proceeds and any new lease obligations reconcile.',
            'An observed price or independently supported earnings case offers a downside-aware return margin after dilution and liquidity checks.']}
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
    print(json.dumps({'decision': result['decision'], 'earnings': result['earnings'], 'report_sha256': result['report_sha256']}))
