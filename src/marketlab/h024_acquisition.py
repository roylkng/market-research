from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from marketlab.h024_insider import H024InsiderError, parse_pit_xml

SOURCE_CONTRACT_ID = "H024-NSE-PIT-GG-XBRL-V1"
NSE_HOME = "https://www.nseindia.com/"
PIT_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading"
PIT_GG_ENDPOINT = "https://www.nseindia.com/api/corporates-pit-gg"
APPROVED_ARCHIVE_HOSTS = frozenset(
    {"nsearchives.nseindia.com", "archives.nseindia.com"}
)
IST = ZoneInfo("Asia/Kolkata")


class H024AcquisitionError(RuntimeError):
    """Raised when official H024 source acquisition cannot proceed without guessing."""


def canonical_hash(payload: object) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise H024AcquisitionError("H024 canonical payload must contain finite JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def utc_now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_exchange_timestamp(value: object) -> str:
    raw = clean(value)
    if not raw:
        raise H024AcquisitionError("NSE PIT source lacks exchange dissemination timestamp")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise H024AcquisitionError(f"invalid NSE PIT exchange timestamp: {raw}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _approved_archive_url(value: object, *, field: str) -> str:
    raw = clean(value)
    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        raise H024AcquisitionError(f"invalid {field}: {raw}") from exc
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in APPROVED_ARCHIVE_HOSTS:
        raise H024AcquisitionError(f"{field} is not on an approved NSE archive host")
    return raw


def discovery_session(timeout: float = 30.0) -> requests.Session:
    if timeout <= 0:
        raise H024AcquisitionError("timeout must be positive")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": PIT_PAGE,
        }
    )
    session.get(NSE_HOME, timeout=timeout)
    session.get(PIT_PAGE, timeout=timeout)
    return session


def archive_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept": "application/xml,text/xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": PIT_PAGE,
        }
    )
    return session


def _nse_date(value: date) -> str:
    return value.strftime("%d-%m-%Y")


def fetch_discovery(
    session: requests.Session,
    *,
    start: date,
    end: date,
    timeout: float = 30.0,
    attempts: int = 4,
) -> requests.Response:
    if start > end:
        raise H024AcquisitionError("PIT discovery start date exceeds end date")
    if attempts < 1 or timeout <= 0:
        raise H024AcquisitionError("invalid PIT discovery configuration")
    params = {
        "index": "equities",
        "from_date": _nse_date(start),
        "to_date": _nse_date(end),
    }
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(PIT_GG_ENDPOINT, params=params, timeout=timeout)
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(min(2**attempt, 8))
            try:
                session.get(NSE_HOME, timeout=timeout)
                session.get(PIT_PAGE, timeout=timeout)
            except requests.RequestException:
                pass
    raise H024AcquisitionError(
        f"NSE PIT-GG request failed {start.isoformat()}..{end.isoformat()}: {last_error}"
    )


def discovery_rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        raw = payload.get("data")
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise H024AcquisitionError("NSE PIT-GG payload.data is not a list")
        return [row for row in raw if isinstance(row, dict)]
    raise H024AcquisitionError("NSE PIT-GG payload is neither object nor list")


def source_from_discovery_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        raise TypeError("H024 discovery row must be an object")
    if clean(row.get("regulation")) != "Regulation 7 (2)":
        return None
    submission_type = clean(row.get("typeOfSubmission"))
    if submission_type not in {"Original", "Revision"}:
        raise H024AcquisitionError(
            f"unexpected Regulation 7(2) submission type: {submission_type}"
        )
    symbol = clean(row.get("symbol")).upper()
    app_id = clean(row.get("appId"))
    if not symbol or not app_id:
        raise H024AcquisitionError("Regulation 7(2) row lacks symbol/appId")
    broadcast_at_utc = normalize_exchange_timestamp(row.get("broadcastDateTime"))
    exchange_disseminated_at_utc = normalize_exchange_timestamp(row.get("exchdisstime"))
    if exchange_disseminated_at_utc < broadcast_at_utc:
        raise H024AcquisitionError(
            f"{symbol}/{app_id}: exchange dissemination precedes NSE broadcast timestamp"
        )
    xml_url = _approved_archive_url(row.get("xmlFileName"), field="xmlFileName")
    ixbrl_url = _approved_archive_url(row.get("ixbrl"), field="ixbrl")
    payload = {
        "source_contract_id": SOURCE_CONTRACT_ID,
        "symbol": symbol,
        "app_id": app_id,
        "submission_type": submission_type,
        "exchange_disseminated_at_utc": exchange_disseminated_at_utc,
        "xml_url": xml_url,
    }
    return {
        "source_id": canonical_hash(payload),
        "symbol": symbol,
        "company_name": clean(row.get("companyName")),
        "app_id": app_id,
        "prev_app_id": clean(row.get("prevAppId")),
        "submission_type": submission_type,
        "revision_remark": clean(row.get("revisionRemark")),
        "broadcast_at_utc": broadcast_at_utc,
        "exchange_disseminated_at_utc": exchange_disseminated_at_utc,
        "xml_url": xml_url,
        "ixbrl_url": ixbrl_url,
        "discovery_row_sha256": canonical_hash(row),
    }


