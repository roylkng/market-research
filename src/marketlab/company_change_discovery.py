"""CC001 broad NSE discovery, bounded persistent processing and visible coverage.

This is issuer-disclosure discovery, not licensed general-news redistribution.
It never approves financial interpretations, predicts returns or submits orders.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from marketlab.company_change import ChangeError, canonical_hash, timestamp
from marketlab.company_change_pipeline import (
    code_fingerprint,
    fetch_original,
    process_capture,
    project_html,
    write_outputs,
)
from marketlab.company_change_store import EvidenceStore, loads_unique
from marketlab.company_change_tables import PERIOD

VERSION = "CC001-DISCOVERY-v1"
IST = ZoneInfo("Asia/Kolkata")
ARCHIVE_HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com"}


def setup_queue(store: EvidenceStore) -> None:
    store.db.executescript("""
      CREATE TABLE IF NOT EXISTS cc_discovery_batches (
        id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, receipt TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS cc_discovery_queue (
        id TEXT PRIMARY KEY, first_seen TEXT NOT NULL, published_at TEXT NOT NULL,
        payload TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', recipe TEXT);
      CREATE INDEX IF NOT EXISTS cc_queue_pending ON cc_discovery_queue(state,first_seen);
    """)
    store.db.commit()


def parse_day(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (AttributeError, ValueError):
            continue
    raise ChangeError("missing or invalid reporting date")


def publication_clock(row: dict) -> datetime:
    clocks = []
    for key in ("broadcast_Date", "revised_Date", "creation_Date", "exchdisstime", "an_dt"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            clocks.append(timestamp(value))
            continue
        except ChangeError:
            pass
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%m-%Y %H:%M:%S"):
            try:
                clocks.append(datetime.strptime(value + " +0530", fmt + " %z").astimezone(UTC))
                break
            except ValueError:
                continue
    if not clocks:
        raise ChangeError("no usable exchange publication timestamp")
    # A revised document must not inherit the earlier publication clock.
    return max(clocks)


def security_master(raw: bytes) -> dict[str, str]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    names = {str(k).strip(): k for k in (reader.fieldnames or [])}
    if not {"SYMBOL", "SERIES", "ISIN NUMBER"} <= names.keys():
        raise ChangeError("security master lacks SYMBOL, SERIES or ISIN NUMBER")
    identities = {}
    for row in reader:
        if str(row[names["SERIES"]]).strip() != "EQ":
            continue
        symbol, isin = str(row[names["SYMBOL"]]).strip(), str(row[names["ISIN NUMBER"]]).strip()
        if not re.fullmatch(r"[A-Z0-9&._-]{1,30}", symbol) or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
            raise ChangeError("malformed EQ identity in current security master")
        if symbol in identities and identities[symbol] != isin:
            raise ChangeError("conflicting current security-master identity")
        identities[symbol] = isin
    if not identities:
        raise ChangeError("empty current EQ security master")
    return identities


def rows_from_payload(payload) -> list:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ChangeError("discovery response does not contain a row list")
    return rows


def candidate(row: dict, identities: dict, start: date, end: date, seen: str, lane: str) -> dict:
    if not isinstance(row, dict):
        raise ChangeError("malformed discovery row")
    published = publication_clock(row)
    if not start <= published.astimezone(IST).date() <= end:
        raise ChangeError("OUTSIDE_REQUESTED_WINDOW")
    if published > timestamp(seen):
        raise ChangeError("FUTURE_PUBLICATION")
    symbol = str(row.get("symbol") or "").strip().upper()
    if symbol not in identities:
        raise ChangeError("NOT_IN_CURRENT_EQ_MASTER")
    if lane == "financials":
        kind = str(row.get("type") or "Integrated Filing- Financials").strip().casefold()
        if kind != "integrated filing- financials":
            raise ChangeError("NOT_INTEGRATED_FINANCIALS")
        url = str(row.get("xbrl") or "").strip()
        scope = str(row.get("consolidated") or "").strip().upper()
        if scope not in {"CONSOLIDATED", "STANDALONE"}:
            raise ChangeError("MISSING_ACCOUNTING_SCOPE")
        period = parse_day(row.get("qe_Date")).isoformat()
        if date.fromisoformat(period) > published.astimezone(IST).date():
            raise ChangeError("FUTURE_REPORTED_PERIOD")
        subject = "Integrated financials"
    else:
        url = str(row.get("attchmntFile") or "").strip()
        scope, period = None, None
        subject = str(row.get("desc") or "").strip()
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ARCHIVE_HOSTS or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ChangeError("UNSUPPORTED_ORIGINAL_URL")
    identity = {"symbol": symbol, "isin": identities[symbol], "url": url,
                "scope": scope, "period_end": period, "published_at": published.isoformat(), "lane": lane}
    item = {**identity, "subject": subject, "discovery_row_sha256": canonical_hash(row)}
    item["id"] = canonical_hash(identity)
    if lane == "announcements":
        item["initial_state"] = "NEEDS_SEMANTIC_MAPPING"
    elif parsed.path.lower().endswith((".html", ".htm", ".xml")):
        item["initial_state"] = "PENDING"
    else:
        item["initial_state"] = "UNSUPPORTED_FORMAT"
    return item


def discover(store: EvidenceStore, client, *, start: date, end: date) -> dict:
    """Read the existing NSE client, preserving exact discovery bytes and exclusions.

    NSE current-response coverage is not asserted to be a complete historical
    census. No source or event is silently promoted into a frozen experiment.
    """
    setup_queue(store)
    if start > end or (end - start).days > 30:
        raise ChangeError("discovery window must contain at most 31 calendar days")
    raw_master = client.all_equity_csv()
    master_hash = store.put_blob(raw_master)
    identities = security_master(raw_master)
    sources, exclusions, accepted, errors = [], [], {}, []
    for lane in ("financials", "announcements"):
        try:
            page, page_hashes, total_seen = 1, set(), 0
            while True:
                if lane == "financials":
                    payload, raw = client._json_get_with_raw(client.INTEGRATED_FILING_ENDPOINT, params={
                        "index": "equities", "period": "Quarterly", "page": page, "size": 200,
                        "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")})
                else:
                    payload, raw = client.corporate_announcements_with_raw(
                        from_date=start.strftime("%d-%m-%Y"), to_date=end.strftime("%d-%m-%Y"))
                raw_hash = store.put_blob(raw)
                if canonical_hash(loads_unique(raw)) != canonical_hash(payload):
                    raise ChangeError("discovery bytes do not match the parsed payload")
                seen = timestamp(store.clock()).isoformat()
                rows = rows_from_payload(payload)
                page_hash = canonical_hash(rows)
                if page_hash in page_hashes and rows:
                    raise ChangeError("pagination repeated a page instead of advancing")
                page_hashes.add(page_hash)
                total_seen += len(rows)
                total = payload.get("totalCount") if isinstance(payload, dict) else None
                sources.append({"lane": lane, "raw_sha256": raw_hash, "observed_at": seen,
                    "returned_rows": len(rows), "requested_page": page, "source_total": total,
                    "response_keys": sorted(payload) if isinstance(payload, dict) else []})
                for index, row in enumerate(rows):
                    try:
                        item = candidate(row, identities, start, end, seen, lane)
                        accepted.setdefault(item["id"], item)
                    except (ChangeError, TypeError, ValueError) as exc:
                        exclusions.append({"lane": lane, "page": page, "row": index,
                            "reason": str(exc), "row_sha256": canonical_hash(row)})
                if lane != "financials" or total is None:
                    break
                if type(total) is not int or total < 0:
                    raise ChangeError("invalid pagination total")
                if total_seen >= total:
                    break
                if not rows or page >= 50:
                    raise ChangeError("financial pagination incomplete at bounded page limit")
                page += 1
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
            errors.append({"lane": lane, "error_type": type(exc).__name__, "reason": str(exc)[:600]})
    observed = timestamp(store.clock()).isoformat()
    with store.transaction():
        for item in sorted(accepted.values(), key=lambda r: (r["published_at"], r["symbol"], r["id"])):
            store.db.execute("INSERT OR IGNORE INTO cc_discovery_queue(id,first_seen,published_at,payload,state,updated_at) VALUES (?,?,?,?,?,?)",
                (item["id"], observed, item["published_at"], json.dumps(item, sort_keys=True), item["initial_state"], observed))
    receipt = {"engine": VERSION, "observed_at": observed, "requested_start": start.isoformat(),
        "requested_end": end.isoformat(), "security_master_sha256": master_hash,
        "current_eq_identities": len(identities), "source_responses": sources,
        "accepted_distinct_rows": len(accepted), "exclusions": exclusions, "errors": errors,
        "coverage_class": "CURRENT_EXCHANGE_RESPONSE_NOT_CERTIFIED_CENSUS",
        "current_master_not_historical_membership": True, "live_capital_allowed": False}
    receipt["receipt_sha256"] = canonical_hash(receipt)
    with store.transaction():
        store.db.execute("INSERT OR IGNORE INTO cc_discovery_batches VALUES (?,?,?)",
            (receipt["receipt_sha256"], observed, json.dumps(receipt, sort_keys=True)))
    return receipt


def selectors_from_document(raw: bytes, item: dict) -> list[dict]:
    tables, _ = project_html(raw)
    selectors = set()
    for table in tables:
        headers = {}
        for key, label in PERIOD.items():
            matches = [row[row.index(label) + 1:] for row in table if label in row]
            if len(matches) == 1:
                headers[key] = matches[0]
        if set(headers) != set(PERIOD):
            continue
        if len({len(v) for v in headers.values()}) != 1:
            raise ChangeError("unaligned original period headers")
        for begin, finish, scope in zip(headers["start"], headers["end"], headers["scope"], strict=True):
            begin, finish, scope = parse_day(begin).isoformat(), parse_day(finish).isoformat(), scope.upper()
            if finish <= item["period_end"] and scope == item["scope"]:
                selectors.add((begin, finish, scope))
    if not selectors:
        raise ChangeError("no original-document column matches the discovery period and scope")
    return [{"period_start": begin, "period_end": finish, "scope": scope}
            for begin, finish, scope in sorted(selectors)]


def drain(store: EvidenceStore, *, limit: int = 20, fetcher=fetch_original) -> dict:
    setup_queue(store)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ChangeError("document budget must be between one and 100")
    now = timestamp(store.clock()).isoformat()
    stale = (timestamp(now) - timedelta(minutes=30)).isoformat()
    with store.transaction():
        store.db.execute("UPDATE cc_discovery_queue SET state='FAILED',detail='interrupted processing lease' WHERE state='PROCESSING' AND updated_at < ?", (stale,))
        queue = store.db.execute("SELECT * FROM cc_discovery_queue WHERE state='PENDING' OR (state='FAILED' AND attempts < 3) ORDER BY first_seen,published_at,attempts,id LIMIT ?", (limit,)).fetchall()
    successes, failures = [], []
    for row in queue:
        with store.transaction():
            changed = store.db.execute("UPDATE cc_discovery_queue SET state='PROCESSING',attempts=attempts+1,updated_at=? WHERE id=? AND state IN ('PENDING','FAILED')", (now, row["id"])).rowcount
        if not changed:
            continue
        item = loads_unique(row["payload"])
        try:
            raw, final_url = fetcher(item["url"], ARCHIVE_HOSTS)
            # Retain unsupported originals too, before parsing their layout.
            digest = store.put_blob(raw)
            if urlsplit(item["url"]).path.lower().endswith(".xml"):
                from marketlab.company_change_xbrl import persist_xbrl
                outputs = persist_xbrl(store, raw, item, final_url)
            else:
                selectors = selectors_from_document(raw, item)
                outputs = []
                for selector in selectors:
                    spec = {"source_id": "discovery-" + item["id"] + "-" + selector["period_start"],
                        "url": item["url"], "symbol": item["symbol"], "isin": item["isin"],
                        "kind": "earnings_quality", "event_key": selector["period_start"] + "/" + selector["period_end"],
                        **selector, "published_at": item["published_at"], "format": "html", "extractor": "statement", "rights": "INTERNAL_RESEARCH"}
                    capture = store.capture(raw, {"spec": spec, "origin": "HTTP_RESPONSE_BYTES",
                        "final_url": final_url, "discovery_row_sha256": item["discovery_row_sha256"],
                        "publication_time_verified": False})
                    result = process_capture(store, capture, spec)
                    outputs.append({"source_id": spec["source_id"], "extraction_id": result["extraction_id"],
                        "symbol": item["symbol"], "raw_sha256": digest, "facts": len(result["facts"]), "selector": selector,
                        "origin": "HTTP_RESPONSE_BYTES"})
            successes.extend(outputs)
            state, detail = "EXTRACTED", json.dumps({"raw_sha256": digest, "records": outputs})
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
            state, detail = "FAILED", f"{type(exc).__name__}: {exc}"[:800]
            failures.append({"source_id": item["id"], "symbol": item["symbol"], "reason": detail})
        with store.transaction():
            store.db.execute("UPDATE cc_discovery_queue SET state=?,detail=?,updated_at=?,recipe=? WHERE id=?",
                (state, detail, timestamp(store.clock()).isoformat(), code_fingerprint(), item["id"]))
    return {"attempted_documents": len(queue), "successes": successes, "failures": failures}


def coverage(store: EvidenceStore) -> dict:
    setup_queue(store)
    counts = {r["state"]: r["n"] for r in store.db.execute("SELECT state,COUNT(*) n FROM cc_discovery_queue GROUP BY state")}
    newest = store.db.execute("SELECT observed_at FROM cc_discovery_batches ORDER BY observed_at DESC LIMIT 1").fetchone()
    return {"counts": counts, "total_discovered": sum(counts.values()),
            "last_discovery_at": newest[0] if newest else None,
            "unsupported_in_denominator": True, "live_capital_allowed": False}


def retry_failed(store: EvidenceStore) -> int:
    """Explicit operator action. Keep attempts and history, do not backdate anything."""
    setup_queue(store)
    with store.transaction():
        n = store.db.execute("UPDATE cc_discovery_queue SET state='PENDING' WHERE state='FAILED'").rowcount
    return n


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--require-documents", type=int, default=0)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.days <= 31:
            raise ChangeError("days must be between one and 31")
        with EvidenceStore(args.workspace) as store:
            if args.retry_failed:
                retry_failed(store)
            receipt = None
            if args.fetch:
                from marketlab.nse import NSEClient
                end = timestamp(store.clock()).astimezone(IST).date()
                client = NSEClient(timeout=20, attempts=2)
                try:
                    receipt = discover(store, client, start=end - timedelta(days=args.days - 1), end=end)
                    processed = drain(store, limit=args.limit)
                finally:
                    client.session.close()
            else:
                processed = {"attempted_documents": 0, "successes": [], "failures": []}
            report = {"engine": VERSION, "discovery": receipt, "coverage": coverage(store),
                **processed, "snapshot": store.snapshot(), "live_capital_allowed": False, "trained_predictor": False}
            report["report_sha256"] = canonical_hash(report)
            paths = write_outputs(store, report)
            compact = {k: v for k, v in report.items() if k not in {"snapshot", "discovery"}}
            compact["discovery"] = ({k: v for k, v in receipt.items() if k != "exclusions"} if receipt else None)
            compact["artifacts"] = paths
            print("CC001_DISCOVERY=" + json.dumps(compact, allow_nan=False))
        return 1 if processed["failures"] or (receipt and receipt["errors"]) or processed["attempted_documents"] < args.require_documents else 0
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
        print(f"CC001 discovery: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
