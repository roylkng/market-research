"""Join reviewed events to dated company evidence and finite-contract cash scenarios.

One-off cash is discounted once. It is never capitalized as perpetual earnings.
Amount scope, FX, cash margin, overlap, investment and timing remain explicit.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from marketlab.company_change import ChangeError, canonical_hash, finite, strict_keys, timestamp
from marketlab.company_change_context import build_card
from marketlab.company_change_decisions import load_latest
from marketlab.company_change_news_review import REVIEW_KEYS, validate_review
from marketlab.company_change_store import EvidenceStore, loads_unique, writable_workspace

VERSION = "CC001-EVENT-BRIDGE-v1"
SCALES = {"unit": 1, "lakh": 100_000, "crore": 10_000_000,
          "million": 1_000_000, "billion": 1_000_000_000}
MONEY = re.compile(r"(USD|INR|EUR|GBP|Rs\.?|₹)\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)\s*"
                   r"(crores?|lakhs?|millions?|billions?)?", re.IGNORECASE)
CASE_KEYS = {"name", "fx_inr_per_currency_unit", "issuer_fraction", "not_in_baseline_fraction",
             "after_tax_cash_margin", "additional_capex_crore", "working_capital_crore",
             "working_capital_recovery_fraction", "cash_receipt_months", "discount_rate"}


def source_amount(review: dict, specification: dict) -> dict:
    strict_keys(specification, {"literal", "amount_scope"}, "event amount")
    if set(specification) != {"literal", "amount_scope"}:
        raise ChangeError("amount requires source literal and explicit economic scope")
    literal = specification["literal"]
    if not isinstance(literal, str) or specification["amount_scope"] not in {"ISSUER_SCOPE", "CONSORTIUM_TOTAL"}:
        raise ChangeError("unresolved currency amount or economic scope")
    match = MONEY.fullmatch(literal.strip())
    if not match:
        raise ChangeError("amount literal is not an unambiguous supported money amount")
    evidence = [c for c in review["claims"] if c["field"] == "amount" and any(m[0].strip() == literal.strip() for m in MONEY.finditer(c["quote"]))]
    if len(evidence) != 1:
        raise ChangeError("amount must bind to one reviewed amount quotation")
    currency = match[1].upper()
    currency = "INR" if currency in {"RS", "RS.", "₹"} else currency
    scale = match[3].lower().rstrip("s") if match[3] else "unit"
    value = Decimal(match[2].replace(",", "")) * SCALES[scale]
    finite(value, "contract amount", minimum=0.000001)
    return {"currency": currency, "amount_units": str(value), "literal": literal,
            "amount_scope": specification["amount_scope"], "evidence": evidence[0],
            "scope_status": "REVIEWER_SUPPLIED_ALLOCATION_NOT_AUTOMATICALLY_PROVEN"}


def finite_contract(amount: dict, scenario: dict) -> dict:
    strict_keys(scenario, CASE_KEYS, "contract scenario")
    if set(scenario) != CASE_KEYS or not isinstance(scenario["name"], str) or not scenario["name"].strip():
        raise ChangeError("all scenario assumptions must be explicit")
    bounds = {"fx_inr_per_currency_unit": (0.000001, 10000), "issuer_fraction": (0, 1),
              "not_in_baseline_fraction": (0, 1), "after_tax_cash_margin": (-1, 1),
              "additional_capex_crore": (0, 1e9), "working_capital_crore": (0, 1e9),
              "working_capital_recovery_fraction": (0, 1), "cash_receipt_months": (0, 120),
              "discount_rate": (0, 1)}
    for key, (low, high) in bounds.items():
        finite(scenario[key], key, minimum=low, maximum=high)
    if amount["currency"] == "INR" and scenario["fx_inr_per_currency_unit"] != 1:
        raise ChangeError("INR amount cannot be FX-converted again")
    if amount["amount_scope"] == "ISSUER_SCOPE" and scenario["issuer_fraction"] != 1:
        raise ChangeError("issuer-specific amount cannot be allocated a second time")
    if amount["amount_scope"] not in {"ISSUER_SCOPE", "CONSORTIUM_TOTAL"}:
        raise ChangeError("unsupported allocation scope")
    amount_units = Decimal(str(amount["amount_units"]))
    finite(amount_units, "contract amount", minimum=0)
    def d(key):
        return Decimal(str(scenario[key]))
    contract = amount_units * d("fx_inr_per_currency_unit") * d("issuer_fraction") / Decimal(10_000_000)
    incremental_receipts = contract * d("not_in_baseline_fraction")
    surplus = incremental_receipts * d("after_tax_cash_margin")
    upfront = d("additional_capex_crore") + d("working_capital_crore")
    recovered_wc = d("working_capital_crore") * d("working_capital_recovery_fraction")
    terminal = surplus + recovered_wc
    discount = (1 + scenario["discount_rate"]) ** (scenario["cash_receipt_months"] / 12)
    value = -float(upfront) + float(terminal) / discount
    return {"name": scenario["name"], "assumptions": dict(scenario),
            "attributed_contract_crore": float(contract),
            "not_in_baseline_contract_crore": float(incremental_receipts),
            "after_tax_cash_surplus_before_investment_crore": float(surplus),
            "upfront_cash_outflow_crore": float(upfront),
            "terminal_net_receipt_crore": float(terminal),
            "finite_incremental_npv_crore": finite(value, "finite contract NPV"),
            "terminal_value_crore": 0, "per_share_value": None,
            "formula": "-capex - working_capital + (incremental_contract * cash_margin + recovered_working_capital)/(1+r)^(months/12)",
            "interpretation": "ILLUSTRATIVE_SINGLE_CONTRACT_CASH_NPV_NOT_COMPANY_FAIR_VALUE"}


def timing(review: dict, quote: dict | None, as_of: str) -> dict:
    cutoff = timestamp(as_of)
    published = timestamp(review["source_published_at"])
    available = max(timestamp(review["source_known_at"]), timestamp(review["recorded_at"]), published)
    if available > cutoff:
        raise ChangeError("event review unavailable at decision cutoff")
    if quote is None:
        return {"status": "NO_PRICE", "post_publication_price": False,
                "after_system_review_price": False, "executable_price_verified": False}
    observed = timestamp(quote["observed_at"])
    if observed > cutoff:
        raise ChangeError("price observation unavailable at cutoff")
    if quote.get("quoted_at"):
        instant = timestamp(quote["quoted_at"])
        if instant > observed:
            raise ChangeError("price timestamp exceeds observation")
        public, system = instant > published, instant > available
        status = "POST_REVIEW_OBSERVATION" if system else "PRE_REVIEW_REFERENCE" if public else "PRE_EVENT_REFERENCE"
    else:
        session = date.fromisoformat(quote["session_date"])
        zone = ZoneInfo("Asia/Kolkata")
        if session > observed.astimezone(zone).date():
            raise ChangeError("price session exceeds observed date")
        public = session > published.astimezone(zone).date()
        system = session > available.astimezone(zone).date()
        status = "POST_REVIEW_SESSION_REFERENCE" if system else "DATE_ONLY_TIMING_UNRESOLVED" if session == published.astimezone(zone).date() else "PRE_REVIEW_REFERENCE" if public else "PRE_EVENT_REFERENCE"
    return {"status": status, "post_publication_price": public,
            "after_system_review_price": system, "executable_price_verified": False,
            "event_published_at": published.isoformat(), "research_available_at": available.isoformat()}


def join_event(review: dict, context: dict | None, as_of: str, plan: dict | None = None) -> dict:
    if canonical_hash({k: v for k, v in review.items() if k != "review_sha256"}) != review.get("review_sha256"):
        raise ChangeError("event review integrity failure")
    if review.get("review_status") != "REVIEWED_RESEARCH_ONLY":
        raise ChangeError("unreviewed model proposals cannot enter the economic bridge")
    quote, financial, blockers = None, None, []
    if context is not None:
        if canonical_hash({k: v for k, v in context.items() if k != "card_sha256"}) != context.get("card_sha256"):
            raise ChangeError("financial context integrity failure")
        if any(context["identity"][k] != review["source"][k] for k in ("symbol", "isin")):
            raise ChangeError("event and company security identities differ")
        if timestamp(context["as_of"]) > timestamp(as_of):
            raise ChangeError("financial context unavailable at cutoff")
        financial = build_card(context["identity"], context["financial_periods"],
                               context["current_period_end"], context.get("quote"),
                               context.get("corporate_actions"), as_of)
        quote = financial["quote"]
        blockers += financial["blockers"]
        if context.get("retrieval_errors"):
            blockers.append("The company context has unresolved source retrieval errors.")
        if context.get("anchor_review_status", "UNREVIEWED") != "ACCEPT":
            blockers.append("Company accounting evidence is not accepted as reviewed.")
    else:
        blockers.append("No matched company financial/price context is retained.")
    clock = timing(review, quote, as_of)
    if not clock["post_publication_price"]:
        blockers.append("Price is missing, pre-event, or lacks sufficient timing precision. No post-event entry is established.")
    elif not clock["after_system_review_price"]:
        blockers.append("Price preceded the completed system review. It cannot be treated as a prospective fill.")
    scenarios, amount = [], None
    if plan is not None:
        strict_keys(plan, {"source_raw_sha256", "amount", "scenarios", "rationale"}, "economic plan")
        if set(plan) != {"source_raw_sha256", "amount", "scenarios", "rationale"}:
            raise ChangeError("incomplete event economic plan")
        if plan["source_raw_sha256"] != review["source"]["raw_sha256"]:
            raise ChangeError("economic plan targets another disclosure")
        if review["category"] != "ORDER" or review["stage"] not in {"LETTER_OF_AWARD", "AGREEMENT_SIGNED"}:
            raise ChangeError("finite order model is not valid for this event/stage")
        if review["actor_scope"] not in {"ISSUER", "CONSORTIUM"}:
            raise ChangeError("unresolved parent/subsidiary economics cannot be assigned automatically")
        if not isinstance(plan["rationale"], str) or len(plan["rationale"].strip()) < 20:
            raise ChangeError("scenario assumptions need an explicit rationale")
        if not isinstance(plan["scenarios"], list) or not 1 <= len(plan["scenarios"]) <= 20:
            raise ChangeError("economic plan must contain 1..20 explicit cases")
        amount = source_amount(review, plan["amount"])
        scenarios = [finite_contract(amount, case) for case in plan["scenarios"]]
        blockers.append("Cash margin, FX, baseline overlap, investment and collection timing are assumptions, not established forecasts.")
    else:
        blockers.append("No approved economic amount/allocation and complete scenario assumptions are supplied.")
    if review["stage"] in {"UNRESOLVED", "CANCELLED", "PROPOSED", "INCORPORATED_NOT_OPERATING"}:
        blockers.append("Event stage does not establish operating revenue or realized cash.")
    result = {"engine": VERSION, "symbol": review["source"]["symbol"], "isin": review["source"]["isin"],
              "as_of": as_of, "review_sha256": review["review_sha256"],
              "event": {k: review[k] for k in ("category", "stage", "actor_scope", "interpretation", "next_check")},
              "source": review["source"], "price_timing": clock,
              "price_reference": quote, "financial_context_sha256": context.get("card_sha256") if context else None,
              "amount": amount, "finite_contract_scenarios": scenarios,
              "blockers": list(dict.fromkeys(blockers)), "decision": "DILIGENCE_ONLY_NO_ENTRY_APPROVED",
              "per_share_effect": None, "terminal_value_assumed": False,
              "live_capital_allowed": False, "validated_predictive_edge": False}
    result["dossier_sha256"] = canonical_hash(result)
    return result


def build_workspace(store: EvidenceStore, plans: list[dict]) -> dict:
    cutoff = store.clock()
    contexts = load_latest(store, cutoff)
    latest = {}
    for context in contexts:
        identity = context["identity"]
        key = (identity["symbol"], identity["isin"])
        prior = latest.get(key)
        if prior is None or (identity["scope"] == "CONSOLIDATED", timestamp(context["as_of"])) > (prior["identity"]["scope"] == "CONSOLIDATED", timestamp(prior["as_of"])):
            latest[key] = context
    if len({p["source_raw_sha256"] for p in plans}) != len(plans):
        raise ChangeError("duplicate economic plan per source")
    by_source = {p["source_raw_sha256"]: p for p in plans}
    dossiers = []
    exists = store.db.execute("SELECT name FROM sqlite_master WHERE name='cc_news_reviews'").fetchone()
    if exists:
        for row in store.db.execute("SELECT payload FROM cc_news_reviews ORDER BY recorded_at,id"):
            review = loads_unique(row[0])
            if timestamp(review["recorded_at"]) > timestamp(cutoff):
                continue
            reading_row = store.db.execute("SELECT payload FROM cc_news_readings WHERE id=?", (review["reading_sha256"],)).fetchone()
            if reading_row is None:
                raise ChangeError("review no longer has a retained reading")
            reading = loads_unique(reading_row[0])
            from marketlab.company_change_semantics import checked_reading
            checked_reading(store, reading)
            validate_review(reading, {k: review[k] for k in REVIEW_KEYS})
            key = (review["source"]["symbol"], review["source"]["isin"])
            dossiers.append(join_event(review, latest.get(key), cutoff,
                                       by_source.get(review["source"]["raw_sha256"])))
    unused = sorted(set(by_source) - {d["source"]["raw_sha256"] for d in dossiers})
    report = {"engine": VERSION, "as_of": cutoff, "dossiers": dossiers,
              "unmatched_plan_sources": unused, "live_capital_allowed": False}
    report["report_sha256"] = canonical_hash(report)
    return report


def render(report: dict) -> str:
    def esc(v):
        return html.escape(str(v), quote=True)
    cards = []
    for d in report["dossiers"]:
        rows = "".join(f"<tr><td>{esc(s['name'])}</td><td>{s['assumptions']['after_tax_cash_margin']:.0%}</td>"
                       f"<td>{s['assumptions']['not_in_baseline_fraction']:.0%}</td>"
                       f"<td>{s['finite_incremental_npv_crore']:,.2f}</td></tr>" for s in d["finite_contract_scenarios"])
        warnings = "".join(f"<li>{esc(b)}</li>" for b in d["blockers"])
        cards.append(f"<article><small>{esc(d['event']['stage'])}</small><h2>{esc(d['symbol'])}</h2>"
            f"<p>{esc(d['event']['interpretation'])}</p><strong>{esc(d['price_timing']['status'])}</strong>"
            f"<table><tr><th>Scenario</th><th>Cash margin</th><th>Incremental</th><th>Finite NPV, ₹ crore</th></tr>{rows}</table>"
            f"<details><summary>Evidence and assumptions</summary><ul>{warnings}</ul>"
            f"<pre>{esc(json.dumps(d['finite_contract_scenarios'], indent=2))}</pre></details>"
            f"<p><b>Next check:</b> {esc(d['event']['next_check'])}</p></article>")
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Event to economics</title><style>*{box-sizing:border-box}body{margin:0;font:15px system-ui;color:#18333f;background:#f4f6f6}main{max-width:1200px;margin:auto;padding:30px 22px}h1{font-size:36px}.banner{background:#18333f;color:white;border-radius:12px;padding:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:18px;margin-top:24px}article{background:white;border:1px solid #ccdada;border-radius:12px;padding:22px;min-width:0}table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px}td,th{text-align:left;padding:8px 3px;border-bottom:1px solid #dce5e5;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}summary{cursor:pointer;margin:18px 0}li{margin:10px 0}small{letter-spacing:.1em}</style><main><small>MARKETLAB / EVENT ECONOMICS</small><h1>What is the event actually worth?</h1><div class='banner'><b>Finite cash, not a perpetual earnings multiple.</b><p>Source-supported event amounts stay separate from hypothetical margins, cash timing, FX and overlap. No per-share value is invented. Pre-event prices are references, not post-event entry prices.</p></div>""" + f"<p>As of {esc(report['as_of'])}</p><div class='grid'>{''.join(cards)}</div></main></html>"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--plans", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.plans and args.plans.stat().st_size > 2 * 1024 * 1024:
        raise ChangeError("economic plans exceed byte limit")
    plans = loads_unique(args.plans.read_bytes()) if args.plans else []
    if not isinstance(plans, list) or len(plans) > 100:
        raise ChangeError("expected at most 100 economic plans")
    with EvidenceStore(args.workspace) as store:
        report = build_workspace(store, plans)
    writable_workspace(args.output_prefix.parent)
    args.output_prefix.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    args.output_prefix.with_suffix('.html').write_text(render(report), encoding='utf-8')
    print(json.dumps({"dossiers": len(report["dossiers"]), "unmatched_plan_sources": report["unmatched_plan_sources"],
                      "report_sha256": report["report_sha256"], "live_capital_allowed": False}))
    return int(bool(report["unmatched_plan_sources"]))


if __name__ == '__main__':
    raise SystemExit(main())