def discover_sources(payload: object) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    by_app_id: dict[tuple[str, str], str] = {}
    for row in discovery_rows(payload):
        source = source_from_discovery_row(row)
        if source is None:
            continue
        key = (str(source["symbol"]), str(source["app_id"]))
        source_id = str(source["source_id"])
        previous = by_app_id.get(key)
        if previous is not None and previous != source_id:
            raise H024AcquisitionError(
                f"{key[0]}/{key[1]}: duplicate appId has conflicting source identity"
            )
        by_app_id[key] = source_id
        sources.append(source)
    unique = {str(source["source_id"]): source for source in sources}
    result = list(unique.values())
    result.sort(
        key=lambda source: (
            str(source["exchange_disseminated_at_utc"]),
            str(source["symbol"]),
            str(source["app_id"]),
        )
    )
    return result


def fetch_xbrl(
    session: requests.Session,
    *,
    url: str,
    timeout: float = 30.0,
    attempts: int = 5,
) -> requests.Response:
    _approved_archive_url(url, field="raw XBRL URL")
    if attempts < 1 or timeout <= 0:
        raise H024AcquisitionError("invalid raw-XBRL fetch configuration")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
            if response.status_code not in {403, 429, 500, 502, 503, 504}:
                break
        except requests.RequestException as exc:
            last_error = exc
        if attempt < attempts:
            cooldown = min(5.0 * attempt, 30.0) if isinstance(last_error, RuntimeError) else min(2**attempt, 10)
            time.sleep(cooldown)
    raise H024AcquisitionError(f"raw-XBRL fetch failed: {url}: {last_error}")


def build_xbrl_evidence(source: dict[str, Any], raw: bytes) -> dict[str, Any]:
    source_id = str(source.get("source_id") or "")
    symbol = str(source.get("symbol") or "")
    submission_type = str(source.get("submission_type") or "")
    try:
        parsed = parse_pit_xml(raw, expected_symbol=symbol)
    except H024InsiderError as exc:
        return {
            "status": "PARSE_BLOCKED",
            "source_id": source_id,
            "xbrl_sha256": sha256_bytes(raw),
            "error": f"{type(exc).__name__}: {exc}",
        }
    expected_revision = submission_type == "Revision"
    if parsed.revised_filing != expected_revision:
        return {
            "status": "PARSE_BLOCKED",
            "source_id": source_id,
            "xbrl_sha256": sha256_bytes(raw),
            "error": "discovery submission type disagrees with raw-XBRL RevisedFilling",
        }
    direct = parsed.direct_market_purchases
    return {
        "status": "READY",
        "source_id": source_id,
        "xbrl_sha256": sha256_bytes(raw),
        "date_of_filing": parsed.date_of_filing,
        "transaction_count": len(parsed.transactions),
        "direct_market_purchase_count": len(direct),
        "direct_market_purchase_value_inr": parsed.direct_market_purchase_value_inr,
        "direct_market_purchase_quantity": parsed.direct_market_purchase_quantity,
        "direct_market_purchase_ownership_delta_pp": sum(
            transaction.ownership_delta_pp for transaction in direct
        ),
        "direct_market_purchase_actor_count": len(
            {transaction.person_name for transaction in direct}
        ),
        "direct_market_purchase_categories": sorted(
            {transaction.category for transaction in direct}
        ),
        "direct_market_purchase_names": sorted(
            {transaction.person_name for transaction in direct}
        ),
    }


def trailing_discovery_window(
    *,
    now_utc: datetime,
    lookback_days: int = 7,
) -> tuple[date, date]:
    if now_utc.tzinfo is None:
        raise H024AcquisitionError("now_utc must include timezone")
    if lookback_days < 1:
        raise H024AcquisitionError("lookback_days must be positive")
    local_day = now_utc.astimezone(IST).date()
    return local_day - timedelta(days=lookback_days - 1), local_day
