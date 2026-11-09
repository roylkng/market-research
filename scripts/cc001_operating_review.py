"""Decision-first review of retained CC001 reports, without network or state writes.

Priorities are diligence tasks, not return scores. Historical decisions are not
backdated paper entries. Whole-source coverage and investment skill stay unproven.
"""
from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, timestamp
from marketlab.company_change_store import loads_unique, now_utc

FILES = ('latest', 'checkpoint', 'business-changes', 'cash-underwriting', 'decision-context', 'news-inbox')
POLICY = {
    'version': 'CC001-DECISION-FIRST-REVIEW-v1',
    'interpretation': 'DILIGENCE_ALLOCATION_NOT_ALPHA_OR_BUY_RANKING',
    'maximum_live_cases': 5,
    'unfinished_case_slots': 1,
    'maximum_cash_cue_slots': 3,
    'exploration_slots': 2,
    'daily_financial_document_budget': 40,
    'daily_announcement_budget': 4,
    'daily_context_budget': 3,
    'source_observation_stale_hours': 24,
    'order': 'NEVER_ENRICHED_THEN_OLDEST_CONTEXT_THEN_SOURCE_HASH',
}
EXCEPTION_FLAGS = {'PRETAX_EXCEPTIONAL_ITEM_PRESENT', 'OTHER_INCOME_AT_LEAST_REPORTED_PBT', 'REPORTED_PRETAX_LOSS'}


def checked_report(value, time_key, cutoff):
    if canonical_hash({k: v for k, v in value.items() if k != 'report_sha256'}) != value.get('report_sha256'):
        raise ChangeError('retained report hash mismatch')
    if timestamp(value[time_key]) > cutoff:
        raise ChangeError('report unavailable at review cutoff')
    return value


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def identity(card):
    return card['symbol'], card['isin'], card['scope']


