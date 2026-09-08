"""Acquire exact NSE evidence for H005. This command never fits or scores a model."""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import json
import math
import os
import statistics
import threading
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, time as dtime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests

from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.nse import NSEClient, NSEEndpoint

LEGACY = NSEEndpoint("legacy_financials", "https://www.nseindia.com/api/corporates-financial-results")
LOCAL = threading.local()
ALLOWED = {"nsearchives.nseindia.com", "archives.nseindia.com"}


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def retain(root: Path, raw: bytes, url: str, kind: str) -> dict:
    sha = hashlib.sha256(raw).hexdigest()
    dest = root / "raw" / sha
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open("xb") as f:
            f.write(raw)
    except FileExistsError:
        if dest.read_bytes() != raw:
            raise ValueError("content-addressed source collision")
    return {"url": url, "kind": kind, "sha256": sha, "bytes": len(raw),
            "raw_path": str(dest.relative_to(root)),
            "captured_at_utc": datetime.now(UTC).isoformat(), "status": "OK"}


def archive(root: Path, url: str, kind: str) -> dict:
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in ALLOWED:
        raise ValueError("archive URL outside allowed NSE source hosts")
    if not hasattr(LOCAL, "session"):
        LOCAL.session = requests.Session()
        LOCAL.session.headers["User-Agent"] = "marketlab-research/0.1"
    failure = None
    for attempt in range(3):
        try:
            r = LOCAL.session.get(url, timeout=(8, 18), allow_redirects=True)
            if urlparse(r.url).hostname not in ALLOWED:
                raise ValueError("archive redirected outside NSE hosts")
            if r.status_code == 404:
                return {"url": url, "kind": kind, "status": "HTTP_404_NOT_CALENDAR_PROOF"}
            if r.status_code in (401, 403):
                return {"url": url, "kind": kind, "status": f"HTTP_{r.status_code}"}
            r.raise_for_status()
            if not r.content:
                raise ValueError("empty archive response")
            return retain(root, r.content, url, kind)
        except (requests.RequestException, ValueError) as e:
            failure = str(e)
            time.sleep(0.5 * (attempt + 1))
    return {"url": url, "kind": kind, "status": "FETCH_FAILED", "error": failure}


def fetch_many(root: Path, work: list[tuple[str, str]], name: str) -> list[dict]:
    rows = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        pending = {pool.submit(archive, root, url, kind): (url, kind) for url, kind in work}
        for task in as_completed(pending):
            rows.append(task.result())
            if len(rows) % 100 == 0:
                print(name, len(rows), "/", len(work), flush=True)
    rows.sort(key=lambda r: (r["kind"], r["url"]))
    dump(root / f"{name}-manifest.json", rows)
    return rows


def months(start: date, end: date):
    cursor = start
    while cursor <= end:
        last = date(cursor.year, cursor.month, calendar.monthrange(cursor.year, cursor.month)[1])
        yield cursor, min(last, end)
        cursor = last + timedelta(days=1)


def parse_date(value: object) -> date | None:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    return None


def normalize(row: dict, source: str) -> dict | None:
    try:
        published = datetime.strptime(str(row.get("broadcast_Date") or row.get("broadCastDate")),
                                      "%d-%b-%Y %H:%M:%S")
    except ValueError:
        return None
    end = parse_date(row.get("qe_Date") or row.get("toDate"))
    url = str(row.get("xbrl") or "").strip()
    symbol = str(row.get("symbol") or "").strip().upper()
    if not end or not symbol or urlparse(url).hostname not in ALLOWED or not url.lower().endswith(".xml"):
        return None
    return {"symbol": symbol, "quarter_end": end.isoformat(), "published": published.isoformat(),
            "basis": "C" if str(row.get("consolidated", "")).casefold() == "consolidated" else "S",
            "url": url, "listing_source_sha256": source,
            "submission_type": str(row.get("type_Sub") or ""),
            "company": str(row.get("cmName") or row.get("smName") or row.get("companyName") or symbol)}


