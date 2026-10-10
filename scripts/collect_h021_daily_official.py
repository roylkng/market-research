"""Collect one verified *completed* NSE H021 source session after the entry.

No historical outcome inspection, trade, benchmark excess or EPS refitting.
Original official source bytes and immutable SHA-256 receipts are retained.
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

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_daily_prices import (
    build_daily_source_observation,
    validate_daily_source_observation,
)
from marketlab.h021_first_entry_intent import (
    CALENDAR_PATH,
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)
from marketlab.marketdata import index_snapshot_url, udiff_url

INTENT_PATH = Path("research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json")
UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
INTENT_BLOB_SHA = "e25f77e1c845456473e624899d4748e306b1225b"
UNIVERSE_BLOB_SHA = "8026e81faee3e913d2fba1dba72d60603b69fa07"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_frozen_sources() -> tuple[dict, dict, Any]:
    comparison, calendar = load_pinned_inputs()
    original_intent = INTENT_PATH.read_bytes()
    if git_blob_sha(original_intent) != INTENT_BLOB_SHA:
        raise ValueError("original first H021 intent Git blob modified")
    intent = json.loads(original_intent)
    if intent != build_first_entry_intent(comparison, calendar):
        raise ValueError("first H021 intent fails independent reproduction")
    raw_universe = UNIVERSE_PATH.read_bytes()
    if git_blob_sha(raw_universe) != UNIVERSE_BLOB_SHA:
        raise ValueError("original U001 Git blob modified")
    universe = json.loads(raw_universe)
    snapshot = load_calendar_snapshot(CALENDAR_PATH)
    return intent, universe, snapshot


def download_source(
    *, session_date: date, source_type: str, attempts: int, sleep_seconds: float
) -> dict[str, Any]:
    if source_type not in {"udiff","index"}:
        raise ValueError("source type must be exact official NSE stock or index")
    if attempts < 1 or sleep_seconds < 0:
        raise ValueError("download retries must be bounded and nonnegative")
    url = udiff_url(session_date) if source_type == "udiff" else index_snapshot_url(session_date)
    last_error = "NO_HTTP_RESPONSE"
    last_http: int | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(
                url, timeout=30, allow_redirects=False,
                headers={"User-Agent":"marketlab-h021-daily-official/1.0","Accept":"*/*"},
            )
            last_http = response.status_code
            captured = _now()
            if response.status_code == 200 and response.content:
                return dict(url=url,status="OK",captured_at_utc=captured,
                            http_status=200,raw=response.content,error=None)
            if response.status_code == 404:
                return dict(url=url,status="NOT_PUBLISHED",captured_at_utc=captured,
                            http_status=404,raw=None,error="OFFICIAL_REPORT_NOT_PUBLISHED")
            if response.status_code in (401,403,429):
                return dict(url=url,status="ACCESS_BLOCKED",captured_at_utc=captured,
                            http_status=response.status_code,raw=None,
                            error=f"HTTP_{response.status_code}_NO_BYPASS")
            last_error = f"HTTP_{response.status_code}_OR_EMPTY_BODY"
            if response.status_code < 500:
                break
        except requests.RequestException as exc:
            last_error = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(sleep_seconds)
    return dict(url=url,status="FETCH_FAILED",captured_at_utc=_now(),
                http_status=last_http,raw=None,error=last_error)


def save_attempt(
    *,
    output_dir: Path,
    session_date: str,
    intent: dict,
    universe: dict,
    calendar: Any,
    udiff: dict,
    index: dict,
    recorded_at_utc: str,
) -> dict:
    result = build_daily_source_observation(
        intent, universe, calendar,
        session_date=session_date, udiff_source=udiff, index_source=index,
        recorded_at_utc=recorded_at_utc,
    )
    validate_daily_source_observation(result)
    output_dir.mkdir(parents=True, exist_ok=True)
    retained = []
    for key,source in (("udiff",udiff),("index",index)):
        raw = source.get("raw")
        if not isinstance(raw,bytes):
            continue
        digest = hashlib.sha256(raw).hexdigest()
        ext = ".zip" if key == "udiff" else ".csv"
        path = output_dir / "raw" / "sha256" / f"{digest}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("content-addressed NSE raw source collision")
        path.write_bytes(raw)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("failed source-byte retention verification")
        retained.append({"source":key,"path":str(path.relative_to(output_dir)),"sha256":digest})

    (output_dir/"observation.json").write_text(
        json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8",
    )
    receipt = {
        "schema_version":1,
        "id":"H021-P008-OFFICIAL-SOURCE-ATTEMPT-v1",
        "session_date":session_date,
        "recorded_at_utc":recorded_at_utc,
        "packet_sha256":result["packet_sha256"],
        "capture_state":result["capture_state"],
        "originals_retained":retained,
        "workflow_run_id":os.environ.get("GITHUB_RUN_ID"),
        "workflow_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
        "source_index":result["index_source"],
        "source_stock":result["stock_source"],
        "horizon_returns_opened":False,
        "live_capital_allowed":False,
    }
    (output_dir/"attempt.json").write_text(
        json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-date",required=True)
    parser.add_argument("--out-dir",required=True,type=Path)
    parser.add_argument("--attempts",type=int,default=3)
    parser.add_argument("--sleep-seconds",type=float,default=5.0)
    args=parser.parse_args()
    intent,universe,calendar=load_frozen_sources()
    day=date.fromisoformat(args.session_date)
    matches=[s for s in calendar.sessions if s.session_date==args.session_date]
    if len(matches)!=1:
        raise ValueError("NSE session not present in sealed source calendar")
    official_close=datetime.fromisoformat(matches[0].close_timestamp_utc)
    if datetime.now(UTC) < official_close:
        raise ValueError("daily NSE source acquisition cannot occur before completed close")
    udiff=download_source(
        session_date=day,source_type="udiff",
        attempts=args.attempts,sleep_seconds=args.sleep_seconds,
    )
    index=download_source(
        session_date=day,source_type="index",
        attempts=args.attempts,sleep_seconds=args.sleep_seconds,
    )
    attempt=save_attempt(
        output_dir=args.out_dir,
        session_date=args.session_date,
        intent=intent,universe=universe,calendar=calendar,
        udiff=udiff,index=index,recorded_at_utc=_now(),
    )
    print(json.dumps(attempt,sort_keys=True,allow_nan=False))


if __name__=="__main__":
    main()
