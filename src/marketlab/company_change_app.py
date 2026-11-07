"""Loopback-only CC001 research desk. Reviews extracted facts, never investments."""
from __future__ import annotations

import argparse
import html
import json
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from marketlab.company_change import ChangeError
from marketlab.company_change_discovery import coverage
from marketlab.company_change_pipeline import economic_features
from marketlab.company_change_store import EvidenceStore, loads_unique


def render_desk(snapshot: dict, ledger: dict, queue: list, token: str = "", *, readonly=False) -> str:
    def esc(value):
        return html.escape(str(value), quote=True)
    counts = ledger['counts']
    chips = ''.join(f"<span>{esc(k.replace('_', ' '))} <b>{v}</b></span>" for k, v in sorted(counts.items()))
    cards = []
    for row in sorted(snapshot['active'], key=lambda r: (r['symbol'], r['selector']['period_end'], r['selector']['period_start'])):
        facts = ''.join(f"<tr><td>{esc(name)}</td><td>{esc(fact['value'])}</td><td>{esc(fact['unit'])}</td></tr>"
                        for name, fact in row['facts'].items())
        evidence = ''.join(f"<li><b>{esc(name)}</b><pre>{esc(f.get('quote', f.get('literal', '')))}</pre></li>"
                           for name, f in row['facts'].items())
        warnings = ''.join(f"<p role='alert'>{esc(message)}</p>" for message in row.get('warnings', []))
        form = "<p class='muted'>Read-only exported view.</p>" if readonly else (
            f"<form method='post' action='/review'><input type='hidden' name='csrf' value='{esc(token)}'>"
            f"<input type='hidden' name='extraction_id' value='{esc(row['extraction_id'])}'>"
            "<label>Reviewer <input name='reviewer' maxlength='120' required></label>"
            "<label>Evidence checked and rationale <textarea name='rationale' maxlength='4000' required></textarea></label>"
            "<button name='verdict' value='ACCEPT'>Accept extracted facts</button> "
            "<button name='verdict' value='REJECT'>Reject extraction</button></form>")
        cards.append(f"<article><div class='eyebrow'>{esc(row['review_status'])}</div><h2>{esc(row['symbol'])}</h2>"
            f"<p>{esc(row['selector']['scope'])}<br>{esc(row['selector']['period_start'])} to {esc(row['selector']['period_end'])}</p>"
            f"{warnings}<table><thead><tr><th>Fact</th><th>Value</th><th>Unit</th></tr></thead><tbody>{facts}</tbody></table>"
            f"<details><summary>Inspect evidence and calculations</summary><ul>{evidence}</ul>"
            f"<pre>{esc(json.dumps(row['bridge'], indent=2))}</pre>"
            f"<p>Source bytes <code>{esc(row['raw_sha256'])}</code></p>"
            f"<p>Captured facts known at {esc(row['known_at'])}</p>"
            f"<a href='{esc(row['url'])}' rel='noopener noreferrer'>Issuer source</a></details>{form}</article>")
    pending = ''.join(f"<tr><td>{esc(r['symbol'])}</td><td>{esc(r['state'])}</td><td>{esc(r['subject'])}</td><td>{esc(r['detail'])}</td></tr>"
                      for r in queue)
    return """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>MarketLab research desk</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f5f5;color:#17313d;font:15px system-ui}main{max-width:1280px;padding:32px 24px;margin:auto}
h1{font-size:38px;margin:10px 0}h2{margin:8px 0}.eyebrow{font-size:11px;letter-spacing:.12em}.banner{background:#17313d;color:white;border-radius:14px;padding:22px;margin:20px 0}
.chips{display:flex;flex-wrap:wrap;gap:8px}.chips span{border:1px solid #cddcdd;border-radius:24px;padding:9px 12px;font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:18px;margin:24px 0}
article{min-width:0;border:1px solid #d3e0e1;background:white;padding:22px;border-radius:14px}table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px}td,th{padding:8px 4px;text-align:left;border-bottom:1px solid #e0e9e9;overflow-wrap:anywhere}th:first-child{width:46%}
pre,code{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer;margin:18px 0;font-weight:600}form{border-top:1px solid #dce6e7;margin-top:18px;padding-top:12px}label{display:block;font-size:12px;margin:10px 0}
input,textarea{display:block;width:100%;border:1px solid #bacdd1;border-radius:6px;padding:9px;font:14px system-ui}button{background:#17313d;color:white;border:0;border-radius:6px;padding:10px;cursor:pointer;font-size:12px}.muted{font-size:13px;color:#5b7078}a{color:#006675}li{margin-bottom:12px}.queue{background:white;border-radius:12px;padding:16px;overflow-x:auto}
</style></head><body><main><div class='eyebrow'>MARKETLAB / EVIDENCE-FIRST RESEARCH</div><h1>Company-change research desk</h1>
<div class='banner'><b>Review facts, not stock tips.</b><p>Accepting an extraction records a review of the data. It does not approve a trade, a valuation or an investment recommendation.</p></div>
""" + f"<p>Latest discovery: {esc(ledger['last_discovery_at'] or 'not run')} · {ledger['total_discovered']} distinct disclosures retained</p>" \
        f"<div class='chips'>{chips}</div><p class='muted'>Coverage is the exchange response received, not a certified census. Unsupported documents remain in the denominator.</p>" \
        f"<div class='grid'>{''.join(cards) or '<article>No extracted records yet. The coverage ledger remains visible below.</article>'}</div>" \
        f"<h2>Unprocessed and failed disclosures</h2><div class='queue'><table><tr><th>Company</th><th>State</th><th>Subject</th><th>Detail</th></tr>{pending}</table></div>" \
        "<p class='muted'>This local workspace is not a public multi-user service. Original timestamps and source hashes are retained. Live capital is disabled.</p></main></body></html>"


