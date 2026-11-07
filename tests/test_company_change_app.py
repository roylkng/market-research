from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from urllib.parse import urlencode

import requests

from marketlab.company_change_app import desk_data, make_server, render_desk
from marketlab.company_change_pipeline import ingest
from marketlab.company_change_store import EvidenceStore

ROOT = Path(__file__).resolve().parents[1]


def populate(tmp_path):
    source = json.loads((ROOT / 'data/fixtures/company_change_v1.json').read_text())['sources'][0]
    (tmp_path / 'filing.txt').write_text(source['text'])
    spec = {k: source[k] for k in ('source_id', 'symbol', 'isin', 'kind', 'event_key', 'scope', 'period_start', 'period_end', 'url', 'rights')}
    spec.update(local_file='filing.txt', extractor='labels', format='text')
    workspace = tmp_path / 'workspace'
    with EvidenceStore(workspace) as store:
        result = ingest({'schema_version': 1, 'sources': [spec]}, store, base=tmp_path)
        assert not result['failures']
    return workspace, result['successes'][0]['extraction_id']


def test_readonly_export_is_escaped_and_has_no_forms(tmp_path):
    workspace, _ = populate(tmp_path)
    with EvidenceStore(workspace) as store:
        snapshot, ledger, queue = desk_data(store)
    snapshot['active'][0]['symbol'] = '<script>bad</script>'
    page = render_desk(snapshot, ledger, queue, readonly=True)
    assert '<script>' not in page
    assert '&lt;script&gt;' in page
    assert '<form' not in page
    assert 'Live capital is disabled' in page


def test_local_review_roundtrip_csrf_host_and_no_trade(tmp_path):
    workspace, extraction = populate(tmp_path)
    server = make_server(workspace, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = requests.Session()
    session.trust_env = False
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        page = session.get(url, timeout=3)
        assert page.status_code == 200
        assert 'UNREVIEWED' in page.text
        assert page.headers['X-Frame-Options'] == 'DENY'
        assert session.get(url, headers={'Host': 'evil.example'}, timeout=3).status_code == 403
        token = re.search("name='csrf' value='([^']+)'", page.text).group(1)
        form = {'csrf': 'wrong', 'extraction_id': extraction, 'reviewer': 'test analyst', 'verdict': 'ACCEPT', 'rationale': 'Checked synthetic source'}
        assert session.post(url + '/review', data=form, timeout=3).status_code == 400
        form['csrf'] = token
        assert session.post(url + '/review', data=form, allow_redirects=False, timeout=3).status_code == 303
        result = session.get(url + '/features.json', timeout=3).json()
        assert len(result['rows']) == 1
        assert result['live_capital_allowed'] is False
        form['verdict'] = 'BUY'
        assert session.post(url + '/review', data=form, timeout=3).status_code == 400
        body = urlencode({**form, 'verdict': 'ACCEPT'}) + '&csrf=second'
        assert session.post(url + '/review', data=body, headers={'Content-Type': 'application/x-www-form-urlencoded'}, timeout=3).status_code == 400
    finally:
        session.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
