"""Historical evidence and dated price context, without invented owner earnings.

All historical documents are observed now. Neither reconstructed history nor
price-implied scenarios are prospective prediction results or trade approval.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

from marketlab.company_change import ChangeError, canonical_hash, finite, timestamp
from marketlab.company_change_pipeline import fetch_original, project_html
from marketlab.company_change_prices import archive_close, quote_session
from marketlab.company_change_store import EvidenceStore, loads_unique, writable_workspace
from marketlab.company_change_tables import PERIOD, extract_statement

VERSION = "CC001-CONTEXT-v1"
HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com"}
IST = ZoneInfo("Asia/Kolkata")
FLOW_FIELDS = ("revenue", "group_pat", "owner_pat", "cfo")
CAPEX = ("ppe_purchases", "intangible_purchases", "intangible_development")


def day(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    raise ChangeError("unrecognized source date")


def year_ago(value: str) -> str:
    d = date.fromisoformat(value)
    try:
        return d.replace(year=d.year - 1).isoformat()
    except ValueError:
        return d.replace(year=d.year - 1, day=28).isoformat()


def source_time(value: str) -> datetime:
    try:
        return timestamp(value)
    except ChangeError:
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%m-%Y %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=IST)
            except (ValueError, TypeError):
                continue
    raise ChangeError("unrecognized source timestamp")


def rows(payload) -> list:
    value = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(value, list):
        raise ChangeError("source response has no row list")
    return value


def retain_json(store: EvidenceStore, payload, raw: bytes, url: str) -> dict:
    if canonical_hash(loads_unique(raw)) != canonical_hash(payload):
        raise ChangeError("source response bytes differ from parsed JSON")
    return store.capture(raw, {"url": url, "origin": "HTTP_RESPONSE_BYTES", "lane": VERSION})


def parse_quote(payload: dict, identity: dict, observed_at: str) -> dict:
    info, metadata = payload.get("info", {}), payload.get("metadata", {})
    if info.get("symbol") != identity["symbol"]:
        raise ChangeError("quote symbol mismatch")
    isins = {v for v in (info.get("isin"), metadata.get("isin")) if v}
    if isins != {identity["isin"]} or metadata.get("series") != "EQ":
        raise ChangeError("quote ISIN or EQ series is not verified")
    observed = timestamp(observed_at)
    quoted = source_time(metadata.get("lastUpdateTime"))
    if quoted > observed:
        raise ChangeError("quote timestamp is in the future")
    price = finite(payload.get("priceInfo", {}).get("lastPrice"), "last traded price", minimum=0.000001)
    return {"price": price, "currency": "INR", "quoted_at": quoted.isoformat(),
            "observed_at": observed.isoformat(), "price_type": "LAST_TRADED_OBSERVATION_NOT_EXECUTABLE_CLOSE",
            "stale": (observed - quoted).total_seconds() > 7 * 86400,
            "identity": identity, "live_capital_allowed": False}


def parse_actions(payload, symbol: str, start: str, end: str) -> dict:
    changes, excluded = [], 0
    for row in rows(payload):
        if not isinstance(row, dict):
            raise ChangeError("malformed corporate action")
        if row.get("symbol") != symbol:
            excluded += 1
            continue
        ex_date = day(row.get("exDate")).isoformat()
        if not start < ex_date <= end:
            continue
        subject = row.get("subject")
        if not isinstance(subject, str) or not subject.strip():
            raise ChangeError("corporate-action purpose missing")
        # Dividends alone do not change a share denominator. Unknown purposes
        # are NOT silently ignored. Mixed dividend/bonus actions are blocking.
        simple_dividend = "dividend" in subject.casefold() and not any(
            word in subject.casefold() for word in ("bonus", "split", "right", "merger", "consolidation", "capital", "scheme"))
        if not simple_dividend:
            changes.append({"ex_date": ex_date, "subject": subject, "row_sha256": canonical_hash(row)})
    return {"start_exclusive": start, "end_inclusive": end, "share_basis_changes_or_unknown_actions": changes,
            "other_symbols_excluded": excluded, "coverage": "EXCHANGE_RESPONSE_NOT_INDEPENDENT_CAPITAL_EVENT_AUDIT"}


def number(period: dict | None, field: str) -> float | None:
    fact = period.get("facts", {}).get(field) if period else None
    if fact is None:
        return None
    expected = "INR_per_share" if field == "diluted_eps" else "INR_crore"
    if fact.get("unit") != expected:
        raise ChangeError("historical financial unit mismatch")
    return finite(fact["value"], field)


def period_refs(period: dict) -> dict:
    return {k: period[k] for k in ("period_start", "period_end", "source_url", "raw_sha256", "known_at")}


def compare_period(current: dict, previous: dict | None) -> dict:
    metrics = {}
    for field in FLOW_FIELDS:
        current_value, previous_value = number(current, field), number(previous, field)
        metrics[field] = {"current": current_value, "previous": previous_value,
            "reported_growth_fraction": current_value / previous_value - 1
            if current_value is not None and previous_value is not None and previous_value > 0 else None}
    return {"metrics": metrics, "current_evidence": period_refs(current),
            "previous_evidence": period_refs(previous) if previous else None,
            "basis": "SAME_SOURCE" if previous and current["raw_sha256"] == previous["raw_sha256"]
            else "CROSS_SOURCE_REPORTED_NOT_RESTATEMENT_RECONCILED" if previous else "MISSING_EXACT_YEAR_AGO_PERIOD"}


def select_period(periods: list, start: str, end: str, preferred_sha: str = "") -> dict | None:
    candidates = [p for p in periods if p["period_start"] == start and p["period_end"] == end]
    if not candidates:
        return None
    # A later public restatement wins. An observation timestamp is not a
    # replacement for publication ordering. Same-time conflicts are rejected.
    latest = max(timestamp(p["published_at"]) for p in candidates)
    candidates = [p for p in candidates if timestamp(p["published_at"]) == latest]
    signatures = {canonical_hash({k: (v["value"], v["unit"]) for k, v in p["facts"].items()}) for p in candidates}
    if len(signatures) != 1:
        raise ChangeError("conflicting same-publication historical periods")
    return max(candidates, key=lambda p: (p["raw_sha256"] == preferred_sha, timestamp(p["known_at"])))


def build_card(identity: dict, periods: list, current_end: str, quote: dict | None,
               actions: dict | None, as_of: str) -> dict:
    cutoff = timestamp(as_of)
    if (set(identity) != {"symbol", "isin", "scope"}
            or not re.fullmatch(r"[A-Z0-9&._-]{1,30}", str(identity["symbol"]))
            or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", str(identity["isin"]))
            or identity["scope"] not in {"STANDALONE", "CONSOLIDATED"}):
        raise ChangeError("invalid research identity")
    for p in periods:
        if p["identity"] != identity:
            raise ChangeError("cross-issuer or cross-scope history")
        if timestamp(p["known_at"]) > cutoff or timestamp(p["published_at"]) > cutoff:
            raise ChangeError("historical evidence unavailable at cutoff")
        if day(p["period_start"]) > day(p["period_end"]) or day(p["period_end"]) > cutoff.date():
            raise ChangeError("invalid financial period")
    current_options = [p for p in periods if p["period_end"] == current_end]
    # Same-end overlapping source periods are selected explicitly, never added.
    ends = sorted({(p["period_start"], p["period_end"]) for p in current_options})
    comparisons = []
    for start, end in ends:
        current = select_period(periods, start, end)
        peer = select_period(periods, year_ago(start), year_ago(end), current["raw_sha256"])
        comparisons.append(compare_period(current, peer))
    annuals = [p for p in periods if 360 <= (day(p["period_end"]) - day(p["period_start"])).days + 1 <= 371
               and p["period_end"] <= current_end and (day(current_end) - day(p["period_end"])).days <= 550]
    annual = None
    if annuals:
        candidate = max(annuals, key=lambda p: p["period_end"])
        annual = select_period(periods, candidate["period_start"], candidate["period_end"])
    ttm = None
    if annual:
        next_start = (day(annual["period_end"]) + timedelta(days=1)).isoformat()
        interim = select_period(periods, next_start, current_end)
        prior = select_period(periods, annual["period_start"], year_ago(current_end))
        if interim and prior and day(prior["period_end"]) < day(annual["period_end"]):
            fields = {}
            for field in FLOW_FIELDS + CAPEX:
                a, b, c = number(annual, field), number(interim, field), number(prior, field)
                fields[field] = {"annual": a, "current_interim": b, "prior_interim": c,
                    "value": finite(Decimal(str(a)) + Decimal(str(b)) - Decimal(str(c)), field)
                    if a is not None and b is not None and c is not None else None}
            ttm = {"start": (day(prior["period_end"]) + timedelta(days=1)).isoformat(), "end": current_end,
                   "fields": fields, "formula": "ANNUAL + CURRENT_INTERIM - PRIOR_INTERIM",
                   "sources": [period_refs(p) for p in (annual, interim, prior)],
                   "basis": "REPORTED_CROSS_DOCUMENT_NOT_NORMALIZED_OR_RESTATEMENT_RECONCILED"}
    blockers = []
    if not current_options:
        blockers.append("No parsed financial evidence for the current anchor period.")
    eps = number(annual, "diluted_eps")
    ratio, scenarios = None, []
    if not annual:
        blockers.append("No supported full-year financial period. Interim earnings were not annualized.")
    if eps is None or eps <= 0:
        blockers.append("Positive reported annual diluted EPS is missing.")
    if quote is None:
        blockers.append("No verified dated exchange price.")
    else:
        if (quote["identity"] != identity or timestamp(quote["observed_at"]) > cutoff
                or quote.get("quoted_at") is not None and timestamp(quote["quoted_at"]) > timestamp(quote["observed_at"])):
            raise ChangeError("quote identity or information clock mismatch")
        if (cutoff.astimezone(IST).date() - quote_session(quote)).days > 7:
            blockers.append("Exchange observation is more than seven calendar days old.")
    if actions is not None and actions.get("observed_at") and timestamp(actions["observed_at"]) > cutoff:
        raise ChangeError("corporate actions unavailable at cutoff")
    if actions is None:
        blockers.append("Corporate-action response unavailable. Share-price/EPS comparison withheld.")
    elif annual and (actions["start_exclusive"] > annual["period_end"] or
                     quote and actions["end_inclusive"] < quote_session(quote).isoformat()):
        blockers.append("Corporate-action window does not cover the annual EPS date through the price.")
    elif annual and any(annual["period_end"] < change["ex_date"] <= actions["end_inclusive"]
                        for change in actions.get("share_basis_changes_or_unknown_actions", [])):
        blockers.append("Share-basis change or unclassified corporate action requires reconciliation.")
    if not blockers:
        ratio = quote["price"] / eps
        # Reverse hurdle, not a forecast. No growth estimate, exit multiple,
        # fair value or outcome probability is claimed to have been learned.
        for multiple in (12, 15, 18):
            required_growth = (ratio * 1.15**5 / multiple) ** .2 - 1
            scenarios.append({"years": 5, "target_price_cagr": .15, "exit_pe_assumption": multiple,
                              "required_annual_eps_growth": required_growth,
                              "baseline": "UNNORMALIZED_REPORTED_ANNUAL_DILUTED_EPS"})
    gaps = ["Reported earnings are not normalized owner earnings.",
            "An empty exchange action response is not proof of no issuance, dilution or restatement.",
            "Share-basis adjustments, fully diluted shares and cash restrictions still require review.",
            "Reverse-hurdle scenarios omit dividends, taxes and transaction costs and assume unchanged EPS comparability.",
            "A single year-ago comparison does not establish multi-year seasonality or sustainable growth."]
    return {"identity": identity, "as_of": as_of, "current_period_end": current_end,
            "year_ago_comparisons": comparisons, "reported_ttm_flows": ttm,
            "annual_evidence": period_refs(annual) if annual else None,
            "reported_annual_diluted_eps": eps, "quote": quote, "corporate_actions": actions,
            "price_over_reported_annual_eps": ratio, "reverse_hurdle_scenarios": scenarios,
            "blockers": blockers, "limitations": gaps, "disposition": "RESEARCH_CONTEXT_NOT_BUY_APPROVAL",
            "live_capital_allowed": False, "validated_predictive_edge": False}


def parse_document(raw: bytes, url: str, identity: dict, known_at: str, published_at: str) -> list:
    if urlsplit(url).path.lower().endswith(".xml"):
        from marketlab.company_change_financials import extract_financials
        periods = extract_financials(raw, identity, known_at)["periods"]
    else:
        tables, _ = project_html(raw)
        selectors = set()
        for table in tables:
            headers = {}
            for key, label in PERIOD.items():
                matches = [r[r.index(label) + 1:] for r in table if label in r]
                if len(matches) == 1:
                    headers[key] = matches[0]
            if set(headers) != set(PERIOD):
                continue
            for start, end, scope in zip(headers["start"], headers["end"], headers["scope"], strict=True):
                if scope.upper() == identity["scope"]:
                    selectors.add((day(start).isoformat(), day(end).isoformat()))
        periods = []
        mapping = {"reported_pat": "group_pat", "noncontrolling_pat": "minority_pat"}
        for start, end in sorted(selectors):
            manifest = {"source_id": hashlib.sha256(raw).hexdigest(), "url": url, "captured_at": known_at,
                        "representation": "CAPTURED_HTML_TABLES", "payload_sha256": canonical_hash(tables),
                        "usage": "INTERNAL_DEVELOPMENT", "symbol": identity["symbol"], "isin": identity["isin"]}
            statement = extract_statement(tables, manifest, {"period_start": start, "period_end": end,
                                            "scope": identity["scope"]}, known_at)
            periods.append({"period_start": start, "period_end": end,
                            "facts": {mapping.get(k, k): v for k, v in statement["facts"].items()}})
    digest = hashlib.sha256(raw).hexdigest()
    return [{**p, "identity": identity, "source_url": url, "raw_sha256": digest,
             "known_at": known_at, "published_at": published_at} for p in periods]


def discover_history(client, store, identity: dict, current_end: str) -> tuple[list, list]:
    candidates, receipts, seen, total_seen = {}, [], set(), 0
    cutoff = timestamp(store.clock())
    for page in range(1, 6):
        params = {"index": "equities", "symbol": identity["symbol"], "period": "Quarterly",
                  "page": page, "size": 200}
        payload, raw = client._json_get_with_raw(client.INTEGRATED_FILING_ENDPOINT, params=params)
        capture = retain_json(store, payload, raw, client.INTEGRATED_FILING_ENDPOINT.url + "?" + urlencode(params))
        items = rows(payload)
        digest = canonical_hash(items)
        if digest in seen and items:
            raise ChangeError("historical discovery repeated a page")
        seen.add(digest)
        total_seen += len(items)
        receipts.append({"raw_sha256": capture["raw_sha256"], "observed_at": capture["captured_at"], "page": page})
        for item in items:
            if item.get("symbol") != identity["symbol"] or str(item.get("consolidated", "")).upper() != identity["scope"]:
                continue
            end = day(item.get("qe_Date")).isoformat()
            published = max(source_time(item[k]) for k in ("broadcast_Date", "revised_Date", "creation_Date") if item.get(k))
            if end > current_end or published > cutoff or (day(current_end) - day(end)).days > 800:
                continue
            url = str(item.get("xbrl", ""))
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.query or parsed.fragment or parsed.username:
                continue
            if not parsed.path.lower().endswith((".xml", ".html", ".htm")):
                continue
            key = (end, url)
            candidates[key] = {"url": url, "period_end": end, "published_at": published.isoformat()}
        total = payload.get("totalCount") if isinstance(payload, dict) else None
        if total is None:
            break
        if type(total) is not int or total < 0:
            raise ChangeError("invalid historical discovery total")
        if total_seen >= total:
            break
        if not items:
            raise ChangeError("historical discovery stopped before the reported total")
    else:
        raise ChangeError("historical discovery exceeded page bound")
    # Prioritize exact year-ago and nearby year-end dates for retrieval only.
    # No fiscal period is inferred. Original context dates decide annual/TTM use.
    prior_end = year_ago(current_end)
    fiscal_search_end = f"{day(current_end).year}-03-31"
    targets = [prior_end, fiscal_search_end, year_ago(fiscal_search_end)]
    ordered = sorted(candidates.values(), key=lambda x: (
        targets.index(x["period_end"]) if x["period_end"] in targets else 3,
        -day(x["period_end"]).toordinal(), -timestamp(x["published_at"]).timestamp()))
    unique = {}
    for item in ordered:
        unique.setdefault(item["period_end"], item)
    return list(unique.values()), receipts


def refresh_one(store, client, anchor: dict, *, max_documents=4, fetcher=fetch_original) -> dict:
    identity = {"symbol": anchor["symbol"], "isin": anchor["isin"], "scope": anchor["selector"]["scope"]}
    errors, receipts, periods = [], [], []
    current_end = anchor["selector"]["period_end"]
    try:
        capture = store.get_capture(anchor["capture_id"])
        meta = capture["metadata"]
        published = meta.get("published_at") or meta.get("spec", {}).get("published_at")
        if not published:
            raise ChangeError("current filing publication time is unknown")
        periods.extend(parse_document(store.read_blob(anchor["raw_sha256"]), anchor["url"], identity,
                                      store.clock(), published))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        errors.append({"stage": "current_document", "reason": str(exc)})
    try:
        historical, receipts = discover_history(client, store, identity, current_end)
        for item in [x for x in historical if x["url"] != anchor["url"]][:max_documents]:
            try:
                raw, final_url = fetcher(item["url"], HOSTS)
                cap = store.capture(raw, {"identity": identity, **item, "final_url": final_url, "lane": VERSION,
                                          "origin": "HTTP_RESPONSE_BYTES"})
                periods.extend(parse_document(raw, item["url"], identity, store.clock(), item["published_at"]))
                receipts.append({"url": item["url"], "raw_sha256": cap["raw_sha256"], "observed_at": cap["captured_at"]})
            except (ValueError, TypeError, KeyError, OSError) as exc:
                errors.append({"stage": "historical_document", "url": item["url"], "reason": str(exc)})
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
        errors.append({"stage": "historical_discovery", "reason": str(exc)})
    quote, actions = None, None
    try:
        payload, raw = client.quote_equity_with_raw(identity["symbol"])
        cap = retain_json(store, payload, raw, client.QUOTE_ENDPOINT.url + "?" + urlencode({"symbol": identity["symbol"]}))
        quote = {**parse_quote(payload, identity, cap["captured_at"]), "raw_sha256": cap["raw_sha256"]}
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
        primary_error = str(exc)
        try:
            quote = archive_close(store, identity)
            quote["primary_quote_endpoint_error"] = primary_error
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as fallback:
            errors.append({"stage": "quote", "reason": primary_error, "archive_error": str(fallback)})
    try:
        start = min((p["period_end"] for p in periods), default=year_ago(current_end))
        end = timestamp(store.clock()).astimezone(IST).date().isoformat()
        payload, raw = client.corporate_actions_with_raw(identity["symbol"],
            from_date=day(start).strftime("%d-%m-%Y"), to_date=day(end).strftime("%d-%m-%Y"))
        cap = retain_json(store, payload, raw, client.CORPORATE_ACTION_ENDPOINT.url + "?" + urlencode({
            "index": "equities", "symbol": identity["symbol"], "from_date": day(start).strftime("%d-%m-%Y"),
            "to_date": day(end).strftime("%d-%m-%Y")}))
        actions = {**parse_actions(payload, identity["symbol"], start, end), "raw_sha256": cap["raw_sha256"],
                   "observed_at": cap["captured_at"]}
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
        errors.append({"stage": "corporate_actions", "reason": str(exc)})
    card = build_card(identity, periods, current_end, quote, actions, store.clock())
    card["anchor_review_status"] = anchor.get("review_status", "UNREVIEWED")
    if card["anchor_review_status"] == "REJECT":
        card["blockers"].append("Current anchor extraction has been rejected. Reconcile before interpreting price/earnings.")
        card["price_over_reported_annual_eps"] = None
        card["reverse_hurdle_scenarios"] = []
    card.update(source_receipts=receipts, retrieval_errors=errors, anchor_sha256=anchor["raw_sha256"],
                financial_periods=periods, evidence_mode="OBSERVED_NOW_HISTORICAL_RECONSTRUCTION")
    card["card_sha256"] = canonical_hash(card)
    return card


def render_report(report: dict) -> str:
    def esc(v):
        return html.escape(str(v), quote=True)
    def fmt(v, digits=2):
        return "Unknown" if v is None else f"{v:,.{digits}f}"
    cards = []
    for card in report["cards"]:
        quote = card["quote"]
        rows_ = "".join(f"<tr><td>{esc(c['current_evidence']['period_start'])} to {esc(c['current_evidence']['period_end'])}</td>"
            f"<td>{fmt(c['metrics']['revenue']['reported_growth_fraction'] * 100 if c['metrics']['revenue']['reported_growth_fraction'] is not None else None)}%</td>"
            f"<td>{esc(c['basis'])}</td></tr>" for c in card["year_ago_comparisons"])
        scenarios = "".join(f"<tr><td>{s['exit_pe_assumption']}×</td><td>{s['required_annual_eps_growth']:.1%}</td></tr>"
                            for s in card["reverse_hurdle_scenarios"])
        gaps = "".join(f"<li>{esc(x)}</li>" for x in card["blockers"] + card["limitations"])
        cards.append(f"<article><div class='tag'>RESEARCH ONLY / {esc(card['identity']['scope'])}</div><h2>{esc(card['identity']['symbol'])}</h2>"
            f"<div class='numbers'><div><b>₹{fmt(quote['price'] if quote else None)}</b><span>Dated exchange price observation</span></div>"
            f"<div><b>{fmt(card['price_over_reported_annual_eps'])}×</b><span>Price / reported annual diluted EPS</span></div></div>"
            f"<p>Quote timestamp: {esc((quote.get('quoted_at') or quote.get('session_date') + ' (official close, date only)') if quote else 'Unavailable')}</p>"
            f"<h3>Reported year-ago comparisons</h3><table><tr><th>Current period</th><th>Revenue change</th><th>Evidence basis</th></tr>{rows_}</table>"
            f"<h3>What would a 15% price return require?</h3><p>Five-year sensitivity using unnormalized annual EPS. No forecast is implied.</p>"
            f"<table><tr><th>Assumed exit P/E</th><th>Required EPS growth/year</th></tr>{scenarios}</table>"
            f"<details><summary>Evidence, trailing flows and unresolved assumptions</summary><ul>{gaps}</ul>"
            f"<pre>{esc(json.dumps(card['reported_ttm_flows'], indent=2))}</pre><pre>{esc(json.dumps(card['retrieval_errors'], indent=2))}</pre></details></article>")
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Historical and price context</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f5f5;color:#183641;font:15px system-ui}main{max-width:1200px;margin:auto;padding:32px 22px}.banner{background:#183641;color:white;padding:24px;border-radius:14px}h1{font-size:36px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));gap:18px;margin:24px 0}article{background:white;border:1px solid #cbdcdd;border-radius:12px;padding:22px;min-width:0}.tag{font-size:11px;letter-spacing:.08em}.numbers{display:flex;flex-wrap:wrap;gap:20px}.numbers b{display:block;font-size:27px}.numbers span,p{font-size:13px}table{border-collapse:collapse;width:100%;font-size:12px;table-layout:fixed}td,th{text-align:left;border-bottom:1px solid #dbe5e5;padding:9px 4px;overflow-wrap:anywhere}pre{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;margin:18px 0}li{margin:10px 0}</style><main><div class='tag'>MARKETLAB / HISTORICAL EVIDENCE + PRICE CONTEXT</div><h1>What is already in the price?</h1>
<div class='banner'><b>Reported history is evidence. Future growth is an assumption.</b><p>Price observations are dated, historical figures are not silently restated, and share-basis changes block misleading ratios. No buy recommendation or validated prediction is implied.</p></div>
""" + f"<p>Run at {esc(report['as_of'])}. {len(report['cards'])} completed issuer-context records.</p><div class='grid'>{''.join(cards)}</div></main></html>"


