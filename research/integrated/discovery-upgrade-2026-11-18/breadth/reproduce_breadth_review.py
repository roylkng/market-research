#!/usr/bin/env python3
"""Current-price research routing from a pinned, UNREVIEWED financial export.

No frozen experiment or production priority rule is modified. This report is
not an alpha model. Corporate actions, financial semantics and sector labels
are not automatically cleared by a successful identity/price join.
"""
import argparse, collections, csv, hashlib, io, json, math, zipfile
from pathlib import Path

SNAPSHOT_COMMIT = 'bed62144e1c8f0407113ecd19442a7a4c13c5aa6'
FIN_HASH = 'a3ad549f445e88f7da3afe1cd614e1b68322a42b4b8ca8140a6d75281a6c2929'
PRICE_HASH = '9b434afe659efc880b74ff68f9643038e5876d23e6abf5046a620e044f1a725c'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--financial',type=Path,required=True)
    p.add_argument('--prices',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    fb,pb=a.financial.read_bytes(),a.prices.read_bytes()
    assert hashlib.sha256(fb).hexdigest()==FIN_HASH
    assert hashlib.sha256(pb).hexdigest()==PRICE_HASH
    financial=json.loads(fb)
    with zipfile.ZipFile(io.BytesIO(pb)) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        assert len(names)==1
        prices=list(csv.DictReader(io.StringIO(z.read(names[0]).decode('utf-8-sig'))))
    assert all(r['TradDt']=='2026-11-18' for r in prices)
    price_map={}
    for r in prices:
        if r['SctySrs']=='EQ' and r['FinInstrmTp']=='STK':
            key=(r['TckrSymb'],r['ISIN'])
            assert key not in price_map
            price_map[key]=r
    preferred={}
    for c in financial['cards']:
        k=c['symbol']
        if k not in preferred or c['scope']=='CONSOLIDATED':
            preferred[k]=c
    def value(f,k):
        obj=f.get(k)
        return obj.get('value') if isinstance(obj,dict) else None
    rows=[]
    for symbol,c in sorted(preferred.items()):
        x=c['analysis']; f=x['cash_period_facts']; r=price_map.get((symbol,c['isin']))
        close=float(r['ClsPric']) if r else None
        eps=value(f,'diluted_eps'); lease=value(f,'lease_payments'); interest=value(f,'financing_interest_paid')
        cfo=x.get('cfo_crore'); capex=x.get('specified_capex_crore')
        residual=cfo-capex-lease-interest if all(v is not None for v in [cfo,capex,lease,interest]) else None
        half=(x['period_start'],x['period_end'])==('2026-04-01','2026-09-30')
        ratio=close/(2*eps) if close is not None and eps is not None and eps>0 and half else None
        if not r: triage='PRICE_IDENTITY_UNRESOLVED'
        elif 'NBFC' in c['source_url']: triage='SECTOR_SPECIFIC_LENS'
        elif x['disposition']=='RECONCILE_SOURCE_FIRST': triage='RECONCILE_SOURCE_FIRST'
        elif not half: triage='PERIOD_NOT_COMPARABLE'
        elif eps is None or eps<=0: triage='EARNINGS_BASIS_UNRESOLVED'
        elif residual is None: triage='CASH_COMPONENT_INCOMPLETE'
        elif residual<=0: triage='CASH_AFTER_SELECTED_USES_NONPOSITIVE'
        elif ratio>18: triage='ABOVE_ROUTING_MULTIPLE'
        else: triage='ORIGINAL_REVIEW_QUEUE'
        rows.append({'symbol':symbol,'isin':c['isin'],'scope':c['scope'],
          'original_status':x['disposition'],'financial_fact_review':c['financial_fact_review'],
          'price_date':'2026-11-18','close':close,'turnover_cr':float(r['TtlTrfVal'])/1e7 if r else None,
          'h1_eps':eps if half else None,'reported_period_eps':eps,'reported_period_pat_cr':x.get('group_pat_crore'),
          'reported_period_cfo_cr':cfo,'reported_period_capex_cr':capex,
          'lease_payment_cr':lease,'financing_interest_cr':interest,
          'cash_after_selected_uses_cr':residual,'net_borrowings_ex_leases_and_ex_investments_cr':x.get('net_borrowings_excluding_leases_crore'),
          'source_url':c['source_url'],'source_hash_imported_not_reverified_here':c['raw_sha256'],
          'cash_period_start':x['period_start'],'cash_period_end':x['period_end'],
          'price_to_doubled_h1_eps':ratio,'triage':triage})
    result={'classification':'UNVALIDATED_RESEARCH_ROUTING_NOT_ALPHA',
      'financial_snapshot_as_of':'2026-11-08T19:12:26.689261+00:00',
      'financial_snapshot_commit':SNAPSHOT_COMMIT,'financial_export_sha256_verified':FIN_HASH,
      'price_date':'2026-11-18','official_price_zip_sha256_verified':PRICE_HASH,
      'original_market_rows':len(prices),'market_STK_EQ_identities':len(price_map),
      'issuer_count':len(rows),'current_price_joined':sum(r['close'] is not None for r in rows),
      'six_month_period_count':sum(r['cash_period_start']=='2026-04-01' and r['cash_period_end']=='2026-09-30' for r in rows),
      'counts':dict(collections.Counter(r['triage'] for r in rows)),
      'rule':'Prefer consolidated, exact symbol/ISIN/EQ. Separate NBFC templates and source reconciliation failures. Require comparable six-month EPS, positive cash after specified capex/leases/financing interest, price <=18x doubled H1 EPS solely for research attention. No liquidity exclusion.',
      'limitations':['This is 196 retained issuers, not all 2756 quoted EQ names or a full NSE/BSE discovery census.',
        'All imported financial facts remain UNREVIEWED. Successful source hashing and arithmetic do not establish correct financial tags.',
        'The 18x rule was chosen for current attention routing, not preregistered or validated for expected returns.',
        'Doubled H1 EPS is not normalized annual earnings. Period/share-basis/corporate-action and sector checks remain necessary.',
        'Current prices do not make the 8 November financial/event snapshot current.',
        'Primary-review overrides for Cosmo and Sandesh are maintained separately. Do not reuse the raw cash figures for valuation.'],
      'rows':rows}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['issuer_count','current_price_joined','six_month_period_count','counts']},indent=2))
if __name__=='__main__':main()