def query(client: NSEClient, root: Path, endpoint: NSEEndpoint, params: dict, kind: str):
    url = endpoint.url + "?" + urlencode(params)
    try:
        payload, raw = client._json_get_with_raw(endpoint, params=params)
        meta = retain(root, raw, url, kind)
        return payload, meta
    except Exception as e:
        return None, {"url": url, "kind": kind, "status": "FETCH_FAILED", "error": str(e)}


def read_market(root: Path, manifest: list[dict]):
    prices, sessions, errors = defaultdict(list), [], []
    for meta in manifest:
        if meta["kind"] != "bhavcopy" or meta["status"] != "OK":
            continue
        day = datetime.strptime(meta["url"].split("_0_0_0_")[1][:8], "%Y%m%d").date()
        try:
            with zipfile.ZipFile(io.BytesIO((root / meta["raw_path"]).read_bytes())) as z:
                if len(z.namelist()) != 1:
                    raise ValueError("expected one bhavcopy CSV")
                raw = z.read(z.namelist()[0]).decode("utf-8-sig")
            parsed = []
            for row in csv.DictReader(io.StringIO(raw)):
                if (row.get("Sgmt"), row.get("Src"), row.get("FinInstrmTp"), row.get("SctySrs")) != ("CM", "NSE", "STK", "EQ"):
                    continue
                if row.get("TradDt") != day.isoformat():
                    raise ValueError("bhavcopy trade date mismatch")
                values = [float(row[k]) for k in ("OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol", "TtlTrfVal")]
                if not all(math.isfinite(v) for v in values) or min(values[:4]) <= 0:
                    continue
                parsed.append((row["TckrSymb"].strip().upper(), {"date": day.isoformat(), "isin": row["ISIN"],
                    **dict(zip(("open", "high", "low", "close", "volume", "turnover"), values)),
                    "source_sha256": meta["sha256"]}))
            if not parsed:
                raise ValueError("no usable EQ rows")
            sessions.append(day.isoformat())
            for symbol, row in parsed:
                prices[symbol].append(row)
        except Exception as e:
            errors.append({"date": day.isoformat(), "error": str(e), "source_sha256": meta["sha256"]})
    for rows in prices.values():
        rows.sort(key=lambda r: r["date"])
    return sorted(set(sessions)), prices, errors


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    args = p.parse_args()
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)
    client = NSEClient(timeout=18, attempts=2)
    listings, current, prior = [], [], []
    for start, end in months(date(2025, 10, 1), date(2026, 7, 31)):
        seen, total, page = 0, None, 1
        while True:
            params = {"type": "Integrated Filing- Financials", "page": page, "size": 200,
                      "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")}
            payload, meta = query(client, root, client.INTEGRATED_FILING_ENDPOINT, params, "current-listing")
            listings.append(meta)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                break
            rows = payload["data"]
            total = int(payload.get("totalCount") or len(rows))
            for row in rows:
                record = normalize(row, meta["sha256"])
                if record and date(2025,10,1) <= date.fromisoformat(record["published"][:10]) <= date(2026,7,31):
                    current.append(record)
            seen += len(rows)
            if seen >= total or not rows:
                break
            page += 1
            if page > 100:
                raise ValueError("filing pagination runaway")
        print("current listing", start, seen, total, flush=True)
    for period in ("Quarterly", "Annual"):
        for start, end in months(date(2024,7,1), date(2025,9,30)):
            params = {"index": "equities", "period": period,
                      "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")}
            payload, meta = query(client, root, LEGACY, params, "legacy-" + period)
            listings.append(meta)
            if isinstance(payload, list):
                for row in payload:
                    record = normalize(row, meta["sha256"])
                    if record:
                        prior.append(record)
                meta["reported_rows"] = len(payload)
            print("legacy listing", period, start, meta.get("reported_rows"), flush=True)
    actions, action_meta = query(client, root, client.CORPORATE_ACTION_ENDPOINT,
        {"index": "equities", "from_date": "01-05-2025", "to_date": "31-08-2026"}, "corporate-actions")
    listings.append(action_meta)
    dump(root / "listing-manifest.json", listings)
    dump(root / "current-listings.json", current)
    dump(root / "prior-listings.json", prior)
    dump(root / "corporate-actions.json", actions if isinstance(actions,list) else [])
    work = []
    day = date(2025,5,1)
    while day <= date(2026,8,31):
        work.extend([(udiff_url(day), "bhavcopy"), (index_snapshot_url(day), "index")])
        day += timedelta(days=1)
    market_manifest = fetch_many(root, work, "market")
    sessions, prices, errors = read_market(root, market_manifest)
    dump(root / "sessions.json", sessions)
    dump(root / "prices.json", prices)
    dump(root / "market-parse-errors.json", errors)
    groups = defaultdict(list)
    for record in current:
        groups[(record["symbol"], record["quarter_end"])].append(record)
    prior_groups = defaultdict(list)
    for record in prior:
        prior_groups[(record["symbol"], record["quarter_end"],record["basis"])].append(record)
    urls, candidates, exclusions = {}, [], Counter()
    for (symbol, quarter_end), group in sorted(groups.items()):
        group.sort(key=lambda r:(r["published"],r["url"]))
        first = datetime.fromisoformat(group[0]["published"])
        before = [r for r in prices.get(symbol,[]) if datetime.combine(date.fromisoformat(r["date"]), dtime(15,30)) < first]
        if len(before)<60:
            exclusions["insufficient_pre_event_history"] += 1
            continue
        if statistics.median(r["turnover"] for r in before[-20:]) < 20_000_000:
            exclusions["below_primary_liquidity"] += 1
            continue
        reaction = next((d for d in sessions if datetime.combine(date.fromisoformat(d),dtime(9,15)) > first),None)
        if reaction is None:
            exclusions["no_reaction_session"] += 1
            continue
        cutoff = datetime.combine(date.fromisoformat(reaction),dtime(20))
        eligible = [r for r in group if datetime.fromisoformat(r["published"]) <= cutoff]
        for variant in ("H005-A","H005-B"):
            bound = datetime.combine(date.fromisoformat(reaction),dtime(9,15)) if variant=="H005-A" else cutoff
            pool = [r for r in eligible if datetime.fromisoformat(r["published"]) < bound]
            consolidated = [r for r in pool if r["basis"]=="C"]
            pool = consolidated or pool
            if not pool:
                continue
            selected = max(pool,key=lambda r:(r["published"],r["url"]))
            qdate = date.fromisoformat(quarter_end)
            target = qdate.replace(year=qdate.year-1).isoformat()
            priors = [r for r in prior_groups[(symbol,target,selected["basis"])] if datetime.fromisoformat(r["published"]) < first]
            previous = max(priors,key=lambda r:(r["published"],r["url"])) if priors else None
            candidate = {"symbol":symbol,"quarter_end":quarter_end,"first_publication":first.isoformat(),
                         "variant":variant,"current":selected,"prior":previous,"reaction_date":reaction,
                         "decision_timestamp_local":bound.isoformat(),"pre_event_date":before[-1]["date"]}
            candidates.append(candidate)
            urls[selected["url"]]="current-xbrl"
            if previous:
                urls.setdefault(previous["url"],"prior-xbrl")
    dump(root / "candidate-events.json",candidates)
    xbrl_manifest=fetch_many(root,sorted(urls.items()),"xbrl")
    summary={"status":"SOURCE_ACQUISITION_NOT_MODEL_VALIDATION","source_head":os.environ.get("GITHUB_SHA"),
             "current_listing_rows":len(current),"prior_listing_rows":len(prior),"current_company_quarters":len(groups),
             "candidate_variant_rows":len(candidates),"candidate_company_quarters":len({(c['symbol'],c['quarter_end']) for c in candidates}),
             "candidate_quarters":dict(Counter(c['quarter_end'] for c in candidates if c['variant']=='H005-B')),
             "candidates_missing_prior":sum(c['prior'] is None for c in candidates),"pre_acquisition_exclusions":dict(exclusions),
             "listing_status":dict(Counter(x['status'] for x in listings)),"market_status":dict(Counter(x['status'] for x in market_manifest)),
             "xbrl_status":dict(Counter(x['status'] for x in xbrl_manifest)),"market_parse_errors":errors,
             "sessions":len(sessions),"holdout_returns_opened":False,"live_capital_allowed":False}
    dump(root / "acquisition-summary.json",summary)
    print(json.dumps(summary,indent=2),flush=True)


if __name__ == "__main__":
    main()