def run(store: EvidenceStore, client, symbols: list | None = None, limit: int = 3) -> dict:
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ChangeError("context issuer budget must be 1..10")
    store.db.execute("CREATE TABLE IF NOT EXISTS cc_context_runs(id TEXT PRIMARY KEY, symbol TEXT NOT NULL, known_at TEXT NOT NULL, payload TEXT NOT NULL)")
    store.db.commit()
    groups = {}
    for row in store.snapshot()["active"]:
        if row["kind"] == "earnings_quality":
            groups.setdefault(row["symbol"], []).append(row)
    if symbols and len(set(symbols)) != len(symbols):
        raise ChangeError("duplicate requested issuer")
    if symbols and set(symbols) - set(groups):
        raise ChangeError("requested issuer has no retained financial anchor")
    previous = {r[0]: r[1] for r in store.db.execute("SELECT symbol,MAX(known_at) FROM cc_context_runs GROUP BY symbol")}
    chosen = symbols if symbols is not None else sorted(groups, key=lambda s: (previous.get(s, ""), s))[:limit]
    if len(chosen) > limit:
        raise ChangeError("requested issuers exceed budget")
    cards, failures = [], []
    for symbol in chosen:
        available = groups[symbol]
        consolidated = [r for r in available if r["selector"]["scope"] == "CONSOLIDATED"]
        anchor = max(consolidated or available, key=lambda r: (r["selector"]["period_end"], timestamp(r["known_at"])))
        try:
            card = refresh_one(store, client, anchor)
            cards.append(card)
            with store.transaction():
                store.db.execute("INSERT OR IGNORE INTO cc_context_runs VALUES (?,?,?,?)",
                    (card["card_sha256"], symbol, card["as_of"], json.dumps(card, allow_nan=False)))
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
            failures.append({"symbol": symbol, "reason": str(exc)})
    report = {"engine": VERSION, "as_of": store.clock(), "cards": cards, "failures": failures,
              "planned_issuers": chosen, "live_capital_allowed": False, "validated_predictive_edge": False}
    report["report_sha256"] = canonical_hash(report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--output-prefix", type=Path)
    args = parser.parse_args(argv)
    from marketlab.nse import NSEClient
    with EvidenceStore(args.workspace) as store:
        client = NSEClient(timeout=20, attempts=2)
        try:
            report = run(store, client, args.symbols, args.limit)
        finally:
            client.session.close()
        folder = store.root / "reports" / "context"
        folder.mkdir(parents=True, exist_ok=True)
        for suffix, payload in (("json", json.dumps(report, indent=2, allow_nan=False)), ("html", render_report(report))):
            target = folder / f"{report['report_sha256']}.{suffix}"
            with target.open("xb") as stream:
                stream.write(payload.encode())
            if args.output_prefix:
                writable_workspace(args.output_prefix.parent)
                args.output_prefix.with_suffix("." + suffix).write_text(payload, encoding="utf-8")
        print("CC001_CONTEXT=" + json.dumps({"hash": report["report_sha256"], "failures": report["failures"],
            "cards": [{k: c[k] for k in ("identity", "quote", "reported_annual_diluted_eps", "price_over_reported_annual_eps", "blockers", "retrieval_errors")}
                      for c in report["cards"]]}))
    return 1 if report["failures"] or any(c["retrieval_errors"] for c in report["cards"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
