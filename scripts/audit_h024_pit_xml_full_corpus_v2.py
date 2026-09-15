from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from audit_h024_pit_xml_full_corpus import (
    APPROVED_ARCHIVE_HOSTS,
    ARCHIVE_HEADERS,
    H024FullAuditError,
    _clean,
    _collect_rows,
    _sha256,
    _write_json,
)

from marketlab.h024_insider import H024InsiderError, parse_pit_xml, parser_contract

PIT_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading"


class _PoliteArchiveClient:
    def __init__(self, *, min_interval_seconds: float) -> None:
        if min_interval_seconds < 0:
            raise H024FullAuditError("archive request interval must be non-negative")
        self.min_interval_seconds = min_interval_seconds
        self._last_request_started = 0.0
        self._session = self._new_session()

    @staticmethod
    def _new_session() -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                **ARCHIVE_HEADERS,
                "Referer": PIT_PAGE,
                "Connection": "keep-alive",
            }
        )
        return session

    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_request_started
        delay = self.min_interval_seconds - elapsed
        if delay > 0:
            time.sleep(delay)
        self._last_request_started = time.monotonic()

    def _renew(self) -> None:
        self._session.close()
        self._session = self._new_session()

    def fetch(self, url: str, *, timeout: float, attempts: int) -> bytes:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").casefold() not in APPROVED_ARCHIVE_HOSTS
        ):
            raise H024FullAuditError(f"unapproved PIT XML URL: {url}")
        if timeout <= 0 or attempts < 1:
            raise H024FullAuditError("invalid PIT XML fetch configuration")

        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            self._pace()
            try:
                response = self._session.get(url, timeout=timeout)
            except requests.RequestException as exc:
                last_error = exc
            else:
                if response.status_code == 200:
                    return response.content
                last_error = RuntimeError(f"HTTP {response.status_code}")
                if response.status_code not in {403, 429, 500, 502, 503, 504}:
                    break

            if attempt < attempts:
                if isinstance(last_error, RuntimeError) and any(
                    marker in str(last_error) for marker in ("HTTP 403", "HTTP 429")
                ):
                    cooldown = min(15.0 * attempt, 60.0)
                    self._renew()
                else:
                    cooldown = min(2.0**attempt, 15.0)
                time.sleep(cooldown)

        raise H024FullAuditError(f"PIT XML fetch failed: {url}: {last_error}")


def _audit_one(
    row: dict[str, Any],
    *,
    client: _PoliteArchiveClient,
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
        raw = client.fetch(url, timeout=timeout, attempts=attempts)
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
            "transaction_categories": [item.category for item in parsed.transactions],
            "transaction_modes": [item.acquisition_mode for item in parsed.transactions],
            "transaction_types": [item.transaction_type for item in parsed.transactions],
            "transaction_instruments": [item.instrument for item in parsed.transactions],
            "direct_market_purchase_categories": [
                item.category for item in parsed.direct_market_purchases
            ],
            "direct_market_purchase_names": [
                item.person_name for item in parsed.direct_market_purchases
            ],
            "transactions": [item.to_dict() for item in parsed.transactions],
        }
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rate-limited full current NSE Regulation 7(2) raw-XBRL parser/source audit"
        )
    )
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--pause-seconds", type=float, default=0.85)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date)
    if start > end:
        raise H024FullAuditError("from-date exceeds to-date")
    if args.attempts < 1 or args.timeout_seconds <= 0 or args.pause_seconds < 0:
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

    client = _PoliteArchiveClient(min_interval_seconds=args.pause_seconds)
    reports: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        report = _audit_one(
            row,
            client=client,
            raw_dir=args.raw_dir,
            timeout=args.timeout_seconds,
            attempts=args.attempts,
        )
        reports.append(report)
        if index % 100 == 0 or index == len(rows):
            complete_count = sum(item["status"] == "COMPLETE" for item in reports)
            print(
                f"[{index:04d}/{len(rows):04d}] complete={complete_count} "
                f"failed={index - complete_count}",
                flush=True,
            )

    reports.sort(
        key=lambda item: (
            str(item["broadcastDateTime"]),
            str(item["symbol"]),
            str(item["xmlFileName"]),
        )
    )
    complete = [item for item in reports if item["status"] == "COMPLETE"]
    failed = [item for item in reports if item["status"] != "COMPLETE"]
    direct_docs = [item for item in complete if item["direct_market_purchase_count"] > 0]
    categories = Counter(
        category for item in complete for category in item["transaction_categories"]
    )
    modes = Counter(mode for item in complete for mode in item["transaction_modes"])
    transaction_types = Counter(
        value for item in complete for value in item["transaction_types"]
    )
    instruments = Counter(
        value for item in complete for value in item["transaction_instruments"]
    )
    direct_categories = Counter(
        category
        for item in direct_docs
        for category in item["direct_market_purchase_categories"]
    )
    failure_classes = Counter(
        str(item.get("error") or "").split(":", 1)[0] for item in failed
    )
    report = {
        "schema_version": 2,
        "hypothesis_candidate": "H024_INSIDER_CAPITAL_COMMITMENT",
        "audit_id": "H024-PIT-XML-FULL-CORPUS-AUDIT-V2",
        "purpose": (
            "Full post-migration source-only parser feasibility audit of current official NSE "
            "Regulation 7(2) raw XBRLs using globally rate-limited archive acquisition. "
            "No price/return outcome data consumed."
        ),
        "generated_at_utc": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "source_window": {
            "from_date": args.from_date,
            "to_date": args.to_date,
            "discovery_endpoint": "https://www.nseindia.com/api/corporates-pit-gg",
        },
        "transport_contract": {
            "parallel_archive_fetches": 1,
            "minimum_request_interval_seconds": args.pause_seconds,
            "attempts": args.attempts,
            "throttle_statuses": [403, 429],
            "throttle_cooldown_seconds_by_retry": [15, 30, 45, 60, 60],
        },
        "parser_contract": parser_contract(),
        "summary": {
            "discovery_row_count": len(discovery_rows),
            "eligible_regulation_7_2_document_count": len(rows),
            "complete_document_count": len(complete),
            "failed_document_count": len(failed),
            "parse_coverage": len(complete) / len(rows) if rows else 0.0,
            "transaction_row_count": sum(item["transaction_count"] for item in complete),
            "direct_market_purchase_document_count": len(direct_docs),
            "direct_market_purchase_symbol_count": len(
                {item["symbol"] for item in direct_docs}
            ),
            "direct_market_purchase_transaction_count": sum(
                item["direct_market_purchase_count"] for item in direct_docs
            ),
            "direct_market_purchase_value_inr": sum(
                item["direct_market_purchase_value_inr"] for item in direct_docs
            ),
            "original_document_count": sum(
                item["typeOfSubmission"] == "Original" for item in complete
            ),
            "revision_document_count": sum(
                item["typeOfSubmission"] == "Revision" for item in complete
            ),
        },
        "failure_class_counts": dict(failure_classes.most_common()),
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
