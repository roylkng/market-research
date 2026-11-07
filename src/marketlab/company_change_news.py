"""Source-first announcement reading. Routing and quoted claims, not return forecasts.

The exchange row locates a document. Neither its voice summary nor its headline
supplies financial facts. Original attachments and observation clocks are kept.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from marketlab.company_change import ChangeError, canonical_hash, timestamp
from marketlab.company_change_discovery import ARCHIVE_HOSTS, setup_queue
from marketlab.company_change_pipeline import check_url, document_text, fetch_original
from marketlab.company_change_store import EvidenceStore, loads_unique, writable_workspace

VERSION = "CC001-NEWS-v1"
MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_BATCH_BYTES = 12 * 1024 * 1024
# Existing checkpoint limit is not increased by the new lane.
RESERVE_BYTES = 8 * 1024 * 1024
MAX_ACTIVE_BYTES = 128 * 1024 * 1024
FAMILIES = {
    "RISK": r"default|fraud|forensic|insolvency|resignation of statutory auditor|disruption|closure of operations|rescission|termination|litigation|action\(s\)|licenses/ regulatory",
    "ORDER": r"bagging|receiving of orders|awarding of order",
    "CAPACITY": r"capacity addition|commercial production|commercial operations|new line",
    "ACQUISITION": r"acquisition|merger|demerger|sale or disposal|scheme of arrangement",
    "FINANCING": r"allotment|issue of securities|rights issue|conversion|utilisation of funds|guarantees|esop|options to purchase",
    "CREDIT": r"credit rating",
    "CAPITAL_RETURN": r"buyback|dividend|bonus|stock split|open offer|offer for sale",
    "GOVERNANCE": r"resignation|management|auditor|appointment|director|related party",
    "BUSINESS_UPDATE": r"monthly business|product launch|agreements|tie up|press release|outcome of board",
    "PRESENTATION": r"investor presentation|analysts/|con\. call",
    "ROUTINE": r"newspaper|trading window|loss of share|record date|shareholders meeting|certificate under|statement of deviation|monitoring agency|address change|registrar",
}
PASSAGE_TERMS = re.compile(
    r"letter of (?:award|intent)|\borders?\b|contract|commission|capacity|commercial production|"
    r"acqui[rs]|investment|allot|warrant|rating|outlook|default|borrow|repay|dividend|buyback|"
    r"approved|terminated|cancelled|subsidiar|consortium|related party|cash consideration|"
    r"(?:crore|lakh|million|billion)\b", re.IGNORECASE)
STAGE_PATTERNS = {
    "CANCELLATION_MENTION": r"\b(?:cancelled|canceled|terminated|rescinded)\b",
    "PROPOSAL_MENTION": r"\b(?:proposed|proposes?|plans? to|intends? to|will consider)\b",
    "APPROVAL_MENTION": r"\b(?:approved|approval)\b",
    "LETTER_OF_AWARD_MENTION": r"\bletter of award\b|\bletters of award\b|\bLOA\b",
    "LETTER_OF_INTENT_MENTION": r"\bletter of intent\b|\bLOI\b",
    "AGREEMENT_MENTION": r"\b(?:signed|executed|entered into)\b.{0,100}\b(?:agreement|contract)\b",
    "COMMISSIONING_MENTION": r"\b(?:commenced|commencement of) commercial (?:production|operations)\b|\bcommissioned\b",
    "COMPLETION_MENTION": r"\b(?:completed|completion of|allotted)\b",
    "CREDIT_OUTLOOK_MENTION": r"\b(?:upgraded|downgraded|reaffirmed|negative outlook|outlook.{0,30}negative)\b",
}
MONEY = re.compile(
    r"(?<!\w)(?:INR\.?|Rs\.?|₹|USD|US\$|EUR)\s*[\d,]+(?:\.\d+)?"
    r"(?:\s*(?:crores?|lakhs?|lacs?|millions?|billions?))?", re.IGNORECASE)


def recipe() -> str:
    return canonical_hash({"engine": VERSION, "source": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           "text_adapter": hashlib.sha256(Path(document_text.__code__.co_filename).read_bytes()).hexdigest()})


def setup(store: EvidenceStore) -> None:
    setup_queue(store)
    store.db.executescript("""
      CREATE TABLE IF NOT EXISTS cc_news_readings(
        id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, recipe TEXT NOT NULL,
        known_at TEXT NOT NULL, payload TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS cc_news_candidate ON cc_news_readings(candidate_id,recipe);
      CREATE TABLE IF NOT EXISTS cc_news_attempts(
        id INTEGER PRIMARY KEY, candidate_id TEXT NOT NULL, recipe TEXT NOT NULL,
        recorded_at TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL);
    """)
    store.db.commit()


def route(subject: str) -> str:
    for family, pattern in FAMILIES.items():
        if re.search(pattern, subject, re.IGNORECASE):
            return family
    return "OTHER_DISCLOSURE"


def retained_index(store: EvidenceStore, cutoff: str) -> dict:
    """Resolve queue rows to exact retained exchange response bytes, never summaries."""
    found, seen = {}, set()
    for batch in store.db.execute("SELECT id,observed_at,receipt FROM cc_discovery_batches ORDER BY observed_at"):
        if timestamp(batch["observed_at"]) > timestamp(cutoff):
            continue
        receipt = loads_unique(batch["receipt"])
        if (receipt.get("receipt_sha256") != batch["id"] or canonical_hash(
                {k: v for k, v in receipt.items() if k != "receipt_sha256"}) != batch["id"]):
            raise ChangeError("discovery receipt integrity failure")
        for source in receipt["source_responses"]:
            sha = source["raw_sha256"]
            if source["lane"] != "announcements" or sha in seen:
                continue
            if timestamp(source["observed_at"]) > timestamp(cutoff):
                continue
            payload = loads_unique(store.read_blob(sha))
            values = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(values, list):
                raise ChangeError("retained announcement response has no row list")
            for position, row in enumerate(values):
                if not isinstance(row, dict):
                    continue
                key = canonical_hash(row)
                found.setdefault(key, {"row": row, "response_sha256": sha, "row_index": position,
                                       "row_sha256": key, "observed_at": source["observed_at"]})
            seen.add(sha)
    return found


def triage(store: EvidenceStore, cutoff: str) -> list[dict]:
    setup(store)
    index = retained_index(store, cutoff)
    result = []
    for record in store.db.execute("SELECT * FROM cc_discovery_queue ORDER BY published_at,id"):
        item = loads_unique(record["payload"])
        if item["lane"] != "announcements" or timestamp(record["first_seen"]) > timestamp(cutoff):
            continue
        if timestamp(item["published_at"]) > timestamp(cutoff):
            raise ChangeError("future announcement in observed queue")
        check_url(item["url"], ARCHIVE_HOSTS, resolve=False)
        origin = index.get(item["discovery_row_sha256"])
        issue = None
        if not origin:
            issue = "RETAINED_EXCHANGE_ROW_MISSING"
        else:
            row = origin["row"]
            if (row.get("symbol") != item["symbol"] or row.get("attchmntFile") != item["url"]
                    or row.get("sm_isin") != item["isin"]):
                issue = "EXCHANGE_IDENTITY_OR_URL_MISMATCH"
        result.append({"candidate": item, "first_seen": record["first_seen"],
                       "family": route(item["subject"]), "origin": origin, "blocker": issue})
    return result


def document_identity(text: str, item: dict, source_row: dict) -> dict:
    """A text match is corroboration of exchange linkage, not legal verification."""
    normalized = re.sub(r"\W+", " ", text).casefold()
    names = [("SYMBOL", item["symbol"]), ("ISIN", item["isin"]),
             ("ISSUER_NAME", source_row.get("sm_name", ""))]
    matched = []
    for field, value in names:
        value = re.sub(r"\W+", " ", value).casefold().strip()
        if value and re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", normalized):
            matched.append(field)
    if not matched:
        raise ChangeError("no exact issuer identifier/name in original attachment text")
    return {"matched": matched, "basis": "EXCHANGE_ROW_PLUS_ATTACHMENT_TEXT_NOT_LEGAL_IDENTITY_AUDIT"}


def passages(text: str) -> list[dict]:
    """Literal local windows retain offsets and page, without semantic promotion."""
    spans = []
    for match in PASSAGE_TERMS.finditer(text):
        start = max(0, text.rfind("\n", 0, max(0, match.start() - 90)) + 1)
        end = text.find("\n", min(len(text), match.end() + 200))
        end = len(text) if end < 0 else end
        end = min(end, start + 800)
        if spans and start <= spans[-1][1]:
            a, b = spans[-1]
            if max(b, end) - a <= 1000:
                spans[-1] = (a, max(b, end))
                continue
        spans.append((start, end))
    result = []
    for start, end in spans[:30]:
        quote = text[start:end]
        page_markers = list(re.finditer(r"\[PAGE (\d+)\]", text[:start + 1]))
        page = int(page_markers[-1][1]) if page_markers else 1
        mentions = [name for name, pattern in STAGE_PATTERNS.items()
                    if re.search(pattern, re.sub(r"\s+", " ", quote), re.IGNORECASE)]
        result.append({"start": start, "end": end, "page": page, "quote": quote,
                       "lexical_stage_mentions": mentions,
                       "amount_literals_unattributed": list(dict.fromkeys(m[0] for m in MONEY.finditer(quote)))[:12],
                       "semantic_status": "UNREVIEWED_MENTIONS_NOT_VERIFIED_EVENT"})
    return result


def analyze_attachment(raw: bytes, routed: dict, observed_at: str) -> dict:
    item = routed["candidate"]
    if routed["blocker"]:
        raise ChangeError(routed["blocker"])
    if not raw or len(raw) > MAX_DOCUMENT_BYTES:
        raise ChangeError("announcement attachment exceeds the four-MiB pilot limit")
    suffix = urlsplit(item["url"]).path.lower()
    format_name = "pdf" if suffix.endswith(".pdf") else "html" if suffix.endswith((".html", ".htm")) else None
    if format_name is None:
        raise ChangeError("announcement attachment format not supported")
    text = document_text(raw, format_name)
    if len(re.sub(r"\W", "", text)) < 100:
        raise ChangeError("too little original text, image/scanned attachment requires review")
    identity = document_identity(text, item, routed["origin"]["row"])
    quoted = passages(text)
    known = timestamp(observed_at)
    if known < max(timestamp(item["published_at"]), timestamp(routed["first_seen"]),
                   timestamp(routed["origin"]["observed_at"])):
        raise ChangeError("attachment observation precedes its source availability")
    source_row = routed["origin"]["row"]
    return {"engine": VERSION, "candidate_id": item["id"], "symbol": item["symbol"],
            "isin": item["isin"], "issuer_name": source_row.get("sm_name"), "subject": item["subject"],
            "routing_family": routed["family"], "url": item["url"], "published_at": item["published_at"],
            "first_seen_at": routed["first_seen"], "known_at": known.isoformat(),
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "text": text, "identity_check": identity,
            "exchange_evidence": {k: routed["origin"][k] for k in ("response_sha256", "row_index", "row_sha256", "observed_at")},
            "passages": quoted, "passage_selection": "FIRST_30_MATCHED_WINDOWS_NOT_EXHAUSTIVE",
            "review_status": "UNREVIEWED",
            "reading_status": "QUOTED_PASSAGES_READY" if quoted else "NO_SUPPORTED_PASSAGE_MANUAL_REVIEW",
            "economic_event_verified": False, "forecast_earnings_effect": None,
            "forecast_cash_effect": None, "live_capital_allowed": False,
            "limits": ["Exchange subject is routing metadata, not verified economics.",
                       "Stage terms and amounts are literal mentions, not affirmative claims or issuer-attributable values.",
                       "Read whole attachment, negations, subsidiaries, consortium shares, taxes and conditions before approving an event.",
                       "An order, proposal or capacity announcement is not recognized revenue, profit or collected cash.",
                       "Voice summaries are excluded. No model was called and no predictive edge was validated."]}


def choose(store: EvidenceStore, candidates: list[dict], limit: int, code: str) -> list[dict]:
    done = {r[0] for r in store.db.execute("SELECT candidate_id FROM cc_news_readings WHERE recipe=?", (code,))}
    attempts = {}
    last_family = {}
    by_id = {r["candidate"]["id"]: r for r in candidates}
    for row in store.db.execute("SELECT * FROM cc_news_attempts WHERE recipe=? ORDER BY recorded_at,id", (code,)):
        attempts.setdefault(row["candidate_id"], []).append(dict(row))
        if row["candidate_id"] in by_id:
            last_family[by_id[row["candidate_id"]]["family"]] = row["recorded_at"]
    eligible = [r for r in candidates if r["candidate"]["id"] not in done and not r["blocker"]
                and len(attempts.get(r["candidate"]["id"], [])) < 3]
    selected, symbols = [], set()
    retries = [r for r in eligible if r["candidate"]["id"] in attempts]
    if retries:
        first = min(retries, key=lambda r: attempts[r["candidate"]["id"]][0]["recorded_at"])
        selected.append(first)
        symbols.add(first["candidate"]["symbol"])
    family_order = {f: n for n, f in enumerate(list(FAMILIES) + ["OTHER_DISCLOSURE"])}
    while len(selected) < limit:
        pool = [r for r in eligible if r not in selected and r["candidate"]["symbol"] not in symbols]
        if not pool:
            break
        used = Counter(r["family"] for r in selected)
        pick = min(pool, key=lambda r: (used[r["family"]], last_family.get(r["family"], ""),
            family_order[r["family"]], -timestamp(r["candidate"]["published_at"]).timestamp(), r["candidate"]["id"]))
        selected.append(pick)
        symbols.add(pick["candidate"]["symbol"])
    return selected


def active_size(store: EvidenceStore) -> int:
    files = [store.root / "evidence.sqlite3", store.root / "evidence.sqlite3-wal"]
    return sum(p.stat().st_size for p in files if p.exists()) + sum(
        p.stat().st_size for p in (store.root / "blobs").rglob("*") if p.is_file())


def run(store: EvidenceStore, *, limit: int = 4, fetcher=fetch_original) -> dict:
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ChangeError("news document budget must be 1..20")
    setup(store)
    code, cutoff = recipe(), store.clock()
    candidates = triage(store, cutoff)
    plan = choose(store, candidates, limit, code)
    failures, acquired_bytes, deferred = [], 0, []
    for routed in plan:
        item = routed["candidate"]
        if active_size(store) + MAX_DOCUMENT_BYTES + RESERVE_BYTES > MAX_ACTIVE_BYTES:
            deferred.append({"candidate_id": item["id"], "reason": "ACTIVE_STORAGE_HEADROOM_REQUIRED"})
            continue
        if acquired_bytes + MAX_DOCUMENT_BYTES > MAX_BATCH_BYTES:
            deferred.append({"candidate_id": item["id"], "reason": "BATCH_BYTE_BUDGET"})
            continue
        try:
            raw, final_url = fetcher(item["url"], ARCHIVE_HOSTS)
            check_url(final_url, ARCHIVE_HOSTS, resolve=False)
            if not raw or len(raw) > MAX_DOCUMENT_BYTES:
                raise ChangeError("announcement attachment exceeds four-MiB pilot limit")
            acquired_bytes += len(raw)
            capture = store.capture(raw, {"url": item["url"], "final_url": final_url,
                "candidate_id": item["id"], "lane": VERSION, "origin": "HTTP_RESPONSE_BYTES",
                "published_at": item["published_at"], "exchange_row_sha256": item["discovery_row_sha256"]})
            result = analyze_attachment(raw, routed, store.clock())
            result.update(capture_id=capture["id"], recipe_sha256=code)
            result["reading_sha256"] = canonical_hash(result)
            with store.transaction():
                store.db.execute("INSERT OR IGNORE INTO cc_news_readings VALUES (?,?,?,?,?)", (
                    result["reading_sha256"], item["id"], code, result["known_at"], json.dumps(result, allow_nan=False)))
            status, detail = "READ_UNREVIEWED", result["reading_sha256"]
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
            status, detail = "FAILED", f"{type(exc).__name__}: {exc}"[:800]
            failures.append({"candidate_id": item["id"], "symbol": item["symbol"], "url": item["url"], "reason": detail})
        with store.transaction():
            store.db.execute("INSERT INTO cc_news_attempts(candidate_id,recipe,recorded_at,status,detail) VALUES (?,?,?,?,?)",
                             (item["id"], code, store.clock(), status, detail))
    all_readings = []
    for row in store.db.execute("SELECT payload FROM cc_news_readings WHERE recipe=? ORDER BY known_at,id", (code,)):
        reading = loads_unique(row[0])
        if canonical_hash({k: v for k, v in reading.items() if k != "reading_sha256"}) != reading["reading_sha256"]:
            raise ChangeError("news reading integrity failure")
        all_readings.append(reading)
    report = {"engine": VERSION, "as_of": store.clock(), "recipe_sha256": code,
        "triage_counts": dict(Counter(r["family"] for r in candidates)),
        "coverage": {"announcements_in_received_queue": len(candidates),
                     "original_attachments_read": len({r["candidate_id"] for r in all_readings}),
                     "distinct_document_hashes": len({r["raw_sha256"] for r in all_readings}),
                     "identity_or_evidence_blocked": sum(bool(r["blocker"]) for r in candidates),
                     "readings_remaining": len(candidates) - len({r["candidate_id"] for r in all_readings}),
                     "verified_economic_events": 0, "coverage_class": "RECEIVED_QUEUE_NOT_MARKET_CENSUS"},
        "planned_symbols": [r["candidate"]["symbol"] for r in plan], "readings": all_readings,
        "failures": failures, "deferred": deferred, "bytes_acquired": acquired_bytes,
        "model_called": False, "validated_predictive_edge": False, "live_capital_allowed": False}
    report["report_sha256"] = canonical_hash(report)
    return report


def render(report: dict) -> str:
    def esc(value):
        return html.escape(str(value), quote=True)
    articles = []
    for r in sorted(report["readings"], key=lambda r: r["published_at"], reverse=True):
        quotes = "".join(f"<div class='quote'><small>Page {p['page']} · {esc(', '.join(p['lexical_stage_mentions']) or 'No stage assigned')}</small>"
            f"<pre>{esc(p['quote'])}</pre></div>" for p in r["passages"])
        articles.append(f"<article><span class='tag'>{esc(r['routing_family'])} / UNREVIEWED</span><h2>{esc(r['symbol'])}</h2>"
            f"<p>{esc(r['subject'])}</p><p class='muted'>Published {esc(r['published_at'])}</p>"
            f"<a href='{esc(r['url'])}' rel='noopener noreferrer'>Original attachment</a>"
            f"<details><summary>{len(r['passages'])} source passages</summary>{quotes}"
            f"<p class='muted'>Original SHA-256 {esc(r['raw_sha256'])}</p></details></article>")
    coverage = report["coverage"]
    counts = "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in sorted(report["triage_counts"].items()))
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Company-change announcement inbox</title><style>*{box-sizing:border-box}body{margin:0;background:#f3f5f5;color:#16353f;font:15px system-ui}main{max-width:1200px;margin:auto;padding:30px 22px}.banner{padding:22px;background:#16353f;color:white;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr));gap:18px;margin-top:24px}article{padding:22px;background:white;border:1px solid #d0dddd;border-radius:12px;min-width:0}.tag,.muted,small{font-size:11px}.muted{overflow-wrap:anywhere}.quote{border-top:1px solid #d0dddd;padding:14px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px system-ui}summary{cursor:pointer;margin:18px 0}table{border-collapse:collapse}td{padding:5px 20px 5px 0}a{color:#006469}</style><main><div class='tag'>MARKETLAB / ORIGINAL ANNOUNCEMENTS</div><h1>What changed beyond the accounts?</h1><div class='banner'><b>Original-source reading, not stock tips.</b><p>Routing categories, stage words and amounts remain unreviewed mentions. No order value is converted into profit, no proposal into completion, and no exchange voice summary into financial evidence.</p></div>""" + f"<p>{coverage['announcements_in_received_queue']:,} announcements routed · {coverage['original_attachments_read']} attachments read · 0 verified economic events</p>" + f"<details><summary>Coverage and unresolved failures</summary><table>{counts}</table><pre>{esc(json.dumps({'failures':report['failures'],'deferred':report['deferred']},indent=2))}</pre></details><div class='grid'>{''.join(articles)}</div><p class='muted'>As of {esc(report['as_of'])}. No predictor was trained or called.</p></main></html>"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=4)
    args = parser.parse_args(argv)
    writable_workspace(args.output_prefix.parent)
    with EvidenceStore(args.workspace) as store:
        report = run(store, limit=args.limit)
    args.output_prefix.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    args.output_prefix.with_suffix(".html").write_text(render(report), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "readings"}))
    return 1 if report["failures"] or report["deferred"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
