#!/usr/bin/env python3
"""Build the self-contained long-term research report and exact illustration.

Run with a Python environment containing matplotlib and with pandoc on PATH.
This report is an authored research artifact, not a live data feed.
"""
from pathlib import Path
import argparse
import base64
import html
import json
import re
import subprocess
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
REPO_URL = "https://github.com/roylkng/market-research/blob/research/discovery-reset-20261117/research/integrated/long-term-opportunities-2026-11-21/"


def fragment(path, prefix):
    text = subprocess.run(
        ["pandoc", "--from=gfm", "--to=html5", "--shift-heading-level-by=2", str(path)],
        check=True, capture_output=True, text=True).stdout
    text = re.sub(r'id="([^"]+)"', lambda m: 'id="' + prefix + '-' + m[1] + '"', text)
    def fix_link(match):
        target = match[1]
        if target.startswith('#'):
            target = '#' + prefix + '-' + target[1:]
        elif not target.startswith(('https://', 'http://', 'mailto:', 'data:')):
            target = urljoin(REPO_URL + str(path.parent.relative_to(ROOT)) + '/', target)
        return 'href="' + target + '"'
    text = re.sub(r'href="([^"]+)"', fix_link, text)
    return text


def build_chart(destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    multiples = [30, 45, 60, 80]
    results = [100 * (1.15 * (30 / m) ** .1 - 1) for m in multiples]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12})
    fig, ax = plt.subplots(figsize=(11.8, 5.8), dpi=180)
    fig.patch.set_facecolor('#f5f8fb')
    ax.set_facecolor('#f5f8fb')
    colors = ['#178579', '#367cac', '#cd8234', '#a95f6c']
    bars = ax.barh(range(4), results, color=colors, height=.56)
    ax.invert_yaxis()
    ax.set_yticks(range(4), [f'{m}× entry P/E' for m in multiples])
    ax.set_xlim(0, 17.3)
    ax.set_xticks([0, 5, 10, 15], ['0%', '5%', '10%', '15%'])
    ax.set_xlabel('Annual share-price growth over ten years', labelpad=14)
    ax.xaxis.grid(True, color='#dce5eb', linewidth=.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis='both', length=0, pad=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for bar, value in zip(bars, results):
        ax.text(value + .22, bar.get_y() + bar.get_height()/2, f'{value:.1f}%',
                va='center', fontsize=16, fontweight='bold', color='#152f43')
    fig.text(.06, .925, 'The price of growth matters', fontsize=23, weight='bold', color='#152f43')
    fig.text(.06, .865, 'Identical 15% annual EPS growth. Different purchase valuations.', fontsize=13, color='#486074')
    fig.subplots_adjust(left=.19, right=.95, top=.77, bottom=.24)
    fig.text(.06, .10, 'All cases: 10 years, 15% EPS growth and 30× exit P/E. Dividends, tax and costs excluded.',
             fontsize=10.5, color='#486074')
    fig.text(.06, .052, 'Mathematical illustration, not a company forecast. Source: calculation supplied in the research package.',
             fontsize=10, color='#486074')
    fig.savefig(destination, facecolor=fig.get_facecolor(), bbox_inches=None)
    plt.close(fig)
    return [{'entry_pe': m, 'exit_pe': 30, 'eps_growth': .15, 'years': 10,
             'price_cagr': r / 100} for m, r in zip(multiples, results)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    chart = out / 'Long_Term_Growth_And_Price_2026-11-21.png'
    illustration = build_chart(chart)
    (ROOT / 'valuation_illustration.json').write_text(json.dumps({
        'classification': 'MATHEMATICAL_ILLUSTRATION_NOT_FORECAST',
        'formula': '(1 + annual_eps_growth) * (exit_PE / entry_PE) ** (1 / years) - 1',
        'EPS': 'Per-share earnings growth already includes any dilution effect',
        'excluded': ['dividends', 'tax', 'trading costs', 'funding feasibility'],
        'scenarios': illustration}, indent=2) + '\n')
    cases = {name: json.loads((ROOT/name/'case_summary.json').read_text())
             for name in ['financial_infrastructure', 'power', 'health']}
    register = {
        'review_date': '2026-11-21', 'timezone': 'Asia/Calcutta',
        'official_price_date': '2026-11-20',
        'research_scope': {'new_bounded_cases': 3, 'sector_comparators': 6,
                           'official_EQ_price_matches': 27, 'raw_exchange_rows': 3742,
                           'new_fully_funded_decade_forecasts': 0, 'new_blind_replays': 0},
        'ranking_basis': 'Analyst judgment among the three new cases, not a calibrated statistical score',
        'priority': ['CAMS', 'POWERGRID comparator', 'APARINDS long-term business', 'VIJAYA long-term business'],
        'new_unconditional_buy': False,
        'previous_conditional_candidates_retained': ['CMSINFO', 'RSYSTEMS'],
        'case_summaries': cases,
        'new_outcomes': None,
        'preserved_review_dates': ['2026-12-20', '2027-02-18', '2027-05-19'],
        'structural_observation_horizons_years': [1, 3, 5, 10],
        'horizons_are_waiting_gates': False,
        'watch_change': 'Add structural economics, price conditions and eClerx clarification to the existing NSE Opportunity Watch without changing its schedule',
        'restrictions': ['No broker actions', 'No main-branch merge', 'No frozen protocol or source-acceptance changes',
                         'No user allocation invented', 'No universal 15% hurdle'],
    }
    (ROOT/'decision_register.json').write_text(json.dumps(register, indent=2, ensure_ascii=False)+'\n')

    note_specs = [
        ('synthesis', 'Complete synthesis and investment decisions', ROOT/'README.md'),
        ('cams', 'CAMS: financial infrastructure, cash and price', ROOT/'financial_infrastructure'/'README.md'),
        ('apar', 'APAR: grid opportunity, funding and the cycle', ROOT/'power'/'README.md'),
        ('vijaya', 'Vijaya: patient demand, regional density and expansion', ROOT/'health'/'README.md'),
        ('existing', 'Existing candidates, AI, water and the eClerx correction', ROOT/'structural'/'existing_candidates_and_future_demand.md'),
    ]
    notes = ''.join('<details id="' + key + '"><summary>' + html.escape(title) +
                    '</summary><article>' + fragment(path, key) + '</article></details>'
                    for key, title, path in note_specs)
    image_data = base64.b64encode(chart.read_bytes()).decode()
    css = '''
    :root{--ink:#173246;--muted:#536b7d;--line:#dbe5eb;--teal:#087d70;--amber:#a8691c;--paper:#f4f7fa;--white:#fff}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    header{background:#15384b;color:white;padding:44px max(5vw,22px) 38px}header>div,main{max-width:1160px;margin:auto}
    .eyebrow{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#a9dbd4;font-weight:700}h1{font-size:clamp(30px,4vw,49px);line-height:1.14;max-width:900px;margin:14px 0 20px;letter-spacing:-.025em}
    header p{max-width:890px;font-size:18px;color:#d9e7ed;margin:0}.meta{font-size:13px;color:#b8ccd6;margin-top:23px}main{padding:30px 22px 60px}
    nav{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:26px}nav a,.pill{font-size:12px;padding:7px 11px;border:1px solid var(--line);border-radius:30px;background:white;color:var(--ink);text-decoration:none}
    h2{font-size:27px;line-height:1.25;letter-spacing:-.02em;margin:34px 0 14px}h3{line-height:1.3}a{color:#096b9a}p{margin:10px 0 16px}.muted,small{color:var(--muted)}
    .lead{background:#e6f2ef;border:1px solid #b9d9d1;border-left:5px solid var(--teal);padding:21px 24px;border-radius:8px}.lead strong{color:#085d53}.lead p{margin:6px 0}
    .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:22px 0}.card{border:1px solid var(--line);border-top:4px solid var(--teal);border-radius:9px;background:white;padding:22px}.card:nth-child(2){border-top-color:#cd8234}.card:nth-child(3){border-top-color:#95636f}.card h3{font-size:23px;margin:8px 0}.card .quote{font-size:24px;font-weight:700}.card .label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}.card p{font-size:14px;line-height:1.6}.card .status{font-size:13px;font-weight:700;padding:8px 0;border-top:1px solid var(--line)}
    .tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:white}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:14px;vertical-align:top;border-bottom:1px solid var(--line)}th{background:#e9f0f5;font-size:12px;letter-spacing:.02em}tr:last-child td{border-bottom:0}
    .compare{padding:18px 22px;border:1px solid #ccdce7;background:#eaf1f7;border-radius:8px}.compare p{margin:4px 0}.compare strong{color:#264f6b}
    .chart{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:8px;margin:18px 0}.calc{background:white;border:1px solid var(--line);padding:24px;border-radius:8px}.controls{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}label{font-size:13px;color:var(--muted)}label span{display:block;font-size:19px;font-weight:700;color:var(--ink);margin-bottom:8px}input{width:100%;accent-color:var(--teal)}.answer{font-size:37px;font-weight:750;color:var(--teal);margin-top:18px;line-height:1.2}.formula{font:13px/1.6 ui-monospace,monospace;background:#eff4f7;padding:11px;border-radius:5px;margin-top:15px;overflow-x:auto}
    .twocol{display:grid;grid-template-columns:1fr 1fr;gap:18px}.box{background:white;border:1px solid var(--line);padding:20px 23px;border-radius:8px}.box h3{margin-top:0;font-size:20px}.box li{font-size:14px;margin:8px 0}ul{padding-left:21px}li{margin:6px 0}
    details{border:1px solid var(--line);border-radius:8px;background:white;margin:13px 0;scroll-margin-top:20px}summary{padding:19px 22px;cursor:pointer;font-weight:700;color:#254c62}details[open] summary{border-bottom:1px solid var(--line);background:#edf4f7}article{padding:4px 25px 26px;font-size:15px}article h3{font-size:25px;margin-top:30px}article h4{font-size:20px;margin-top:27px}article h5{font-size:17px}article table{display:block;overflow-x:auto;font-size:13px}article td,article th{padding:10px}article a{overflow-wrap:anywhere}article pre{white-space:pre-wrap;word-break:break-word;background:#f2f5f7;padding:12px}article code{font-size:.87em;overflow-wrap:anywhere}blockquote{margin-left:0;padding-left:18px;border-left:3px solid #bad5d9;color:var(--muted)}
    footer{border-top:1px solid var(--line);font-size:12px;color:var(--muted);margin-top:28px;padding-top:20px}.fine{font-size:12px;color:var(--muted);margin-top:10px}.badge{display:inline-block;background:#e4f1ee;color:#116557;font-size:12px;padding:3px 9px;border-radius:20px;font-weight:700}
    @media(max-width:800px){.cards,.twocol{grid-template-columns:1fr}.controls{grid-template-columns:1fr 1fr}header{padding:30px 22px}.card{padding:19px}main{padding:23px 15px}.tablewrap{font-size:13px}article{padding:0 16px 20px}}
    @media print{header{background:white;color:#173246;padding:15px}header p,.meta{color:#536b7d}main{max-width:none;padding:10px}nav,.controls{display:none}details{break-inside:auto}summary{font-size:18px}article{display:block}.card,.box{break-inside:avoid}a{color:#173246}.chart{max-height:400px;object-fit:contain}}
    '''
    body = '''
    <header><div><div class="eyebrow">Investment discovery · 21 November 2026</div>
    <h1>Which businesses can compound for the next decade?</h1>
    <p>Demand creates the opportunity. Competitive advantage, reinvestment and the purchase price determine what shareholders receive.</p>
    <div class="meta">Three new detailed cases · Six sector comparisons · Official NSE prices from 20 November 2026 · Research judgments, no trades</div></div></header>
    <main><nav><a href="#decisions">Decisions</a><a href="#patterns">Long-term patterns</a><a href="#valuation">Price and growth</a><a href="#evidence">What changes confidence</a><a href="#fullnotes">Full notes and sources</a></nav>
    <section class="lead"><strong>CAMS leads the new long-term shortlist.</strong><p>Its current price has a plausible route to being justified, but it requires sustained cash growth and successful platform execution. APAR and Vijaya remain credible businesses with more demanding entry expectations. Existing CMS and R Systems conditional cases remain active.</p><p class="fine">This is an analyst ranking among three new cases. It is not a calibrated score or an unconditional buy recommendation.</p></section>
    <section id="decisions"><h2>The businesses and the entry prices</h2>
    <div class="cards">
    <div class="card"><div class="label">Financial infrastructure</div><h3>CAMS</h3><div class="quote">₹724.65</div><div class="muted">About 35.2× TTM owner profit</div><p><b>Why it can compound:</b> embedded fund servicing, recurring workflows and adjacent financial infrastructure.</p><p><b>What must work:</b> fee discipline, technology productivity and cash conversion after all investment.</p><div class="status">Priority conditional candidate</div><a href="#cams">Read the full case ↓</a></div>
    <div class="card"><div class="label">Power infrastructure</div><h3>APAR Industries</h3><div class="quote">₹14,339.00</div><div class="muted">About 43.6× TTM profit</div><p><b>Why it can compound:</b> grid upgrades, qualified conductors, specialty cables and transformer fluids.</p><p><b>What must work:</b> physical growth, normal unit margins and cash returns on a much larger capital base.</p><div class="status">Current-price pass for five years</div><a href="#apar">Read the full case ↓</a></div>
    <div class="card"><div class="label">Healthcare diagnostics</div><h3>Vijaya</h3><div class="quote">₹1,572.30</div><div class="muted">About 79.5× TTM profit</div><p><b>Why it can compound:</b> recurring diagnostic demand, trusted regional networks and strong patient collections.</p><p><b>What must work:</b> new clusters must earn attractive cash returns after equipment, rent and integration.</p><div class="status">Watch price and center economics</div><a href="#vijaya">Read the full case ↓</a></div>
    </div><div class="compare"><strong>POWERGRID is the lower-priced power comparison.</strong><p>₹269.00, about 15.4× trailing reported EPS. The FY26 announced ₹9 dividend gives a 3.35% historical reference yield. New work is 89% competitive tariff bidding, so project funding and bid economics still need a full valuation. This remains a bounded comparator.</p></div>
    <p class="fine">P/E calculations use company-specific reported share and earnings dates. Price is not an assumed fill. Full notes identify split, dilution and weighted-denominator limitations.</p></section>
    <section id="patterns"><h2>Five patterns worth following</h2><div class="tablewrap"><table><thead><tr><th>Pattern</th><th>Potential value capture</th><th>What can break the investment</th></tr></thead><tbody>
    <tr><td><b>Electricity and grid upgrades</b><br>APAR, GVT&D, POWERGRID</td><td>Qualification, reliability and productive infrastructure</td><td>Weak bid pricing, excess supply, commodity margins and financing</td></tr>
    <tr><td><b>Managed financial savings</b><br>CAMS, KFin, CDSL</td><td>Embedded servicing, compliance and operating scale</td><td>Fee erosion, market declines and technology investment without payoff</td></tr>
    <tr><td><b>Diagnosis and chronic monitoring</b><br>Vijaya, Dr Lal, Metropolis</td><td>Trust, regional density and equipment utilization</td><td>Expensive expansion, tariff normalization and stronger buyer bargaining</td></tr>
    <tr><td><b>Water treatment and reuse</b><br>Existing WABAG lead</td><td>Funded industrial offtake and paid lifetime operations</td><td>Necessary infrastructure with delayed collections or uneconomic contracts</td></tr>
    <tr><td><b>AI-enabled work</b><br>Existing R Systems and eClerx cases</td><td>Profitable customer outcomes and embedded workflows</td><td>Productivity gains passed to customers without enough new profitable demand</td></tr>
    </tbody></table></div><p class="fine">Structural mechanisms, not sector return forecasts. Policy targets are not orders. Sources and limits are in the expandable notes.</p></section>
    <section id="valuation"><h2>A good decade for a business can be an ordinary decade for its stock</h2>
    <img class="chart" alt="With 15 percent annual EPS growth and a 30 times exit P/E, ten-year share-price CAGR is 15.0 percent from a 30 times entry, 10.4 percent from 45 times, 7.3 percent from 60 times, and 4.3 percent from 80 times." src="data:image/png;base64,IMAGE_DATA">
    <div class="calc"><h3 style="margin-top:0">Explore the price-growth relationship</h3><div class="controls">
    <label>Entry P/E<span id="entryValue">60×</span><input aria-label="Entry P/E" id="entry" type="range" min="10" max="100" value="60"></label>
    <label>Exit P/E<span id="exitValue">30×</span><input aria-label="Exit P/E" id="exit" type="range" min="10" max="60" value="30"></label>
    <label>Annual EPS growth<span id="growthValue">15%</span><input aria-label="Annual EPS growth" id="growth" type="range" min="-5" max="30" value="15" step="0.5"></label>
    <label>Years held<span id="yearsValue">10</span><input aria-label="Years held" id="years" type="range" min="3" max="15" value="10"></label></div>
    <div class="answer" id="result" aria-live="polite">7.3%</div><div class="muted">Illustrative annual share-price growth</div>
    <div class="formula">Price CAGR = (1 + EPS growth) × (exit P/E ÷ entry P/E)<sup>1 / years</sup> − 1</div>
    <p class="fine">Dividends, tax and costs excluded. EPS growth is after dilution. This calculator does not establish funding, growth probability or a fair terminal multiple. It is not a company forecast.</p></div>
    <h3>The actual case expectations</h3><div class="tablewrap"><table><thead><tr><th>Case</th><th>Illustrative result</th><th>Assumptions and limits</th></tr></thead><tbody>
    <tr><td><b>CAMS</b><br>Required company cash growth</td><td>About <b>13.3% a year for ten years</b> for a 10% illustrative return. About 16.5% from reported cash.</td><td>₹400cr favorable normalized starting cash, ₹650cr provisional treasury, 0.5% dilution, 25× terminal cash. All future growth is assumed after required reinvestment. Feasibility remains to be established.</td></tr>
    <tr><td><b>APAR</b><br>Dividend-inclusive scenario IRR</td><td><b>3.6% over five years</b> and <b>9.3% over ten</b> in the working case. Profit-reset stress: −13.4% and −3.15%.</td><td>Working: ₹1,400cr assumed starting PAT, 15% growth, 25× exit, 20% payout and 0.3% dilution. Reset: ₹976.93cr, 8% growth, 20× exit. Neither is a fully funded forecast.</td></tr>
    <tr><td><b>Vijaya</b><br>Price CAGR, excluding dividends</td><td>15% EPS growth for ten years produces <b>4.3–7.4%</b> price CAGR at 30–40× exit.</td><td>Starts near 79.5× earnings. EPS growth already includes dilution. No separate treasury addition. New-center investment returns still need evidence.</td></tr>
    </tbody></table></div><p class="fine">These outputs use different return measures and must not be ranked as directly comparable expected returns. No probabilities are assigned. The 10% illustration is not a universal required-return rule.</p></section>
    <section id="evidence"><h2>What changes confidence</h2><div class="twocol">
    <div class="box"><h3>Evidence to act on</h3><ul><li><b>CAMS:</b> cash conversion, FY28 AMC renewals, actual platform savings and succession after the announced December officer departure.</li><li><b>APAR:</b> physical volumes, ordinary unit margins, supplier-finance reconciliation and returns on the expanded capital base.</li><li><b>Vijaya:</b> new-cluster cash after rent, equipment and tax, with tariff effects and acquisition commitments separated.</li><li><b>Existing candidates:</b> retain CMS collections and reinvestment tests and R Systems' organic customer economics.</li></ul></div>
    <div class="box"><h3>Corrections that improve the process</h3><ul><li>Growth investment can be attractive even when current free cash is low. Its future return and financing must justify it.</li><li>APAR's initial low case was too favorable. A separate profit reset is now visible.</li><li>Vijaya's cash coverage does not eliminate future lease obligations.</li><li>eClerx's original notice concerns existing option perquisites. The proposed 18% ceiling is not a new recurring cash charge.</li></ul></div></div>
    <div class="tablewrap" style="margin-top:18px"><table><thead><tr><th>Observation horizon</th><th>What we test</th></tr></thead><tbody><tr><td>Next disclosure to 1 year</td><td>The immediate economic mechanism and price assumptions</td></tr><tr><td>3 years</td><td>Repeatable cash returns on new investments and geographies</td></tr><tr><td>5 years</td><td>Per-share growth through normal competition and a weaker cycle</td></tr><tr><td>10 years</td><td>Durable customer economics, succession and continued productive reinvestment</td></tr></tbody></table></div>
    <p class="fine">These are observation horizons, not compulsory waiting periods. Price or credible evidence can change a decision earlier. Historical mechanism studies remain retrospective, and the previous selected-cohort advantage remains unproven.</p></section>
    <section id="fullnotes"><h2>Complete notes, assumptions and primary sources</h2><p class="muted">Open a section for the full investment reasoning, historical counterexamples, cash bridges, management evidence and source links. These notes are embedded in this report.</p>FULL_NOTES</section>
    <footer>Prepared 21 November 2026, Asia/Calcutta. Official market reference: 20 November NSE archive. Three new detailed cases, six comparators and 27 security price matches do not constitute full-market underwriting. All charts and reverse calculations are conditional. No trades or portfolio weights are assumed. Research is retained in <a href="https://github.com/roylkng/market-research/pull/620">PR #620</a>, with older judgments preserved. The evidence archive carries source bytes, hashes and executable calculations.</footer></main>
    '''.replace('IMAGE_DATA', image_data).replace('FULL_NOTES', notes)
    js = '''
    function update(){
      const entry=Number(document.getElementById('entry').value);
      const exit=Number(document.getElementById('exit').value);
      const growth=Number(document.getElementById('growth').value);
      const years=Number(document.getElementById('years').value);
      document.getElementById('entryValue').textContent=entry+'×';
      document.getElementById('exitValue').textContent=exit+'×';
      document.getElementById('growthValue').textContent=growth+'%';
      document.getElementById('yearsValue').textContent=years;
      const result=100*((1+growth/100)*Math.pow(exit/entry,1/years)-1);
      document.getElementById('result').textContent=result.toFixed(1)+'%';
    }
    for(const id of ['entry','exit','growth','years']) document.getElementById(id).addEventListener('input',update);
    for(const link of document.querySelectorAll('a[href^="#"]')){
      link.addEventListener('click',function(){
        const target=document.getElementById(this.getAttribute('href').slice(1));
        if(target && target.tagName==='DETAILS') target.open=true;
      });
    }
    update();
    '''
    report=out/'Investment_Long_Term_Opportunity_Map_2026-11-21.html'
    report.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Investment long-term opportunity map | 21 November 2026</title><style>'+css+'</style></head><body>'+body+'<script>'+js+'</script></body></html>')
    print(json.dumps({'report':str(report),'chart':str(chart),'html_bytes':report.stat().st_size,'chart_bytes':chart.stat().st_size}))


if __name__ == '__main__':
    main()