def build(inputs: dict, decisions: list, as_of: str) -> dict:
    cutoff = timestamp(as_of)
    latest, checkpoint = inputs['latest'], inputs['checkpoint']
    if timestamp(latest['recorded_at']) > cutoff:
        raise ChangeError('workspace state is newer than the cutoff')
    reports = {}
    for name, clock, link in (
        ('business-changes', 'as_of', 'business_change_sha256'),
        ('cash-underwriting', 'evaluated_at', 'cash_underwriting_sha256'),
        ('decision-context', 'as_of', 'decision_context_sha256'),
        ('news-inbox', 'as_of', 'news_reader_sha256'),
    ):
        report = checked_report(inputs[name], clock, cutoff)
        # A failed lane may retain a partial report, but cannot be called healthy.
        if latest.get(link) is not None and report['report_sha256'] != latest[link]:
            raise ChangeError('export does not match the saved-state receipt')
        reports[name] = report
    business, cash = reports['business-changes'], reports['cash-underwriting']
    # Snapshot hashes include evaluation clocks, so sequential exports can differ.
    # Use the saved-run receipt plus exact per-card source/extraction identity.
    for report, clock in ((business, 'as_of'), (cash, 'evaluated_at')):
        if timestamp(report[clock]) > timestamp(latest['recorded_at']):
            raise ChangeError('export is newer than its saved-state receipt')
    if (latest.get('business_change_status') != 'SUCCESS' or latest.get('cash_underwriting_status') != 'SUCCESS'
            or not latest.get('business_change_sha256') or not latest.get('cash_underwriting_sha256')):
        raise ChangeError('successful business and cash exports required for allocation')
    changes = {}
    for card in business['cards']:
        key = identity(card)
        if key in changes:
            raise ChangeError('ambiguous business card')
        changes[key] = card
    issuers, seen = {}, set()
    for card in cash['cards']:
        key = identity(card)
        if key in seen:
            raise ChangeError('ambiguous cash card')
        seen.add(key)
        previous = issuers.get(card['isin'])
        order = (card['analysis']['period_end'], card['scope'] == 'CONSOLIDATED')
        if previous is None or order > (previous['analysis']['period_end'], previous['scope'] == 'CONSOLIDATED'):
            issuers[card['isin']] = card
    contexts = {}
    for card in reports['decision-context']['cards']:
        ident = card['identity']
        key = (ident['symbol'], ident['isin'], ident['scope'])
        if key in contexts:
            raise ChangeError('ambiguous retained company context')
        if timestamp(card['context_observed_at']) > cutoff:
            raise ChangeError('company context is in the future')
        contexts[key] = card
    if not isinstance(decisions, list):
        raise ChangeError('carried decisions must be a list')
    journal, memo_issuers = [], {}
    for record in decisions:
        if record.get('evidence_class') != 'HISTORICAL_CARRY_FORWARD_NOT_PROSPECTIVE_ENTRY':
            raise ChangeError('legacy memo cannot become a prospective trade')
        if record.get('disposition') not in {'WAIT', 'PASS', 'RESEARCH_ONLY'}:
            raise ChangeError('unsupported carried-forward decision')
        if timestamp(record['decision_published_at']) > cutoff:
            raise ChangeError('decision unavailable at cutoff')
        key = (record['symbol'], record['isin'])
        if key in memo_issuers or record.get('live_capital_allowed') is not False:
            raise ChangeError('duplicate or capital-enabled carried-forward decision')
        if record.get('case_depth') not in {'FULL_UNDERWRITING', 'PRELIMINARY_SCREEN'}:
            raise ChangeError('case depth must distinguish full underwriting from a screen')
        if type(record.get('resume_underwriting', False)) is not bool:
            raise ChangeError('unfinished-case marker must be explicit Boolean')
        if record.get('resume_underwriting') and record['case_depth'] != 'PRELIMINARY_SCREEN':
            raise ChangeError('only an unfinished preliminary case can use the resume slot')
        if not isinstance(record.get('reviewed_source_hashes'), list) or not record['reviewed_source_hashes']:
            raise ChangeError('reviewed filing hashes required')
        memo_issuers[key] = record
        journal.append(record)
    candidates = []
    for card in issuers.values():
        key, data = identity(card), card['analysis']
        change, context = changes.get(key), contexts.get(key)
        flags = set(change.get('flags', [])) if change else set()
        same_source = bool(change and change.get('current') and change['current']['raw_sha256'] == card['raw_sha256']
                           and change['period_end'] == data['period_end']
                           and change['current']['extraction_id'] == card['prior_extraction_id'])
        metrics = change.get('metrics', {}) if same_source else {}
        growth = metrics.get('revenue', {}).get('growth_fraction')
        qprofit = metrics.get('pbt', {}).get('current')
        cue = (same_source and data['disposition'] == 'CASH_COVERED_SPECIFIED_CAPEX'
               and positive(growth) and positive(qprofit) and not flags.intersection(EXCEPTION_FLAGS))
        yo = data.get('same_source_year_ago', {}).get('revenue', {}).get('growth_fraction')
        known = change['current']['known_at'] if same_source else card['parsed_at']
        if timestamp(known) > cutoff:
            raise ChangeError('candidate evidence is in the future')
        if card['financial_fact_review'] == 'REJECT':
            lane = 'REJECTED_EXTRACTION_REVIEW'
        elif data['disposition'] == 'RECONCILE_SOURCE_FIRST':
            lane = 'ACCOUNTING_RECONCILIATION'
        elif cue:
            lane = 'CASH_SUPPORTED_SEQUENTIAL_CUE'
        elif data['disposition'] == 'REINVESTMENT_FUNDING_REVIEW':
            lane = 'REINVESTMENT_DILIGENCE'
        else:
            lane = 'EXPLORATION'
        gaps = ['Confirm business model before applying industrial cash metrics, especially to financial firms.',
                'Check restatements, working capital, recurring earnings, dilution, price and liquidity.']
        if yo is None:
            gaps.insert(0, 'Retrieve exact year-ago periods. Sequential improvement is not seasonality-adjusted growth.')
        if card['financial_fact_review'] != 'ACCEPT':
            gaps.append('The retained financial extraction is not accepted as reviewed.')
        if not same_source:
            gaps.append('No same-source/same-period business card. No mixed-document growth cue is used.')
        if flags.intersection(EXCEPTION_FLAGS):
            gaps.append('Exceptional items, other income or a reported loss require reconciliation.')
        previous_case = memo_issuers.get((key[0], key[1]))
        carried = bool(previous_case and card['raw_sha256'] in previous_case['reviewed_source_hashes'])
        candidates.append({
            'symbol': key[0], 'isin': key[1], 'scope': key[2], 'period_end': data['period_end'],
            'lane': lane, 'reported_cash_surplus_crore': data['cfo_less_specified_capex_crore'],
            'cash_period_start': data['period_start'], 'sequential_revenue_growth': growth,
            'same_source_year_ago_revenue_growth': yo,
            'source_url': card['source_url'], 'raw_sha256': card['raw_sha256'],
            'source_review_status': card['financial_fact_review'], 'gaps': gaps,
            'context_observed_at': context['context_observed_at'] if context else None,
            'existing_company_memo': carried, 'resume_underwriting': bool(previous_case and previous_case.get('resume_underwriting')),
            'reopened_for_new_filing': bool(previous_case and not carried), 'buy_approved': False,
        })
    def priority(card):
        known = card['context_observed_at']
        return (known is not None, timestamp(known).timestamp() if known else 0,
                canonical_hash([POLICY['version'], card['isin'], card['raw_sha256']]))
    resumable = sorted((c for c in candidates if c['resume_underwriting']
                        and c['source_review_status'] != 'REJECT'
                        and c['lane'] != 'ACCOUNTING_RECONCILIATION'), key=priority)
    selected = resumable[:POLICY['unfinished_case_slots']]
    used = {c['isin'] for c in selected}
    eligible = [c for c in candidates if not c['existing_company_memo']
                and c['source_review_status'] != 'REJECT' and c['isin'] not in used]
    cues = sorted((c for c in eligible if c['lane'] == 'CASH_SUPPORTED_SEQUENTIAL_CUE'), key=priority)
    cue_slots = POLICY['maximum_live_cases'] - POLICY['exploration_slots'] - len(selected)
    selected += cues[:min(POLICY['maximum_cash_cue_slots'], cue_slots)]
    used = {c['isin'] for c in selected}
    # Reserve breadth. Accounting-problem cases stay visible but do not consume
    # the ordinary exploratory slots. No source omission becomes a stock rejection.
    pool = sorted((c for c in eligible if c['isin'] not in used and c['lane'] not in {'ACCOUNTING_RECONCILIATION', 'CASH_SUPPORTED_SEQUENTIAL_CUE'}), key=priority)
    selected += pool[:POLICY['exploration_slots']]
    counts = latest['coverage']['counts']
    news = reports['news-inbox']
    blocked_storage = any(d.get('reason') == 'ACTIVE_STORAGE_HEADROOM_REQUIRED' for d in news['deferred'])
    age = (cutoff - timestamp(latest['recorded_at'])).total_seconds() / 3600
    selected_ids = {c['isin'] for c in selected}
    result = {
        'engine': POLICY['version'], 'evaluated_at': as_of, 'policy': POLICY,
        'input_hashes': {name: canonical_hash(inputs[name]) for name in FILES},
        'snapshot_recorded_at': latest['recorded_at'], 'snapshot_age_hours': age,
        'source_commit': latest['source_commit'], 'source_run_url': latest['run_url'],
        'health': {'snapshot_stale': age > POLICY['source_observation_stale_hours'],
                   'news_status': latest['news_reader_status'], 'news_storage_blocked': blocked_storage,
                   'checkpoint_expanded_bytes': checkpoint['expanded_bytes'],
                   'checkpoint_limit_bytes': 128 * 1024 * 1024,
                   'raw_source_deletion_or_limit_increase': False},
        'funnel': {'processed_financial_documents': counts.get('EXTRACTED', 0),
                   'pending_financial_documents': counts.get('PENDING', 0),
                   'failed_financial_documents': counts.get('FAILED', 0),
                   'financial_issuers': len(issuers), 'scope_cards': len(cash['cards']),
                   'unreviewed_period_records': latest['unreviewed'],
                   'retained_price_contexts': len(contexts),
                   'same_source_yoy_revenue_available_issuers': sum(c['same_source_year_ago_revenue_growth'] is not None for c in candidates),
                   'received_announcements': news['coverage']['announcements_in_received_queue'],
                   'read_announcements': news['coverage']['original_attachments_read'],
                   'unread_announcements': news['coverage']['readings_remaining'],
                   'identity_blocked_announcements': news['coverage']['identity_or_evidence_blocked'],
                   'carried_forward_company_decisions': len(journal),
                   'full_underwriting_memos': sum(r['case_depth'] == 'FULL_UNDERWRITING' for r in journal),
                   'preliminary_screens': sum(r['case_depth'] == 'PRELIMINARY_SCREEN' for r in journal),
                   'explicit_unfinished_cases': sum(r.get('resume_underwriting', False) for r in journal), 'new_buy_decisions': 0},
        'capacity_lower_bounds_no_new_arrivals': {
            'news_processing_runs': math.ceil(news['coverage']['readings_remaining'] / POLICY['daily_announcement_budget']),
            'financial_processing_runs': math.ceil(counts.get('PENDING', 0) / POLICY['daily_financial_document_budget']),
            'issuer_context_rotation_runs': math.ceil(len(issuers) / POLICY['daily_context_budget'])},
        'lane_counts': dict(Counter(c['lane'] for c in candidates)),
        'next_diligence_batch': selected,
        'remaining_candidates': sorted((c for c in candidates if c['isin'] not in selected_ids), key=priority),
        'carried_forward_decisions': journal,
        'coverage_class': 'RECEIVED_NSE_REPORTS_NOT_ALL_NSE_BSE_OR_INVESTABLE_COVERAGE',
        'selection_validation': 'UNVALIDATED_ATTENTION_POLICY_NOT_STOCK_RETURN_SIGNAL',
        'live_capital_allowed': False, 'validated_predictive_edge': False,
        'limits': ['Four prior case records imported, one full memo and three preliminary screens, not an exhaustive inventory of project judgments.',
                   'Cash surplus is reported CFO minus specified purchases, not maintenance or distributable owner cash.',
                   'These reports are triage inputs. No new source was acquired or accepted by this review.',
                   'Year-ago coverage here is the same-source broad report. Separate historical-context cards may contain additional comparisons.',
                   'Scheduled production ingestion and frozen experiments are not changed by this offline report.']}
    result['report_sha256'] = canonical_hash(result)
    return result


