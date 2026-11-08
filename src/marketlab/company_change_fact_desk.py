"""Assisted event-fact review desk, with explicit unknowns and blocked assumptions."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, timestamp
from marketlab.company_change_decisions import load_latest
from marketlab.company_change_event_bridge import timing
from marketlab.company_change_event_facts import REQUIRED, VERSION, admit, order_scenarios, states
from marketlab.company_change_store import EvidenceStore, loads_unique, writable_workspace


def decision(state: dict) -> dict:
    facts, category = state["facts"], state["category"]
    issues = ["Review contradictory source assertions: " + k.replace("_", " ")
              for k in state["conflicts"]]
    missing = [k for k in sorted(REQUIRED.get(category, set())) if facts[k]["status"] == "UNKNOWN"]
    if category is None:
        issues.append("Reviewers disagree on event category.")
    if any(a["status"] == "CONFLICT" or a["owner"]["status"] == "CONFLICT" for a in state["amounts"]):
        issues.append("Amount or ownership assertions conflict.")
    if issues:
        status = "RECONCILE_SOURCE_FIRST"
    elif category == "ORDER":
        status = "UNDERWRITE_FINITE_ORDER"
    elif category == "CREDIT":
        status = "REVIEW_FUNDING_AND_LIQUIDITY"
    else:
        status = "UNDERWRITE_TRANSACTION"
    return {"research_action": status, "source_issues": issues, "unknown_dimensions": missing,
            "automatic_accounting_update_allowed": False, "automatic_trade_allowed": False}


def build_report(store, plans: list | None = None) -> dict:
    cutoff = store.clock()
    rows = states(store, cutoff)
    plans = [] if plans is None else plans
    if not isinstance(plans, list) or len(plans) > 100:
        raise ChangeError("at most one hundred source-bound plans allowed")
    by_key = {}
    for plan in plans:
        if not isinstance(plan, dict) or not {"source_raw_sha256", "event_key"} <= plan.keys():
            raise ChangeError("economic plan lacks exact source and event")
        key = (plan["source_raw_sha256"], plan["event_key"])
        if key in by_key:
            raise ChangeError("duplicate economic plan")
        by_key[key] = plan
    contexts = load_latest(store, cutoff)
    dossiers, used = [], set()
    for state in rows:
        source = state["source"]
        matching = [c for c in contexts if all(c["identity"][k] == source[k] for k in ("symbol", "isin"))]
        context = max(matching, key=lambda c: (c["identity"]["scope"] == "CONSOLIDATED", timestamp(c["as_of"]))) if matching else None
        quote = context.get("quote") if context else None
        if quote and any(quote["identity"][k] != source[k] for k in ("symbol", "isin")):
            raise ChangeError("price and fact-review security mismatch")
        review_clock = {"source_published_at": state["source_published_at"],
                        "source_known_at": state["source_known_at"], "recorded_at": state["reviewed_at"]}
        clock = timing(review_clock, quote, cutoff)
        key = (source["raw_sha256"], state["event_key"])
        scenarios, scenario_error = None, None
        if key in by_key:
            used.add(key)
            try:
                scenarios = order_scenarios(state, by_key[key])
            except ChangeError as exc:
                # Retain the review even when the attempted economic use is blocked.
                scenario_error = str(exc)
        dossiers.append({"state": state, "decision": decision(state), "price": quote,
                         "price_timing": clock, "financial_context_hash": context.get("card_sha256") if context else None,
                         "hypothetical_economics": scenarios, "economic_use_blocker": scenario_error})
    report = {"engine": VERSION, "as_of": cutoff, "dossiers": dossiers,
              "unmatched_plan_keys": [list(k) for k in sorted(set(by_key) - used)],
              "counts": {"source_events": len(dossiers),
                         "conflicted_source_events": sum(bool(d["decision"]["source_issues"]) for d in dossiers),
                         "observed_dimensions": sum(v["status"] != "UNKNOWN" for s in rows for v in s["facts"].values()),
                         "finite_scenario_cases": sum(len(d["hypothetical_economics"]["scenarios"]) if d["hypothetical_economics"] else 0 for d in dossiers)},
              "model_called": False, "independent_accuracy_measured": False,
              "buy_approved": False, "live_capital_allowed": False,
              "limits": ["Explicit assisted source review, not model-extracted or independently labelled ground truth.",
                         "Distinct states preserve what the reviewer asserted. They cannot prove interpretation entailment.",
                         "Unknown, conflict and absence of an assertion are not evidence of completion or payment.",
                         "An event does not establish normalized earnings, company fair value, liquidity or a tradable entry."]}
    report["report_sha256"] = canonical_hash(report)
    return report


def render(report: dict) -> str:
    def esc(v):
        return html.escape(str(v), quote=True)
    def label(v):
        return str(v).replace("_", " ").capitalize()
    cards = []
    for item in report["dossiers"]:
        state, action = item["state"], item["decision"]
        fields = set(REQUIRED.get(state["category"], set())) | {k for k, v in state["facts"].items() if v["status"] != "UNKNOWN"}
        facts = []
        for key in sorted(fields):
            fact = state["facts"][key]
            values = " / ".join(fact["alternatives"]) if fact["alternatives"] else "Not established"
            quotes = "".join(f"<div class='assertion'><b>{esc(label(a['value']))}</b>" +
                              "".join(f"<blockquote>{esc(s['quote'])}</blockquote>" for s in a["evidence"]) + "</div>"
                              for a in fact["evidence"])
            facts.append(f"<div class='fact {esc(fact['status'])}'><dt>{esc(label(key))}</dt>"
                         f"<dd>{esc(label(values))}<small>{esc(label(fact['status']))}</small></dd>"
                         f"<details><summary>Source evidence</summary>{quotes or '<p>No supporting assertion supplied.</p>'}</details></div>")
        amounts = []
        for amount in state["amounts"]:
            variant = amount["variants"][0]
            qualifiers = sorted({q["value"] for a in amount["variants"] for q in a["qualifiers"]})
            inr = "" if amount["inr_crore"] is None else f" = ₹{esc(amount['inr_crore'])} crore"
            ev = "".join(f"<blockquote>{esc(e['quote'])}</blockquote>" for a in amount["variants"] for e in a["evidence"])
            amounts.append(f"<div class='amount'><strong>{esc(variant['literal'])}{inr}</strong>"
                           f"<p>{esc(label(variant['purpose']))}. Amount owner: {esc(label(amount['owner']['value'] or amount['owner']['status']))}.</p>"
                           f"<p>{esc(', '.join(label(q) for q in qualifiers))}</p><details><summary>Amount evidence</summary>{ev}</details></div>")
        quote = item["price"]
        quoted = f"₹{quote['price']:,.2f}, {esc(quote.get('session_date') or quote.get('quoted_at'))}" if quote else "No matched dated price"
        economics = item["hypothetical_economics"]
        cash = ""
        if economics:
            table = "".join(f"<tr><td>{esc(s['name'])}</td><td>{s['finite_incremental_npv_crore']:,.2f}</td></tr>" for s in economics["scenarios"])
            cash = f"<details><summary>Hypothetical finite cash, not company valuation</summary><p>{esc(economics['rationale'])}</p><table><tr><th>Scenario</th><th>NPV, ₹ crore</th></tr>{table}</table></details>"
        checks = "".join(f"<li>{esc(c)}</li>" for c in state["next_checks"])
        warning = "".join(f"<p class='issue'>{esc(c)}</p>" for c in action["source_issues"])
        if item["economic_use_blocker"]:
            warning += f"<p class='issue'>Economic calculation blocked: {esc(item['economic_use_blocker'])}</p>"
        cards.append(f"<article data-symbol='{esc(state['source']['symbol'])}' data-conflict='{str(bool(action['source_issues'])).lower()}'>"
                     f"<div class='eyebrow'>{esc(label(action['research_action']))}</div><h2>{esc(state['source']['symbol'])}</h2>"
                     f"<p class='subtitle'>{esc(state['event_key'].replace('-',' '))}</p>{warning}"
                     f"<a href='{esc(state['source']['url'])}' rel='noopener noreferrer'>Original disclosure</a>"
                     f"<dl class='facts'>{''.join(facts)}</dl>{''.join(amounts)}"
                     f"<p class='price'>{quoted}<br><b>{esc(label(item['price_timing']['status']))}</b>. Not an executable entry.</p>"
                     f"{cash}<details open><summary>Next investment checks</summary><ul>{checks}</ul></details>"
                     f"<p class='audit'>Reviewed {esc(state['reviewed_at'])}. {esc(', '.join(state['reviewers']))}. No automatic buy approval.</p></article>")
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MarketLab | Reviewed event facts</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f5f5;color:#19343e;font:15px system-ui}main{max-width:1260px;margin:auto;padding:32px 22px}h1{font-size:clamp(28px,4vw,42px);line-height:1.1;max-width:800px}h2{font-size:28px;margin:8px 0}.eyebrow{font-size:11px;letter-spacing:.09em;text-transform:uppercase}.banner{background:#19343e;color:white;padding:22px 26px;border-radius:14px;line-height:1.6}.pipeline{font-family:monospace;overflow-wrap:anywhere}.stats{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.stats div{background:white;border:1px solid #d4e0e0;border-radius:9px;padding:14px 20px;flex:1;min-width:145px}.stats b{display:block;font-size:26px}.stats span{font-size:12px}.toolbar{display:flex;gap:10px;flex-wrap:wrap}input,select{font:inherit;padding:11px 14px;border:1px solid #b5c7c8;border-radius:7px;background:white;color:inherit;max-width:100%}input{min-width:200px;flex:1}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,470px),1fr));gap:22px;margin-top:22px}article{background:white;padding:24px;border:1px solid #cddcdd;border-radius:13px;min-width:0}.subtitle{color:#5b747c;margin:0 0 16px}a{color:#00676b}.facts{margin:20px 0}.fact{border-left:3px solid #87aaa8;padding:10px 12px;margin:8px 0;background:#f5f8f7}.fact.UNKNOWN{border-color:#b2bdc0}.fact.CONFLICT{border-color:#bd6a43;background:#fff4ed}dt{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#5b747c}dd{margin:4px 0;font-weight:650}dd small{font-size:10px;text-transform:uppercase;display:block;margin-top:4px;font-weight:400}.fact details{margin-top:6px}summary{cursor:pointer;font-size:12px;font-weight:600}details>p{font-size:13px}.assertion{margin:12px 0;font-size:12px}blockquote{margin:10px 0;padding:8px 12px;border-left:2px solid #aac3c4;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.6}.amount{background:#eaf1ef;border-radius:8px;padding:14px 16px;margin:14px 0}.amount strong{font-size:18px}.amount p{font-size:12px;margin:6px 0}.issue{border-left:3px solid #bd6a43;padding:10px 12px;font-weight:650;font-size:13px}.price{font-size:12px;margin:18px 0;line-height:1.7}table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px;margin:12px 0}td,th{padding:8px 4px;border-bottom:1px solid #d0dcdc;text-align:left;overflow-wrap:anywhere}ul{padding-left:20px}li{font-size:13px;line-height:1.55;margin:9px 0}.audit{font-size:10px;line-height:1.5;overflow-wrap:anywhere;color:#5c737b}footer{font-size:12px;line-height:1.7;margin:26px 0}.hidden{display:none}
</style></head><body><main><div class="eyebrow">MarketLab / Assisted investment research</div><h1>A signed agreement is not a completed investment.</h1><div class="banner"><b>Ownership, completion, payment and operations are reviewed separately.</b><p>Contradictory source statements remain visible. Missing evidence stays unknown. These are explicit assisted reviews, not new autonomous-model results.</p><div class="pipeline">Original filing → exact claims → separate fact states → conditional economics → investment diligence</div></div>
""" + f"<div class='stats'><div><b>{report['counts']['source_events']}</b><span>Source-bound event records</span></div><div><b>{report['counts']['conflicted_source_events']}</b><span>Unresolved source conflicts</span></div><div><b>{report['counts']['finite_scenario_cases']}</b><span>Explicit hypothetical cash cases</span></div><div><b>0</b><span>Automatic buy approvals</span></div></div>" + """<div class="toolbar"><input id="search" type="search" aria-label="Filter by company" placeholder="Filter by company"><select id="filter" aria-label="Filter by status"><option value="all">All reviewed sources</option><option value="conflict">Source conflicts</option><option value="clear">No conflicting assertions</option></select></div>""" + f"<div class='grid'>{''.join(cards)}</div><footer>Evaluated {esc(report['as_of'])}. All review identities are local attestations, not authenticated independent labels. Explicit assumptions do not establish normalized earnings, a post-event price or a tradable opportunity. Original model scores and frozen research experiments remain unchanged.<p class='audit'>Report SHA-256 {esc(report['report_sha256'])}</p></footer>" + """</main><script>
const search=document.getElementById('search'), filter=document.getElementById('filter');
function apply(){const query=search.value.trim().toUpperCase();document.querySelectorAll('article').forEach(card=>{const status=filter.value;const match=card.dataset.symbol.includes(query)&&(status==='all'||(status==='conflict')===(card.dataset.conflict==='true'));card.classList.toggle('hidden',!match);});}
search.addEventListener('input',apply);filter.addEventListener('change',apply);
</script></body></html>"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--reviewer")
    parser.add_argument("--plans", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.package) != bool(args.reviewer):
        raise ChangeError("explicit package and named reviewer must be supplied together")
    for path in (args.package, args.plans):
        if path and path.stat().st_size > 2 * 1024 * 1024:
            raise ChangeError("review or scenario input exceeds byte limit")
    with EvidenceStore(args.workspace) as store:
        if args.package:
            admit(store, loads_unique(args.package.read_bytes()), args.reviewer)
        report = build_report(store, loads_unique(args.plans.read_bytes()) if args.plans else [])
    writable_workspace(args.output_prefix.parent)
    args.output_prefix.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    args.output_prefix.with_suffix(".html").write_text(render(report), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "report_sha256": report["report_sha256"], "model_called": False}))
    return int(bool(report["unmatched_plan_keys"]) or any(d["economic_use_blocker"] for d in report["dossiers"]))


if __name__ == "__main__":
    raise SystemExit(main())
