from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests

from marketlab.h024_acquisition import (
    PIT_GG_ENDPOINT,
    discover_sources,
    discovery_session,
    fetch_discovery,
    sha256_bytes,
    trailing_discovery_window,
    utc_now_text,
)
from marketlab.h024_events import (
    append_event,
    build_event_record,
    build_investability_evidence,
    due_event_keys,
    new_event_ledger,
    validate_event_ledger,
)
from marketlab.h024_historical import parse_udiff_candidate_bars
from marketlab.h024_prospective import (
    append_scan,
    append_sources,
    build_scan_record,
    new_scan_ledger,
    new_source_ledger,
    validate_evidence_ledger,
    validate_scan_ledger,
    validate_signal_ledger,
    validate_source_ledger,
)
from marketlab.marketdata import udiff_url

IST = ZoneInfo("Asia/Kolkata")
REPORTS_ENDPOINT = "https://www.nseindia.com/api/reports"
SECURITY_MASTER_REPORT_NAME = "CM - MII - Security File (.gz) (NSE Listed securities)"
APPROVED_REPORT_HOSTS = {
    "www.nseindia.com",
    "nsearchives.nseindia.com",
    "archives.nseindia.com",
}
SECURITY_MASTER_FIELDS = (
    "TckrSymb",
    "SctySrs",
    "FinInstrmNm",
    "ISIN",
    "SctyTpFlg",
    "CallAuctnInd",
    "PrtdToTrad",
    "SctyStsNrmlMkt",
    "ElgbltyNrmlMkt",
    "ListgDt",
    "DelFlg",
    "Xchg",
    "FinInstrmTp",
    "InstrmTp",
)


class H024EventSealerError(RuntimeError):
    """Raised when a prospective H024 event cannot be sealed without guessing."""


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise H024EventSealerError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_or_initialize(path: Path, factory) -> dict[str, Any]:
    return _load_json(path) if path.exists() else factory()


