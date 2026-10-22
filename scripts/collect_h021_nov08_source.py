"""Acquire the original Sunday Nov 8 H021 market-source files after exchange close.

This scheduled collector cannot invent a Sunday trading price or use other
dates, venues, redirects or alternative vendors. If the official NSE file is
not published it retains a verifiable failure receipt, not a fake return.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests

from marketlab.h021_first_entry_intent import git_blob_sha
from marketlab.h021_nov08_source import (
    SOURCE_RELEASE_NOT_BEFORE,
    SUNDAY,
    build_h021_muhurat_source,
    validate_h021_muhurat_source,
)
from marketlab.h021_muhurat_amendment import validate_h021_muhurat_amendment
from marketlab.marketdata import index_snapshot_url, udiff_url

INTENT_PATH = Path(
    "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json"
)
INTENT_BLOB_SHA = "e25f77e1c845456473e624899d4748e306b1225b"
UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
UNIVERSE_BLOB_SHA = "8026e81faee3e913d2fba1dba72d60603b69fa07"
AMENDMENT_PATH = Path(
    "research/prospective/h021/amendments/h021-p023-nov08-calendar-v1.json"
)
AMENDMENT_BLOB_SHA = "f1a64d4664f855fd2bc59bd5d921ff4ca613072f"
ALLOWED_URLS = frozenset({udiff_url(SUNDAY), index_snapshot_url(SUNDAY)})


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pinned_json(path: Path, blob: str) -> dict:
    raw = path.read_bytes()
    if git_blob_sha(raw) != blob:
        raise ValueError(f"Sunday NSE immutable source Git blob drift: {path}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError(f"frozen source must be JSON object: {path}")
    return value


def load_source_ancestry() -> tuple[dict, dict, dict]:
    intent = _pinned_json(INTENT_PATH, INTENT_BLOB_SHA)
    universe = _pinned_json(UNIVERSE_PATH, UNIVERSE_BLOB_SHA)
    amendment = _pinned_json(AMENDMENT_PATH, AMENDMENT_BLOB_SHA)
    validate_h021_muhurat_amendment(amendment)
    return intent, universe, amendment


def fetch_exact_source(
    url: str, *, attempts: int = 2, sleep_seconds: float = 3.0
) -> dict[str, Any]:
    if url not in ALLOWED_URLS:
        raise ValueError("only 8 Nov original NSE EQ UDiFF/index URLs supported")
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("official source attempts must be from 1 to 3")
    if type(sleep_seconds) not in (int, float) or not 0 <= sleep_seconds <= 30:
        raise ValueError("official source retry pause is invalid")
    last_http = None
    last_error = "NO_EXCHANGE_RESPONSE"
    for n in range(attempts):
        try:
            response = requests.get(
                url, timeout=30, allow_redirects=False,
                headers={
                    "User-Agent": "marketlab-h021-muhurat-original/1.0",
                    "Accept": "*/*",
                },
            )
            last_http = response.status_code
            captured = _now()
            if getattr(response, "url", url) != url or 300 <= last_http < 400:
                return {
                    "url": url, "captured_at_utc": captured,
                    "status": "FETCH_FAILED", "http_status": last_http,
                    "raw": None, "error": "UNVERIFIED_REDIRECT_NOT_FOLLOWED",
                }
            if last_http == 200 and response.content:
                return {
                    "url": url, "captured_at_utc": captured,
                    "status": "OK", "http_status": 200,
                    "raw": response.content, "error": None,
                }
            if last_http == 404:
                return {
                    "url": url, "captured_at_utc": captured,
                    "status": "NOT_PUBLISHED", "http_status": 404,
                    "raw": None, "error": "EXACT_NSE_MUHURAT_DAILY_FILE_NOT_PUBLISHED",
                }
            if last_http in (401, 403, 429):
                return {
                    "url": url, "captured_at_utc": captured,
                    "status": "ACCESS_BLOCKED", "http_status": last_http,
                    "raw": None, "error": f"HTTP_{last_http}_NO_BYPASS",
                }
            last_error = f"HTTP_{last_http}_OR_EMPTY"
            if last_http < 500:
                break
        except requests.RequestException as exc:
            last_error = type(exc).__name__
        if n + 1 < attempts:
            time.sleep(sleep_seconds)
    return {
        "url": url, "captured_at_utc": _now(),
        "status": "FETCH_FAILED", "http_status": last_http,
        "raw": None, "error": last_error,
    }


def persist_source_attempt(
    out_dir: Path,
    *,
    intent: dict,
    universe: dict,
    amendment: dict,
    udiff: dict,
    index: dict,
    recorded_at_utc: str,
) -> dict[str, Any]:
    packet = build_h021_muhurat_source(
        intent, universe, amendment,
        udiff_source=udiff, index_source=index,
        recorded_at_utc=recorded_at_utc,
    )
    validate_h021_muhurat_source(packet)
    out_dir.mkdir(parents=True, exist_ok=True)
    originals = []
    for kind, source in (("udiff", udiff), ("index", index)):
        raw = source.get("raw")
        if not isinstance(raw, bytes):
            continue
        digest = hashlib.sha256(raw).hexdigest()
        ext = ".zip" if kind == "udiff" else ".csv"
        path = out_dir / "raw" / "sha256" / f"{digest}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("original Sunday NSE source digest collision")
        path.write_bytes(raw)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Sunday original NSE source retention SHA mismatch")
        originals.append({
            "source": kind,
            "original_sha256": digest,
            "relative_path": str(path.relative_to(out_dir)),
        })
    (out_dir / "special-source-observation-v1.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    receipt = {
        "schema_version": 1,
        "attempt_id": "H021-P024-ORIGINAL-NOV08-SOURCE-ATTEMPT-v1",
        "session_date_ist": SUNDAY.isoformat(),
        "source_observation_packet_sha256": packet["packet_sha256"],
        "captured_result": packet["capture_state"],
        "original_source_receipts": {
            "udiff": packet["original_udiff_source_receipt"],
            "index": packet["original_index_source_receipt"],
        },
        "originals_retained": originals,
        "recorded_at_utc": recorded_at_utc,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "benchmark_excess_returns_opened": False,
        "live_capital_allowed": False,
    }
    (out_dir / "attempt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=3.0)
    args = parser.parse_args()
    if datetime.now(UTC) < SOURCE_RELEASE_NOT_BEFORE:
        raise ValueError("8 Nov special NSE source cannot be requested before 16:15 IST")
    intent, universe, clock = load_source_ancestry()
    stock = fetch_exact_source(
        udiff_url(date.fromisoformat(clock["newly_verified_special_trading_session_date_ist"])),
        attempts=args.attempts, sleep_seconds=args.sleep_seconds,
    )
    benchmark = fetch_exact_source(
        index_snapshot_url(SUNDAY),
        attempts=args.attempts, sleep_seconds=args.sleep_seconds,
    )
    result = persist_source_attempt(
        args.out_dir, intent=intent, universe=universe, amendment=clock,
        udiff=stock, index=benchmark, recorded_at_utc=_now(),
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
