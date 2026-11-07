"""One reported-evidence decision view. Sensitivities and diligence, never buy scores."""
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, finite, public_url, timestamp
from marketlab.company_change_context import CAPEX, build_card
from marketlab.company_change_store import EvidenceStore, loads_unique, writable_workspace

VERSION = "CC001-DECISION-CONTEXT-v1"
POLICY = {"years": 5, "price_return_hurdle": 0.15, "exit_pe_assumption": 15.0,
          "eps_growth_scenarios": [0.10, 0.15, 0.20], "retained_eps_fractions": [0.8, 1.0],
          "classification": "ILLUSTRATIVE_UNCALIBRATED_SENSITIVITIES_NOT_FORECASTS"}


def sensitivity(eps: float, price: float, policy: dict) -> dict:
    """Normalization haircut and EPS growth are explicit assumptions, not facts."""
    if set(policy) != set(POLICY):
        raise ChangeError("incomplete sensitivity policy")
    eps = finite(eps, "reported annual EPS", minimum=1e-9)
    price = finite(price, "price", minimum=1e-9)
    years = finite(policy["years"], "years", minimum=1, maximum=10)
    hurdle = finite(policy["price_return_hurdle"], "hurdle", minimum=0, maximum=1)
    multiple = finite(policy["exit_pe_assumption"], "exit multiple", minimum=1, maximum=100)
    growths, fractions = policy["eps_growth_scenarios"], policy["retained_eps_fractions"]
    if not isinstance(growths, list) or not growths or not isinstance(fractions, list) or not fractions:
        raise ChangeError("sensitivity ranges must be nonempty lists")
    rows = []
    for g in growths:
        finite(g, "EPS growth assumption", minimum=-0.99, maximum=1)
        for fraction in fractions:
            finite(fraction, "retained EPS fraction", minimum=0.01, maximum=1)
            terminal = eps * fraction * (1 + g) ** years * multiple
            rows.append({"eps_growth_assumption": g, "retained_reported_eps_fraction": fraction,
                         "terminal_price": terminal,
                         "price_consistent_with_hurdle": terminal / (1 + hurdle) ** years,
                         "price_cagr_at_observed_price": (terminal / price) ** (1 / years) - 1})
    return {"required_eps_growth_at_full_reported_eps":
            (price * (1 + hurdle) ** years / (eps * multiple)) ** (1 / years) - 1,
            "rows": rows, "policy": policy,
            "limits": ["Price-only outcomes, excluding dividends, tax and transaction costs.",
                       "Retained EPS fractions are hypothetical haircuts, not verified normalization.",
                       "EPS growth includes per-share effects. No calibrated likelihood or valuation target is implied."]}


def trailing_cash(card: dict) -> dict:
    ttm = card.get("reported_ttm_flows")
    result = {"status": "MISSING_INPUT", "cfo_crore": None, "specified_capex_crore": None,
              "cfo_less_specified_capex_crore": None,
              "limits": "Reported cross-document cash diagnostic, not normalized parent-distributable free cash flow."}
    if not ttm:
        return result
    fields = ttm["fields"]
    terms = [fields.get(k, {}) for k in CAPEX]
    if any(t.get("value") is None for t in terms) or fields.get("cfo", {}).get("value") is None:
        return result
    if any(t.get(k) is None or t[k] < 0 for t in terms for k in ("annual", "current_interim", "prior_interim")):
        result["status"] = "AMBIGUOUS_PURCHASE_SIGN"
        return result
    cfo = Decimal(str(fields["cfo"]["value"]))
    capex = sum((Decimal(str(t["value"])) for t in terms), Decimal(0))
    if capex < 0:
        result["status"] = "NEGATIVE_DERIVED_PURCHASES"
        return result
    result.update(status="REPORTED_FLOW_DIAGNOSTIC", cfo_crore=float(cfo),
                  specified_capex_crore=float(capex), cfo_less_specified_capex_crore=float(cfo - capex))
    return result