def _fetch_archive(
    http: requests.Session,
    url: str,
    *,
    required: bool,
    attempts: int = 4,
    timeout: float = 30.0,
) -> bytes | None:
    if attempts < 1 or timeout <= 0:
        raise H024EventSealerError("invalid NSE archive fetch configuration")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = http.get(url, timeout=timeout)
            if response.status_code == 404:
                if required:
                    raise H024EventSealerError(
                        f"required NSE archive returned 404: {url}"
                    )
                return None
            if (
                response.status_code in {403, 429} or response.status_code >= 500
            ) and attempt < attempts:
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            if not response.content:
                raise H024EventSealerError(
                    f"NSE archive returned empty bytes: {url}"
                )
            return response.content
        except (requests.RequestException, H024EventSealerError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            break
    raise H024EventSealerError(
        f"NSE archive fetch failed for {url}: {last_error}"
    ) from last_error


def _safe_report_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in APPROVED_REPORT_HOSTS:
        raise H024EventSealerError(f"unapproved NSE report URL: {value}")
    return value


def _find_report_url(payload: object) -> str | None:
    if isinstance(payload, str):
        text = payload.strip()
        if urlparse(text).path.endswith(".gz"):
            if text.startswith("https://"):
                return _safe_report_url(text)
            return _safe_report_url(urljoin("https://www.nseindia.com/", text))
        return None
    if isinstance(payload, list):
        for item in payload:
            found = _find_report_url(item)
            if found:
                return found
        return None
    if isinstance(payload, dict):
        preferred = ("filePath", "filepath", "fileLink", "link", "url")
        for key in preferred:
            if key in payload:
                found = _find_report_url(payload[key])
                if found:
                    return found
        for value in payload.values():
            found = _find_report_url(value)
            if found:
                return found
    return None


def _download_security_master(
    session: requests.Session,
    *,
    entry_day: date,
    raw_dir: Path,
    attempts: int,
    timeout: float,
) -> tuple[bytes, str]:
    archive_spec = json.dumps(
        [
            {
                "name": SECURITY_MASTER_REPORT_NAME,
                "type": "daily-reports",
                "category": "capital-market",
                "section": "equities",
            }
        ],
        separators=(",", ":"),
    )
    params = {
        "archives": archive_spec,
        "date": entry_day.strftime("%d-%b-%Y"),
        "type": "equities",
        "mode": "single",
    }
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                REPORTS_ENDPOINT,
                params=params,
                timeout=timeout,
            )
            if (
                response.status_code in {403, 429} or response.status_code >= 500
            ) and attempt < attempts:
                time.sleep(1.0 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            raw = response.content
            source_url = response.url
            if raw[:2] == b"\x1f\x8b":
                _safe_report_url(source_url)
            else:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise H024EventSealerError(
                        "NSE security-master report response is neither gzip nor JSON"
                    ) from exc
                report_url = _find_report_url(payload)
                if report_url is None:
                    raise H024EventSealerError(
                        "NSE security-master report response contains no approved .gz URL"
                    )
                report_response = session.get(report_url, timeout=timeout)
                report_response.raise_for_status()
                raw = report_response.content
                source_url = report_url
                if raw[:2] != b"\x1f\x8b":
                    raise H024EventSealerError(
                        "NSE security-master report is not gzip"
                    )
            raw_dir.mkdir(parents=True, exist_ok=True)
            path = raw_dir / f"NSE_CM_security_{entry_day.strftime('%d%m%Y')}.csv.gz"
            path.write_bytes(raw)
            return raw, source_url
        except (requests.RequestException, H024EventSealerError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(1.0 * (2 ** (attempt - 1)))
                continue
            break
    raise H024EventSealerError(
        f"NSE security-master fetch failed: {last_error}"
    ) from last_error


def _parse_security_master(
    raw_gz: bytes,
    *,
    symbols: set[str],
) -> dict[str, dict[str, Any]]:
    try:
        raw_csv = gzip.decompress(raw_gz)
    except (OSError, EOFError) as exc:
        raise H024EventSealerError("invalid NSE security-master gzip") from exc
    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise H024EventSealerError(
            "NSE security-master CSV is not UTF-8"
        ) from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {
        "TckrSymb",
        "SctySrs",
        "ISIN",
        "SctyTpFlg",
        "PrtdToTrad",
        "SctyStsNrmlMkt",
        "ElgbltyNrmlMkt",
        "DelFlg",
    }
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise H024EventSealerError(
            f"NSE security-master header changed: {reader.fieldnames}"
        )
    wanted = {symbol.strip().upper() for symbol in symbols}
    result: dict[str, dict[str, Any]] = {}
    for row in reader:
        symbol = str(row.get("TckrSymb") or "").strip().upper()
        series = str(row.get("SctySrs") or "").strip().upper()
        if symbol not in wanted or series != "EQ":
            continue
        if symbol in result:
            raise H024EventSealerError(
                f"duplicate NSE security-master EQ row for {symbol}"
            )
        result[symbol] = {
            field: str(row.get(field) or "").strip()
            for field in SECURITY_MASTER_FIELDS
            if field in row
        }
    return result


def _parse_listing_date(value: object) -> date | None:
    raw = str(value or "").strip()
    if not raw or raw in {"0", "00000000"}:
        return None
    try:
        if len(raw) == 8 and raw.isdigit():
            first = int(raw[:4])
            if 1900 <= first <= 2200:
                return date(first, int(raw[4:6]), int(raw[6:8]))
            return date(int(raw[4:8]), int(raw[2:4]), int(raw[:2]))
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            return date.fromisoformat(raw)
        if len(raw) == 10 and raw[2] == "-" and raw[5] == "-":
            return date(int(raw[6:10]), int(raw[3:5]), int(raw[:2]))
    except ValueError:
        return None
    return None


def _collect_prior_market_sessions(
    *,
    entry_day: date,
    symbols: set[str],
    security_rows: dict[str, dict[str, Any]],
    raw_dir: Path,
    attempts: int,
    timeout: float,
    max_completed_sessions: int,
) -> dict[str, list[dict[str, Any]]]:
    http = requests.Session()
    http.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "*/*",
        }
    )
    evidence: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in symbols}
    entry_isins = {
        symbol: str(security_rows.get(symbol, {}).get("ISIN") or "").strip()
        for symbol in symbols
    }
    listing_dates = {
        symbol: _parse_listing_date(
            security_rows.get(symbol, {}).get("ListgDt")
        )
        for symbol in symbols
    }
    matching_counts = {symbol: 0 for symbol in symbols}
    completed_count = 0
    cursor = entry_day - timedelta(days=1)
    raw_dir.mkdir(parents=True, exist_ok=True)

    while completed_count < max_completed_sessions:
        if cursor < date(2000, 1, 1):
            raise H024EventSealerError("H024 market-history cursor underflowed")
        url = udiff_url(cursor)
        raw = _fetch_archive(
            http,
            url,
            required=False,
            attempts=attempts,
            timeout=timeout,
        )
        if raw is None:
            cursor -= timedelta(days=1)
            continue
        rows = parse_udiff_candidate_bars(
            raw,
            session_date=cursor,
            symbols=symbols,
        )
        raw_hash = sha256_bytes(raw)
        (raw_dir / f"{cursor.isoformat()}-{raw_hash[:12]}.csv.zip").write_bytes(raw)
        completed_count += 1
        for symbol in sorted(symbols):
            row = rows.get(symbol)
            if row is not None and str(row["isin"]) == entry_isins.get(symbol):
                matching_counts[symbol] += 1
            evidence[symbol].append(
                {
                    "session_date": cursor.isoformat(),
                    "source_url": url,
                    "raw_sha256": raw_hash,
                    "isin": None if row is None else str(row["isin"]),
                    "traded_value_inr": (
                        0.0 if row is None else float(row["traded_value_inr"])
                    ),
                }
            )
        enough = all(matching_counts[symbol] >= 60 for symbol in symbols)
        if completed_count >= 20 and enough:
            break
        unresolved_can_have_more = False
        for symbol in symbols:
            if matching_counts[symbol] >= 60:
                continue
            if not entry_isins.get(symbol):
                continue
            listing = listing_dates.get(symbol)
            if listing is None or cursor > listing:
                unresolved_can_have_more = True
                break
        if completed_count >= 20 and not unresolved_can_have_more:
            break
        cursor -= timedelta(days=1)

    if completed_count < 20:
        raise H024EventSealerError(
            "fewer than 20 completed NSE UDiFF sessions were recoverable"
        )
    return evidence


