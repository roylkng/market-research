from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from typing import Any

import requests

from marketlab.h023_ownership import (
    BROADCAST_FORMAT,
    IST,
    REPORT_DATE_FORMAT,
    H023OwnershipError,
    is_standard_quarter_end,
    parse_mutual_fund_ownership_xbrl,
)
from marketlab.h023_prospective import (
    SOURCE_CONTRACT_ID,
    canonical_hash,
    validate_source,
)

MASTER_ENDPOINT = "https://www.nseindia.com/api/corporate-share-holdings-master"
NSE_HOME = "https://www.nseindia.com/"
FILING_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-shareholdingpattern"
APPROVED_ARCHIVE_HOST_PREFIXES = (
    "https://nsearchives.nseindia.com/",
    "https://archives.nseindia.com/",
)


class H023AcquisitionError(ValueError):
    """Raised when official NSE H023 acquisition cannot complete without guessing."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def utc_now_text() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _session(timeout: float) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": FILING_PAGE,
        }
    )
    session.get(NSE_HOME, timeout=timeout)
    session.get(FILING_PAGE, timeout=timeout)
    return session


def xbrl_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept": "application/xml,text/xml,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def master_session(timeout: float) -> requests.Session:
    if timeout <= 0:
        raise H023AcquisitionError("master timeout must be positive")
    return _session(timeout)


def _get_with_retries(
    session: requests.Session,
    *,
    url: str,
    timeout: float,
    attempts: int,
    params: dict[str, str] | None = None,
    warm_nse: bool = False,
) -> requests.Response:
    if timeout <= 0 or attempts < 1:
        raise H023AcquisitionError("invalid H023 acquisition retry configuration")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(min(2**attempt, 8))
            if warm_nse:
                try:
                    session.get(NSE_HOME, timeout=timeout)
                except requests.RequestException:
                    pass
    raise H023AcquisitionError(f"source request failed: {url}: {last_error}")


def fetch_master(
    session: requests.Session,
    *,
    symbol: str,
    timeout: float = 25.0,
    attempts: int = 4,
) -> requests.Response:
    wanted = symbol.strip().upper()
    if not wanted:
        raise H023AcquisitionError("master symbol is empty")
    return _get_with_retries(
        session,
        url=MASTER_ENDPOINT,
        params={"index": "equities", "symbol": wanted},
        timeout=timeout,
        attempts=attempts,
        warm_nse=True,
    )


def fetch_xbrl(
    session: requests.Session,
    *,
    url: str,
    timeout: float = 25.0,
    attempts: int = 4,
) -> requests.Response:
    if not any(url.startswith(prefix) for prefix in APPROVED_ARCHIVE_HOST_PREFIXES):
        raise H023AcquisitionError("XBRL URL is not on an approved NSE archive host")
    return _get_with_retries(
        session,
        url=url,
        timeout=timeout,
        attempts=attempts,
    )


def _broadcast_utc(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise H023AcquisitionError("NSE master row lacks broadcastDate")
    try:
        parsed = datetime.strptime(raw.upper(), BROADCAST_FORMAT).replace(tzinfo=IST)
    except ValueError as exc:
        raise H023AcquisitionError(f"invalid NSE broadcastDate: {raw}") from exc
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _report_date(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw.upper(), REPORT_DATE_FORMAT).replace(tzinfo=IST).date()
    except ValueError:
        return None
    canonical = parsed.isoformat()
    return canonical if is_standard_quarter_end(canonical) else None


def source_from_master_row(row: dict[str, Any], *, symbol: str) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        raise TypeError("NSE master row must be an object")
    report_date = _report_date(row.get("date"))
    if report_date is None:
        return None
    wanted = symbol.strip().upper()
    observed = str(row.get("symbol") or "").strip().upper()
    if observed and observed != wanted:
        raise H023AcquisitionError(
            f"NSE master row symbol mismatch: expected={wanted} observed={observed}"
        )
    record_id = str(row.get("recordId") or "").strip()
    xbrl_url = str(row.get("xbrl") or "").strip()
    if not record_id:
        raise H023AcquisitionError(f"{wanted}/{report_date}: missing NSE recordId")
    if not any(xbrl_url.startswith(prefix) for prefix in APPROVED_ARCHIVE_HOST_PREFIXES):
        raise H023AcquisitionError(f"{wanted}/{report_date}: invalid NSE XBRL URL")
    master_row_sha256 = canonical_hash(row)
    payload = {
        "source_contract_id": SOURCE_CONTRACT_ID,
        "symbol": wanted,
        "record_id": record_id,
        "report_date": report_date,
        "broadcast_at_utc": _broadcast_utc(row.get("broadcastDate")),
        "xbrl_url": xbrl_url,
    }
    source = {
        "source_id": canonical_hash(payload),
        "symbol": wanted,
        "record_id": record_id,
        "report_date": report_date,
        "broadcast_at_utc": payload["broadcast_at_utc"],
        "xbrl_url": xbrl_url,
        "master_row_sha256": master_row_sha256,
    }
    validate_source(source)
    return source


def discover_standard_quarter_sources(payload: object, *, symbol: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise H023AcquisitionError("NSE shareholding master payload must be a list")
    sources: list[dict[str, Any]] = []
    record_ids: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            continue
        source = source_from_master_row(row, symbol=symbol)
        if source is None:
            continue
        record_id = str(source["record_id"])
        if record_id in record_ids:
            raise H023AcquisitionError(f"{symbol}: duplicate NSE recordId in master payload")
        record_ids.add(record_id)
        sources.append(source)
    sources.sort(
        key=lambda item: (
            str(item["broadcast_at_utc"]),
            str(item["report_date"]),
            str(item["record_id"]),
        )
    )
    return sources


def build_xbrl_evidence(source: dict[str, Any], raw: bytes) -> dict[str, Any]:
    validate_source(source)
    digest = sha256_bytes(raw)
    try:
        ownership = parse_mutual_fund_ownership_xbrl(
            raw,
            expected_report_date=str(source["report_date"]),
        )
    except H023OwnershipError as exc:
        return {
            "status": "PARSE_FAILED",
            "source_id": source["source_id"],
            "xbrl_sha256": digest,
            "mutual_fund_percentage": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "status": "READY",
        "source_id": source["source_id"],
        "xbrl_sha256": digest,
        "mutual_fund_percentage": ownership.percentage,
        "error": None,
    }