def decision_context(raw: dict, as_of: str, policy: dict | None = None) -> dict:
    """Re-evaluate cached evidence with current freshness and accounting gates.

    Old derived ratios and claimed quality flags are not trusted. Original facts
    and evidence identity are retained. New outputs never alter review state.
    """
    policy = POLICY if policy is None else policy
    if timestamp(raw["as_of"]) > timestamp(as_of):
        raise ChangeError("context not yet observed at report cutoff")
    for period in raw["financial_periods"]:
        public_url(period["source_url"])
    card = build_card(raw["identity"], raw["financial_periods"], raw["current_period_end"],
                      raw.get("quote"), raw.get("corporate_actions"), as_of)
    source_errors = raw.get("retrieval_errors", [])
    source_review = raw.get("anchor_review_status", "UNREVIEWED")
    blockers = list(card["blockers"])
    if source_review == "REJECT":
        blockers.append("Current anchor was rejected by a reviewer.")
    if source_errors:
        blockers.append("Historical/price retrieval has unresolved errors. Partial evidence is retained.")
    longest = min(card["year_ago_comparisons"], key=lambda c: c["current_evidence"]["period_start"], default=None)
    revenue = longest["metrics"]["revenue"]["reported_growth_fraction"] if longest else None
    owner = longest["metrics"]["owner_pat"]["reported_growth_fraction"] if longest else None
    cash = trailing_cash(card)
    scenarios = None
    if not blockers and card["price_over_reported_annual_eps"] is not None:
        scenarios = sensitivity(card["reported_annual_diluted_eps"], card["quote"]["price"], policy)
    observations = []
    if revenue is not None and owner is not None and revenue > 0 and owner < 0:
        observations.append("Reported revenue rose but owner-attributable profit fell in the matching year-ago comparison.")
    if cash["cfo_less_specified_capex_crore"] is not None and cash["cfo_less_specified_capex_crore"] < 0:
        observations.append("Reported trailing operating cash did not cover the specified cash purchases. Financing and investment returns need review.")
    if any(c["withheld_fields"] for c in card["accounting_checks"]):
        observations.append("At least one source period has inconsistent or rounding-unverified profit attribution. Affected owner-growth and trailing-profit calculations are withheld.")
    if blockers:
        category = "EVIDENCE_BLOCKED"
        next_check = "Resolve the listed source/accounting/basis blockers before interpreting the earnings multiple."
    elif cash["status"] in {"AMBIGUOUS_PURCHASE_SIGN", "NEGATIVE_DERIVED_PURCHASES"}:
        category = "CASH_BASIS_REVIEW"
        next_check = "Resolve the source cash-purchase sign convention before interpreting cash coverage or owner cash."
    elif scenarios and scenarios["required_eps_growth_at_full_reported_eps"] > max(policy["eps_growth_scenarios"]):
        category = "HURDLE_EXCEEDS_ILLUSTRATIVE_GROWTH_RANGE"
        next_check = "Require a defensible stronger per-share earnings case, a different justified exit multiple, or a lower entry price."
    elif cash["cfo_less_specified_capex_crore"] is not None and cash["cfo_less_specified_capex_crore"] < 0:
        category = "FUNDING_DILIGENCE"
        next_check = "Establish expansion funding, investment returns and sustainable cash conversion before considering entry."
    elif owner is not None and owner < 0:
        category = "EARNINGS_DILIGENCE"
        next_check = "Explain the matched-period owner-profit decline and test a normalized earnings case."
    else:
        category = "FULL_UNDERWRITING_REQUIRED"
        next_check = "Complete normalized owner earnings, diluted-share reconciliation, downside, governance and liquidity review."
    result = {"identity": raw["identity"], "context_observed_at": raw["as_of"], "evaluated_at": as_of,
              "input_context_sha256": raw.get("card_sha256"), "source_review_status": source_review,
              "category": category, "next_decisive_check": next_check,
              "comparison_period": longest["current_evidence"] if longest else None,
              "reported_revenue_growth_yoy": revenue, "reported_owner_profit_growth_yoy": owner,
              "quote": card["quote"], "reported_annual_diluted_eps": card["reported_annual_diluted_eps"],
              "reported_reference_pe": card["price_over_reported_annual_eps"] if not blockers else None,
              "reported_trailing_cash": cash, "sensitivity": scenarios,
              "accounting_checks": card["accounting_checks"], "blockers": blockers,
              "observations": observations, "annual_evidence": card["annual_evidence"],
              "live_capital_allowed": False, "buy_approved": False,
              "limits": card["limitations"] + ["Research triage under explicit assumptions, not an investment ranking or a forecast."]}
    result["decision_context_sha256"] = canonical_hash(result)
    return result


