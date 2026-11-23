#!/usr/bin/env python3
"""Build the self-contained market review from adjacent research and captured sources."""
import argparse
import base64
import csv
import hashlib
import html
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def bar_chart(rows, key, domain, suffix='%'):
    low, high = domain
    left, right, top, step = 184, 692, 34, 43
    def x(value):
        return left + (value-low)/(high-low)*(right-left)
    parts = [f'<svg viewBox="0 0 780 {len(rows)*step+65}" role="img" aria-label="Market comparison">']
    parts += [f'<line x1="{x(0)}" y1="12" x2="{x(0)}" y2="{len(rows)*step+17}" stroke="#a7b1be"/>']
    for i, row in enumerate(rows):
        value = float(row[key])
        y = top+i*step
        start, end = sorted([x(0), x(value)])
        color = '#197b67' if value >= 0 else '#c65a54'
        label = row['index'].replace('NIFTY ', 'Nifty ').replace('MIDCAP', 'Midcap').replace('SMALLCAP', 'Smallcap').replace('BANK', 'Bank').replace('METAL', 'Metal')
        parts += [f'<text x="0" y="{y+5}" fill="#25354b" font-size="16">{html.escape(label)}</text>',
                  f'<rect x="{start:.2f}" y="{y-12}" width="{max(end-start,1):.2f}" height="23" rx="3" fill="{color}"/>',
                  f'<text x="710" y="{y+5}" fill="{color}" font-size="16" font-weight="700">{value:+.2f}{suffix}</text>']
    parts += [f'<text x="{x(low):.2f}" y="{len(rows)*step+50}" font-size="13" fill="#667589">{low:g}{suffix}</text>',
              f'<text x="{x(high)-28:.2f}" y="{len(rows)*step+50}" font-size="13" fill="#667589">{high:g}{suffix}</text>', '</svg>']
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    data = json.loads((HERE/'snapshot.json').read_text())
    results = json.loads((HERE/'repricing/results.json').read_text())
    notes = subprocess.run(['pandoc', str(HERE/'README.md'), '-f', 'gfm', '-t', 'html'], capture_output=True, text=True, check=True).stdout
    rows = [v for v in data['indices'] if v['index'] != 'INDIA VIX']
    today = bar_chart(rows, 'percentChange', (-4, 2.5))
    month = bar_chart(rows, 'perChange30d', (-1, 18))
    qmap = {q['symbol']: q for q in data['quotes']['observations']}
    gates = {'CMSINFO':'Collections and recurring investment', 'RSYSTEMS':'Rs210-220 or stronger operating evidence', 'PIXTRANS':'Around Rs1,450 with the thesis intact', 'POWERGRID':'Around Rs220 with commissioning funded', 'MPSLTD':'Owner cash and acquisition returns'}
    names = {'CMSINFO':'CMS Info Systems','RSYSTEMS':'R Systems','PIXTRANS':'PIX Transmissions','POWERGRID':'POWERGRID','MPSLTD':'MPS'}
    qrows = ''
    for sym in ['CMSINFO','RSYSTEMS','PIXTRANS','POWERGRID','MPSLTD']:
        q = qmap[sym]
        direction = 'pos' if q['change_pct_reported'] >= 0 else 'neg'
        gap = q['decline_to_conditional_upper_pct']
        gap_text = f'{gap:.1f}% below quote' if gap is not None else 'Evidence condition'
        qrows += f'<tr><td><a href="{q["source_url"]}">{names[sym]}</a></td><td class="number">₹{q["price_inr"]:,.2f}</td><td class="number {direction}">{q["change_pct_reported"]:+.2f}%</td><td>{q["quote_datetime_ist"][11:16]}</td><td>{gates[sym].replace("Rs", "₹")}<small>{gap_text}</small></td></tr>'
    valuation_rows = ''
    for name in ['NIFTY IT','NIFTY 50','NIFTY 500','NIFTY MIDCAP 150','NIFTY SMALLCAP 250','NIFTY BANK']:
        row = next(v for v in rows if v['index']==name)
        p = float(row['prior_close_valuation']['P/E'])
        dy = float(row['prior_close_valuation']['Div Yield'])
        valuation_rows += f'<tr><td>{name.title().replace("It", "IT")}</td><td><div class="pebar"><span style="width:{p/35*100:.2f}%"></span></div></td><td class="number"><b>{p:.2f}×</b></td><td class="number">{dy:.2f}%</td></tr>'
    rmap = {r['id']:r for r in results['results']}
    sensitivity = [
        ('CMS', '10.8-12.5%', f'{rmap["cms_capex_200_grows"]["repriced_annualized_return"]*100:.1f}-{rmap["cms_working"]["repriced_annualized_return"]*100:.1f}%'),
        ('R Systems', '9.6-10.6%', f'{rmap["rsystems_base_year5_cash"]["repriced_annualized_return"]*100:.1f}-{rmap["rsystems_base_year6_cash"]["repriced_annualized_return"]*100:.1f}%'),
        ('PIX, base', '7.8%', f'{rmap["pixtrans_base"]["repriced_annualized_return"]*100:.1f}%'),
        ('POWERGRID, base', '6.2%', f'{rmap["powergrid_base"]["repriced_annualized_return"]*100:.1f}%')]
    srows = ''.join(f'<tr><td>{n}</td><td class="number">{a}</td><td class="number"><b>{b}</b></td></tr>' for n,a,b in sensitivity)
    files = [
        ('NSE intraday index snapshot','macro/nse_all_indices_20261123.json','application/json'),
        ('NSE 20 November valuation file','macro/nse_indices_20261120.csv','text/csv'),
        ('APL acquisition presentation','apl_event/apl_presentation.pdf','application/pdf'),
        ('APL open-offer announcement','apl_event/apl_open_offer.pdf','application/pdf'),
        ('Tata Steel transaction release','apl_event/tata_release.pdf','application/pdf'),
        ('Newgen CreditAccess contract','other_sources/newgen_creditaccess.pdf','application/pdf'),
        ('NSE 2026 trading holidays','other_sources/nse_holidays_2026.pdf','application/pdf')]
    evidence = ''
    manifest = []
    for title, rel, mime in files:
        p = args.sources/rel
        raw = p.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        encoded = base64.b64encode(raw).decode()
        evidence += f'<li><a download="{p.name}" href="data:{mime};base64,{encoded}">{title}</a><small>{len(raw):,} bytes · SHA256 {sha}</small></li>'
        manifest.append({'title':title,'filename':p.name,'bytes':len(raw),'sha256':sha})
    research_files = ['README.md','snapshot.json','source_receipts.json','repricing/inputs.json','repricing/results.json','repricing/calculate.py','build_report.py']
    for rel in research_files:
        raw = (HERE/rel).read_bytes()
        mime = 'application/json' if rel.endswith('.json') else 'text/plain'
        encoded = base64.b64encode(raw).decode()
        evidence += f'<li><a download="{rel.replace("/", "_")}" href="data:{mime};base64,{encoded}">{html.escape(rel)}</a></li>'
    doc = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Indian Market Check | 23 November 2026</title><style>
