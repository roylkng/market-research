"""Build the complete dated research report and reusable scenario chart.

Uses the retained register and company notes. Does not fetch market data or write
portfolio decisions. Raw evidence is packaged separately from this report.
"""
import argparse
import base64
import html
import json
from pathlib import Path
import re
import subprocess

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def pct(value):
    return f'{100 * value:.1f}%'


def markdown(path, prefix):
    text = subprocess.run(['pandoc', '--from=gfm', '--to=html', '--wrap=none', str(path)],
                          check=True, capture_output=True, text=True).stdout
    text = re.sub(r'id="([^"]+)"', lambda m: f'id="{prefix}-{m.group(1)}"', text)
    text = re.sub(r'href="#([^"]+)"', lambda m: f'href="#{prefix}-{m.group(1)}"', text)
    # The downloadable report can be moved. Relative research links should still
    # resolve to the retained branch, rather than a missing local companion file.
    def externalize(match):
        target = match.group(1)
        if target.startswith(('https:', 'http:', '#', 'mailto:')):
            return match.group(0)
        absolute = (path.parent / target).resolve()
        try:
            rel = absolute.relative_to(HERE.parents[2])
        except ValueError:
            return match.group(0)
        return 'href="https://github.com/roylkng/market-research/blob/research/discovery-reset-20261117/' + str(rel) + '"'
    return re.sub(r'href="([^"]+)"', externalize, text)