def render(report):
    def esc(value):
        return html.escape(str(value), quote=True)
    f, h = report['funnel'], report['health']
    names = ''.join(f"<tr><td>{esc(c['symbol'])}</td><td>{esc(c['lane'].replace('_', ' '))}</td><td>{esc(c['gaps'][0])}</td></tr>" for c in report['next_diligence_batch'])
    journal = ''.join(f"<p><b>{esc(d['symbol'])}: {esc(d['disposition'])}</b> ({esc(d['case_depth'].replace('_', ' ').lower())}) at its {esc(d['price_date'])} reference. This is a carried-forward case, not a new buy signal.</p>" for d in report['carried_forward_decisions'])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MarketLab operating review</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f5f2;color:#203938;font:16px system-ui}main{max-width:1100px;margin:auto;padding:30px 22px}h1{font-size:clamp(28px,4vw,44px)}.banner{background:#203938;color:white;padding:24px;border-radius:12px}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}.metric{background:white;padding:18px;border:1px solid #cbd6cf}.metric b{display:block;font-size:30px}table{width:100%;table-layout:fixed;border-collapse:collapse}th,td{text-align:left;vertical-align:top;padding:12px 6px;border-bottom:1px solid #ccd8d1;overflow-wrap:anywhere;font-size:13px}.panel{padding:22px;background:white;border:1px solid #ccd8d1;margin-top:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer;font-weight:600}.muted{font-size:12px;color:#526961}</style><main><h1>Research output, not pipeline activity</h1><div class="banner"><b>Attention allocation is not an investment score.</b><p>The next batch asks which source gaps to resolve. It does not turn sequential growth, a cash surplus or a valid parser into a buy recommendation.</p></div>''' + f'''<div class="metrics"><div class="metric"><b>{f['financial_issuers']}</b>issuers in received reports</div><div class="metric"><b>{f['retained_price_contexts']}</b>retained price contexts</div><div class="metric"><b>{f['full_underwriting_memos']}</b>completed underwriting memo</div><div class="metric"><b>0</b>new buy decisions</div></div><div class="panel"><h2>Operating blockers</h2><p>Saved state: {esc(report['snapshot_recorded_at'])}. Snapshot age at this review: {report['snapshot_age_hours']:.1f} hours.</p><p>News state: {esc(h['news_status'])}. Storage deferral recorded: {h['news_storage_blocked']}.</p><p>{f['unread_announcements']:,} unread announcements at four per run imply {report['capacity_lower_bounds_no_new_arrivals']['news_processing_runs']:,} runs without new arrivals. {f['same_source_yoy_revenue_available_issuers']}/{f['financial_issuers']} have same-source year-ago revenue in the broad cash report.</p></div><div class="panel"><h2>Next diligence batch</h2><p>An unfinished case first, then cash-supported sequential cues and two breadth slots. Unknown industry, seasonality, price and earnings quality still need review.</p><table><tr><th>Issuer</th><th>Attention lane</th><th>First missing check</th></tr>{names}</table></div><div class="panel"><h2>Decision record</h2>{journal}</div><details class="panel"><summary>Audit inputs and limitations</summary><pre>{esc(json.dumps({k:report[k] for k in ('input_hashes','lane_counts','capacity_lower_bounds_no_new_arrivals','limits')},indent=2))}</pre></details><p class="muted">Evaluated {esc(report['evaluated_at'])}. Report hash {esc(report['report_sha256'])}. No network, source mutation, production switch or portfolio order.</p></main></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--decisions', type=Path, required=True)
    parser.add_argument('--output-prefix', type=Path, required=True)
    parser.add_argument('--as-of')
    args = parser.parse_args(argv)
    if args.output_prefix.resolve().is_relative_to(args.reports.resolve()):
        raise ChangeError('write output outside the retained source-report directory')
    inputs = {name: loads_unique((args.reports / (name + '.json')).read_bytes()) for name in FILES}
    report = build(inputs, loads_unique(args.decisions.read_bytes()), args.as_of or now_utc())
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.output_prefix.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    args.output_prefix.with_suffix('.html').write_text(render(report), encoding='utf-8')
    print(json.dumps({'funnel': report['funnel'], 'next_diligence_symbols': [c['symbol'] for c in report['next_diligence_batch']],
                      'news_storage_blocked': report['health']['news_storage_blocked'], 'report_sha256': report['report_sha256']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
