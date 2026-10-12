"""Collect post-close original NSE Nifty500 index CSV for H021 Oct12 only.

First attempt's official NSE stock prices and HTTP404 remain immutable.
Both candidate index URLs belong to NSE; third-party values are disallowed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from marketlab.h021_index_recovery import (
    ENTRY_CLOSE_UTC,
    SEALABLE_STATES,
    SOURCE_URLS,
    build_recovery,
    read_originals,
    validate_recovery,
)

RETRY_LIMIT = 3


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def retrieve_index_source(
    source_name: str, *, attempts: int = 2, sleep_seconds: float = 4
) -> dict[str, Any]:
    """No redirect, credential substitution, access denial bypass or new URL."""
    if source_name not in SOURCE_URLS:
        raise ValueError("only two frozen official NSE index sources are allowed")
    if type(attempts) is not int or not 1 <= attempts <= RETRY_LIMIT:
        raise ValueError("official NSE acquisition attempts must be bounded")
    if type(sleep_seconds) not in (float, int) or not 0 <= sleep_seconds <= 30:
        raise ValueError("official source retry delay must be bounded")
    url = SOURCE_URLS[source_name]
    previous_http: int | None = None
    previous_error = "NO_HTTP_RESPONSE"
    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                timeout=25,
                headers={
                    "User-Agent": "marketlab-h021-index-recovery/1.0",
                    "Accept": "text/csv,*/*",
                },
                allow_redirects=False,
            )
            previous_http = response.status_code
            now = _now()
            if getattr(response, "url", url) != url:
                return {
                    "url": url, "status": "FETCH_FAILED",
                    "captured_at_utc": now, "http_status": previous_http,
                    "raw": None, "error": "UNVERIFIED_URL_CHANGED_NO_BYPASS"
                }
            if response.status_code == 200 and response.content:
                return {
                    "url": url, "status": "OK",
                    "captured_at_utc": now, "http_status": 200,
                    "raw": response.content, "error": None,
                }
            if response.status_code == 404:
                return {
                    "url": url, "status": "NOT_PUBLISHED",
                    "captured_at_utc": now, "http_status": 404,
                    "raw": None, "error": "OFFICIAL_OCT12_INDEX_NOT_PUBLISHED",
                }
            if response.status_code in (401, 403, 429):
                return {
                    "url": url, "status": "ACCESS_BLOCKED",
                    "captured_at_utc": now, "http_status": response.status_code,
                    "raw": None, "error": f"HTTP_{response.status_code}_NO_BYPASS",
                }
            if 300 <= response.status_code < 400:
                return {
                    "url": url, "status": "FETCH_FAILED",
                    "captured_at_utc": now, "http_status": response.status_code,
                    "raw": None, "error": "UNFOLLOWED_NSE_REDIRECT",
                }
            previous_error = f"HTTP_{response.status_code}_OR_EMPTY"
            if response.status_code < 500:
                break
        except requests.RequestException as exc:
            previous_error = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    return {
        "url": url, "status": "FETCH_FAILED",
        "captured_at_utc": _now(), "http_status": previous_http,
        "raw": None, "error": previous_error,
    }


def write_attempt(
    directory: Path, *,
    original: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    recorded_at_utc: str,
) -> dict[str, Any]:
    packet = build_recovery(
        original, source_candidates=sources, recorded_at_utc=recorded_at_utc
    )
    validate_recovery(packet)
    directory.mkdir(parents=True, exist_ok=True)
    preserved = []
    for name, source in sources.items():
        if source.get("status") != "OK":
            continue
        raw = source.get("raw")
        if not isinstance(raw, bytes) or not raw:
            raise ValueError("original NSE source missing after HTTP200")
        digest = hashlib.sha256(raw).hexdigest()
        destination = directory / "raw" / "sha256" / f"{digest}.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError("same original index SHA filename contains different data")
        destination.write_bytes(raw)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError("NSE source was not retained intact")
        preserved.append({
            "endpoint": name, "path": str(destination.relative_to(directory)),
            "sha256": digest, "byte_count": len(raw)
        })
    (directory / "index-source-evidence-v1.json").write_text(
        json.dumps(packet, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    receipt = {
        "schema_version": 1,
        "recovery_id": packet["recovery_id"],
        "source_state": packet["source_state"],
        "packet_sha256": packet["packet_sha256"],
        "observed_index_primary_or_dual_verified": (
            packet["verified_primary_or_agreed_dual_index_source"]
        ),
        "source_receipts": packet["source_receipts"],
        "original_raw_csv_files_retained": preserved,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    (directory / "attempt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=4)
    args = parser.parse_args()
    if datetime.now(UTC) < datetime.fromisoformat(ENTRY_CLOSE_UTC):
        raise ValueError("original Oct12 exchange session not yet completed")
    original = read_originals(args.repo_root)
    sources = {
        name: retrieve_index_source(
            name, attempts=args.attempts, sleep_seconds=args.sleep_seconds
        )
        for name in SOURCE_URLS
    }
    receipt = write_attempt(
        args.out_dir, original=original, sources=sources,
        recorded_at_utc=_now(),
    )
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))
    if receipt["source_state"] in SEALABLE_STATES:
        print("Official 12 Oct Nifty500 *source* observed; return and total-return gates remain closed.")


if __name__ == "__main__":
    main()
