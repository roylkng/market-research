"""Outcome-blind official NSE filing source feasibility audit for H019.

This script may inspect filing metadata and accounting source structure only.
It must not acquire market prices, calculate rankings, or calculate investment outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import requests

from marketlab.nse import NSEAcquisitionError, NSEClient, NSEEndpoint

LEGACY = NSEEndpoint(
    "legacy_financials",
    "https://www.nseindia.com/api/corporates-financial-results",
)
ALLOWED_HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com"}
START = date(2016, 1, 1)
END = date(2020, 12, 31)
SAMPLE_PER_YEAR = 40
USER_AGENT = "Mozilla/5.0 marketlab-h019-source-audit/1"
IST = ZoneInfo("Asia/Kolkata")

CONCEPT_PATTERNS = {
    "revenue": ("revenuefromoperations", "revenue", "totalincome"),
    "operating_profit": ("profitfromoperations", "operatingprofit", "ebit"),
    "profit_after_tax": ("profitloss", "profitaftertax", "netprofit"),
    "eps": ("basicearningspershare", "dilutedearningspershare", "earningspershare"),
    "total_assets": ("assets", "totalassets"),
    "equity": ("equity", "networth", "shareholdersequity"),
    "borrowings": ("borrowings", "debt"),
    "operating_cash_flow": (
        "cashflowsfromusedinoperatingactivities",
        "netcashflowsfromusedinoperatingactivities",
        "cashflowfromoperatingactivities",
    ),
    "capex": (
        "purchaseofpropertyplantandequipment",
        "paymentstoacquirepropertyplantandequipment",
        "capitalexpenditure",
    ),
}


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def retain(root: Path, raw: bytes, *, url: str, kind: str) -> dict[str, object]:
    digest = hashlib.sha256(raw).hexdigest()
    path = root / "raw" / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("content-addressed collision")
    else:
        path.write_bytes(raw)
    return {
        "url": url,
        "kind": kind,
        "sha256": digest,
        "bytes": len(raw),
        "raw_path": str(path.relative_to(root)),
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "status": "OK",
    }


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed = time.strptime(text, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    return None


def parse_publication(value: object) -> datetime | None:
    text = str(value or "").strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    return None


def valid_source_url(value: object) -> str | None:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        return None
    if not url.lower().endswith((".xml", ".html", ".xhtml")):
        return None
    return url


def normalize_local_name(tag: str) -> str:
    local = tag.rsplit("}", 1)[-1].split(":")[-1]
    return re.sub(r"[^a-z0-9]", "", local.casefold())


def concept_presence(raw: bytes) -> dict[str, bool]:
    names: set[str] = set()
    try:
        root = ET.fromstring(raw)
        names.update(normalize_local_name(node.tag) for node in root.iter() if isinstance(node.tag, str))
    except (ET.ParseError, UnicodeDecodeError):
        text = raw.decode("utf-8", errors="ignore")
        for match in re.finditer(r"<\s*/?\s*(?:[A-Za-z0-9_.-]+:)?([A-Za-z][A-Za-z0-9_.-]*)", text):
            names.add(normalize_local_name(match.group(1)))
    result = {}
    for concept, patterns in CONCEPT_PATTERNS.items():
        result[concept] = any(any(pattern in name for pattern in patterns) for name in names)
    return result


def fetch_source(url: str) -> tuple[bytes | None, dict[str, object]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,text/html,*/*"})
    last_error = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=(8, 25), allow_redirects=True)
            host = (urlparse(response.url).hostname or "").lower()
            if host not in ALLOWED_HOSTS:
                raise ValueError("filing redirected outside approved NSE archive hosts")
            if response.status_code in {403, 429} or response.status_code >= 500:
                last_error = f"HTTP_{response.status_code}"
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
            if response.status_code == 404:
                return None, {"url": url, "status": "HTTP_404"}
            response.raise_for_status()
            if not response.content:
                raise ValueError("empty filing response")
            return response.content, {"url": response.url, "status": "OK"}
        except (requests.RequestException, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    return None, {"url": url, "status": "FETCH_FAILED", "error": last_error}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    root = Path(parser.parse_args().out)
    root.mkdir(parents=True, exist_ok=True)

    client = NSEClient(timeout=20, attempts=4)
    listing_manifest: list[dict[str, object]] = []
    filings: list[dict[str, object]] = []

    for year in range(START.year, END.year + 1):
        params = {
            "index": "equities",
            "period": "Annual",
            "from_date": f"01-01-{year}",
            "to_date": f"31-12-{year}",
        }
        url = LEGACY.url + "?" + urlencode(params)
        try:
            payload, raw = client._json_get_with_raw(LEGACY, params=params)
            meta = retain(root, raw, url=url, kind="annual-listing")
            listing_manifest.append(meta)
        except (NSEAcquisitionError, KeyError, TypeError, ValueError) as exc:
            listing_manifest.append(
                {"url": url, "kind": "annual-listing", "status": "FETCH_FAILED", "error": str(exc)}
            )
            continue
        if not isinstance(payload, list):
            continue
        for row in payload:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            period_end = parse_date(row.get("toDate") or row.get("qe_Date"))
            published = parse_publication(row.get("broadCastDate") or row.get("broadcast_Date"))
            source_url = valid_source_url(row.get("xbrl")) or valid_source_url(row.get("ixbrl"))
            if not symbol or period_end is None or published is None:
                continue
            filings.append(
                {
                    "listing_year": year,
                    "symbol": symbol,
                    "company": str(row.get("companyName") or row.get("smName") or symbol),
                    "period_end": period_end.isoformat(),
                    "published": published.isoformat(),
                    "basis": (
                        "C" if str(row.get("consolidated") or "").strip().casefold() == "consolidated" else "S"
                    ),
                    "source_url": source_url,
                    "listing_source_sha256": meta["sha256"],
                }
            )

    dump(root / "listing-manifest.json", listing_manifest)
    dump(root / "annual-filings.json", filings)

    groups: dict[int, list[dict[str, object]]] = defaultdict(list)
    for filing in filings:
        if filing["source_url"]:
            groups[int(filing["listing_year"])].append(filing)

    sample: list[dict[str, object]] = []
    for year, rows in sorted(groups.items()):
        consolidated = [row for row in rows if row["basis"] == "C"]
        pool = consolidated or rows
        pool = sorted(pool, key=lambda row: (str(row["symbol"]), str(row["period_end"]), str(row["published"])))
        # Deterministic spread across the alphabet rather than selecting by any investment variable.
        if len(pool) <= SAMPLE_PER_YEAR:
            chosen = pool
        else:
            indexes = [round(i * (len(pool) - 1) / (SAMPLE_PER_YEAR - 1)) for i in range(SAMPLE_PER_YEAR)]
            chosen = [pool[index] for index in indexes]
        sample.extend(chosen)

    sample_manifest: list[dict[str, object]] = []
    concept_counts: Counter[str] = Counter()
    successful = 0
    for number, filing in enumerate(sample, 1):
        url = str(filing["source_url"])
        raw, meta = fetch_source(url)
        record = {**filing, **meta}
        if raw is not None:
            retained = retain(root, raw, url=str(meta["url"]), kind="annual-filing-sample")
            presence = concept_presence(raw)
            record.update(retained)
            record["concept_presence"] = presence
            successful += 1
            concept_counts.update(name for name, present in presence.items() if present)
        sample_manifest.append(record)
        if number % 25 == 0:
            print(f"H019 filing samples {number}/{len(sample)}", flush=True)

    dump(root / "filing-sample-manifest.json", sample_manifest)

    by_symbol: dict[str, set[int]] = defaultdict(set)
    for filing in filings:
        if filing["source_url"]:
            by_symbol[str(filing["symbol"])].add(int(filing["listing_year"]))

    consecutive_counts = {str(length): 0 for length in (2, 3, 4, 5)}
    for years in by_symbol.values():
        for length in (2, 3, 4, 5):
            if any(
                all(start + offset in years for offset in range(length))
                for start in range(START.year, END.year - length + 2)
            ):
                consecutive_counts[str(length)] += 1

    year_counts = Counter(int(filing["listing_year"]) for filing in filings)
    source_counts = Counter(
        int(filing["listing_year"]) for filing in filings if filing["source_url"] is not None
    )
    basis_counts = Counter(str(filing["basis"]) for filing in filings)
    sample_status = Counter(str(row.get("status")) for row in sample_manifest)

    summary = {
        "status": "H019_SOURCE_FEASIBILITY_ONLY",
        "market_outcomes_opened": False,
        "live_capital_allowed": False,
        "source_window": [START.isoformat(), END.isoformat()],
        "listing_status": dict(Counter(str(row.get("status")) for row in listing_manifest)),
        "annual_filing_rows": len(filings),
        "annual_filing_rows_by_listing_year": dict(sorted(year_counts.items())),
        "rows_with_exchange_source_url_by_year": dict(sorted(source_counts.items())),
        "basis_counts": dict(basis_counts),
        "unique_symbols_with_source_url": len(by_symbol),
        "symbols_with_consecutive_annual_source_years": consecutive_counts,
        "sample_requested": len(sample),
        "sample_successful": successful,
        "sample_status": dict(sample_status),
        "sample_concept_coverage": {
            name: {
                "count": concept_counts[name],
                "rate": concept_counts[name] / successful if successful else 0.0,
            }
            for name in CONCEPT_PATTERNS
        },
    }
    dump(root / "source-audit-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