def load_latest(store: EvidenceStore, as_of: str) -> list[dict]:
    if store.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cc_context_runs'").fetchone() is None:
        return []
    selected = {}
    for row in store.db.execute("SELECT id,known_at,payload FROM cc_context_runs"):
        record = loads_unique(row["payload"])
        digest = record.get("card_sha256")
        if digest != row["id"] or canonical_hash({k: v for k, v in record.items() if k != "card_sha256"}) != digest:
            raise ChangeError("stored context integrity failure")
        observed = timestamp(record["as_of"])
        if observed != timestamp(row["known_at"]):
            raise ChangeError("stored context observation clock mismatch")
        if observed > timestamp(as_of):
            continue
        key = tuple(record["identity"][k] for k in ("symbol", "isin", "scope"))
        prior = selected.get(key)
        if prior is None or observed > timestamp(prior["as_of"]):
            selected[key] = record
        elif observed == timestamp(prior["as_of"]) and digest != prior["card_sha256"]:
            raise ChangeError("ambiguous latest context record")
    return [selected[k] for k in sorted(selected)]


def build_report(contexts: list[dict], as_of: str) -> dict:
    cards = [decision_context(c, as_of) for c in contexts]
    report = {"engine": VERSION, "as_of": as_of, "policy": POLICY, "cards": cards,
              "counts": {"context_cards": len(cards), "issuers": len({c["identity"]["isin"] for c in cards}),
                         "categories": dict(Counter(c["category"] for c in cards))},
              "live_capital_allowed": False, "validated_predictive_edge": False}
    report["report_sha256"] = canonical_hash(report)
    return report


