"""Auditable reported-business changes. Review cues, never forecasts or stock ranks."""
from __future__ import annotations

import argparse
import calendar
import html
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, finite, public_url, timestamp
from marketlab.company_change_store import EvidenceStore, writable_workspace

VERSION = "CC001-COMPARISONS-v1"
# Flows only. EPS, shares, capital and other stock/ratio measures are NOT additive.
FLOW_FIELDS = ("revenue", "other_income", "pbt", "pretax_exceptional_items",
               "tax_expense", "reported_pat", "owner_pat", "noncontrolling_pat")
POLICY = {"revenue_change_fraction": 0.10, "pbt_margin_change_pp": 2.0,
          "class": "FIXED_UNVALIDATED_REVIEW_THRESHOLDS_NOT_INVESTMENT_SIGNALS"}


def shift_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def full_months(selector: dict, count: int) -> bool:
    start = date.fromisoformat(selector["period_start"])
    end = date.fromisoformat(selector["period_end"])
    return start.day == 1 and shift_months(start, count) == end + timedelta(days=1)


def reference(row: dict) -> dict:
    return {"extraction_id": row["extraction_id"], "raw_sha256": row["raw_sha256"],
            "source_id": row["source_id"], "url": row["url"], "selector": row["selector"],
            "known_at": row["known_at"], "review_status": row["review_status"]}


def amount(row: dict, field: str) -> float | None:
    fact = row["facts"].get(field)
    if fact is None:
        return None
    expected = "INR_per_share" if field == "diluted_eps" else "INR_crore"
    if fact.get("unit") != expected:
        raise ChangeError(f"incompatible units for {field}")
    if isinstance(fact.get("value"), bool):
        raise ChangeError(f"boolean is not a financial amount: {field}")
    return finite(fact["value"], field)


def period_record(rows: list[dict], start: str, end: str, current: dict) -> dict | None:
    # Refuse cross-document subtraction or mixed/restated comparative sources.
    matches = [r for r in rows if r["selector"]["period_start"] == start
               and r["selector"]["period_end"] == end
               and r["raw_sha256"] == current["raw_sha256"]
               and all(r[k] == current[k] for k in ("symbol", "isin"))
               and r["selector"]["scope"] == current["selector"]["scope"]]
    if len(matches) > 1:
        raise ChangeError("ambiguous same-source accounting period")
    return matches[0] if matches else None


def comparative(current: dict, rows: list[dict], *, year_ago: bool) -> dict:
    start = date.fromisoformat(current["selector"]["period_start"])
    end = date.fromisoformat(current["selector"]["period_end"])
    previous_start = shift_months(start, -12 if year_ago else -3)
    previous_end = shift_months(start, -9) - timedelta(days=1) if year_ago else start - timedelta(days=1)
    direct = period_record(rows, previous_start.isoformat(), previous_end.isoformat(), current)
    if direct:
        warnings = list(direct.get("warnings", []))
        if not year_ago:
            total = period_record(rows, previous_start.isoformat(), end.isoformat(), current)
            if total and full_months(total["selector"], 6):
                for field in FLOW_FIELDS:
                    a, b, c = amount(direct, field), amount(current, field), amount(total, field)
                    if a is not None and b is not None and c is not None and abs(a + b - c) > 1e-6:
                        warnings.append(f"Direct {field} quarters do not sum to the half-year. Check rounding and comparability before interpreting change.")
        return {"method": "DIRECT_SAME_DISCLOSURE", "selector": direct["selector"],
                "values": {k: amount(direct, k) for k in FLOW_FIELDS},
                "diluted_eps": amount(direct, "diluted_eps"), "evidence": [reference(direct)],
                "warnings": warnings, "known_at": direct["known_at"]}
    if year_ago:
        return {"method": "UNAVAILABLE", "reason": "No exact prior-year quarter in the same retained disclosure."}
    prefix = period_record(rows, previous_start.isoformat(), end.isoformat(), current)
    if prefix is None or not full_months(prefix["selector"], 6):
        return {"method": "UNAVAILABLE", "reason": "No exact previous quarter or matching half-year in this disclosure."}
    values, equations = {}, {}
    for field in FLOW_FIELDS:
        total, quarter = amount(prefix, field), amount(current, field)
        values[field] = finite(total - quarter, field) if total is not None and quarter is not None else None
        if values[field] is not None:
            equations[field] = {"operation": "SUBTRACT", "total": total, "quarter": quarter,
                                "result": values[field], "unit": "INR_crore"}
    return {"method": "DERIVED_HALF_YEAR_MINUS_CURRENT_QUARTER",
            "selector": {"period_start": previous_start.isoformat(), "period_end": previous_end.isoformat(),
                         "scope": current["selector"]["scope"]},
            "values": values, "equations": equations, "diluted_eps": None,
            "evidence": [reference(prefix), reference(current)], "warnings": list(prefix.get("warnings", [])),
            "known_at": max(timestamp(prefix["known_at"]), timestamp(current["known_at"])).isoformat(),
            "limitations": ["Derived reported flows subject to source rounding, not a separately reported quarter.",
                            "EPS, share counts and balance-sheet stocks are never subtracted."]}


