from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from probe_h024_nse_pit_gg import _clean, _request, _rows, _session

from marketlab.h024_insider import H024InsiderError, parse_pit_xml, parser_contract

APPROVED_ARCHIVE_HOSTS = frozenset({"nsearchives.nseindia.com", "archives.nseindia.com"})
ARCHIVE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml,text/xml,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
_THREAD_LOCAL = threading.local()


class H024FullAuditError(RuntimeError):
    """Raised when the full current PIT corpus cannot be audited without guessing."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _windows(start: date, end: date, days: int = 28) -> list[tuple[date, date]]:
    result: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        result.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return result


def _collect_rows(
    *,
    start: date,
    end: date,
    timeout: float,
    attempts: int,
) -> list[dict[str, Any]]:
    session = _session(timeout)
    deduped: dict[str, dict[str, Any]] = {}
    for window_start, window_end in _windows(start, end):
        response = _request(
            session,
            start=window_start,
            end=window_end,
            timeout=timeout,
            attempts=attempts,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise H024FullAuditError("PIT-GG response is not JSON") from exc
        for row in _rows(payload):
            raw = json.dumps(
                row,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            digest = _sha256(raw)
            existing = deduped.get(digest)
            if existing is not None and existing != row:
                raise H024FullAuditError("PIT-GG row digest collision with changed bytes")
            deduped[digest] = row
    return list(deduped.values())


def _archive_session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(ARCHIVE_HEADERS)
        _THREAD_LOCAL.session = session
    return session


def _fetch_xml(url: str, *, timeout: float, attempts: int) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in APPROVED_ARCHIVE_HOSTS:
        raise H024FullAuditError(f"unapproved PIT XML URL: {url}")
    session = _archive_session()
    last_error: Exception | None = None
    for _attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.content
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
    raise H024FullAuditError(f"PIT XML fetch failed: {url}: {last_error}")


def _audit_one(
    row: dict[str, Any],
    *,
    raw_dir: Path | None,
    timeout: float,
    attempts: int,
) -> dict[str, Any]:
    symbol = _clean(row.get("symbol")).upper()
    url = _clean(row.get("xmlFileName"))
    submission_type = _clean(row.get("typeOfSubmission"))
    result: dict[str, Any] = {
        "symbol": symbol,
        "companyName": _clean(row.get("companyName")),
        "broadcastDateTime": _clean(row.get("broadcastDateTime")),
        "exchdisstime": _clean(row.get("exchdisstime")),
        "typeOfSubmission": submission_type,
        "revisionRemark": _clean(row.get("revisionRemark")),
        "appId": _clean(row.get("appId")),
        "prevAppId": _clean(row.get("prevAppId")),
        "ixbrl": _clean(row.get("ixbrl")),
        "xmlFileName": url,
        "status": "FAILED",
        "error": None,
    }
    try:
        raw = _fetch_xml(url, timeout=timeout, attempts=attempts)
        parsed = parse_pit_xml(raw, expected_symbol=symbol)
        expected_revision = submission_type == "Revision"
        if submission_type not in {"Original", "Revision"}:
            raise H024FullAuditError(f"unexpected typeOfSubmission: {submission_type}")
        if parsed.revised_filing != expected_revision:
            raise H024FullAuditError(
                "discovery typeOfSubmission does not match XML RevisedFilling"
            )
        if raw_dir is not None:
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f"{_sha256(url.encode('utf-8'))}.xml").write_bytes(raw)
    except (H024FullAuditError, H024InsiderError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result.update(
        {
            "status": "COMPLETE",
            "xml_sha256": _sha256(raw),
            "xml_byte_count": len(raw),
            "date_of_filing": parsed.date_of_filing,
            "transaction_count": len(parsed.transactions),
            "direct_market_purchase_count": len(parsed.direct_market_purchases),
            "direct_market_purchase_value_inr": parsed.direct_market_purchase_value_inr,
            "direct_market_purchase_quantity": parsed.direct_market_purchase_quantity,
            "transaction_categories": [row.category for row in parsed.transactions],
            "transaction_modes": [row.acquisition_mode for row in parsed.transactions],
            "transaction_types": [row.transaction_type for row in parsed.transactions],
            "transaction_instruments": [row.instrument for row in parsed.transactions],
            "direct_market_purchase_categories": [
                row.category for row in parsed.direct_market_purchases
            ],
            "direct_market_purchase_names": [
                row.person_name for row in parsed.direct_market_purchases
            ],
            "transactions": [row.to_dict() for row in parsed.transactions],
        }
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full current NSE Regulation 7(2) raw-XBRL parser/source feasibility audit"
    )
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date)
    if start > end:
        raise H024FullAuditError("from-date exceeds to-date")
    if args.workers < 1 or args.attempts < 1 or args.timeout_seconds <= 0:
        raise H024FullAuditError("invalid full-audit configuration")

    discovery_rows = _collect_rows(
        start=start,
        end=end,
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    rows = [
        row
        for row in discovery_rows
        if _clean(row.get("regulation")) == "Regulation 7 (2)"
        and _clean(row.get("typeOfSubmission")) in {"Original", "Revision"}
        and bool(_clean(row.get("xmlFileName")))
    ]
    urls = [_clean(row.get("xmlFileName")) for row in rows]
    if len(urls) != len(set(urls)):
        raise H024FullAuditError("current Regulation 7(2) corpus contains duplicate XML URLs")

    reports: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _audit_one,
                row,
                raw_dir=args.raw_dir,
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            ): row
            for row in rows
        }
        for index, future in enumerate(as_completed(futures), start=1):
            report = future.result()
            reports.append(report)
            if index % 100 == 0 or index == len(futures):
                complete = sum(row["status"] == "COMPLETE" for row in reports)
                print(
                    f"[{index:04d}/{len(futures):04d}] complete={complete} "
                    f"failed={index - complete}",
                    flush=True,
                )

    reports.sort(
        key=lambda row: (
            str(row["broadcastDateTime"]),
            str(row["symbol"]),
            str(row["xmlFileName"]),
        )
    )
    complete = [row for row in reports if row["status"] == "COMPLETE"]
    failed = [row for row in reports if row["status"] != "COMPLETE"]
    direct_docs = [row for row in complete if row["direct_market_purchase_count"] > 0]
    categories = Counter(
        category for row in complete for category in row["transaction_categories"]
    )
    modes = Counter(mode for row in complete for mode in row["transaction_modes"])
    transaction_types = Counter(
        value for row in complete for value in row["transaction_types"]
    )
    instruments = Counter(
        value for row in complete for value in row["transaction_instruments"]
    )
    direct_categories = Counter(
        category
        for row in direct_docs
        for category in row["direct_market_purchase_categories"]
    )
    report = {
        "schema_version": 1,
        "hypothesis_candidate": "H024_INSIDER_CAPITAL_COMMITMENT",
        "audit_id": "H024-PIT-XML-FULL-CORPUS-AUDIT-V1",
        "purpose": (
            "Full post-migration source-only parser feasibility audit of current official NSE "
            "Regulation 7(2) raw XBRLs. No price/return outcome data consumed."
        ),
        "generated_at_utc": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "source_window": {
            "from_date": args.from_date,
            "to_date": args.to_date,
            "discovery_endpoint": "https://www.nseindia.com/api/corporates-pit-gg",
        },
        "parser_contract": parser_contract(),
        "summary": {
            "discovery_row_count": len(discovery_rows),
            "eligible_regulation_7_2_document_count": len(rows),
            "complete_document_count": len(complete),
            "failed_document_count": len(failed),
            "parse_coverage": len(complete) / len(rows) if rows else 0.0,
            "transaction_row_count": sum(row["transaction_count"] for row in complete),
            "direct_market_purchase_document_count": len(direct_docs),
            "direct_market_purchase_symbol_count": len(
                {row["symbol"] for row in direct_docs}
            ),
            "direct_market_purchase_transaction_count": sum(
                row["direct_market_purchase_count"] for row in direct_docs
            ),
            "direct_market_purchase_value_inr": sum(
                row["direct_market_purchase_value_inr"] for row in direct_docs
            ),
            "original_document_count": sum(
                row["typeOfSubmission"] == "Original" for row in complete
            ),
            "revision_document_count": sum(
                row["typeOfSubmission"] == "Revision" for row in complete
            ),
        },
        "category_counts": dict(categories.most_common()),
        "mode_counts": dict(modes.most_common()),
        "transaction_type_counts": dict(transaction_types.most_common()),
        "instrument_counts": dict(instruments.most_common()),
        "direct_market_purchase_category_counts": dict(direct_categories.most_common()),
        "failed_documents": failed,
        "direct_market_purchase_documents": direct_docs,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out, report)
    print(json.dumps(report["summary"], sort_keys=True), flush=True)
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
