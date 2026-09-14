from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ARCHIVE_HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com"}
ARCHIVE_BASE = "https://nsearchives.nseindia.com/"
CATEGORY_TERMS = (
    "mutual fund",
    "foreign portfolio investor",
    "fpi",
    "insurance compan",
    "promoter",
    "institution",
    "public shareholding",
)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _scalar_parent(parent: dict[str, Any]) -> dict[str, Any]:
    retained: dict[str, Any] = {}
    for key, value in parent.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            text = str(value) if value is not None else None
            retained[str(key)] = text[:500] if isinstance(text, str) else text
    return retained


def _looks_like_xbrl(value: str) -> bool:
    lower = value.casefold()
    return (
        "xbrl" in lower
        or "ixbrl" in lower
        or "_shp_" in lower
        or ("shareholding" in lower and (".html" in lower or ".xml" in lower))
    )


def _resolve_xbrl_url(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.startswith("//"):
        candidate = f"https:{candidate}"
    elif candidate.startswith("/"):
        candidate = urljoin(ARCHIVE_BASE, candidate)
    elif not candidate.startswith(("http://", "https://")):
        if "/" in candidate or candidate.lower().endswith((".html", ".xml", ".xhtml")):
            candidate = urljoin(ARCHIVE_BASE, candidate)
        else:
            return None
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ARCHIVE_HOSTS:
        return None
    return candidate


def _inventory_xbrl_records(payload: object) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def visit(value: object, path: str, parent: dict[str, Any] | None) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                visit(nested, f"{path}.{key}" if path else str(key), value)
            return
        if isinstance(value, list):
            for index, nested in enumerate(value):
                visit(nested, f"{path}[{index}]", parent)
            return
        if not isinstance(value, str) or not _looks_like_xbrl(value):
            return
        url = _resolve_xbrl_url(value)
        if url is None:
            return
        record = found.setdefault(
            url,
            {
                "url": url,
                "paths": [],
                "parent_scalar_fields": [],
            },
        )
        record["paths"].append(path)
        if parent is not None:
            scalar = _scalar_parent(parent)
            if scalar and scalar not in record["parent_scalar_fields"]:
                record["parent_scalar_fields"].append(scalar)

    visit(payload, "", None)
    return sorted(found.values(), key=lambda item: item["url"], reverse=True)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def _fetch(
    session: requests.Session, *, url: str, timeout: float, attempts: int
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"XBRL fetch failed: {url}: {last_error}")


def _clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _category_rows(html: bytes) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    for index, tr in enumerate(soup.find_all("tr")):
        cells = [_clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if not cells:
            continue
        joined = " | ".join(cells)
        lowered = joined.casefold()
        matched = sorted(term for term in CATEGORY_TERMS if term in lowered)
        if matched:
            rows.append(
                {
                    "row_index": index,
                    "matched_terms": matched,
                    "cells": cells[:30],
                }
            )
    return rows


def _date_candidates(html: bytes) -> list[str]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return sorted(set(DATE_RE.findall(text)))[:100]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect official NSE shareholding XBRLs for stable ownership categories"
    )
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-filings-per-symbol", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if (
        args.max_filings_per_symbol < 1
        or args.timeout_seconds <= 0
        or args.attempts < 1
        or args.pause_seconds < 0
    ):
        raise ValueError("invalid XBRL probe configuration")

    session = _session()
    symbol_reports: list[dict[str, Any]] = []
    raw_files = sorted(args.raw_dir.glob("*.json"))
    if not raw_files:
        raise SystemExit(f"no official NSE raw API responses found in {args.raw_dir}")

    for raw_path in raw_files:
        symbol = raw_path.stem.upper()
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        inventory = _inventory_xbrl_records(payload)
        selected = inventory[: args.max_filings_per_symbol]
        filings: list[dict[str, Any]] = []
        for index, item in enumerate(selected, start=1):
            url = item["url"]
            try:
                response = _fetch(
                    session,
                    url=url,
                    timeout=args.timeout_seconds,
                    attempts=args.attempts,
                )
                body = response.content
                report = {
                    **item,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("Content-Type"),
                    "content_length": len(body),
                    "sha256": _sha256(body),
                    "category_rows": _category_rows(body),
                    "date_candidates": _date_candidates(body),
                    "error": None,
                }
            except (RuntimeError, requests.RequestException, ValueError) as exc:
                report = {
                    **item,
                    "status_code": None,
                    "content_type": None,
                    "content_length": None,
                    "sha256": None,
                    "category_rows": [],
                    "date_candidates": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            filings.append(report)
            print(
                f"{symbol} filing {index}/{len(selected)}: "
                f"status={report['status_code']} category_rows={len(report['category_rows'])}",
                flush=True,
            )
            if args.pause_seconds:
                time.sleep(args.pause_seconds)
        symbol_reports.append(
            {
                "symbol": symbol,
                "xbrl_reference_count": len(inventory),
                "probed_filing_count": len(filings),
                "successful_filing_count": sum(row["status_code"] == 200 for row in filings),
                "filings_with_category_rows": sum(bool(row["category_rows"]) for row in filings),
                "filings": filings,
            }
        )

    report = {
        "schema_version": 1,
        "hypothesis_probe": "H023-OWNERSHIP-XBRL-PROBE",
        "purpose": (
            "Source-only semantic probe of official NSE shareholding XBRLs. "
            "No price, return, benchmark, or outcome input is consumed."
        ),
        "symbols": [row["symbol"] for row in symbol_reports],
        "symbol_count": len(symbol_reports),
        "symbols_with_xbrl": sum(row["xbrl_reference_count"] > 0 for row in symbol_reports),
        "symbols_with_category_rows": sum(
            row["filings_with_category_rows"] > 0 for row in symbol_reports
        ),
        "symbol_reports": symbol_reports,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out, report)
    print(
        "H023 XBRL probe: "
        f"symbols={report['symbol_count']} xbrl={report['symbols_with_xbrl']} "
        f"category_rows={report['symbols_with_category_rows']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