def delta(current: float | None, previous: float | None) -> dict:
    if current is None or previous is None:
        return {"current": current, "previous": previous, "absolute_change": None,
                "growth_fraction": None, "basis": "MISSING"}
    return {"current": current, "previous": previous, "absolute_change": finite(current - previous, "change"),
            "growth_fraction": finite(current / previous - 1, "growth") if previous > 0 else None,
            "basis": "POSITIVE_BASE" if previous > 0 else "NONPOSITIVE_BASE_NO_PERCENTAGE"}


def compare_values(current: dict, previous: dict) -> dict:
    values = previous.get("values", {})
    metrics = {k: delta(amount(current, k), values.get(k)) for k in FLOW_FIELDS}
    revenue, pbt = metrics["revenue"], metrics["pbt"]
    current_margin = 100 * pbt["current"] / revenue["current"] if revenue["current"] and revenue["current"] > 0 and pbt["current"] is not None else None
    prior_margin = 100 * pbt["previous"] / revenue["previous"] if revenue["previous"] and revenue["previous"] > 0 and pbt["previous"] is not None else None
    metrics["pbt_margin"] = {"current_pct": current_margin, "previous_pct": prior_margin,
        "change_pp": current_margin - prior_margin if current_margin is not None and prior_margin is not None else None}
    return metrics


