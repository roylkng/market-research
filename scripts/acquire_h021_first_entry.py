"""Acquire original official NSE entry-session files after the session is complete.

This one-time H021 first-cohort collector has no access to future returns,
does not change frozen selection and never reports a trade fill.
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

from marketlab.h021_entry_observation import (
    ENTRY_CLOSE_UTC,
    ENTRY_DAY,
    build_entry_observation,
    validate_entry_observation,
)
from marketlab.h021_first_entry_intent import (
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)
from marketlab.marketdata import index_snapshot_url, udiff_url

INTENT_PATH = Path("research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json")
UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
INTENT_GIT_BLOB_SHA = "e25f77e1c845456473e624899d4748e306b1225b"
UNIVERSE_GIT_BLOB_SHA = "8026e81faee3e913d2fba1dba72d60603b69fa07"
USER_AGENT = "marketlab-h021-source-observation/1.0"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_and_verify_sources() -> tuple[dict[str, Any], dict[str, Any]]:
    """Recheck original pre-entry decisions before reading a market price."""
    comparison, calendar = load_pinned_inputs()
    expected_intent = build_first_entry_intent(comparison, calendar)
    intent_raw = INTENT_PATH.read_bytes()
    if git_blob_sha(intent_raw) != INTENT_GIT_BLOB_SHA:
        raise ValueError("original first entry intent Git blob changed")
    intent = json.loads(intent_raw)
    if intent != expected_intent:
        raise ValueError("stored H021 entry intent not reproducible from sealed sources")
    universe_raw = UNIVERSE_PATH.read_bytes()
    if git_blob_sha(universe_raw) != UNIVERSE_GIT_BLOB_SHA:
        raise ValueError("original U001 universe Git blob changed")
    universe = json.loads(universe_raw)
    if not isinstance(universe, dict):
        raise TypeError("U001 universe must be an object")
    return intent, universe


def download_official_source(
    url: str, *, attempts: int = 3, sleep_seconds: float = 5
) -> dict[str, Any]:
    """Never retry an access restriction or follow redirect to evade a block."""
    if url not in (
        udiff_url(date.fromisoformat(ENTRY_DAY)),
        index_snapshot_url(date.fromisoformat(ENTRY_DAY)),
    ):
        raise ValueError("only predeclared official entry-date URLs are allowed")
    if attempts < 1 or sleep_seconds < 0:
        raise ValueError("invalid bounded acquisition retry configuration")
    last_status: int | None = None
    last_error = "UNSPECIFIED_FETCH_FAILURE"
    for index in range(attempts):
        try:
            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                allow_redirects=False,
            )
            last_status = response.status_code
            now = _timestamp()
            if response.status_code == 200 and response.content:
                return {
                    "status": "OK", "url": url, "captured_at_utc": now,
                    "http_status": 200, "raw": response.content, "error": None,
                }
            if response.status_code in (401, 403, 429):
                return {
                    "status": "ACCESS_BLOCKED", "url": url,
                    "captured_at_utc": now, "http_status": response.status_code,
                    "raw": None, "error": f"HTTP_{response.status_code}_NO_BYPASS",
                }
            if response.status_code == 404:
                return {
                    "status": "NOT_PUBLISHED", "url": url,
                    "captured_at_utc": now, "http_status": 404,
                    "raw": None, "error": "OFFICIAL_FILE_NOT_PUBLISHED",
                }
            last_error = f"HTTP_{response.status_code}_OR_EMPTY_BODY"
            # A 3xx redirect is not followed to another unverified host.
            if response.status_code < 500:
                break
        except requests.RequestException as exc:
            last_error = f"REQUEST_{type(exc).__name__}"
        if index + 1 < attempts:
            time.sleep(sleep_seconds)

    return {
        "status": "FETCH_FAILED", "url": url, "captured_at_utc": _timestamp(),
        "http_status": last_status, "raw": None, "error": last_error,
    }


def write_acquisition(
    out_dir: Path,
    *,
    intent: dict[str, Any],
    universe: dict[str, Any],
    udiff: dict[str, Any],
    index: dict[str, Any],
    recorded_at_utc: str,
) -> dict[str, Any]:
    """Retain exact hashes/bytes, and never promote a partial source."""
    packet = build_entry_observation(
        intent, universe,
        udiff_source=udiff,
        index_source=index,
        recorded_at_utc=recorded_at_utc,
    )
    validate_entry_observation(packet)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for name, source in (("udiff", udiff), ("index", index)):
        if source["status"] != "OK":
            continue
        raw = source["raw"]
        sha = hashlib.sha256(raw).hexdigest()
        ext = ".zip" if name == "udiff" else ".csv"
        destination = out_dir / "raw" / "sha256" / f"{sha}{ext}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError("content addressed official source hash collision")
        destination.write_bytes(raw)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != sha:
            raise ValueError("retained official source failed SHA verification")
        saved.append({"kind": name, "path": str(destination.relative_to(out_dir)), "sha256": sha})
    (out_dir / "entry-observation-v1.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    attempt = {
        "schema_version": 1,
        "intent_id": intent["intent_id"],
        "session_date_ist": ENTRY_DAY,
        "recorded_at_utc": recorded_at_utc,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "source_observation_status": packet["source_observation_status"],
        "observed_official_stock_open_count": packet["observed_official_stock_open_count"],
        "source_receipts": packet["source_receipts"],
        "packet_sha256": packet["packet_sha256"],
        "raw_sources_retained": saved,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    (out_dir / "attempt.json").write_text(
        json.dumps(attempt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return attempt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--sleep-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if args.attempts < 1 or args.sleep_seconds < 0:
        parser.error("bounded attempts >=1 and sleep >=0 required")
    close = datetime.fromisoformat(ENTRY_CLOSE_UTC.replace("Z", "+00:00"))
    if datetime.now(UTC) < close:
        raise RuntimeError("cannot acquire entry-session source before completed NSE session")

    intent, universe = load_and_verify_sources()
    session = date.fromisoformat(ENTRY_DAY)
    # The two independent official reports are fetched even if one fails.
    udiff = download_official_source(
        udiff_url(session), attempts=args.attempts, sleep_seconds=args.sleep_seconds
    )
    index = download_official_source(
        index_snapshot_url(session), attempts=args.attempts,
        sleep_seconds=args.sleep_seconds,
    )
    attempt = write_acquisition(
        args.out_dir,
        intent=intent,
        universe=universe,
        udiff=udiff,
        index=index,
        recorded_at_utc=_timestamp(),
    )
    print(json.dumps(attempt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
