from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

ENDPOINT = "https://www.nseindia.com/api/corporate-share-holdings-master"
HOME = "https://www.nseindia.com/"
FILING_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-shareholdingpattern"
DEFAULT_SYMBOLS = (
    "RELIANCE",
    "INFY",
    "LT",
    "ABB",
    "SUNPHARMA",
    "DLF",
    "INDIGO",
    "DMART",
    "MARUTI",
    "TATASTEEL",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json_shape(payload: object) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {
            "type": "object",
            "keys": sorted(str(key) for key in payload),
            "size": len(payload),
        }
    if isinstance(payload, list):
        keys: set[str] = set()
        for item in payload[:20]:
            if isinstance(item, dict):
                keys.update(str(key) for key in item)
        return {
            "type": "array",
            "length": len(payload),
            "sample_object_keys": sorted(keys),
        }
    return {"type": type(payload).__name__}


def _walk_strings(payload: object) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                visit(nested, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                visit(nested, f"{path}[{index}]")
        elif isinstance(value, str):
            found.append((path, value))

    visit(payload, "")
    return found


def _interesting_strings(payload: object) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {
        "xbrl_like": [],
        "date_like": [],
        "quarter_like": [],
    }
    for path, value in _walk_strings(payload):
        lower_path = path.casefold()
        lower_value = value.casefold()
        if (
            "xbrl" in lower_path
            or "xbrl" in lower_value
            or "ixbrl" in lower_value
            or "_shp_" in lower_value
        ):
            result["xbrl_like"].append({"path": path, "value": value})
        if "date" in lower_path or "report" in lower_path:
            result["date_like"].append({"path": path, "value": value})
        if "quarter" in lower_path or "quarter" in lower_value:
            result["quarter_like"].append({"path": path, "value": value})
    for key in result:
        result[key] = result[key][:40]
    return result


def _request_with_retries(
    session: requests.Session,
    *,
    symbol: str,
    timeout: float,
    attempts: int,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                ENDPOINT,
                params={"index": "equities", "symbol": symbol},
                timeout=timeout,
            )
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(min(2**attempt, 8))
            try:
                session.get(HOME, timeout=timeout)
            except requests.RequestException:
                pass
    raise RuntimeError(f"NSE shareholding request failed for {symbol}: {last_error}")


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
    session.get(HOME, timeout=timeout)
    session.get(FILING_PAGE, timeout=timeout)
    return session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Source-only probe of official NSE shareholding-pattern master API"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.35)
    parser.add_argument("--symbols", nargs="*", default=list(DEFAULT_SYMBOLS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout_seconds <= 0 or args.attempts < 1 or args.pause_seconds < 0:
        raise ValueError("invalid probe timing configuration")
    symbols = [str(symbol).strip().upper() for symbol in args.symbols if str(symbol).strip()]
    if not symbols or len(symbols) != len(set(symbols)):
        raise ValueError("symbols must be a non-empty unique list")

    started = _utc_now()
    session = _session(args.timeout_seconds)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for index, symbol in enumerate(symbols, start=1):
        observed_at = _utc_now()
        try:
            response = _request_with_retries(
                session,
                symbol=symbol,
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            )
            body = response.content
            raw_path = args.out_dir / "raw" / f"{symbol}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(body)
            content_type = response.headers.get("Content-Type")
            payload = response.json()
            host = (urlparse(response.url).hostname or "").lower()
            row = {
                "symbol": symbol,
                "observed_at_utc": observed_at,
                "requested_endpoint": ENDPOINT,
                "final_url": response.url,
                "final_host": host,
                "status_code": response.status_code,
                "content_type": content_type,
                "content_length": len(body),
                "sha256": _sha256(body),
                "json_shape": _json_shape(payload),
                "interesting_strings": _interesting_strings(payload),
                "raw_artifact_path": raw_path.as_posix(),
            }
            rows.append(row)
            print(
                f"[{index:02d}/{len(symbols):02d}] {symbol}: HTTP {response.status_code} "
                f"bytes={len(body)} shape={row['json_shape']}",
                flush=True,
            )
        except (RuntimeError, requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            failure = {
                "symbol": symbol,
                "observed_at_utc": observed_at,
                "error": f"{type(exc).__name__}: {exc}",
            }
            failures.append(failure)
            print(
                f"[{index:02d}/{len(symbols):02d}] {symbol}: FAILED {failure['error']}",
                flush=True,
            )
        if index < len(symbols) and args.pause_seconds:
            time.sleep(args.pause_seconds)

    completed = _utc_now()
    report = {
        "schema_version": 1,
        "hypothesis_probe": "H023-OWNERSHIP-SOURCE-PROBE",
        "purpose": (
            "Source-only feasibility probe of official NSE shareholding-pattern enumeration. "
            "No price, return, benchmark, or outcome input is consumed."
        ),
        "endpoint": ENDPOINT,
        "endpoint_parameters": {"index": "equities", "symbol": "<NSE_SYMBOL>"},
        "started_at_utc": started,
        "completed_at_utc": completed,
        "symbols": symbols,
        "success_count": len(rows),
        "failure_count": len(failures),
        "rows": rows,
        "failures": failures,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out_dir / "report.json", report)
    print(
        f"H023 shareholding source probe complete: {len(rows)}/{len(symbols)} successful",
        flush=True,
    )
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