def _entry_open_for_session(
    signal_ledger: dict[str, Any],
    planned_entry_session: str,
) -> datetime:
    values = {
        str(row["planned_entry_open_utc"])
        for row in signal_ledger["records"]
        if row["status"] == "QUALIFYING"
        and str(row["planned_entry_session"]) == planned_entry_session
    }
    if not values:
        raise H024EventSealerError(
            f"no H024 qualifying signals for {planned_entry_session}"
        )
    if len(values) != 1:
        raise H024EventSealerError(
            f"H024 signals disagree on entry open for {planned_entry_session}"
        )
    parsed = datetime.fromisoformat(next(iter(values)))
    if parsed.tzinfo is None:
        raise H024EventSealerError("H024 entry open lacks timezone")
    return parsed.astimezone(UTC)


def _final_revision_refresh(
    *,
    source_ledger: dict[str, Any],
    scan_ledger: dict[str, Any],
    raw_dir: Path,
    lookback_days: int,
    timeout: float,
    attempts: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    api = discovery_session(timeout)
    now = datetime.now(UTC)
    window_start, window_end = trailing_discovery_window(
        now_utc=now,
        lookback_days=lookback_days,
    )
    response = fetch_discovery(
        api,
        start=window_start,
        end=window_end,
        timeout=timeout,
        attempts=attempts,
    )
    raw = response.content
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / (
        f"final-pit-gg-{window_start.isoformat()}-{window_end.isoformat()}.json"
    )
    path.write_bytes(raw)
    try:
        payload = response.json()
    except ValueError as exc:
        raise H024EventSealerError(
            "H024 final PIT-GG refresh is not JSON"
        ) from exc
    sources = discover_sources(payload)
    observed_at = utc_now_text()
    updated_sources = append_sources(
        source_ledger,
        sources,
        first_seen_at_utc=observed_at,
    )
    scan = build_scan_record(
        scanned_at_utc=observed_at,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        discovery_raw_sha256=sha256_bytes(raw),
        source_ids=[str(source["source_id"]) for source in sources],
    )
    updated_scans = append_scan(scan_ledger, scan)
    metadata = {
        "observed_at_utc": observed_at,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "source_count": len(sources),
        "scan_id": scan["scan_id"],
        "pit_gg_endpoint": PIT_GG_ENDPOINT,
    }
    return updated_sources, updated_scans, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seal due H024 prospective symbol-entry events before the NSE open"
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--entry-session", default=None)
    parser.add_argument("--lookback-days", type=int, default=35)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--final-refresh-seconds-before-open", type=int, default=45)
    parser.add_argument("--max-completed-sessions", type=int, default=260)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if (
        args.lookback_days < 1
        or args.timeout_seconds <= 0
        or args.attempts < 1
        or args.final_refresh_seconds_before_open < 5
        or args.max_completed_sessions < 60
    ):
        raise H024EventSealerError("invalid H024 event-sealer configuration")

    source_path = args.state_dir / "source-ledger.json"
    evidence_path = args.state_dir / "evidence-ledger.json"
    signal_path = args.state_dir / "signal-ledger.json"
    scan_path = args.state_dir / "scan-ledger.json"
    event_path = args.state_dir / "event-ledger.json"

    source_ledger = _load_or_initialize(source_path, new_source_ledger)
    evidence_ledger = _load_json(evidence_path)
    signal_ledger = _load_json(signal_path)
    scan_ledger = _load_or_initialize(scan_path, new_scan_ledger)
    event_ledger = _load_or_initialize(event_path, new_event_ledger)
    validate_source_ledger(source_ledger)
    validate_evidence_ledger(evidence_ledger)
    validate_signal_ledger(signal_ledger)
    validate_scan_ledger(scan_ledger)
    validate_event_ledger(event_ledger)

    entry_session = (
        args.entry_session
        if args.entry_session is not None
        else datetime.now(IST).date().isoformat()
    )
    due = due_event_keys(
        signal_ledger=signal_ledger,
        event_ledger=event_ledger,
        planned_entry_session=entry_session,
    )
    started_at = utc_now_text()
    if not due:
        report = {
            "schema_version": 1,
            "hypothesis_id": "H024",
            "started_at_utc": started_at,
            "completed_at_utc": utc_now_text(),
            "planned_entry_session": entry_session,
            "due_event_count": 0,
            "sealed_event_count": 0,
            "final_revision_refresh_performed": False,
            "event_ledger_sha256": event_ledger["ledger_sha256"],
            "outcome_data_attached": False,
            "live_capital_allowed": False,
        }
        _write_json(args.report, report)
        print(json.dumps(report, sort_keys=True), flush=True)
        return 0

    symbols = {symbol for symbol, _ in due}
    entry_day = date.fromisoformat(entry_session)
    nse = discovery_session(args.timeout_seconds)
    security_raw, security_url = _download_security_master(
        nse,
        entry_day=entry_day,
        raw_dir=args.raw_dir / "security-master",
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )
    security_hash = sha256_bytes(security_raw)
    security_rows = _parse_security_master(security_raw, symbols=symbols)

    prior_by_symbol = _collect_prior_market_sessions(
        entry_day=entry_day,
        symbols=symbols,
        security_rows=security_rows,
        raw_dir=args.raw_dir / "udiff",
        attempts=args.attempts,
        timeout=args.timeout_seconds,
        max_completed_sessions=args.max_completed_sessions,
    )
    investability_by_symbol = {
        symbol: build_investability_evidence(
            symbol=symbol,
            planned_entry_session=entry_session,
            security_master_source_url=security_url,
            security_master_sha256=security_hash,
            security_master_fields=security_rows.get(symbol),
            prior_sessions=prior_by_symbol[symbol],
        )
        for symbol in sorted(symbols)
    }

    entry_open = _entry_open_for_session(signal_ledger, entry_session)
    refresh_target = entry_open - timedelta(
        seconds=args.final_refresh_seconds_before_open
    )
    now = datetime.now(UTC)
    if now < refresh_target:
        time.sleep((refresh_target - now).total_seconds())

    source_ledger, scan_ledger, refresh_metadata = _final_revision_refresh(
        source_ledger=source_ledger,
        scan_ledger=scan_ledger,
        raw_dir=args.raw_dir / "final-discovery",
        lookback_days=args.lookback_days,
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    frozen_at = utc_now_text()

    sealed_ids: list[str] = []
    status_counts: dict[str, int] = {}
    for symbol, planned_session in due:
        record = build_event_record(
            source_ledger=source_ledger,
            evidence_ledger=evidence_ledger,
            signal_ledger=signal_ledger,
            symbol=symbol,
            planned_entry_session=planned_session,
            investability=investability_by_symbol[symbol],
            frozen_at_utc=frozen_at,
        )
        event_ledger = append_event(event_ledger, record)
        sealed_ids.append(str(record["event_id"]))
        key = (
            str(record["status"])
            if record["status"] == "PRIMARY_ELIGIBLE"
            else f"EXCLUDED:{record['exclusion_reason']}"
        )
        status_counts[key] = status_counts.get(key, 0) + 1

    validate_source_ledger(source_ledger)
    validate_scan_ledger(scan_ledger)
    validate_event_ledger(event_ledger)
    _write_json(source_path, source_ledger)
    _write_json(scan_path, scan_ledger)
    _write_json(event_path, event_ledger)

    report = {
        "schema_version": 1,
        "hypothesis_id": "H024",
        "started_at_utc": started_at,
        "completed_at_utc": utc_now_text(),
        "planned_entry_session": entry_session,
        "planned_entry_open_utc": entry_open.isoformat().replace("+00:00", "Z"),
        "due_event_count": len(due),
        "sealed_event_count": len(sealed_ids),
        "sealed_event_ids": sorted(sealed_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "security_master_source_url": security_url,
        "security_master_sha256": security_hash,
        "final_revision_refresh_performed": True,
        "final_revision_refresh": refresh_metadata,
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "scan_ledger_sha256": scan_ledger["ledger_sha256"],
        "event_ledger_sha256": event_ledger["ledger_sha256"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.report, report)
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
