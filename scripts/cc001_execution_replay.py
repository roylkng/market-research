"""Read-only development replay of four previously inspected original filings.

Exact originals and retained exchange rows must match. The model is not called.
These are explicitly seen fixtures, not an independent accuracy experiment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_news import analyze_attachment, recipe, triage
from marketlab.company_change_news_review import admit
from marketlab.company_change_pipeline import fetch_original
from marketlab.company_change_store import EvidenceStore, loads_unique


def replay(workspace: Path, package: Path) -> dict:
    reviews = loads_unique(package.read_bytes())
    with EvidenceStore(workspace) as store:
        candidates = triage(store, store.clock())
        for review in reviews:
            source = review['source']
            matches = [r for r in candidates if all(r['candidate'][k] == source[k] for k in ('symbol','isin','url'))]
            if not matches:
                raise ChangeError('Development source lacks retained exchange row')
            routed = max(matches, key=lambda r:r['candidate']['published_at'])
            raw, final_url = fetch_original(source['url'], {'nsearchives.nseindia.com','archives.nseindia.com'})
            capture = store.capture(raw, {'url':source['url'],'final_url':final_url,
                'origin':'HTTP_RESPONSE_BYTES','lane':'CC001-P010-DEVELOPMENT-REPLAY'})
            reading = analyze_attachment(raw, routed, store.clock())
            if any(reading[k] != source[k] for k in source):
                raise ChangeError('Previously inspected development original/text has changed')
            reading.update(capture_id=capture['id'],recipe_sha256=recipe())
            reading['reading_sha256'] = canonical_hash(reading)
            with store.transaction():
                store.db.execute('INSERT OR IGNORE INTO cc_news_readings VALUES (?,?,?,?,?)',
                    (reading['reading_sha256'],reading['candidate_id'],recipe(),reading['known_at'],json.dumps(reading)))
        admitted = admit(store,reviews,'assistant-source-review-seen-development')
    return {'originals_read':len(reviews),'assisted_reviews':len(admitted),
            'independent_accuracy_evaluation':False,'model_called':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--package',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(replay(args.workspace,args.package)))
