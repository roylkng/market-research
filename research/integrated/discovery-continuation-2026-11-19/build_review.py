#!/usr/bin/env python3
"""Build the dated research report from retained case calculations.

Requires pandoc and matplotlib. Company calculators use the standard library.
No network access, broker action or experimental-ledger mutation occurs here.
"""
import argparse
import base64
import copy
import datetime as dt
import html
import json
import pathlib
import re
import subprocess

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent


def read(path):
    return json.loads((HERE / path).read_text())


def pct(x):
    return f'{x * 100:.1f}%'


def money(x):
    return f'₹{x:,.0f}'


def markdown_html(path):
    result = subprocess.run(['pandoc', '--from=gfm', '--to=html', '--wrap=none', str(path)],
                            check=True, capture_output=True, text=True)
    prefix = path.stem + "-"
    content = re.sub(r'id="([^"]+)"', lambda m: 'id="' + prefix + m.group(1) + '"', result.stdout)
    return re.sub(r'href="#([^"]+)"', lambda m: 'href="#' + prefix + m.group(1) + '"', content)


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    epi = read('epigral/epigral_calculations.json')
    ei = read('epigral/epigral_model_inputs.json')
    ev = read('epigral/epigral_verdict.json')
    nr = read('nrail/decision_calculations.json')
    kr = read('krsnaa/krsnaa_calculations_2026-11-19.json')
    fd = read('fdc/decision_calculations.json')
    fv = read('fdc/verdict.json')
    pt = read('petronet/petronet_calculations_2026-11-19.json')
    ep = epi['scenarios']['working']
    np = nr['scenarios']['working']
    fp = fd['scenarios']['working']
    kp = next(x for x in kr['scenarios'] if x['name'] == 'working')

    cases = [
        dict(symbol='EPIGRAL', name='Epigral', isin='INE071N01016', price=944.30,
             decision='WATCH_PRICE', depth='COMPLETED_COMPANY_UNDERWRITING_WITH_STATED_GAPS',
             research_entry_reference=[800, 875], horizon_years=ev['model_years_from_reference'],
             working_annual_return_range=ev['current_working_annual_return_range'],
             return_basis='Working financing scenario. Funding access and captive transfer convention are analyst assumptions.',
             reopen='₹800–875 with economics intact, or profitable utilization, controlled spending and demonstrated funding at the same price.',
             note='epigral/epigral_review_2026-11-19.md'),
        dict(symbol='FDC', name='FDC', isin='INE258B01022', price=373.90,
             decision='WATCH_PRICE_BUSINESS', depth='BOUNDED_PRIMARY_SOURCE_BUSINESS_UNDERWRITING',
             research_entry_reference=fv['conditional_price_reference'], horizon_years=5,
             working_annual_return_range=[fp['irr_at_reference']] * 2,
             return_basis='Core business and treasury modeled separately. Full future buyback completion remains conditional.',
             reopen='₹285–311 with business and quality intact, or substantially stronger recurring margins, plant returns and recall remediation at the same price.',
             note='fdc/fdc_review_2026-11-19.md'),
        dict(symbol='NRAIL', name='N R Agarwal', isin='INE740D01017', price=618.80,
             decision='PASS_CURRENT_PRICE', depth='COMPLETED_BOUNDED_PROJECT_AND_FUNDING_UNDERWRITING',
             research_entry_reference=[430, 475], horizon_years=5,
             working_annual_return_range=[np['five_year_irr_at_reference']] * 2,
             return_basis='Explicit debt roll-forward includes remaining project cost, cash interest and working capital. Funding access assumed.',
             reopen='₹430–475 with acceptable funding, or verified earlier/better plant economics. About ₹262cr new-plant Y5 EBITDA reaches 12% if other assumptions hold.',
             note='nrail/nrail_review_2026-11-19.md'),
        dict(symbol='KRSNAA', name='Krsnaa Diagnostics', isin='INE08LI01020', price=511.30,
             decision='WATCH_EVIDENCE_AT_CURRENT_PRICE', depth='CASH_FUNDING_UPDATE_WITH_CONDITIONAL_EPS_SENSITIVITIES',
             research_entry_reference=None, horizon_years=5,
             working_annual_return_range=None,
             conditional_eps_scenario_return=kp['modeled_annual_return'],
             return_basis='Conditional EPS sensitivity only. Growth path is not independently certified as funded.',
             reopen='Actual collections net of new billing, supplier settlements, capex and amortizing debt. Use already-financed capacity before another borrowing-led expansion.',
             note='krsnaa/krsnaa_review_2026-11-19.md'),
        dict(symbol='PETRONET', name='Petronet LNG', isin='INE347G01014', price=325.50,
             decision='WATCH_CAPITAL_ALLOCATION', depth='BOUNDED_FUNDING_AND_REVERSE_PROJECT_CASH_REVIEW',
             research_entry_reference=None, horizon_years=None, working_annual_return_range=None,
             return_basis='No stock fair value or expected return claimed. Project cash requirement is not a stock-return forecast.',
             reopen='Normalized core cash and a funded project spread/utilization case. Cash already committed to expansion cannot be treated as wholly distributable.',
             note='petronet/petronet_review_2026-11-19.md'),
    ]
    cases[1]['event_review_dates'] = fv['next_checkpoints']
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for c in cases:
        c.update(price_date='2026-11-18', series='EQ', decision_date='2026-11-19',
                 reference_is_executable_fill=False, reference_precedes_decision=True,
                 action_or_order_authorized=False, economic_return_outcome=None,
                 false_negative_classification=None, probability_of_outperformance=None)
    register = dict(authored_at_utc=now, research_date_ist='2026-11-19',
                    price_source=read('prices/prices_20261118.json')['source_url'],
                    price_source_sha256=read('prices/prices_20261118.json')['sha256'],
                    research_scope='Targeted continuation, not a complete NSE/BSE universe enumeration.',
                    user_return_hurdle=None, return_preference_sensitivities=[.10, .12, .15],
                    scenarios_are_probabilities=False, cases=cases,
                    review_dates=['2026-12-19', '2027-02-17', '2027-05-18'],
                    performance_protocol='Preserve every dated decision and adverse-to-WAIT move. First available post-publication execution reference, corporate actions, dividends and costs must be verified before any economic-return claim. Original prior-close marks are descriptive only.',
                    historical_learning='18 November frozen-cohort diagnostic retained unchanged. No new backtest, model retraining or validated alpha claim this session.',
                    previous_register='../discovery-upgrade-2026-11-18/decision_register.json')
    (HERE / 'decision_register.json').write_text(json.dumps(register, indent=2) + '\n')

    # These are unweighted scenarios, not statistical confidence intervals.
    chart_rows = [
        ('Epigral', '5.37 years', epi['scenarios']['downside']['annualized_scenario_return'],
         ev['current_working_annual_return_range'][0], ep['annualized_scenario_return'],
         epi['scenarios']['upside']['annualized_scenario_return']),
        ('FDC', '5 years', fd['scenarios']['downside']['irr_at_reference'],
         fp['irr_at_reference'], fp['irr_at_reference'], fd['scenarios']['upside']['irr_at_reference']),
        ('N R Agarwal', '5 years', nr['scenarios']['downside']['five_year_irr_at_reference'],
         np['five_year_irr_at_reference'], np['five_year_irr_at_reference'],
         nr['scenarios']['upside']['five_year_irr_at_reference'])]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
    fig, ax = plt.subplots(figsize=(13, 5.4), dpi=160)
    fig.patch.set_facecolor('#f7f9fc')
    ax.set_facecolor('#f7f9fc')
    for i, (name, horizon, low, midlow, mid, high) in enumerate(chart_rows):
        y = 2 - i
        ax.hlines(y, low * 100, high * 100, color='#c5ceda', linewidth=4, zorder=1)
        ax.scatter([low * 100], [y], c='#bc4942', s=85, zorder=3, marker='v')
        ax.scatter([high * 100], [y], c='#66958a', s=85, zorder=3, marker='^')
        ax.hlines(y, midlow * 100, mid * 100, color='#175e85', linewidth=9, zorder=3)
        ax.scatter([mid * 100], [y], c='#175e85', s=90, zorder=4)
        for x, label, color, va, dy in [
            (low * 100, pct(low), '#a13535', 'top', -.14),
            (high * 100, pct(high), '#376d5e', 'top', -.14),
            ((midlow + mid) * 50, f'{pct(midlow)} to {pct(mid)}' if mid != midlow else pct(mid), '#154a69', 'bottom', .13)]:
            ax.text(x, y + dy, label, color=color, ha='center', va=va, fontsize=11, fontweight='bold')
    ax.set_yticks([2, 1, 0], [f'{x[0]}\n{x[1]}' for x in chart_rows])
    ax.set_xlim(-25, 30)
    ax.set_ylim(-.55, 2.7)
    ax.set_xticks(range(-20, 31, 10), [f'{x}%' for x in range(-20, 31, 10)])
    ax.axvline(0, color='#8493a4', linewidth=1, linestyle='--')
    ax.grid(axis='x', color='#e1e6ed', linewidth=.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.tick_params(axis='both', length=0, pad=12)
    ax.set_xlabel('Modeled annualized return at the verified 18 November reference price', labelpad=16)
    fig.suptitle('Epigral has the strongest working case in this batch', x=.08, y=.98, ha='left', fontsize=18, fontweight='bold', color='#183a52')
    ax.set_title('Red: downside scenario   •   Blue: working scenario   •   Green: upside scenario', loc='left', fontsize=11, color='#52657b', pad=14)
    fig.text(.08, .015, 'Analyst assumptions, not probabilities or forecasts. Krsnaa and Petronet are excluded because their model depth differs.\nNo fees or investor taxes. Epigral range varies recognition of retained cash from 75% to 100%.', fontsize=9, color='#52657b')
    fig.subplots_adjust(left=.15, right=.97, top=.80, bottom=.20)
    chart_path = output / 'Discovery_Scenario_Comparison_2026-11-19.png'
    fig.savefig(chart_path, bbox_inches='tight')
    plt.close(fig)

    summary = f'''# Discovery continuation: 19 November 2026

**Epigral is the strongest new candidate. It remains WATCH_PRICE at ₹944.30.** The working financing scenario gives {pct(ev['current_working_annual_return_range'][0])}–{pct(ep['annualized_scenario_return'])} annually through March 2032. A conditional ₹800–875 research range offers more room for operating or valuation disappointments. No universal 15% hurdle has been imposed. A 10% return preference can support accepting more of today's risk, but that is different from finding a compelling concentrated investment.

This targeted continuation completes the unfinished N R Agarwal funding case, adds a full Epigral case, underwrites FDC's underlying business independently of its expired record-date opportunity, updates Krsnaa's collection/funding economics, and bounds Petronet's capital-allocation question. It does not establish that the whole Indian market lacks attractive investments.

## The decisions

| Company | Official 18 Nov reference | Working model | Decision and condition |
|---|---:|---:|---|
| Epigral | ₹944.30 | {pct(ev['current_working_annual_return_range'][0])}–{pct(ep['annualized_scenario_return'])}, 5.37 years | WATCH_PRICE. Review ₹800–875 with economics intact, or stronger evidence at the same price. |
| FDC | ₹373.90 | {pct(fp['irr_at_reference'])}, 5 years | WATCH_PRICE for the business. Conditional ₹285–311 for 10–8% modeled returns, or materially better owner economics. At about ₹261 the working return is 12%. No tender premium for a new buyer. |
| N R Agarwal | ₹618.80 | {pct(np['five_year_irr_at_reference'])}, 5 years | PASS_CURRENT_PRICE. Conditional ₹430–475 and satisfactory project funding. |
| Krsnaa | ₹511.30 | {pct(kp['modeled_annual_return'])} conditional EPS sensitivity | WATCH_EVIDENCE. This is not a funded growth forecast. Net collections, supplier payments, capex and debt amortization decide the case. |
| Petronet LNG | ₹325.50 | No stock-return estimate | WATCH_CAPITAL_ALLOCATION. Normalize core cash and establish incremental project economics. |

Returns are explicit analyst scenarios before trading costs and investor taxes. Entry references are not orders, floors or personal policy. Price is the latest original archive verified for this research, not a claimed 19 November close or executable post-decision fill. The first 19 November final-archive probe returned 404 and is retained in the price receipt.

## Why Epigral leads, and why the price still matters

H1 cash after reported capex, finance and lease payments is ₹24.73cr, or ₹19.42cr after the separate renewable investment. Proper trailing owner earnings are ₹284.88cr, giving 14.30× reported P/E. The apparently cheaper 12.36× measure simply doubles H1. The old deferred-tax credit cancels in the trailing calculation and must not be subtracted again.

The model funds the future spending path in its arithmetic, but actual access to that funding remains an assumption. The independent review identifies approximately ₹235cr of new or replacement borrowing in H2 FY27 and ₹75cr in FY28 before buffers. Core and downstream activity use an explicit transfer-price convention. Their aggregate turnover is not independently verified consolidated external revenue.

At the current reference, the working 12% present value is ₹946.59, essentially the price. A 6× exit instead of 7× gives 9.47% annualized. A 19% core margin instead of 21% gives 9.72%. A 10% reduction in aggregate modeled EBITDA gives 9.21%. The downside terminal price is ₹492.94, approximately 48% below the reference, with a −11.41% annualized scenario. That is an end-horizon scenario, not a maximum drawdown or near-term target.

Competition is observable. Grasim's 50kt CPVC plant started commercially in August, its 50kt ECH plant in October, and DCM's total 52kt ECH capacity was commissioned in April. Epigral's own CPVC utilization was 60–65% before its doubling. An expanding Indian market does not ensure that all producers earn attractive margins.

The completed [company note](epigral/epigral_review_2026-11-19.md), [independent review](epigral/epigral_independent_review.md) and [peer response](epigral/epigral_peer_review_response.json) distinguish these facts from assumptions. The author accepted the transfer-accounting and gross-funding clarifications. The original scenario arithmetic reproduced independently.

## What changed in the other cases

**FDC:** the business now has a priced cash model, beyond the already completed tender decision. Current investments and cash cannot be credited while capitalizing all treasury income again. Full buyback completion reduces both cash and share count. Growth and maintenance spending remain in the forecast. The working result is about {pct(fp['irr_at_reference'])}, despite the debt-free balance sheet. Removing all working portfolio haircuts and both liquidity/claims buffers still produces only about 4.57% in the independent sensitivity. Its annual report also records product recalls and a US profit-share impact, so brand age does not establish flawless execution. The [case note](fdc/fdc_review_2026-11-19.md) carries quality, tax-refund, treasury and capex details. The historical recall record is not a finding of fraud or a company-wide import ban.

**N R Agarwal:** the cash-source blocker is closed. H1 cash after capex, non-lease interest and full lease payments is approximately minus ₹0.92cr. The next project is about ₹1,500cr, compared with approximately ₹1,053cr equity capitalization. About ₹1,250cr future non-interest project cash is an explicit model assumption, with an overlap/interest sensitivity retained. Capitalizing the earnings rebound without future funding would overstate value. The [note](nrail/nrail_review_2026-11-19.md) gives a same-price path if the plant can support roughly ₹262cr year-five EBITDA with other assumptions fixed. Borrowing authorization is not a bank commitment.

**Krsnaa:** earlier funding work is preserved rather than recounted as new. The added useful findings are ageing and repayment economics. Receivables considered good and aged one to two years rose to ₹38.33cr at March from ₹0.28cr the prior year. September net receivables were ₹474.56cr. A ₹200cr collection expectation does not imply a ₹200cr reduction if the business also makes new credit sales. The ADB debt amortizes, rather than giving seven years of free cash. The [note](krsnaa/krsnaa_review_2026-11-19.md) keeps a same-price reopening route through cash from existing capacity.

**Petronet:** the approximately 10.5× consolidated trailing P/E is not sufficient to establish a bargain. The arithmetic remaining petrochemical budget is ₹17,385cr. A transparent remaining-investment illustration requires roughly ₹2,562cr annual after-tax project cash at a 12% discount rate, rising to ₹3,443cr with a 20% overrun and one-year delay. This is a project cash requirement, not stock fair value. Vessel claims, tax timing, inventory/commercial gains and capital committed elsewhere also matter. The [bounded review](petronet/petronet_review_2026-11-19.md) leaves stock expected return null.

## The improvement in the process

The earlier historical work showed why attractive stories and lane counts cannot be treated as proven return rankings. Today's response is to make the company's cash path and the price's requirements explicit, then challenge them independently. Negative cash after expansion is investigated as a funding question. It is not an automatic rejection of a growing business. Conversely, cash and low P/E are not allowed to hide future commitments or treasury double counting.

Each case has a specific price or operating event that can change the decision. Unknown employee or customer reputation is disclosed without indefinitely preventing a supported price decision. The registry preserves current judgments and leaves future outcomes null. The 18 November frozen-cohort audit remains unchanged. No new blind backtest, calibrated win rate or investment alpha was established today.

## Portfolio context and next decisive work

Official 18 November context: Nifty 50 25,227.95 and Nifty 500 23,630.25. Published P/Es were 20.55× and 22.07×. These are context, not return forecasts or an automatic index recommendation. Five company watches do not constitute an all-market cash allocation. Portfolio weights and the user's return preference remain unspecified.

Priority among this batch is Epigral's profitable post-commissioning ramp and funding access. Krsnaa has the most useful same-price collection test. FDC and N R Agarwal leave the unfinished-file queue and reopen only when economics or price changes. Petronet needs a normalized core-cash and project-value bridge before promotion. Broader discovery continues beyond this selected batch, including businesses with less capital-intensive growth.

The [dated decision register](decision_register.json) sets review dates of 19 December 2026, 17 February 2027 and 18 May 2027. These are research checkpoints, not new scheduled jobs. Preserve gains after WAIT as well as avoided losses. Prior-close reference marks must not be backfilled as trades. The prior five completed 18 November cases remain unchanged until material new evidence or price warrants reopening.

## Evidence and reproducibility

The case folders contain original-source URLs and SHA-256 receipts, reproducible calculations, funding assumptions and review limitations. The accompanying evidence archive also contains retained original source bytes with a bundle index. Human-readable company notes explain all material formulas. Krsnaa's conditional EPS test and Petronet's project reverse test remain visibly different from full per-share cash forecasts. No customer interviews, lender confirmations, regulatory legal opinions or return probabilities are invented.
'''
    (HERE / 'README.md').write_text(summary)
    (HERE.parent / 'discovery-continuation-2026-11-19.md').write_text(summary.replace('](epigral/', '](discovery-continuation-2026-11-19/epigral/').replace('](fdc/', '](discovery-continuation-2026-11-19/fdc/').replace('](nrail/', '](discovery-continuation-2026-11-19/nrail/').replace('](krsnaa/', '](discovery-continuation-2026-11-19/krsnaa/').replace('](petronet/', '](discovery-continuation-2026-11-19/petronet/').replace('](decision_register.json)', '](discovery-continuation-2026-11-19/decision_register.json)'))

    detail_blocks = []
    for c in cases:
        content = markdown_html(HERE / c['note'])
        detail_blocks.append(f'<details class="case" id="{c["symbol"].lower()}"><summary><span>{html.escape(c["name"])}</span><span class="badge">{html.escape(c["decision"].replace("_", " "))}</span></summary><div class="casebody">{content}</div></details>')
    detail_blocks.append('<details class="case"><summary><span>Epigral independent challenge</span><span class="badge">Accepted clarifications</span></summary><div class="casebody">' + markdown_html(HERE / 'epigral/epigral_independent_review.md') + '</div></details>')
    if (HERE / 'fdc/fdc_independent_review.md').exists():
        detail_blocks.append('<details class="case"><summary><span>FDC independent challenge</span><span class="badge">Treasury and business</span></summary><div class="casebody">' + markdown_html(HERE / 'fdc/fdc_independent_review.md') + '</div></details>')
    table_rows = []
    for c in cases:
        ret = c['working_annual_return_range']
        value = (f'{pct(ret[0])}–{pct(ret[1])}' if ret[0] != ret[1] else pct(ret[0])) if ret else ('7.1% conditional EPS only' if c['symbol'] == 'KRSNAA' else 'Not estimated')
        table_rows.append(f'<tr><td><a href="#{c["symbol"].lower()}" class="casejump">{html.escape(c["name"])}</a></td><td>₹{c["price"]:,.2f}</td><td>{value}</td><td>{html.escape(c["decision"].replace("_", " "))}</td><td>{html.escape(c["reopen"])}</td></tr>')
    # Terminal assumptions vary. Underlying working cash operations stay fixed.
    simulation = dict(shares=ei['shares'] / 1e7, ebitda=ep['rows'][-1]['post_lease_ebitda'],
                      debt=ep['rows'][-1]['closing_net_debt'],
                      flows=copy.deepcopy(ep['cashflows_per_share']),
                      original_terminal=ep['terminal_share_value'])
    chart64 = base64.b64encode(chart_path.read_bytes()).decode()
    core_css = '''
    :root{--ink:#163247;--muted:#5b6f82;--accent:#12647c;--line:#dce4eb;--paper:#fff;--bg:#edf2f6;--gold:#8d6519}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:var(--accent)}
    .wrap{max-width:1180px;margin:auto;padding:36px 24px 70px}header{background:linear-gradient(120deg,#12384e,#126176);color:white;border-radius:20px;padding:38px 42px}header p{max-width:870px;color:#e2f1f5}h1{font-size:clamp(30px,4.4vw,48px);line-height:1.12;margin:12px 0 20px;letter-spacing:-.035em}h2{font-size:26px;line-height:1.25;margin:4px 0 18px}h3{font-size:19px;margin:4px 0 12px}.eyebrow{text-transform:uppercase;letter-spacing:.13em;font-weight:700;font-size:12px}.meta{font-size:13px;color:#d5e8ee}.nav{display:flex;gap:20px;flex-wrap:wrap;margin:22px 0}.nav a{font-weight:700;text-decoration:none}.panel{background:var(--paper);border:1px solid var(--line);border-radius:16px;margin:22px 0;padding:26px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.metric{background:#f2f7f9;padding:18px;border-radius:12px}.metric b{font-size:30px;display:block;line-height:1.2;margin:8px 0}.muted,.small{color:var(--muted)}.small{font-size:13px}.note{border-left:4px solid #c39237;background:#faf5e9;padding:14px 18px;border-radius:0 10px 10px 0}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.045em;background:#f5f8fa}th,td{padding:13px 12px;border-bottom:1px solid var(--line);vertical-align:top}td:nth-child(2){white-space:nowrap}td:first-child{font-weight:700}.chart{width:100%;height:auto;display:block}.controls{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin:24px 0}.controls label{display:block;font-size:14px;font-weight:700}.controls output{display:block;font-size:24px;margin:6px 0;color:var(--accent)}input[type=range]{width:100%;accent-color:var(--accent)}.results{display:grid;grid-template-columns:1.2fr 1fr;gap:20px}.big{font-size:48px;font-weight:750;line-height:1.15;letter-spacing:-.04em}.case{background:white;border:1px solid var(--line);border-radius:12px;margin:12px 0}.case>summary{padding:20px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:18px;font-weight:750}.badge{font-size:11px;font-weight:700;border:1px solid #c7d9e0;color:var(--accent);background:#f1f7fa;padding:5px 9px;border-radius:7px;text-transform:uppercase;letter-spacing:.04em}.casebody{padding:4px 24px 28px;font-size:15px}.casebody h1{font-size:28px;letter-spacing:-.02em}.casebody h2{font-size:22px;margin:30px 0 12px}.casebody h3{font-size:18px;margin:23px 0 10px}.casebody table{display:block;overflow:auto}.casebody code{word-break:break-word;font-size:12px}.casebody a{overflow-wrap:anywhere}.steps{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.steps article{background:#f5f8fa;padding:18px;border-radius:10px}.steps p{margin:0}.footer{padding:10px 5px;color:var(--muted);font-size:12px}button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px 15px;cursor:pointer;font:inherit}button:focus-visible,a:focus-visible,summary:focus-visible,input:focus-visible{outline:3px solid #e5ac40;outline-offset:3px}li{margin:6px 0}p{margin:12px 0}.claim{color:#12647c;font-weight:700}
    @media(max-width:760px){.wrap{padding:16px 12px 35px}header{padding:25px 24px}.panel{padding:20px}.grid,.controls,.results,.steps{grid-template-columns:1fr}.case>summary{align-items:flex-start;flex-direction:column}.big{font-size:42px}.casebody{padding:0 16px 20px}th,td{min-width:110px}.nav{gap:12px}}
    @media print{body{background:#fff}.wrap{max-width:none;padding:0}header{background:#fff;color:#163247;border:1px solid #ddd}header p,.meta{color:#163247}.nav,.controls,button{display:none}.case{break-inside:avoid}.panel{break-inside:avoid}.badge{font-size:9px}}
    '''
    doc = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Investment discovery | 19 November 2026</title><style>''' + core_css + '''</style></head><body><main class="wrap">
    <header><div class="eyebrow">Investment research • 19 November 2026</div><h1>Epigral leads this batch.<br>The price still matters.</h1><p>Five decisions advanced. Epigral offers the strongest new working case, but its current price leaves little room for weaker margins or a lower exit valuation. The next step is specific price and operating evidence, not another generic research checklist.</p><div class="meta">Official reference closes: 18 November • Research only • No universal 15% hurdle • Scenarios are not probabilities</div></header>
    <nav class="nav"><a href="#board">Decision board</a><a href="#scenarios">Scenarios</a><a href="#explorer">Price explorer</a><a href="#changed">What changed</a><a href="#dossiers">Complete company notes</a></nav>
    <section class="panel"><div class="grid"><div class="metric"><span>Epigral working annual return</span><b>11.2–12.1%</b><span class="small">At ₹944.30 through March 2032. Future funding access remains assumed.</span></div><div class="metric"><span>Conditional research range</span><b>₹800–875</b><span class="small">Business and funding must remain intact. A lower price alone is insufficient.</span></div><div class="metric"><span>Epigral downside terminal value</span><b>₹493</b><span class="small">Approximately 48% below the reference. This is not a maximum drawdown estimate.</span></div></div><p class="note"><strong>No new high-conviction BUY.</strong> That conclusion applies to this targeted batch. It does not establish that the entire market is unattractive or that the portfolio should stay in cash.</p></section>
    <section class="panel" id="board"><h2>Decisions with explicit reopening conditions</h2><p class="muted">Three per-share cash models, one conditional earnings sensitivity, and one bounded project review. Model depths are intentionally visible.</p><div class="scroll"><table><thead><tr><th>Company</th><th>Reference</th><th>Working annual scenario</th><th>Disposition</th><th>What changes it</th></tr></thead><tbody>''' + ''.join(table_rows) + '''</tbody></table></div><p class="small">Entry ranges are research references, not orders or floors. Current prices are dated. No shares were bought or sold.</p></section>
    <section class="panel" id="scenarios"><h2>Compare the assumptions, not just the point estimate</h2><img class="chart" alt="Scenario annualized returns. Epigral downside minus 11.4%, working 11.2 to 12.1%, upside 19.7%. FDC and N R Agarwal modeled separately over five years. These are unweighted scenarios, not confidence intervals." src="data:image/png;base64,''' + chart64 + '''"><p>Epigral's 12% working present value is <strong>₹946.59</strong>, almost equal to the reference. The independent review reproduced its three original scenarios and made the captive-feedstock convention and gross refinancing needs explicit.</p></section>
    <section class="panel" id="explorer"><h2>Epigral: what must the price compensate for?</h2><p class="muted">Change the entry price, exit enterprise multiple, or recognition of accumulated cash. Operating sales, margins, capex, taxes and debt path stay at the working assumptions. This is a valuation sensitivity, not a forecast.</p><div class="controls"><label for="entry">Entry price <output id="entryLabel"></output><input id="entry" type="range" min="650" max="1200" step="0.1" value="944.3"></label><label for="multiple">Exit multiple of EBITDA after cash leases <output id="multipleLabel"></output><input id="multiple" type="range" min="5" max="8" step="0.25" value="7"></label><label for="cash">Value credited to retained cash <output id="cashLabel"></output><input id="cash" type="range" min="0.5" max="1" step="0.05" value="0.75"></label></div><div class="results"><div class="metric"><span>Annualized scenario return</span><div class="big" id="irrValue"></div><p class="small">Includes the assumed dividends. Final valuation date: 31 March 2032.</p></div><div><table><thead><tr><th>Return preference</th><th>Present value</th></tr></thead><tbody id="pvRows"></tbody></table><p class="small">10%, 12% and 15% are sensitivities. No personal minimum has been inferred.</p></div></div><p class="note">A 6× exit gives about 9.5% at the reference when all retained cash receives value. Reducing the core operating margin from 21% to 19% gives about 9.7% in the separate operating stress. Roughly 98% of baseline present value arrives in the terminal share value.</p><button type="button" id="reset">Reset assumptions</button><noscript><p>JavaScript is disabled. Baseline working return is 11.17–12.05%. Full-cash working present values at 10/12/15% are ₹1,042/947/822. All company notes below remain readable.</p></noscript></section>
    <section class="panel" id="changed"><h2>What became clearer</h2><div class="steps"><article><h3>Expansion has to earn and fund its growth</h3><p>Epigral's model allows future borrowing, with gross replacement funding exposed. N R Agarwal's ₹1,500cr project materially changes the cheap-earnings story. A borrowing authorization is not a lender commitment.</p></article><article><h3>Cash and earnings need different treatment</h3><p>FDC's treasury is modeled separately from core operations. The buyback reduces cash and shares together. Its first full business model gives about 4% annually in the working case at the reference.</p></article><article><h3>Collections must exceed fresh credit billing</h3><p>Krsnaa's ₹200cr collection expectation cannot simply be subtracted from receivables. New bills, suppliers, equipment spending and amortizing ADB debt determine cash available to owners.</p></article><article><h3>Low P/E can hide capital already committed</h3><p>Petronet has a large remaining petrochemical budget. The reverse project test asks what after-tax cash that investment must earn. It deliberately leaves stock fair value unestimated.</p></article></div><p class="small">Source-backed facts, management claims and analyst scenarios are separated in the complete notes below. Historical recall evidence is a quality issue to investigate, not a blanket misconduct finding.</p></section>
    <section class="panel"><h2>The historical lesson now changes current work</h2><p>The earlier frozen-cohort audit did not validate the old opportunity-lane ranking. Today's cases therefore stand on explicit company economics and independently challenged assumptions. Negative expansion cash is no longer an automatic veto. Known misses and gains after WAIT remain in the record.</p><p><strong>Confidence improved in accounting and decision specificity.</strong> No new blind backtest, calibrated success probability, or demonstrated investment alpha was established. The five new dated decisions have null future outcomes and review checkpoints on 19 December, 17 February and 18 May.</p><p class="small">Market context from 18 November: Nifty 50 at 25,227.95 and Nifty 500 at 23,630.25. These levels and their published valuations are not expected returns. Broad exposure and portfolio allocation remain separate decisions.</p></section>
    <section id="dossiers"><h2>Complete research, sources and limitations</h2><p class="muted">Expand each case for the original cash reconciliation, assumptions, leadership and quality coverage, sensitivities and exact source URLs.</p>''' + ''.join(detail_blocks) + '''</section>
    <section class="panel"><h2>Next evidence with the highest decision value</h2><ol><li><strong>Epigral:</strong> profitable utilization after commissioning, consolidated recurring EBITDA, controlled cash spending and actual financing access.</li><li><strong>Krsnaa:</strong> original collection and receivables bridge after new billing, supplier settlements, equipment spending and principal repayments.</li><li><strong>FDC and N R Agarwal:</strong> price or operating evidence that changes the completed valuation, rather than repeatedly reopening unchanged files.</li><li><strong>Fresh discovery:</strong> continue beyond this batch, including businesses where growth consumes less incremental capital.</li></ol><p class="small">Datamatics, Cosmo First, GESHIP, Sandesh and CMS retain their separately dated 18 November judgments until material price or evidence changes. This report does not silently revise those historical entries.</p></section>
    <footer class="footer">Research date 19 November 2026, Asia/Calcutta. Models use official 18 November reference closes and the latest disclosed financial statements checked for this review. Costs, investor taxes, execution and portfolio sizing are not modeled. Sources and reproducible calculations accompany the evidence archive. This file works offline and contains the complete company notes.</footer>
    </main><script id="simulationData" type="application/json">''' + json.dumps(simulation).replace('</',r'<\/') + '''</script><script>
    const model = JSON.parse(document.getElementById('simulationData').textContent);
    function priceFlows(mult, cashFraction) {
      const rows = model.flows.map(x => [x[0], x[1]]);
      rows[rows.length - 1][1] -= model.original_terminal;
      const terminal = Math.max(0, model.ebitda * mult - Math.max(model.debt, 0) + Math.max(-model.debt, 0) * cashFraction) / model.shares;
      rows[rows.length - 1][1] += terminal;
      return rows;
    }
    function presentValue(flows, rate) { return flows.reduce((v, x) => v + x[1] / Math.pow(1 + rate, x[0]), 0); }
    function annualReturn(flows, price) {
      let lo = -.99, hi = 3;
      for (let i = 0; i < 160; i++) { const mid = (lo + hi) / 2; if (presentValue(flows, mid) > price) lo = mid; else hi = mid; }
      return (lo + hi) / 2;
    }
    const rupee = x => '₹' + x.toLocaleString('en-IN', {maximumFractionDigits: 0});
    function updateExplorer() {
      const entry = +document.getElementById('entry').value, multiple = +document.getElementById('multiple').value, cash = +document.getElementById('cash').value;
      document.getElementById('entryLabel').textContent = '₹' + entry.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
      document.getElementById('multipleLabel').textContent = multiple.toFixed(2) + '×';
      document.getElementById('cashLabel').textContent = Math.round(cash * 100) + '%';
      const flows = priceFlows(multiple, cash);
      document.getElementById('irrValue').textContent = (annualReturn(flows, entry) * 100).toFixed(2) + '%';
      document.getElementById('pvRows').innerHTML = [.10, .12, .15].map(r => '<tr><td>' + Math.round(r * 100) + '%</td><td>' + rupee(presentValue(flows, r)) + '</td></tr>').join('');
    }
    ['entry', 'multiple', 'cash'].forEach(id => document.getElementById(id).addEventListener('input', updateExplorer));
    document.getElementById('reset').addEventListener('click', () => {document.getElementById('entry').value = '944.3'; document.getElementById('multiple').value = '7'; document.getElementById('cash').value = '.75'; updateExplorer();});
    document.querySelectorAll('.casejump').forEach(a => a.addEventListener('click', () => {const target = document.querySelector(a.getAttribute('href')); if (target) target.open = true;}));
    updateExplorer();
    </script></body></html>'''
    path = output / 'Investment_Discovery_Review_2026-11-19.html'
    path.write_text(doc)
    (output / 'decision_register_2026-11-19.json').write_text(json.dumps(register, indent=2) + '\n')
    print(json.dumps({'report': str(path), 'chart': str(chart_path), 'cases': len(cases), 'html_bytes': path.stat().st_size}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path, required=True)
    build(parser.parse_args().output)