def build(output, commit):
    output.mkdir(parents=True, exist_ok=True)
    register = load('decision_register.json')
    cases = register['cases']
    chart_cases = [c for c in cases if c.get('working_return_range')]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
    fig, ax = plt.subplots(figsize=(12.5, 6.2), dpi=170)
    fig.patch.set_facecolor('#f7f9fc')
    ax.set_facecolor('#f7f9fc')
    for i, case in enumerate(chart_cases):
        y = len(chart_cases) - i - 1
        low, high = case['downside_return'] * 100, case['upside_return'] * 100
        w0, w1 = [100 * x for x in case['working_return_range']]
        ax.plot([low, high], [y, y], color='#ccd5df', linewidth=4, zorder=1)
        ax.scatter([low], [y], color='#ad4949', marker='v', s=80, zorder=3)
        ax.scatter([high], [y], color='#3c8271', marker='^', s=80, zorder=3)
        ax.plot([w0, w1], [y, y], color='#135e86', linewidth=9, zorder=4, solid_capstyle='round')
        if abs(w1-w0) < .01:
            ax.scatter([w0], [y], color='#135e86', s=85, zorder=4)
        working_label = f'{w0:.1f}%' if abs(w1-w0) < .01 else f'{w0:.1f}-{w1:.1f}%'
        ax.text((w0+w1)/2, y+.15, working_label, ha='center', va='bottom', fontsize=11, weight='bold', color='#134c70')
        ax.text(low, y-.15, f'{low:.1f}%', ha='center', va='top', color='#983b3b', fontsize=10)
        ax.text(high, y-.15, f'{high:.1f}%', ha='center', va='top', color='#286857', fontsize=10)
    ax.set_yticks(list(reversed(range(len(chart_cases)))), [c['name'] for c in chart_cases])
    ax.set_xlim(-23, 28)
    ax.set_ylim(-.6, len(chart_cases)-.35)
    ax.set_xticks([-20,-10,0,10,20], ['-20%','-10%','0%','10%','20%'])
    ax.axvline(0, color='#8897a8', linestyle='--', linewidth=1)
    ax.grid(axis='x', color='#e2e8ef', linewidth=.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.tick_params(length=0, pad=12)
    ax.set_xlabel('Five-year annualized shareholder scenario at the 19 November close', labelpad=15)
    fig.suptitle('The cash assumptions decide the return', x=.06, y=.97, ha='left', fontsize=19, weight='bold', color='#173b53')
    ax.set_title('Downside triangle   /   Working blue mark   /   Upside triangle', loc='left', pad=16, fontsize=11, color='#536a7e')
    fig.text(.06,.025,'Unweighted analyst scenarios, not probabilities, confidence intervals or loss limits. Before investor taxes and trading costs.\nWorking ranges vary investment, exit timing or exit multiple. Company models have different operating and valuation assumptions.',fontsize=9,color='#566b7c')
    fig.subplots_adjust(left=.17,right=.97,top=.80,bottom=.20)
    chart = output/'Discovery_Scenario_Comparison_2026-11-20.png'
    fig.savefig(chart,bbox_inches='tight')
    plt.close(fig)
    data_uri = 'data:image/png;base64,' + base64.b64encode(chart.read_bytes()).decode()

    cards, rows, full = [], [], []
    for c in cases:
        working = c.get('working_return_range')
        ret = (pct(working[0]) if working and abs(working[1]-working[0])<1e-6 else f'{pct(working[0])} to {pct(working[1])}') if working else 'Event update'
        price = f'₹{c["price"]:,.2f}'
        name = html.escape(c['name'])
        disposition = html.escape(c['display_disposition'])
        key = html.escape(c['key_finding'])
        action = html.escape(c['reopen'])
        cards.append(f'<article class="card"><div class="eyebrow">{html.escape(c["symbol"])} · {price}</div><h3>{name}</h3><span class="tag">{disposition}</span><div class="metric">{ret}</div><p>{key}</p><p class="next"><b>Decision trigger</b><br>{action}</p><a href="#{c["symbol"]}">Read the full case ↓</a></article>')
        rows.append(f'<tr><td><b>{name}</b><br><small>{html.escape(c["symbol"])}</small></td><td>{price}</td><td>{ret}</td><td>{disposition}</td></tr>')
        full.append(f'<details id="{c["symbol"]}"><summary><span>{name}</span><small>{disposition}</small></summary><div class="detail">{markdown(HERE/c["note"],c["symbol"])}</div></details>')

    learn = markdown(HERE/'README.md','synthesis')
    methods = markdown(HERE/'independent/review_summary.md','review')
    source_index = load('source_bundle_index.json')
    source_rows = []
    for s in source_index['sources']:
        url = s.get('url','')
        label = html.escape(s['archive_path'])
        link = f'<a href="{html.escape(url,quote=True)}">Original publisher</a>' if url else 'Retained source'
        source_rows.append(f'<tr><td>{label}</td><td>{link}</td><td><code>{s["sha256"][:16]}…</code></td></tr>')
    publication = f'<a href="https://github.com/roylkng/market-research/commit/{commit}">Published research commit {commit[:12]}</a>' if commit else 'Prepared on the current research branch for publication'
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Investment discovery | 20 November 2026</title>
<style>
:root{{color-scheme:light;--ink:#16364b;--muted:#526b7c;--line:#dae4ec;--blue:#125f87;--paper:#f4f7fa;--white:#fff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);font:16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink)}}
main{{max-width:1200px;margin:auto;padding:36px 30px 70px}}header{{background:#12344c;color:#fff;border-radius:22px;padding:42px 44px;margin-bottom:24px}}header p{{max-width:850px;color:#d6e6f0;margin:15px 0 0}}h1{{font-size:clamp(30px,4vw,46px);line-height:1.15;margin:10px 0 12px;letter-spacing:-1px}}h2{{font-size:26px;line-height:1.3;margin:36px 0 16px}}h3{{font-size:22px;line-height:1.3;margin:8px 0 12px}}.eyebrow{{text-transform:uppercase;letter-spacing:1.4px;font-size:12px;font-weight:750}}nav{{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}}nav a{{background:#fff;padding:8px 15px;border:1px solid var(--line);border-radius:999px;text-decoration:none;font-weight:650;font-size:14px}}a{{color:var(--blue);text-underline-offset:3px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}.card{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:25px;box-shadow:0 5px 18px #193b5510}}.tag{{display:inline-block;border-radius:5px;background:#e9f0f5;padding:4px 9px;font-size:12px;font-weight:750}}.metric{{font-size:30px;font-weight:800;letter-spacing:-.7px;margin:16px 0 8px;color:#145f85}}.card p{{margin:12px 0}}.next{{border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font-size:14px}}.card>a{{font-size:14px;font-weight:700}}.panel{{background:white;border:1px solid var(--line);border-radius:16px;padding:25px;margin:22px 0}}.panel img{{width:100%;height:auto;display:block}}.callout{{border-left:5px solid #c9933d;background:#fff7e8;padding:20px 24px;border-radius:0 12px 12px 0;margin:24px 0}}.muted,small{{color:var(--muted)}}.tablewrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:14px;margin:18px 0}}th,td{{padding:12px 13px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:#edf3f7;color:#264e67}}td p{{margin:0}}details{{border:1px solid var(--line);border-radius:13px;background:white;margin:14px 0;scroll-margin-top:18px}}summary{{padding:20px 24px;cursor:pointer;font-weight:750;font-size:18px}}summary small{{font-size:12px;margin-left:16px;display:inline-block}}.detail{{padding:0 26px 28px;overflow:auto}}.detail h1{{font-size:27px;line-height:1.35;letter-spacing:-.3px}}.detail h2{{font-size:22px;margin-top:30px}}.detail h3{{font-size:19px}}.detail p,.detail li{{font-size:15px}}.detail pre{{overflow:auto;background:#f3f6f8;padding:14px;border-radius:8px;font-size:12px}}code{{font-size:.85em;overflow-wrap:anywhere}}footer{{border-top:1px solid var(--line);margin-top:35px;padding-top:22px;font-size:13px;color:var(--muted)}}.statline{{display:flex;flex-wrap:wrap;gap:12px;margin-top:22px}}.statline span{{background:#ffffff12;border:1px solid #ffffff29;padding:8px 12px;border-radius:8px;font-size:13px}}button{{border:1px solid var(--line);background:white;color:var(--blue);border-radius:8px;padding:9px 14px;cursor:pointer;font:inherit;font-size:13px}}@media(max-width:700px){{main{{padding:18px 14px 40px}}header{{padding:28px 24px}}.grid{{grid-template-columns:1fr}}.card,.panel{{padding:20px}}.detail{{padding:0 18px 20px}}summary small{{display:block;margin-left:0;margin-top:5px}}}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}header{{border-radius:0}}nav,button{{display:none}}details{{break-inside:avoid}}summary{{padding:12px}}.grid{{grid-template-columns:1fr 1fr}}.card{{box-shadow:none}}a{{color:inherit}}}}
.card:last-child:nth-child(odd){{grid-column:1/-1}}
</style></head><body><main>
<header><div class="eyebrow">Investment research · 20 November 2026 · India</div><h1>Stronger decisions.<br>Confidence tied to cash.</h1><p>{html.escape(register['headline'])}</p><div class="statline"><span>19 November official closes</span><span>{register['completed_funded_models']} funded company models</span><span>{register['new_full_company_cases']} new full company cases</span><span>One material surveillance correction</span></div></header>
<nav><a href="#decisions">Decisions</a><a href="#scenarios">Scenarios</a><a href="#findings">What changed</a><a href="#full">Complete company notes</a><a href="#sources">Sources</a><button onclick="window.print()">Print / save PDF</button></nav>
<div class="callout"><b>How to read this report</b><br>These are dated research judgments under explicit assumptions. The price references precede this research and are not executed fills. Confidence in accounting and valuation has improved. Investment outperformance remains unproven. No universal 15% return hurdle or portfolio allocation is assumed.</div>
<section id="decisions"><h2>Current decisions</h2><div class="tablewrap"><table><thead><tr><th>Company</th><th>Reference close</th><th>Working annualized case</th><th>Research decision</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><div class="grid">{''.join(cards)}</div></section>
<section id="scenarios" class="panel"><img src="{data_uri}" alt="Four company downside, working and upside five-year annualized scenario comparisons"><p class="muted">The working marks are sensitivity ranges where stated. They are not statistical confidence bands. Read the company cash and ownership assumptions before comparing the numbers.</p></section>
<section id="findings"><h2>What changed and why it matters</h2><div class="panel detail">{learn}</div></section>
<section id="full"><h2>Complete company notes</h2><p class="muted">Open a company for its full economics, management and competition assessment, scenarios, primary sources and reopening conditions.</p>{''.join(full)}<details><summary>Independent checks and remaining uncertainty</summary><div class="detail">{methods}</div></details></section>
<section id="sources"><h2>Original evidence and reproducibility</h2><p>{source_index['unique_original_count']} unique original files are retained in the accompanying evidence archive. Their bytes and hashes were checked. Original custody verifies what was read, not the truth of a forecast. Failed retrieval attempts remain in the individual source manifests and are excluded from this count.</p><details><summary>Original source index</summary><div class="detail tablewrap"><table><thead><tr><th>Archived file</th><th>Source</th><th>SHA-256 prefix</th></tr></thead><tbody>{''.join(source_rows)}</tbody></table></div></details></section>
<footer>{publication}. <a href="https://github.com/roylkng/market-research/pull/620">PR #620</a> is research under review, not a main-branch merge. Prior dated cases and frozen experiments remain intact. The evidence archive includes inputs, calculators, source receipts and full original documents. Existing scheduled discovery carries the completed decisions forward.</footer>
</main></body></html>'''
    target=output/'Investment_Discovery_Review_2026-11-20.html'
    target.write_text(document)
    print(json.dumps({'html':str(target),'chart':str(chart),'companies':len(cases),'chart_cases':len(chart_cases),'html_bytes':target.stat().st_size},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--commit',default='')
    args=parser.parse_args()
    build(args.output.resolve(),args.commit)