def build_comparisons(snapshot: dict) -> dict:
    cutoff = timestamp(snapshot["as_of"])
    groups = {}
    for row in snapshot["active"]:
        if row["kind"] != "earnings_quality":
            continue
        if timestamp(row["known_at"]) > cutoff:
            raise ChangeError("future extraction in comparison snapshot")
        public_url(row["url"])
        if row["review_status"] not in {"ACCEPT", "REJECT", "UNREVIEWED"}:
            raise ChangeError("invalid review status")
        selector = row["selector"]
        if date.fromisoformat(selector["period_end"]) > timestamp(row["known_at"]).date():
            raise ChangeError("reporting period ends after observation")
        if selector["scope"] not in {"STANDALONE", "CONSOLIDATED"}:
            raise ChangeError("invalid comparison scope")
        if date.fromisoformat(selector["period_start"]) > date.fromisoformat(selector["period_end"]):
            raise ChangeError("reversed comparison period")
        key = (row["symbol"], row["isin"], selector["scope"])
        groups.setdefault(key, []).append(row)
    cards = []
    for (symbol, isin, scope), rows in sorted(groups.items()):
        newest = max(r["selector"]["period_end"] for r in rows)
        quarters = [r for r in rows if r["selector"]["period_end"] == newest and full_months(r["selector"], 3)]
        if len(quarters) > 1:
            raise ChangeError("ambiguous current quarter in company state")
        if not quarters:
            cards.append({"symbol": symbol, "isin": isin, "scope": scope,
                "period_end": newest, "attention": "INSUFFICIENT_COMPARISON", "flags": [],
                "blockers": ["Latest filing does not contain an exact three-month quarter. No annualization performed."],
                "current": None, "sequential": None, "year_ago": None,
                "metrics": {}, "live_capital_allowed": False})
            continue
        current = quarters[0]
        sequential = comparative(current, rows, year_ago=False)
        year_ago = comparative(current, rows, year_ago=True)
        metrics = compare_values(current, sequential)
        year_ago_metrics = compare_values(current, year_ago)
        flags, positive, negative = [], False, False
        growth = metrics["revenue"]["growth_fraction"]
        margin_change = metrics["pbt_margin"]["change_pp"]
        if growth is not None:
            if growth >= POLICY["revenue_change_fraction"]:
                flags.append("REPORTED_REVENUE_EXPANSION")
                positive = True
            if growth <= -POLICY["revenue_change_fraction"]:
                flags.append("REPORTED_REVENUE_CONTRACTION")
                negative = True
        if margin_change is not None:
            if margin_change >= POLICY["pbt_margin_change_pp"]:
                flags.append("REPORTED_PBT_MARGIN_EXPANSION")
                positive = True
            if margin_change <= -POLICY["pbt_margin_change_pp"]:
                flags.append("REPORTED_PBT_MARGIN_COMPRESSION")
                negative = True
        current_pbt, prior_pbt = metrics["pbt"]["current"], metrics["pbt"]["previous"]
        if current_pbt is not None and prior_pbt is not None and prior_pbt <= 0 < current_pbt:
            flags.append("REPORTED_PBT_TURNAROUND")
            positive = True
        if current_pbt is not None and current_pbt < 0:
            flags.append("REPORTED_PRETAX_LOSS")
            negative = True
        blockers = list(current.get("warnings", [])) + list(sequential.get("warnings", []))
        prior_revenue = metrics["revenue"]["previous"]
        inconsistent_derived_revenue = prior_revenue is not None and prior_revenue < 0
        if inconsistent_derived_revenue:
            blockers.append("Prior-quarter revenue is negative. Review accounting adjustments and period comparability.")
        if sequential["method"] == "UNAVAILABLE":
            attention = "INSUFFICIENT_COMPARISON"
            blockers.append(sequential["reason"])
        elif positive and negative:
            attention = "MIXED_REPORTED_CHANGE"
        elif positive:
            attention = "REPORTED_IMPROVEMENT_REVIEW"
        elif negative:
            attention = "REPORTED_DETERIORATION_REVIEW"
        else:
            attention = "NO_THRESHOLD_CROSSED"
        other = amount(current, "other_income")
        exception = amount(current, "pretax_exceptional_items")
        if other is not None and current_pbt is not None and 0 < current_pbt <= other:
            flags.append("OTHER_INCOME_AT_LEAST_REPORTED_PBT")
            blockers.append("Other income is at least reported PBT. This ratio does not establish nonrecurrence or operating earnings.")
        if exception is not None and exception != 0:
            flags.append("PRETAX_EXCEPTIONAL_ITEM_PRESENT")
            blockers.append("Exceptional items are present. Reported PBT changes are not recurring owner-earnings changes.")
        if year_ago["method"] == "UNAVAILABLE":
            blockers.append("No same-disclosure year-ago comparison. Seasonality remains unresolved.")
        references = [reference(current)] + sequential.get("evidence", []) + year_ago.get("evidence", [])
        if any(r["review_status"] != "ACCEPT" for r in references):
            blockers.append("One or more source extractions are unreviewed or rejected.")
        if any(r["review_status"] == "REJECT" for r in references) or current.get("warnings") or sequential.get("warnings") or inconsistent_derived_revenue:
            attention = "ACCOUNTING_REVIEW_REQUIRED"
        blockers.extend(["No current price, balance-sheet valuation or execution-cost assessment is attached.",
                         "Cash conversion, recurring owner earnings and diluted share reconciliation remain separate checks."])
        cards.append({"symbol": symbol, "isin": isin, "scope": scope, "period_end": newest,
            "attention": attention, "flags": flags, "blockers": list(dict.fromkeys(blockers)),
            "current": reference(current), "sequential": sequential, "year_ago": year_ago,
            "metrics": metrics, "year_ago_metrics": year_ago_metrics,
            "reported_diluted_eps": amount(current, "diluted_eps"),
            "derived_prior_quarter_eps": None, "live_capital_allowed": False})
    report = {"engine": VERSION, "as_of": snapshot["as_of"],
        "snapshot_sha256": snapshot["snapshot_sha256"], "policy": POLICY, "cards": cards,
        "counts": {"issuers": len({c["isin"] for c in cards}), "scope_cards": len(cards),
            "attention": dict(Counter(c["attention"] for c in cards)),
            "derived_quarters": sum(c["sequential"] is not None and c["sequential"]["method"] == "DERIVED_HALF_YEAR_MINUS_CURRENT_QUARTER" for c in cards)},
        "live_capital_allowed": False, "validated_predictive_edge": False,
        "limitations": ["Unreviewed reported accounting changes are review cues, not investment recommendations.",
            "The processing queue is not a representative stock universe or ranked investment portfolio.",
            "Sequential comparisons can be seasonal. No learned predictor or outcome data are used.",
            "These fixed thresholds are unvalidated and were not optimized on subsequent returns."]}
    report["report_sha256"] = canonical_hash(report)
    return report