:root{--ink:#192b43;--muted:#627087;--line:#dce3eb;--green:#197b67;--red:#c65a54;--paper:#f4f6f8;--navy:#152f50}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1180px;margin:0 auto;padding:36px 26px 64px}header{background:var(--navy);color:white;padding:38px;border-radius:18px}.eyebrow{font-size:12px;letter-spacing:2px;text-transform:uppercase;font-weight:700;color:#b5d9d1}h1{font-size:clamp(32px,4.6vw,52px);line-height:1.1;letter-spacing:-1.5px;margin:14px 0 18px;max-width:850px}header p{max-width:820px;color:#d8e4ef;margin:10px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}.card,section{background:white;border:1px solid var(--line);border-radius:14px;padding:24px}.card .value{font-size:36px;font-weight:750;letter-spacing:-1px}.caption,small{font-size:13px;color:var(--muted)}small{display:block}.card small{margin-top:4px}h2{font-size:24px;line-height:1.25;letter-spacing:-.4px;margin:0 0 12px}h3{font-size:18px}p{margin:10px 0 16px}section{margin-top:20px}.twocol{display:grid;grid-template-columns:1.2fr 1fr;gap:20px}.twocol section{min-width:0}.pos{color:var(--green)}.neg{color:var(--red)}.tag{display:inline-block;font-size:12px;border-radius:30px;padding:4px 11px;background:#e8f2ef;color:#11654f;font-weight:700;margin-bottom:8px}.tag.amber{background:#fcf0dc;color:#906116}a{color:#246284;text-underline-offset:3px}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;color:var(--muted);font-weight:600;font-size:12px;padding:10px 9px;border-bottom:2px solid var(--line)}td{padding:12px 9px;border-bottom:1px solid var(--line);vertical-align:top}td:first-child,th:first-child{padding-left:0}.number{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.scroll{overflow-x:auto}svg{width:100%;height:auto;display:block}button{font:inherit;font-size:13px;padding:8px 12px;border:1px solid var(--line);background:white;color:var(--ink);cursor:pointer;border-radius:8px;margin:0 5px 10px 0}button[aria-pressed=true]{background:var(--navy);color:white;border-color:var(--navy)}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #e9a638;outline-offset:4px}.pebar{height:12px;width:95px;background:#eef2f5;border-radius:3px;margin-top:4px}.pebar span{display:block;height:12px;background:#628aa6;border-radius:3px}.note{padding:14px 18px;border-left:3px solid #7c9aaf;background:#f0f5f8;font-size:14px;margin-top:18px}.eventstats{display:flex;gap:18px;flex-wrap:wrap;padding:14px 0}.eventstats b{font-size:27px;display:block}.eventstats div{flex:1;min-width:140px}details{border-top:1px solid var(--line);padding-top:14px;margin-top:16px}summary{cursor:pointer;font-weight:700}details article{padding-top:22px}article h1{font-size:30px}article h2{margin-top:30px}article table{display:block;overflow-x:auto}article p,article li{max-width:1000px}.evidence{overflow-wrap:anywhere}.evidence li{margin:12px 0}footer{font-size:12px;color:var(--muted);margin-top:24px}.key{font-size:18px;font-weight:650}.step{padding:12px 0;border-bottom:1px solid var(--line)}.step b{display:block} @media(max-width:760px){main{padding:16px 12px 40px}header{padding:26px 22px}.cards{gap:8px}.card{padding:15px 12px}.card .value{font-size:27px}.twocol{display:block}section{padding:19px}table{font-size:13px}.pebar{width:70px}} @media print{body{background:white}main{padding:0}header{background:white;color:#192b43;border:1px solid #ddd}header p,.eyebrow{color:#192b43}section,.card{break-inside:avoid}button{display:none}a{color:inherit}details.evidence{display:none}}
</style></head><body><main>
<header><div class="eyebrow">Investment research · 23 November 2026</div><h1>A pullback after a strong month.</h1><p class="key">Prices are moving. Our task is to find an improved purchase case with the business economics intact.</p><p>Primary NSE index snapshot at <b>13:14 IST</b>. Share quotes have their own times. This is an intraday review.</p></header>
<div class="cards"><div class="card"><small>NIFTY 50 TODAY</small><div class="value neg">−1.30%</div><small>25,464.75 · primary exchange data</small></div><div class="card"><small>SINCE 23 OCTOBER</small><div class="value pos">+12.68%</div><small>Price change, excluding dividends</small></div><div class="card"><small>NIFTY 50 BREADTH</small><div class="value">38 / 50</div><small>Constituents declining · VIX 18.03</small></div></div>
<div class="twocol"><section><h2>Sector moves and recent gains</h2><button aria-pressed="true" data-view="today">Today</button><button aria-pressed="false" data-view="month">Since 23 October</button><div id="today">__TODAY__</div><div id="month" hidden>__MONTH__</div><p class="caption">Separate scales for each period. NSE, 23 November at 13:14 IST. IT rises while banks and metals lead the decline.</p></section>
<section><h2>The valuation comparison</h2><p class="caption">Published trailing figures at 20 November close</p><table><thead><tr><th>Index</th><th></th><th class="number">P/E</th><th class="number">Yield</th></tr></thead><tbody>__VALUATION__</tbody></table><div class="note"><b>Research implication:</b> expand the comparison to established IT services and selected banks. Lower P/E alone does not settle growth, AI exposure, credit risk or owner cash.</div></section></div>
<section><span class="tag">Existing decisions retained</span><h2>Five verified candidate quotes</h2><div class="scroll"><table><thead><tr><th>Company</th><th class="number">Quote</th><th class="number">Today</th><th>IST</th><th>Prior reopening condition</th></tr></thead><tbody>__QUOTES__</tbody></table></div><p class="caption">Secondary webpages, separately timestamped and potentially delayed. Percentage gaps are calculations to prior conditional levels. These are not automatic purchase triggers.</p>
<details open><summary>What the lower prices do to our existing scenarios</summary><table><thead><tr><th>Five-year case</th><th class="number">Return at original price</th><th class="number">Return at observed quote</th></tr></thead><tbody>__SENSITIVITY__</tbody></table><p class="caption">Annualized modeled returns including distributions and exit, before personal tax and dealing costs. Only entry price changes. Original cash amounts and timing stay fixed. CMS varies the investment schedule. R Systems uses year-five or year-six cash at the same five-year exit. No probabilities or new operating forecast are implied.</p></details></section>
<div class="twocol"><section><span class="tag amber">New transaction review</span><h2>APL Apollo: re-underwrite the changed business</h2><div class="eventstats"><div><small>Asset purchase</small><b>₹28,000cr</b></div><div><small>FY27 projected EBITDA multiple</small><b>24.8×</b></div></div><p>The issuer expects initial borrowing of ₹280bn, followed by long-term capitalization. Its projected acquisition EBITDA yield is about <b>4.03%</b> before interest, tax and reinvestment.</p><p>Tata's separate purchase of promoter shares pays the seller. The limited open offer at ₹2,301.40 does not guarantee an exit for every share.</p><div class="note"><b>Decisive next evidence:</b> final financing, dilution and acquired cash generation per existing shareholder. No supported BUY conclusion yet.</div></section>
<section><span class="tag">Demand and timing</span><h2>Keep the event date and the economics separate</h2><p><b>Newgen:</b> the ₹17.46cr CreditAccess order is a 20 November event, spread over three years. It supports product demand, but does not prove collections have improved.</p><p><b>Economy:</b> November flash PMI reports continuing expansion, with manufacturing strengthening and services easing. Survey growth is not company cash.</p><div class="note"><b>Calendar:</b> NSE equities are closed Tuesday, 24 November, for Prakash Gurpurb Sri Guru Nanak Dev.</div></section></div>
<section><h2>Research priorities from this market check</h2><div class="step"><b>1. Preserve the concrete company work</b>CMS collections and investment. R Systems organic growth, margins and per-share cash.</div><div class="step"><b>2. Broaden the comparison</b>Established IT services and selected banks now deserve direct comparison with our smaller-company cases.</div><div class="step"><b>3. Separate the special situation</b>APL's financing and capitalization require their own valuation before treating the fall as opportunity.</div><details><summary>Complete assessment, reasoning, sources and limitations</summary><article>__NOTES__</article></details><details class="evidence"><summary>Original evidence and reproducible calculations</summary><p class="caption">Seven original files and the complete research inputs are embedded in this report. Links below download the frozen copies. Live source URLs are in the full assessment.</p><ul>__EVIDENCE__</ul></details></section>
<footer>Prepared for Rajan · Indian equity discovery · Price observations are not executed trades. Existing research decisions and frozen experiments remain unchanged. This snapshot is not an all-market cash recommendation.</footer>
</main><script>document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{const view=button.dataset.view;document.getElementById('today').hidden=view!=='today';document.getElementById('month').hidden=view!=='month';document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)))}));</script></body></html>'''
    replacements = {'__TODAY__':today,'__MONTH__':month,'__VALUATION__':valuation_rows,'__QUOTES__':qrows,'__SENSITIVITY__':srows,'__NOTES__':notes,'__EVIDENCE__':evidence}
    for key, value in replacements.items():
        doc = doc.replace(key, value)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(doc)
    (args.output.parent/'embedded_evidence_receipt.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'bytes':args.output.stat().st_size,'embedded_originals':len(manifest)}))


if __name__ == '__main__':
    main()