def render_report(report: dict) -> str:
    def esc(x):
        return html.escape(str(x), quote=True)
    def fmt(x):
        return "Unknown" if x is None else f"{x:,.2f}"
    def pct(x):
        return "Unknown" if x is None else f"{x:+.1%}"
    cards = []
    for c in report["cards"]:
        q, sen = c["quote"], c["sensitivity"]
        price = q["price"] if q else None
        required = sen["required_eps_growth_at_full_reported_eps"] if sen else None
        rows = "".join(f"<tr><td>{s['eps_growth_assumption']:.0%}</td><td>{s['retained_reported_eps_fraction']:.0%}</td>"
                       f"<td>₹{s['price_consistent_with_hurdle']:,.2f}</td><td>{s['price_cagr_at_observed_price']:.1%}</td></tr>"
                       for s in sen["rows"]) if sen else "<tr><td colspan='4'>Withheld until evidence blockers are resolved.</td></tr>"
        messages = c["blockers"] + c["observations"]
        caveats = "".join(f"<li>{esc(s)}</li>" for s in messages)
        evidence = c["annual_evidence"]
        link = f"<a href='{esc(evidence['source_url'])}' rel='noopener noreferrer'>Annual source filing</a>" if evidence else "Annual source unavailable"
        cards.append(f"<article data-company='{esc(c['identity']['symbol'])}'><div class='tag'>{esc(c['category'].replace('_',' '))}</div>"
            f"<h2>{esc(c['identity']['symbol'])}</h2><p class='muted'>{esc(c['identity']['scope'])} · source review: {esc(c['source_review_status'])}</p>"
            f"<div class='metrics'><div><b>₹{fmt(price)}</b><span>Dated price</span></div><div><b>{fmt(c['reported_reference_pe'])}×</b><span>Price / reported annual EPS</span></div>"
            f"<div><b>{pct(required)}</b><span>EPS growth needed at 15× exit</span></div></div>"
            f"<p>Matched-period revenue: <b>{pct(c['reported_revenue_growth_yoy'])}</b> · Owner profit: <b>{pct(c['reported_owner_profit_growth_yoy'])}</b></p>"
            f"<p>Trailing cash minus specified purchases: <b>₹{fmt(c['reported_trailing_cash']['cfo_less_specified_capex_crore'])} crore</b></p>"
            f"<p class='next'><b>Next decisive check:</b> {esc(c['next_decisive_check'])}</p><ul>{caveats}</ul>"
            f"<details><summary>Assumption-dependent entry prices and evidence</summary><p>Five years, 15% price-return hurdle, 15× exit P/E. EPS haircuts and growth are hypothetical, not predictions.</p>"
            f"<table><tr><th>EPS growth</th><th>EPS retained</th><th>Price meeting hurdle</th><th>Return at observed price</th></tr>{rows}</table>"
            f"<p>{link}</p><p>Price date: {esc((q.get('quoted_at') or q.get('session_date')) if q else 'Unknown')}</p>"
            f"<pre>{esc(json.dumps(c['accounting_checks'],indent=2))}</pre></details></article>")
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>MarketLab decision context</title><style>
*{box-sizing:border-box}body{margin:0;font:15px system-ui;background:#f3f5f5;color:#16353f}main{max-width:1240px;margin:auto;padding:30px 22px}h1{font-size:36px}h2{margin:10px 0}.tag{font-size:11px;letter-spacing:.08em}.banner{background:#16353f;color:white;padding:24px;border-radius:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:18px;margin:24px 0}article{min-width:0;padding:22px;border:1px solid #d0dddd;border-radius:12px;background:white}.metrics{display:flex;gap:16px;flex-wrap:wrap}.metrics b{display:block;font-size:24px}.metrics span{display:block;font-size:11px;max-width:140px}.muted{color:#526d77;font-size:12px}.next{border-left:3px solid #44696d;padding-left:12px}table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:11px}td,th{text-align:left;overflow-wrap:anywhere;padding:8px 3px;border-bottom:1px solid #dde5e5}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}li{margin:9px 0;font-size:13px}summary{cursor:pointer;font-weight:600}a{color:#006469}</style><main><div class='tag'>MARKETLAB / EVIDENCE → ECONOMICS → PRICE</div><h1>What decision does the evidence support?</h1><div class='banner'><b>No buy approval is implied by these cards.</b><p>Growth, owner profit, reported cash and price appear together. The growth range and exit multiple are explicit sensitivity assumptions. Accounting failures block affected calculations, not just the footnote.</p></div>
""" + f"<p>{report['counts']['issuers']} issuers with retained context · evaluated {esc(report['as_of'])}</p><div class='grid'>{''.join(cards)}</div>" \
        "<p class='muted'>No normalized earnings forecast, probability of success or validated investment edge. Cash differences are not parent-distributable free cash flow. Dividends, taxes and costs excluded from sensitivities.</p></main></html>"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args(argv)
    writable_workspace(args.output_prefix.parent)
    with EvidenceStore(args.workspace) as store:
        cutoff = store.clock()
        report = build_report(load_latest(store, cutoff), cutoff)
    for suffix, text in (("json", json.dumps(report, indent=2, allow_nan=False)), ("html", render_report(report))):
        args.output_prefix.with_suffix("." + suffix).write_text(text, encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "report_sha256": report["report_sha256"], "live_capital_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