def desk_data(store: EvidenceStore) -> tuple[dict, dict, list]:
    ledger = coverage(store)
    queue = []
    for row in store.db.execute("SELECT payload,state,detail FROM cc_discovery_queue WHERE state != 'EXTRACTED' ORDER BY first_seen,id LIMIT 200"):
        payload = loads_unique(row['payload'])
        queue.append({'symbol': payload['symbol'], 'subject': payload['subject'],
                      'state': row['state'], 'detail': row['detail']})
    return store.snapshot(), ledger, queue


def make_server(workspace: Path, *, port: int = 8765) -> ThreadingHTTPServer:
    if type(port) is not int or not 0 <= port <= 65535:
        raise ChangeError('invalid port')
    # Fix the binding to loopback. No remote bind option is provided.
    with EvidenceStore(workspace):
        pass
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return None

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def send_payload(self, code, body, mime='text/html; charset=utf-8'):
            raw = body.encode('utf-8') if isinstance(body, str) else body
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.valid_host():
                self.send_payload(403, 'Invalid host', 'text/plain')
                return
            path = urlsplit(self.path).path
            with EvidenceStore(workspace) as store:
                if path == '/':
                    self.send_payload(200, render_desk(*desk_data(store), token))
                elif path == '/features.json':
                    self.send_payload(200, json.dumps(economic_features(store.snapshot())), 'application/json')
                else:
                    self.send_payload(404, 'Not found', 'text/plain')

        def do_POST(self):
            if not self.valid_host() or urlsplit(self.path).path != '/review':
                self.send_payload(403, 'Forbidden', 'text/plain')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                    raise ChangeError('unsupported request')
                fields = parse_qs(self.rfile.read(length).decode(), strict_parsing=True)
                required = {'csrf', 'extraction_id', 'reviewer', 'verdict', 'rationale'}
                if set(fields) != required or any(len(v) != 1 for v in fields.values()):
                    raise ChangeError('invalid review form')
                values = {k: v[0] for k, v in fields.items()}
                if not secrets.compare_digest(values.pop('csrf'), token):
                    raise ChangeError('invalid review token')
                if not re.fullmatch(r'[0-9a-f]{64}', values['extraction_id']):
                    raise ChangeError('invalid extraction identity')
                with EvidenceStore(workspace) as store:
                    store.review(**values)
                self.send_response(303)
                self.send_header('Location', '/')
                self.send_header('Content-Length', '0')
                self.end_headers()
            except (ValueError, TypeError, KeyError) as exc:
                self.send_payload(400, str(exc), 'text/plain')

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--export', type=Path)
    args = parser.parse_args(argv)
    if args.export:
        with EvidenceStore(args.workspace) as store:
            page = render_desk(*desk_data(store), readonly=True)
        args.export.write_text(page, encoding='utf-8')
        print(args.export)
        return 0
    server = make_server(args.workspace, port=args.port)
    print(f'Research desk: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
