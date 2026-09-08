"""Follow exchange-listed alternate documents and restore integrated prior-year filings."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from acquire_h005_corpus import ALLOWED, dump, fetch_many, months, normalize, query
from marketlab.nse import NSEClient


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True)
    root=Path(p.parse_args().root)
    manifests=json.loads((root/'listing-manifest.json').read_text())
    prior=json.loads((root/'prior-listings.json').read_text())
    client=NSEClient(timeout=18,attempts=2)
    for start,end in months(date(2025,3,1),date(2025,9,30)):
        page,count=1,0
        while True:
            params={'type':'Integrated Filing- Financials','page':page,'size':200,
                    'from_date':start.strftime('%d-%m-%Y'),'to_date':end.strftime('%d-%m-%Y')}
            payload,meta=query(client,root,client.INTEGRATED_FILING_ENDPOINT,params,'prior-integrated-listing')
            manifests.append(meta)
            if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
                break
            rows=payload['data']
            for row in rows:
                item=normalize(row,meta['sha256'])
                if item:
                    prior.append(item)
            count+=len(rows)
            if not rows or count>=int(payload.get('totalCount') or len(rows)):
                break
            page+=1
            if page>100:
                raise ValueError('pagination runaway')
        print('integrated prior',start,count,flush=True)
    alternate={}
    for meta in manifests:
        if meta['status']!='OK' or 'listing' not in meta['kind']:
            continue
        payload=json.loads((root/meta['raw_path']).read_text())
        rows=payload.get('data',[]) if isinstance(payload,dict) else payload
        for row in rows:
            native,html=str(row.get('xbrl') or ''),str(row.get('ixbrl') or '')
            if native and urlparse(html).hostname in ALLOWED and html.lower().endswith('.html'):
                alternate[native]={'url':html,'listing_source_sha256':meta['sha256']}
    previous=defaultdict(list)
    for row in prior:
        previous[(row['symbol'],row['quarter_end'],row['basis'])].append(row)
    candidates=json.loads((root/'candidate-events.json').read_text())
    original_manifest=json.loads((root/'xbrl-manifest.json').read_text())
    known={r['url']:r for r in original_manifest}
    work={}
    for c in candidates:
        qdate=date.fromisoformat(c['quarter_end'])
        target=qdate.replace(year=qdate.year-1).isoformat()
        allowed=[r for r in previous[(c['symbol'],target,c['current']['basis'])] if r['published']<c['first_publication']]
        c['prior']=max(allowed,key=lambda r:(r['published'],r['url'])) if allowed else None
        for kind in ('current','prior'):
            record=c.get(kind)
            if not record:
                continue
            native=record['url']
            if native in known and known[native]['status']=='OK':
                record['content_url']=native
            elif native in alternate:
                record['content_url']=alternate[native]['url']
                record['alternate_listing_source_sha256']=alternate[native]['listing_source_sha256']
                work[record['content_url']]='exchange-listed-ixbrl'
            elif native not in known:
                record['content_url']=native
                work[native]='prior-xbrl'
            else:
                record['content_url']=native
    dump(root/'candidate-events-v2.json',candidates)
    dump(root/'listing-manifest-v2.json',manifests)
    dump(root/'prior-listings-v2.json',prior)
    new_manifest=fetch_many(root,sorted(work.items()),'alternate')
    dump(root/'content-manifest-v2.json',original_manifest+new_manifest)
    summary={'status':'SOURCE_ENRICHMENT_NOT_VALIDATION','candidate_variant_rows':len(candidates),
             'candidates_missing_prior':sum(c['prior'] is None for c in candidates),
             'prior_missing_by_quarter':dict(Counter(c['quarter_end'] for c in candidates if c['variant']=='H005-B' and c['prior'] is None)),
             'alternate_requests':len(work),'alternate_status':dict(Counter(m['status'] for m in new_manifest)),
             'denied_native_requests_preserved':sum(m['status']=='HTTP_403' for m in original_manifest),
             'all_alternate_urls_obtained_from_exchange_listing':True,
             'holdout_returns_opened':False,'live_capital_allowed':False}
    dump(root/'enrichment-summary.json',summary)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    main()
