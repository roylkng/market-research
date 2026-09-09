"""Outcome-blind NSE annual-report feasibility and survivorship audit for H019."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from marketlab.nse import NSEAcquisitionError, NSEClient, NSEEndpoint

LEGACY = NSEEndpoint(
    "legacy_financials",
    "https://www.nseindia.com/api/corporates-financial-results",
)
ANNUAL_REPORTS = NSEEndpoint(
    "annual_reports",
    "https://www.nseindia.com/api/annual-reports",
)
ARCHIVE_HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com"}
IST = ZoneInfo("Asia/Kolkata")
GROUP_SAMPLE = 40
CONTENT_SAMPLE_PER_GROUP = 6
MAX_DOCUMENT_BYTES = 50_000_000
MAX_PDF_PAGES = 500

CUTOFFS = {
    "2018-10-01": datetime(2018, 10, 1, tzinfo=IST),
    "2019-10-01": datetime(2019, 10, 1, tzinfo=IST),
    "2020-10-01": datetime(2020, 10, 1, tzinfo=IST),
}

DISCLOSURE_PATTERNS = {
    "revenue": ("revenue from operations", "total income"),
    "profit_after_tax": ("profit after tax", "profit for the year", "profit for the period"),
    "eps": ("basic earnings per share", "diluted earnings per share"),
    "total_assets": ("total assets",),
    "equity_or_net_worth": (
        "total equity",
        "shareholders' funds",
        "shareholders’ funds",
        "net worth",
    ),
    "borrowings_or_debt": ("borrowings", "total debt", "debt equity ratio", "debt-equity ratio"),
    "operating_cash_flow": (
        "cash flow from operating activities",
        "cash flows from operating activities",
        "net cash generated from operating activities",
        "net cash from operating activities",
    ),
    "capex_or_ppe_purchase": (
        "capital expenditure",
        "purchase of property, plant and equipment",
        "purchase of property plant and equipment",
        "additions to property, plant and equipment",
    ),
    "roe": ("return on equity", "return on net worth"),
    "roce": ("return on capital employed",),
}


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def retain(root: Path, raw: bytes, *, url: str, kind: str) -> dict[str, object]:
    if not raw:
        raise ValueError("cannot retain empty source")
    digest = hashlib.sha256(raw).hexdigest()
    target = root / "raw" / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError("content-addressed source collision")
    else:
        target.write_bytes(raw)
    return {
        "url": url,
        "kind": kind,
        "sha256": digest,
        "bytes": len(raw),
        "raw_path": str(target.relative_to(root)),
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "status": "OK",
    }


def parse_broadcast(value: object) -> datetime | None:
    text = str(value or "").strip()
    for fmt in (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    return None


def valid_report_url(value: object) -> str | None:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ARCHIVE_HOSTS:
        return None
    suffix = Path(parsed.path).suffix.casefold()
    return url if suffix in {".pdf", ".zip"} else None


def deterministic_spread(values: set[str], count: int) -> list[str]:
    ordered = sorted(values)
    if len(ordered) <= count:
        return ordered
    if count <= 1:
        return ordered[:count]
    indexes = [round(index * (len(ordered) - 1) / (count - 1)) for index in range(count)]
    return [ordered[index] for index in indexes]


def fetch_listing(client: NSEClient, root: Path, year: int) -> tuple[set[str], dict[str, object]]:
    params = {
        "index": "equities",
        "period": "Annual",
        "from_date": f"01-01-{year}",
        "to_date": f"31-12-{year}",
    }
    payload, raw = client._json_get_with_raw(LEGACY, params=params)
    url = LEGACY.url + "?" + urlencode(params)
    retained = retain(root, raw, url=url, kind=f"annual-listing-{year}")
    if not isinstance(payload, list):
        raise TypeError(f"annual listing {year} is not a list")
    symbols = {
        str(row.get("symbol") or "").strip().upper()
        for row in payload
        if isinstance(row, dict) and str(row.get("symbol") or "").strip()
    }
    retained["row_count"] = len(payload)
    retained["unique_symbol_count"] = len(symbols)
    return symbols, retained


def fetch_annual_report_records(
    client: NSEClient,
    root: Path,
    symbol: str,
    group: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    params = {"index": "equities", "symbol": symbol}
    url = ANNUAL_REPORTS.url + "?" + urlencode(params)
    try:
        payload, raw = client._json_get_with_raw(ANNUAL_REPORTS, params=params)
        retained = retain(root, raw, url=url, kind="annual-report-api")
    except (NSEAcquisitionError, KeyError, TypeError, ValueError) as exc:
        return [], {
            "symbol": symbol,
            "group": group,
            "url": url,
            "status": "FETCH_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = []
    records: list[dict[str, object]] = []
    for source in rows:
        if not isinstance(source, dict):
            continue
        report_url = valid_report_url(source.get("fileName"))
        broadcast = parse_broadcast(source.get("broadcast_dttm")) or parse_broadcast(
            source.get("disseminationDateTime")
        )
        try:
            from_year = int(str(source.get("fromYr") or "").strip())
            to_year = int(str(source.get("toYr") or "").strip())
        except ValueError:
            continue
        if report_url is None or broadcast is None:
            continue
        records.append(
            {
                "symbol": symbol,
                "group": group,
                "company": str(source.get("companyName") or symbol),
                "from_year": from_year,
                "to_year": to_year,
                "broadcast": broadcast.isoformat(),
                "report_url": report_url,
                "api_source_sha256": retained["sha256"],
            }
        )
    unique = {
        (row["from_year"], row["to_year"], row["broadcast"], row["report_url"]): row
        for row in records
    }
    result = sorted(
        unique.values(),
        key=lambda row: (int(row["to_year"]), str(row["broadcast"]), str(row["report_url"])),
    )
    retained.update(
        symbol=symbol,
        group=group,
        status="OK",
        raw_record_count=len(rows),
        usable_record_count=len(result),
    )
    return result, retained


def report_depth(records: list[dict[str, object]], cutoff: datetime) -> int:
    years = {
        int(row["to_year"])
        for row in records
        if datetime.fromisoformat(str(row["broadcast"])) <= cutoff
    }
    return len(years)


def archive_download(client: NSEClient, url: str) -> tuple[bytes | None, dict[str, object]]:
    last_error = None
    for attempt in range(3):
        try:
            response = client.session.get(url, timeout=(10, 60), allow_redirects=True)
            host = (urlparse(response.url).hostname or "").casefold()
            if host not in ARCHIVE_HOSTS:
                raise ValueError("annual report redirected outside approved NSE archive hosts")
            if response.status_code == 404:
                return None, {"url": url, "status": "HTTP_404"}
            if response.status_code in {403, 429} or response.status_code >= 500:
                last_error = f"HTTP_{response.status_code}"
                if attempt < 2:
                    time.sleep(0.75 * (attempt + 1))
                    continue
            response.raise_for_status()
            raw = response.content
            if not raw:
                raise ValueError("empty annual report response")
            if len(raw) > MAX_DOCUMENT_BYTES:
                raise ValueError(f"annual report exceeds {MAX_DOCUMENT_BYTES} bytes")
            return raw, {"url": response.url, "status": "OK"}
        except (requests.RequestException, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < 2:
                time.sleep(0.75 * (attempt + 1))
    return None, {"url": url, "status": "FETCH_FAILED", "error": last_error}


def extract_pdf_bytes(raw: bytes, url: str) -> tuple[bytes | None, dict[str, object]]:
    suffix = Path(urlparse(url).path).suffix.casefold()
    if suffix == ".pdf":
        return raw, {"container": "PDF", "pdf_candidates": 1}
    if suffix != ".zip":
        return None, {"container": "UNSUPPORTED", "pdf_candidates": 0}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            candidates = [
                name
                for name in archive.namelist()
                if not name.endswith("/") and Path(name).suffix.casefold() == ".pdf"
            ]
            if len(candidates) != 1:
                return None, {"container": "ZIP", "pdf_candidates": len(candidates)}
            return archive.read(candidates[0]), {
                "container": "ZIP",
                "pdf_candidates": 1,
                "pdf_name": candidates[0],
            }
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        return None, {
            "container": "ZIP_ERROR",
            "pdf_candidates": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def scan_pdf(pdf_raw: bytes) -> dict[str, object]:
    found = {name: False for name in DISCLOSURE_PATTERNS}
    pages_scanned = 0
    extracted_chars = 0
    try:
        reader = PdfReader(io.BytesIO(pdf_raw), strict=False)
        page_count = len(reader.pages)
        for page in reader.pages[:MAX_PDF_PAGES]:
            try:
                text = page.extract_text() or ""
            except (KeyError, TypeError, ValueError):
                text = ""
            normalized = " ".join(text.casefold().split())
            extracted_chars += len(normalized)
            pages_scanned += 1
            for concept, patterns in DISCLOSURE_PATTERNS.items():
                if not found[concept] and any(pattern.casefold() in normalized for pattern in patterns):
                    found[concept] = True
            if all(found.values()):
                break
        return {
            "status": "OK",
            "page_count": page_count,
            "pages_scanned": pages_scanned,
            "extracted_chars": extracted_chars,
            "text_disclosure_presence": found,
        }
    except (OSError, PdfReadError, TypeError, ValueError) as exc:
        return {
            "status": "PDF_PARSE_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "page_count": None,
            "pages_scanned": pages_scanned,
            "extracted_chars": extracted_chars,
            "text_disclosure_presence": found,
        }


def choose_content_records(
    records_by_symbol: dict[str, list[dict[str, object]]],
    group_symbols: list[str],
) -> list[dict[str, object]]:
    eligible: list[tuple[str, dict[str, object]]] = []
    for symbol in sorted(group_symbols):
        records = [
            row
            for row in records_by_symbol.get(symbol, [])
            if 2016 <= int(row["to_year"]) <= 2020
        ]
        if not records:
            continue
        chosen = min(
            records,
            key=lambda row: (
                abs(int(row["to_year"]) - 2018),
                int(row["to_year"]),
                str(row["report_url"]),
            ),
        )
        eligible.append((symbol, chosen))
    return [row for _, row in eligible[:CONTENT_SAMPLE_PER_GROUP]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    root = Path(parser.parse_args().out)
    root.mkdir(parents=True, exist_ok=True)

    client = NSEClient(timeout=25, attempts=4)
    listing_manifest = []
    symbols_by_year: dict[int, set[str]] = {}
    for year in (2018, 2020):
        symbols, meta = fetch_listing(client, root, year)
        symbols_by_year[year] = symbols
        listing_manifest.append(meta)
    dump(root / "listing-manifest-v2.json", listing_manifest)

    survivor_set = symbols_by_year[2018] & symbols_by_year[2020]
    exit_set = symbols_by_year[2018] - symbols_by_year[2020]
    groups = {
        "SURVIVOR_PROXY": deterministic_spread(survivor_set, GROUP_SAMPLE),
        "EXIT_PROXY": deterministic_spread(exit_set, GROUP_SAMPLE),
    }
    dump(
        root / "historical-symbol-samples.json",
        {
            "survivor_proxy_population": len(survivor_set),
            "exit_proxy_population": len(exit_set),
            "groups": groups,
        },
    )

    records_by_symbol: dict[str, list[dict[str, object]]] = {}
    api_manifest = []
    all_records = []
    for group, symbols in groups.items():
        for number, symbol in enumerate(symbols, 1):
            records, meta = fetch_annual_report_records(client, root, symbol, group)
            records_by_symbol[symbol] = records
            api_manifest.append(meta)
            all_records.extend(records)
            if number % 20 == 0:
                print(f"H019 annual-report API {group} {number}/{len(symbols)}", flush=True)
    dump(root / "annual-report-api-manifest.json", api_manifest)
    dump(root / "annual-report-records.json", all_records)

    depth_summary: dict[str, object] = {}
    for group, symbols in groups.items():
        per_cutoff = {}
        for cutoff_name, cutoff in CUTOFFS.items():
            depths = [report_depth(records_by_symbol.get(symbol, []), cutoff) for symbol in symbols]
            per_cutoff[cutoff_name] = {
                "sample_count": len(symbols),
                "with_1": sum(depth >= 1 for depth in depths),
                "with_3": sum(depth >= 3 for depth in depths),
                "with_5": sum(depth >= 5 for depth in depths),
                "max_depth": max(depths, default=0),
            }
        depth_summary[group] = {
            "api_success_symbols": sum(bool(records_by_symbol.get(symbol)) for symbol in symbols),
            "cutoffs": per_cutoff,
        }

    client._initialize_session()
    content_records = []
    for group, symbols in groups.items():
        for record in choose_content_records(records_by_symbol, symbols):
            report_url = str(record["report_url"])
            raw, fetch_meta = archive_download(client, report_url)
            item = {**record, **fetch_meta}
            if raw is not None:
                original = retain(root, raw, url=str(fetch_meta["url"]), kind="annual-report-document")
                pdf_raw, container = extract_pdf_bytes(raw, report_url)
                item.update(original)
                item["container"] = container
                if pdf_raw is not None:
                    item["pdf_sha256"] = hashlib.sha256(pdf_raw).hexdigest()
                    item["pdf_bytes"] = len(pdf_raw)
                    item["pdf_scan"] = scan_pdf(pdf_raw)
            content_records.append(item)
            print(
                f"H019 annual-report content {group} {record['symbol']} FY{record['to_year']}",
                flush=True,
            )
    dump(root / "annual-report-content-sample.json", content_records)

    disclosure_counts: dict[str, Counter[str]] = {group: Counter() for group in groups}
    parsed_counts = Counter()
    for item in content_records:
        group = str(item["group"])
        scan = item.get("pdf_scan")
        if not isinstance(scan, dict) or scan.get("status") != "OK":
            continue
        parsed_counts[group] += 1
        presence = scan.get("text_disclosure_presence")
        if isinstance(presence, dict):
            disclosure_counts[group].update(name for name, present in presence.items() if present)

    summary = {
        "status": "H019_ANNUAL_REPORT_SOURCE_FEASIBILITY_ONLY",
        "market_outcomes_opened": False,
        "live_capital_allowed": False,
        "historical_symbol_populations": {
            "2018": len(symbols_by_year[2018]),
            "2020": len(symbols_by_year[2020]),
            "survivor_proxy": len(survivor_set),
            "exit_proxy": len(exit_set),
        },
        "sample_groups": {name: len(symbols) for name, symbols in groups.items()},
        "annual_report_api_status": dict(Counter(str(row.get("status")) for row in api_manifest)),
        "historical_depth": depth_summary,
        "content_sample_count": len(content_records),
        "content_fetch_status": dict(Counter(str(row.get("status")) for row in content_records)),
        "content_pdf_parsed_by_group": dict(parsed_counts),
        "content_disclosure_coverage": {
            group: {
                concept: {
                    "count": counts[concept],
                    "rate": counts[concept] / parsed_counts[group] if parsed_counts[group] else 0.0,
                }
                for concept in DISCLOSURE_PATTERNS
            }
            for group, counts in disclosure_counts.items()
        },
    }
    dump(root / "source-audit-v2-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
