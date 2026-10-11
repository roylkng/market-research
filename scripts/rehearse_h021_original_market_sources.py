"""Rehearse actual 9 October NSE market-data source parsers before H021 entry.

The frozen 9 October UDiFF stock ZIP was previously acquired for HG007
with original NSE source SHA. Only index availability may require one
fresh GET. No securities or index prices are printed or used for ranking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

import requests

from marketlab.h021_real_source_rehearsal import (
    FIRST_OPEN_UTC,
    ORIGINAL_TRADING_DAY,
    SOURCE_ZIP_PATH,
    SOURCE_ZIP_SHA256,
    SOURCE_ZIP_SIZE,
    rehearse_original_official_files,
    validate_pre_entry_rehearsal,
)
from marketlab.marketdata import index_snapshot_url
from scripts.acquire_h021_first_entry import load_and_verify_sources


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def acquire_prior_index() -> dict:
    """Exact predeclared source only. No redirect/cookies/blocked source bypass."""
    url = index_snapshot_url(ORIGINAL_TRADING_DAY)
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "marketlab-h021-historical-source-preflight/1.0",
                "Accept": "text/csv",
            },
            allow_redirects=False,
            timeout=25,
        )
    except requests.RequestException as exc:
        return {
            "url": url,
            "captured_at_utc": _now(),
            "status": "FETCH_FAILED",
            "http_status": None,
            "raw": None,
            "error": "REQUEST_" + type(exc).__name__,
        }
    code = response.status_code
    if code == 200 and response.content:
        return {
            "url": url, "captured_at_utc": _now(), "status": "OK",
            "http_status": 200, "raw": response.content, "error": None,
        }
    if code in (401, 403, 429):
        state, reason = "ACCESS_BLOCKED", f"HTTP_{code}_NO_BYPASS"
    elif code == 404:
        state, reason = "NOT_PUBLISHED", "OFFICIAL_INDEX_FILE_NOT_PUBLISHED"
    else:
        state, reason = "FETCH_FAILED", f"HTTP_{code}_OR_EMPTY_UNFOLLOWED_REDIRECT"
    return {
        "url": url, "captured_at_utc": _now(),
        "status": state, "http_status": code,
        "raw": None, "error": reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repo-root", default=Path("."), type=Path)
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--index-csv", type=Path)
    args = parser.parse_args()
    if args.no_network and args.index_csv is not None:
        parser.error("provide either --no-network or --index-csv")
    if datetime.now(UTC) >= FIRST_OPEN_UTC:
        raise RuntimeError("cannot claim pre-entry source preflight after frozen 12 Oct open")

    intent, universe = load_and_verify_sources()
    original = (args.repo_root / SOURCE_ZIP_PATH).read_bytes()
    if (
        len(original) != SOURCE_ZIP_SIZE
        or hashlib.sha256(original).hexdigest() != SOURCE_ZIP_SHA256
    ):
        raise ValueError("original archival NSE stock ZIP differs from pinned Oct9 data")
    if args.index_csv is not None:
        source = {
            "url": index_snapshot_url(date(2026, 10, 9)),
            "captured_at_utc": _now(),
            "status": "OK",
            "http_status": 200,
            "raw": args.index_csv.read_bytes(),
            "error": None,
        }
    elif args.no_network:
        source = {
            "url": index_snapshot_url(date(2026, 10, 9)),
            "captured_at_utc": _now(),
            "status": "FETCH_FAILED",
            "http_status": None,
            "raw": None,
            "error": "LIVE_INDEX_ACQUISITION_NOT_ATTEMPTED",
        }
    else:
        source = acquire_prior_index()

    packet = rehearse_original_official_files(
        intent, universe,
        original_oct9_zip=original,
        index_source=source,
        rehearsal_at_utc=_now(),
    )
    validate_pre_entry_rehearsal(packet)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "preentry-rehearsal-v1.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    source_raw = source.get("raw")
    if isinstance(source_raw, bytes):
        raw_hash = hashlib.sha256(source_raw).hexdigest()
        index_path = args.out_dir / "raw" / "sha256" / f"{raw_hash}.csv"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_bytes(source_raw)
        if hashlib.sha256(index_path.read_bytes()).hexdigest() != raw_hash:
            raise ValueError("original Nifty500 index source failed retention SHA")
    attempt = {
        "schema_version": 1,
        "rehearsal_id": packet["rehearsal_id"],
        "rehearsal_state": packet["rehearsal_state"],
        "real_stock_row_valid_count": packet["real_stock_row_valid_count"],
        "index_schema_ready": packet["index_source_receipt"]["parser_identity_ready"],
        "index_source_status": packet["index_source_receipt"]["status"],
        "recorded_at_utc": packet["recorded_at_utc"],
        "packet_sha256": packet["packet_sha256"],
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "future_entry_prices_observed": False,
        "live_capital_allowed": False,
    }
    (args.out_dir / "attempt.json").write_text(
        json.dumps(attempt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(attempt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
