"""Acquire only 19 missing original pre-9-Oct NSE UDiFF files (P036).

The 9-Oct original is separately source-pinned by HG007-P035.
All requests use exact official archive dates, no redirects or blocks bypass.
Incomplete source batches publish NO twenty-session median or capital signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests

from marketlab.hg007_liquidity_history import (
    HISTORY_ID,
    LAST_SESSION,
    ROOT,
    _five_bars,
    _original_path,
    _receipt_path,
    _utc,
    build_twenty_session_liquidity,
    pinned_window_and_context,
    validate_twenty_session_liquidity,
    validated_historical_source,
)
from marketlab.marketdata import udiff_url

MAX_ZIP_BYTES = 5_000_000
MAX_DOWNLOAD_ATTEMPTS = 3
MAX_RETRY_SLEEP = 15.0


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _download_source(
    day: str,
    *,
    attempts: int = 2,
    sleep_seconds: float = 2.0,
) -> tuple[dict[str, Any], bytes | None]:
    if type(attempts) is not int or not 1 <= attempts <= MAX_DOWNLOAD_ATTEMPTS:
        raise ValueError("bounded official NSE acquisition attempts invalid")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= MAX_RETRY_SLEEP:
        raise ValueError("official NSE retry delay invalid")
    if day > LAST_SESSION or day < "2026-09-01":
        raise ValueError("official source outside frozen September/October liquidity window")
    uri = udiff_url(date.fromisoformat(day))
    status = None
    last_error = "NO_HTTP_RESPONSE"
    for attempt in range(attempts):
        try:
            response = requests.get(
                uri, timeout=30, allow_redirects=False,
                headers={
                    "User-Agent": "marketlab-nse-liquidity-provenance/1.0",
                    "Accept": "application/zip",
                },
            )
            status = response.status_code
            if getattr(response, "url", uri) != uri:
                return {
                    "date": day, "url": uri, "state": "UNFOLLOWED_SOURCE_REDIRECT",
                    "http_status": status, "reason": "HTTP_DESTINATION_CHANGED",
                    "captured_at_utc": _now(),
                }, None
            if status == 200:
                original = response.content
                if (
                    not isinstance(original, bytes) or not 300 <= len(original) <= MAX_ZIP_BYTES
                    or not original.startswith(b"PK")
                ):
                    return {
                        "date": day, "url": uri, "state": "INVALID_ZIP_OR_SIZE",
                        "http_status": status, "reason": "ZIP_SIGNATURE_OR_BYTES_INVALID",
                        "captured_at_utc": _now(),
                    }, None
                return {
                    "date": day, "url": uri, "state": "ORIGINAL_NSE_EQ_ZIP_RETAINED",
                    "http_status": status, "reason": None, "captured_at_utc": _now(),
                    "source_sha256": hashlib.sha256(original).hexdigest(),
                    "raw_bytes": len(original),
                }, original
            if status in (401, 403, 429):
                return {
                    "date": day, "url": uri, "state": "ACCESS_BLOCKED_NO_BYPASS",
                    "http_status": status, "reason": f"HTTP_{status}",
                    "captured_at_utc": _now(),
                }, None
            if status == 404:
                return {
                    "date": day, "url": uri, "state": "OFFICIAL_ZIP_NOT_PUBLISHED",
                    "http_status": 404, "reason": "HTTP_404",
                    "captured_at_utc": _now(),
                }, None
            if 300 <= status < 400:
                return {
                    "date": day, "url": uri, "state": "UNFOLLOWED_SOURCE_REDIRECT",
                    "http_status": status, "reason": "UNAPPROVED_ARCHIVE_REDIRECT",
                    "captured_at_utc": _now(),
                }, None
            last_error = f"HTTP_{status}"
            if status < 500:
                break
        except requests.RequestException as exc:
            last_error = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    return {
        "date": day, "url": uri, "state": "OFFICIAL_SOURCE_FETCH_FAILED",
        "http_status": status, "reason": last_error,
        "captured_at_utc": _now(),
    }, None


def _retain(
    root: Path, day: str, close: str, raw: bytes, receipt: dict[str, Any],
    ids: dict[str, str],
) -> None:
    if day == LAST_SESSION:
        raise ValueError("9 October must use already sealed original P035 ZIP")
    if receipt.get("state") != "ORIGINAL_NSE_EQ_ZIP_RETAINED":
        raise ValueError("cannot retain a blocked/failure source as official original")
    sha = receipt.get("source_sha256")
    if (
        not isinstance(sha, str)
        or hashlib.sha256(raw).hexdigest() != sha
        or receipt.get("raw_bytes") != len(raw)
        or receipt.get("url") != udiff_url(date.fromisoformat(day))
        or _utc(receipt.get("captured_at_utc")) < _utc(close)
    ):
        raise ValueError("NSE date/SHA/captured-time source receipt mismatch")
    _five_bars(raw, day, ids)
    raw_path = _original_path(root, sha)
    receipt_path = _receipt_path(root, day)
    source_receipt = {
        "schema_version": 1,
        "session_date": day,
        "original_source_url": receipt["url"],
        "state": "ORIGINAL_NSE_EQ_ZIP_RETAINED",
        "http_status": 200,
        "captured_at_utc": receipt["captured_at_utc"],
        "source_sha256": sha,
        "raw_bytes": len(raw),
        "historical_later_acquisition_not_early_alpha": True,
    }
    if receipt_path.exists() and json.loads(
        receipt_path.read_text(encoding="utf-8")
    ) != source_receipt:
        raise ValueError("existing original NSE source receipt differs, no overwrite")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists() and raw_path.read_bytes() != raw:
        raise ValueError("content-addressed original NSE archive collision")
    raw_path.write_bytes(raw)
    if hashlib.sha256(raw_path.read_bytes()).hexdigest() != sha:
        raise ValueError("original NSE source raw bytes modified by storage")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x", encoding="utf-8") as out:
        json.dump(source_receipt, out, sort_keys=True, indent=2, allow_nan=False)
        out.write("\n")


def acquire_history(
    root: Path, *,
    attempt_key: str,
    attempts_per_date: int = 2,
    sleep_seconds: float = 2.0,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,100}", attempt_key):
        raise ValueError("unique append-only source attempt key invalid")
    sessions, ids, _prior, _oct9, sources = pinned_window_and_context(root)
    if datetime.now(UTC) < _utc(sessions[-1]["close_utc"]):
        raise ValueError("historical source experiment cannot precede 9 Oct close")
    events = []
    for source_session in sessions:
        day, close = source_session["date"], source_session["close_utc"]
        if day == LAST_SESSION:
            events.append({
                "date": day, "state": "ALREADY_PINNED_OFFICIAL_P035_OCT09",
                "source_sha256": sources["oct9_original_udiff_sha256"],
            })
            continue
        existing, receipt = validated_historical_source(root, day, close)
        if existing is not None:
            events.append({
                "date": day, "state": "ALREADY_RETAINED_ORIGINAL_NSE_SOURCE",
                "source_sha256": receipt["source_sha256"],
            })
            continue
        acquired, original = _download_source(
            day, attempts=attempts_per_date, sleep_seconds=sleep_seconds
        )
        if original is not None:
            try:
                _retain(root, day, close, original, acquired, ids)
            except (OSError, ValueError) as exc:
                acquired = {
                    "date": day, "state": "FAILED_ORIGINAL_SOURCE_IDENTITY_AUDIT",
                    "reason": str(exc), "http_status": 200,
                    "captured_at_utc": acquired["captured_at_utc"],
                }
            else:
                acquired["retained_in_repository_staging"] = True
        events.append(acquired)
    report = build_twenty_session_liquidity(root)
    validate_twenty_session_liquidity(report)
    dest = root / ROOT
    dest.mkdir(parents=True, exist_ok=True)
    state = {
        "schema_version": 1,
        "attempt_id": attempt_key,
        "study_id": HISTORY_ID,
        "captured_at_utc": _now(),
        "events": events,
        "completed_official_sessions": report["observed_complete_session_count"],
        "required_completed_sessions": 20,
        "study_source_state": report["source_status"],
        "missing_or_inconsistent_sessions": report["missing_or_inconsistent_sessions"],
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    attempt_path = dest / "attempts" / f"{attempt_key}.json"
    attempt_path.parent.mkdir(parents=True, exist_ok=True)
    with attempt_path.open("x", encoding="utf-8") as out:
        json.dump(state, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")

    if report["source_status"] == "COMPLETE_ORIGINAL_20_SESSION_EQUITY_EVIDENCE":
        target = dest / "twenty-session-liquidity-v1.json"
        encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if target.exists():
            if target.read_text(encoding="utf-8") != encoded:
                raise ValueError("frozen complete twenty-session liquidity source changed")
        else:
            with target.open("x", encoding="utf-8") as out:
                out.write(encoded)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--attempt-key", required=True)
    parser.add_argument("--attempts-per-date", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    args = parser.parse_args()
    state = acquire_history(
        args.repo_root,
        attempt_key=args.attempt_key,
        attempts_per_date=args.attempts_per_date,
        sleep_seconds=args.sleep_seconds,
    )
    print(json.dumps({
        "study_id": state["study_id"],
        "attempt_id": state["attempt_id"],
        "complete_sessions": state["completed_official_sessions"],
        "required_sessions": state["required_completed_sessions"],
        "state": state["study_source_state"],
        "missing_original_sessions": [
            x["date"] for x in state["missing_or_inconsistent_sessions"]
        ],
        "capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
