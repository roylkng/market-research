"""Cash/solvency evidence over retained filings. A review screen, not stock advice."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, finite, public_url, strict_keys, timestamp
from marketlab.company_change_financials import extract_financials
from marketlab.company_change_store import EvidenceStore, loads_unique, now_utc, writable_workspace

VERSION = "CC001-UNDERWRITING-v1"
CAPEX = ("ppe_purchases", "intangible_purchases", "intangible_development")


def value(facts: dict, name: str) -> Decimal | None:
    fact = facts.get(name)
    return Decimal(fact["decimal_value"]) if fact is not None else None


def total(facts: dict, names: tuple[str, ...]) -> Decimal | None:
    values = [value(facts, name) for name in names]
    return sum(values, Decimal(0)) if all(v is not None for v in values) else None


def number(val: Decimal | None) -> float | None:
    return finite(val, "calculated amount") if val is not None else None


def reconcile(name: str, terms: list[tuple[int, dict | None]]) -> dict:
    """Respect reported rounding. No arbitrary tolerance hides a source mismatch."""
    if any(fact is None for _, fact in terms):
        return {"name": name, "status": "MISSING_INPUT", "residual": None, "tolerance": None}
    residual = sum((sign * Decimal(fact["decimal_value"]) for sign, fact in terms), Decimal(0))
    errors = [fact["rounding_error"] for _, fact in terms]
    tolerance = sum((Decimal(str(e)) for e in errors), Decimal(0)) if all(e is not None for e in errors) else None
    status = ("EXACT" if residual == 0 else "ROUNDING_UNKNOWN" if tolerance is None else
              "WITHIN_REPORTED_ROUNDING" if abs(residual) <= tolerance else "FAIL")
    return {"name": name, "status": status, "residual": number(residual), "tolerance": number(tolerance)}


def analyze_financials(document: dict, end: str) -> dict:
    periods = [p for p in document["periods"] if p["period_end"] == end and
               0 < (date.fromisoformat(end) - date.fromisoformat(p["period_start"])).days < 371]
    cash_periods = [p for p in periods if "cfo" in p["facts"]]
    period = min(cash_periods or periods, key=lambda p: p["period_start"], default=None)
    if period is None:
        raise ChangeError("no supported income/cash period ending on the selected date")
    start = period["period_start"]
    facts = period["facts"]
    closing = next((i["facts"] for i in document["instants"] if i["date"] == end), {})
    opening_date = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    opening = next((i["facts"] for i in document["instants"] if i["date"] == opening_date), {})
    cfo, pat = value(facts, "cfo"), value(facts, "group_pat")
    capex = total(facts, CAPEX)
    alerts, gaps = [], []
    if any(value(facts, f) is not None and value(facts, f) < 0 for f in CAPEX):
        alerts.append("AMBIGUOUS_CAPEX_SIGN")
        capex = None
    net_borrowings = None
    borrowings = total(closing, ("borrowings_current", "borrowings_noncurrent"))
    if borrowings is None:
        borrowings = value(closing, "borrowings_total")
    if borrowings is not None and borrowings < 0:
        alerts.append("NEGATIVE_REPORTED_BORROWINGS")
        borrowings = None
    cash = value(closing, "cash_equivalents")
    if borrowings is not None and cash is not None:
        net_borrowings = borrowings - cash
    asset, liability = value(closing, "current_assets"), value(closing, "current_liabilities")
    if cfo is not None and cfo < 0:
        alerts.append("NEGATIVE_OPERATING_CASH_FLOW")
    if cfo is not None and capex is not None and cfo < capex:
        alerts.append("OPERATING_CASH_BELOW_SPECIFIED_CAPEX")
    if capex is None:
        gaps.append("PPE/intangible/development cash purchases are incomplete or sign-ambiguous.")
    if cfo is None:
        gaps.append("No supported after-tax operating cash-flow total for this exact period.")
    if borrowings is None or cash is None:
        gaps.append("Borrowings or cash-equivalent balance is missing. Net borrowings are unknown.")
    tests = [
        reconcile("owner_plus_minority_equals_group_pat", [(1, facts.get("owner_pat")), (1, facts.get("minority_pat")), (-1, facts.get("group_pat"))]),
        reconcile("assets_equal_equity_plus_liabilities", [(1, closing.get("assets")), (-1, closing.get("equity")), (-1, closing.get("liabilities"))]),
        reconcile("assets_equal_reported_total", [(1, closing.get("assets")), (-1, closing.get("equity_and_liabilities"))]),
        reconcile("cash_rollforward", [(1, opening.get("cash_flow_cash")), (1, facts.get("cfo")),
            (1, facts.get("cfi")), (1, facts.get("cff")), (1, facts.get("fx_on_cash")), (-1, closing.get("cash_flow_cash"))]),
        reconcile("cash_change_matches_flows", [(1, facts.get("cfo")), (1, facts.get("cfi")), (1, facts.get("cff")),
            (1, facts.get("fx_on_cash")), (-1, facts.get("cash_change"))]),
        reconcile("cash_flow_cash_equals_balance_sheet_cash", [(1, closing.get("cash_flow_cash")), (-1, closing.get("cash_equivalents"))]),
    ]
    if value(closing, "borrowings_total") is not None and total(closing, ("borrowings_current", "borrowings_noncurrent")) is not None:
        tests.append(reconcile("borrowings_total_equals_components", [(1, closing["borrowings_current"]),
            (1, closing["borrowings_noncurrent"]), (-1, closing["borrowings_total"])]))
    if any(t["status"] == "FAIL" for t in tests):
        alerts.append("SOURCE_RECONCILIATION_REQUIRED")
    year_start = date.fromisoformat(start)
    year_end = date.fromisoformat(end)
    def last_year(day):
        try:
            return day.replace(year=day.year - 1).isoformat()
        except ValueError:
            return day.replace(year=day.year - 1, day=28).isoformat()
    peer = next((p for p in document["periods"] if p["period_start"] == last_year(year_start)
                 and p["period_end"] == last_year(year_end)), None)
    yoy = {}
    for field in ("revenue", "group_pat", "owner_pat", "cfo"):
        current, prior = value(facts, field), value(peer["facts"], field) if peer else None
        yoy[field] = {"current": number(current), "previous": number(prior),
            "growth_fraction": number(current / prior - 1) if current is not None and prior is not None and prior > 0 else None}
    if peer is None:
        gaps.append(f"Retrieve comparable {last_year(year_start)} to {last_year(year_end)} data. Seasonality is unresolved.")
    if "SOURCE_RECONCILIATION_REQUIRED" in alerts or "AMBIGUOUS_CAPEX_SIGN" in alerts:
        disposition = "RECONCILE_SOURCE_FIRST"
    elif cfo is None or capex is None:
        disposition = "CASH_EVIDENCE_INCOMPLETE"
    elif cfo < 0:
        disposition = "CASH_CONSUMPTION_REVIEW"
    elif cfo < capex:
        disposition = "REINVESTMENT_FUNDING_REVIEW"
    else:
        disposition = "CASH_COVERED_SPECIFIED_CAPEX"
    return {
        "period_start": start, "period_end": end, "duration_days": (year_end - year_start).days + 1,
        "cfo_crore": number(cfo), "specified_capex_crore": number(capex),
        "cfo_less_specified_capex_crore": number(cfo - capex) if cfo is not None and capex is not None else None,
        "cfo_to_group_pat": number(cfo / pat) if cfo is not None and pat is not None and pat > 0 else None,
        "gross_borrowings_crore": number(borrowings), "cash_equivalents_crore": number(cash),
        "net_borrowings_excluding_leases_crore": number(net_borrowings),
        "other_bank_balances_excluded_crore": number(value(closing, "other_bank_balances")),
        "current_ratio": number(asset / liability) if asset is not None and liability is not None and liability > 0 else None,
        "group_pat_crore": number(pat), "owner_pat_crore": number(value(facts, "owner_pat")),
        "checks": tests, "alerts": alerts, "disposition": disposition, "gaps": gaps, "same_source_year_ago": yoy,
        "cash_period_facts": facts, "closing_balance_facts": closing, "opening_cash_fact": opening.get("cash_flow_cash"),
        "limits": [
            "CFO/capex are period cash diagnostics, not annualized, maintenance-only or parent-distributable owner cash.",
            "Specified capex is disclosed PPE, intangible purchases and intangible development only. Other investments and acquisitions are separate.",
            "CFO is compared with same-period group PAT, not parent PAT. Minority rights remain relevant.",
            "Net borrowings exclude unclassified lease obligations and do not credit other bank balances or investments.",
            "Cash-flow/balance-sheet cash differences may reflect overdraft policy or restricted cash. A mismatch requires review, not silent repair.",
            "Current ratio is not sector-adjusted. It is not a solvency rating for banks, insurers or finance companies.",
        ], "live_capital_allowed": False,
    }


def entry_sensitivity(document: dict, case: dict, as_of: str) -> dict:
    """Explicit annual owner-earnings/denominator contract to the existing engine.

    This is an analyst scenario. Exact source quotes bind supplied normalization
    and share evidence but cannot independently certify their economic meaning.
    """
    from marketlab.company_change import valuation_card
    strict_keys(case, {"period_start", "period_end", "normalization", "shares", "specification"}, "entry case")
    period = next((p for p in document["periods"] if p["period_start"] == case["period_start"]
                   and p["period_end"] == case["period_end"]), None)
    if period is None or "owner_pat" not in period["facts"]:
        raise ChangeError("entry case requires source-backed owner PAT for the exact annual period")
    days = (date.fromisoformat(case["period_end"]) - date.fromisoformat(case["period_start"])).days + 1
    if not 360 <= days <= 371:
        raise ChangeError("interim owner earnings cannot be annualized for entry valuation")
    owner_check = reconcile("owner_plus_minority", [(1, period["facts"].get("owner_pat")),
        (1, period["facts"].get("minority_pat")), (-1, period["facts"].get("group_pat"))])
    if owner_check["status"] == "FAIL":
        raise ChangeError("owner-profit attribution does not reconcile")
    if timestamp(document["available_at"]) > timestamp(as_of):
        raise ChangeError("financial evidence unavailable at valuation cutoff")
    anchors = {}
    for field, unit in (("normalization", "INR_crore_after_tax_owner_adjustment"), ("shares", "fully_diluted_shares")):
        record = case[field]
        required = {"value", "unit", "reviewer", "reviewed_at", "source_url", "evidence_text", "quote", "literal", "identity"}
        required |= {"period_start", "period_end"} if field == "normalization" else {"effective_at", "capital_events_checked_through"}
        strict_keys(record, required, field)
        if set(record) != required:
            raise ChangeError("incomplete valuation evidence")
        if record["identity"] != document["identity"]:
            raise ChangeError("valuation evidence belongs to another issuer or scope")
        if field == "normalization":
            if any(record[k] != case[k] for k in ("period_start", "period_end")):
                raise ChangeError("normalization period differs from annual earnings")
        else:
            effective = timestamp(record["effective_at"])
            checked = timestamp(record["capital_events_checked_through"])
            quote_time = timestamp(case["specification"]["quote"]["quoted_at"])
            if not effective <= quote_time <= checked <= timestamp(record["reviewed_at"]):
                raise ChangeError("share evidence does not reconcile capital events through the quote date")
        if record["unit"] != unit or not isinstance(record["reviewer"], str) or not record["reviewer"].strip():
            raise ChangeError("unreviewed or wrong-unit valuation evidence")
        public_url(record["source_url"])
        if timestamp(record["reviewed_at"]) > timestamp(as_of):
            raise ChangeError("valuation evidence unavailable at cutoff")
        for key in ("evidence_text", "quote", "literal"):
            if not isinstance(record[key], str) or not record[key]:
                raise ChangeError("empty valuation evidence")
        if record["quote"] not in record["evidence_text"] or record["literal"] not in record["quote"]:
            raise ChangeError("valuation evidence does not contain supplied quote/literal")
        try:
            numeric = Decimal(record["literal"].replace(",", ""))
        except InvalidOperation as exc:
            raise ChangeError("valuation literal must be a numeric amount in the declared unit") from exc
        if numeric != Decimal(str(record["value"])):
            raise ChangeError("valuation amount differs from cited literal")
        finite(record["value"], field, minimum=0.000001 if field == "shares" else None)
        if field == "shares" and numeric != numeric.to_integral_value():
            raise ChangeError("fully diluted share evidence must be an integer count")
        anchors[field] = {"value": record["value"], "unit": unit, "evidence_sha256": canonical_hash(record)}
    identity = document["identity"]
    spec = case["specification"]
    if any(spec.get(k) != identity[k] for k in ("symbol", "isin", "scope")):
        raise ChangeError("valuation identity or scope mismatch")
    event = {**identity, "event_id": document["facts_sha256"], "period_start": case["period_start"],
             "period_end": case["period_end"], "semantic_review_required": False,
             "facts": {"owner_pat": period["facts"]["owner_pat"], "exceptional_owner_pat": anchors["normalization"],
                       "shares": anchors["shares"]}}
    result = valuation_card(event, spec, timestamp(as_of))
    result["illustrative_disposition"] = result["disposition"]
    result["disposition"] = "ANALYST_SCENARIO_NOT_INVESTMENT_APPROVAL"
    result["normalization_evidence"] = anchors
    result["limitations"].append("Normalization, current share dilution, source scope and reviewer identities are operator attestations, not independently certified.")
    return result


def build_underwriting(snapshot: dict, read_blob, *, evaluated_at: str | None = None, entry_cases: list | None = None) -> dict:
    evaluated = timestamp(evaluated_at or now_utc())
    if evaluated < timestamp(snapshot["as_of"]):
        raise ChangeError("new financial parsing cannot be backdated before the snapshot")
    # Check exactly the snapshot supplied, without modifying its frozen evidence.
    if snapshot["snapshot_sha256"] != canonical_hash({k: v for k, v in snapshot.items() if k != "snapshot_sha256"}):
        raise ChangeError("snapshot integrity failure")
    if entry_cases is not None and (not isinstance(entry_cases, list) or any(not isinstance(c, dict) for c in entry_cases)):
        raise ChangeError("entry cases must be a list of objects")
    groups = {}
    for row in snapshot["active"]:
        if row["kind"] != "earnings_quality":
            continue
        if timestamp(row["known_at"]) > timestamp(snapshot["as_of"]):
            raise ChangeError("future evidence in snapshot")
        identity = (row["symbol"], row["isin"], row["selector"]["scope"])
        groups.setdefault(identity, []).append(row)
    for case in entry_cases or []:
        spec = case.get("specification", {})
        if (spec.get("symbol"), spec.get("isin"), spec.get("scope")) not in groups:
            raise ChangeError("valuation case has no matching retained issuer/scope")
    cards, failures = [], []
    for identity, rows in sorted(groups.items()):
        selected = max(rows, key=lambda r: (r["selector"]["period_end"],
            timestamp(r.get("issuer_published_at") or r["known_at"]), timestamp(r["known_at"]), r["extraction_id"]))
        public_url(selected["url"])
        card = {"symbol": identity[0], "isin": identity[1], "scope": identity[2],
            "source_url": selected["url"], "raw_sha256": selected["raw_sha256"],
            "prior_extraction_id": selected["extraction_id"], "financial_fact_review": "UNREVIEWED",
            "parsed_at": evaluated.isoformat(), "live_capital_allowed": False}
        try:
            raw = read_blob(selected["raw_sha256"])
            if hashlib.sha256(raw).hexdigest() != selected["raw_sha256"]:
                raise ChangeError("retained source-byte integrity failure")
            doc = extract_financials(raw, {k: card[k] for k in ("symbol", "isin", "scope")}, evaluated.isoformat())
            card["analysis"] = analyze_financials(doc, selected["selector"]["period_end"])
            card["facts_sha256"] = doc["facts_sha256"]
            cases = [c for c in entry_cases or [] if all(c["specification"].get(k) == card[k] for k in ("symbol", "isin", "scope"))]
            if len(cases) > 1:
                raise ChangeError("multiple valuation cases for one issuer/scope")
            card["entry_case"] = entry_sensitivity(doc, cases[0], evaluated.isoformat()) if cases else None
            card["valuation_status"] = "EXPLICIT_ANALYST_SCENARIO" if cases else "MISSING_PRICE_NORMALIZATION_AND_DILUTED_SHARE_EVIDENCE"
            if selected.get("review_status") == "REJECT":
                card["analysis"]["alerts"].append("ANCHOR_EXTRACTION_REJECTED")
                card["analysis"]["disposition"] = "RECONCILE_SOURCE_FIRST"
        except (ValueError, TypeError, KeyError, OSError) as exc:
            card["analysis"] = None
            card["failure"] = str(exc)
            failures.append({"symbol": identity[0], "scope": identity[2], "reason": str(exc)})
        cards.append(card)
    implementation = canonical_hash({name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ("company_change_underwriting.py", "company_change_financials.py", "company_change.py")})
    result = {"engine": VERSION, "implementation_sha256": implementation, "evaluated_at": evaluated.isoformat(), "snapshot_sha256": snapshot["snapshot_sha256"],
        "cards": cards, "failures": failures, "counts": {"issuers": len({c["isin"] for c in cards}),
            "scope_cards": len(cards), "analyzed": sum(c["analysis"] is not None for c in cards),
            "failed": len(failures), "dispositions": dict(Counter(c["analysis"]["disposition"] for c in cards if c["analysis"]))},
        "live_capital_allowed": False, "validated_predictive_edge": False,
        "limitations": ["All newly extracted financial facts are unreviewed. Earlier income-statement acceptance does not approve new cash/debt fields.",
            "Current-source coverage is not an independently selected performance sample.",
            "Missing year-ago disclosures, cash restrictions, maintenance reinvestment and share dilution are not inferred."]}
    result["report_sha256"] = canonical_hash(result)
    return result


def render_underwriting(report: dict) -> str:
    def esc(v):
        return html.escape(str(v), quote=True)
    def num(v):
        return "Unknown" if v is None else f"{v:,.2f}"
    body = []
    for c in report["cards"]:
        a = c["analysis"]
        if a is None:
            body.append(f"<article><h2>{esc(c['symbol'])}</h2><p>{esc(c['scope'])}</p><b>Extraction incomplete</b><p>{esc(c['failure'])}</p></article>")
            continue
        rows = "".join(f"<tr><td>{label}</td><td>{num(a[field])}</td></tr>" for field, label in (
            ("cfo_crore", "Operating cash flow"), ("specified_capex_crore", "PPE + intangible cash purchases"),
            ("cfo_less_specified_capex_crore", "Operating cash less those purchases"),
            ("gross_borrowings_crore", "Gross borrowings"), ("cash_equivalents_crore", "Cash equivalents"),
            ("net_borrowings_excluding_leases_crore", "Borrowings less cash, excluding leases")))
        gaps = "".join(f"<li>{esc(g)}</li>" for g in a["gaps"])
        checks = "".join(f"<li>{esc(t['name'])}: <b>{esc(t['status'])}</b></li>" for t in a["checks"])
        body.append(f"<article><div class='tag'>{esc(a['disposition'].replace('_',' '))}</div><h2>{esc(c['symbol'])}</h2>"
            f"<p>{esc(c['scope'])} · {esc(a['period_start'])} to {esc(a['period_end'])}</p><table>{rows}</table>"
            f"<p class='small'>₹ crore. Cash purchase gap is not normalized owner free cash flow.</p>"
            f"<details><summary>Evidence, reconciliation and decision gaps</summary><a href='{esc(c['source_url'])}'>Original filing</a>"
            f"<p><code>{esc(c['raw_sha256'])}</code></p><ul>{checks}</ul><ul>{gaps}</ul>"
            f"<p>{esc(c['valuation_status'])}</p><pre>{esc(json.dumps(a['cash_period_facts'],indent=2))}</pre></details></article>")
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Cash and balance-sheet review</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f5;color:#193540;font:15px system-ui}main{max-width:1250px;margin:auto;padding:32px 22px}h1{font-size:36px}.tag{font-size:11px;letter-spacing:.07em}h2{margin:10px 0}.banner{background:#193540;color:white;padding:22px;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,355px),1fr));gap:18px;margin:24px 0}article{background:white;min-width:0;border:1px solid #d0dedd;border-radius:12px;padding:22px}table{width:100%;font-size:13px;border-collapse:collapse}td{padding:10px 3px;border-bottom:1px solid #dde6e5;overflow-wrap:anywhere}td:last-child{text-align:right}pre,code{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}.small{font-size:12px}summary{cursor:pointer;font-weight:600;margin-top:16px}a{color:#006a62}li{margin:8px 0}</style>
<main><div class='tag'>MARKETLAB / CASH AND BALANCE-SHEET EVIDENCE</div><h1>Does reported profit turn into cash?</h1>
<div class='banner'><b>Research screen, not an investment recommendation.</b><p>New cash/debt facts require review. Growth capex can consume cash without destroying value. Current valuation, cash restrictions, seasonality and owner-earnings normalization remain explicit evidence requirements.</p></div>
""" + f"<p>{report['counts']['issuers']} issuers · {report['counts']['analyzed']} analyzed scope cards · {report['counts']['failed']} extraction failures</p><div class='grid'>{''.join(body)}</div><p class='small'>Parsed at {esc(report['evaluated_at'])}<br>Report <code>{esc(report['report_sha256'])}</code></p></main></html>"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--entry-cases", type=Path)
    args = parser.parse_args(argv)
    folder = writable_workspace(args.output_prefix.parent)
    with EvidenceStore(args.workspace) as store:
        cases = loads_unique(args.entry_cases.read_text()) if args.entry_cases else []
        report = build_underwriting(store.snapshot(), store.read_blob, entry_cases=cases)
    for suffix, payload in (("json", json.dumps(report, indent=2, allow_nan=False)), ("html", render_underwriting(report))):
        path = folder / f"{report['report_sha256']}.{suffix}"
        raw = payload.encode("utf-8")
        try:
            with path.open("xb") as stream:
                stream.write(raw)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ChangeError("refusing inconsistent content-addressed underwriting export")
        args.output_prefix.with_suffix("." + suffix).write_text(payload, encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "report_sha256": report["report_sha256"], "live_capital_allowed": False}))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