def render_comparisons(report: dict) -> str:
    def esc(value):
        return html.escape(str(value), quote=True)
    def pct(value):
        return "Unknown" if value is None else f"{value:+.1f}%"
    def money(value):
        return "Unknown" if value is None else f"{value:,.2f}"
    cards = []
    for card in report["cards"]:
        m = card["metrics"]
        growth = m.get("revenue", {}).get("growth_fraction")
        change = m.get("pbt_margin", {}).get("change_pp")
        blockers = "".join(f"<li>{esc(b)}</li>" for b in card["blockers"])
        source = card["current"]
        source_html = (f"<a href='{esc(source['url'])}' rel='noopener noreferrer'>Original filing</a>"
            f"<p>Source SHA-256 <code>{esc(source['raw_sha256'])}</code></p>") if source else ""
        method = card["sequential"]["method"] if card["sequential"] else "UNAVAILABLE"
        prior_revenue = m.get("revenue", {}).get("previous")
        current_revenue = m.get("revenue", {}).get("current")
        cards.append(f"<article><div class='tag'>{esc(card['attention'].replace('_', ' '))}</div>"
            f"<h2>{esc(card['symbol'])}</h2><p>{esc(card['scope'])} · quarter ended {esc(card['period_end'])}</p>"
            f"<div class='numbers'><div><b>{pct(growth * 100 if growth is not None else None)}</b><span>Revenue vs previous quarter</span></div>"
            f"<div><b>{'Unknown' if change is None else f'{change:+.2f} pp'}</b><span>Reported PBT margin change</span></div></div>"
            f"<p class='small'>Revenue ₹ crore: {money(prior_revenue)} → {money(current_revenue)}</p>"
            f"<p class='small'>Comparison: {esc(method.replace('_', ' '))}</p><details><summary>Evidence and decision gaps</summary>"
            f"{source_html}<ul>{blockers}</ul><pre>{esc(json.dumps(card['sequential'], indent=2))}</pre></details></article>")
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>CC001 business-change review</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6f5;color:#183440;font:15px system-ui}main{max-width:1240px;padding:32px 22px;margin:auto}
h1{font-size:36px}.tag{font-size:11px;letter-spacing:.09em}.banner{background:#183440;color:white;padding:22px;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));gap:18px;margin:24px 0}
article{min-width:0;background:white;border:1px solid #d0dedd;border-radius:12px;padding:22px}h2{margin:8px 0}.numbers{display:flex;flex-wrap:wrap;gap:18px}.numbers b{display:block;font-size:28px}.numbers span,.small{font-size:12px}pre,code{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;margin-top:18px}li{margin:10px 0}a{color:#00655e}</style>
<main><div class='tag'>MARKETLAB / REPORTED BUSINESS CHANGES</div><h1>What changed in the business?</h1>
<div class='banner'><b>Accounting comparisons, not buy recommendations.</b><p>Prior-quarter flows can be derived only from a matching half-year and quarter in the same disclosure. EPS is never subtracted. Seasonality, cash conversion and valuation are unresolved.</p></div>
""" + f"<p>{report['counts']['issuers']} issuers · {report['counts']['scope_cards']} scope-specific cards · as of {esc(report['as_of'])}</p>" \
        f"<div class='grid'>{''.join(cards)}</div><p class='small'>Report SHA-256 <code>{esc(report['report_sha256'])}</code></p></main></html>"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args(argv)
    writable_workspace(args.output_prefix.parent)
    with EvidenceStore(args.workspace) as store:
        report = build_comparisons(store.snapshot())
    # Explicit latest-view exports. Source records remain immutable in the store.
    args.output_prefix.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    args.output_prefix.with_suffix(".html").write_text(render_comparisons(report), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "report_sha256": report["report_sha256"], "live_capital_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
