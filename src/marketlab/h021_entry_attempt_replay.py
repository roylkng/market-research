"""Replay every original H021 Oct-12 source attempt, including partial ones.

An official UDiFF with all ten issuer-matched stock opens is evidence even
when Nifty 500 official index CSV was not yet published. Preserve that
state and the original collection time; NEVER label it a complete return,
executable fill or source-replacement with a future session.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from marketlab.h021_entry_observation import (
    ENTRY_DAY,
    INTENT_ID,
    build_entry_observation,
    validate_entry_observation,
)

ATTEMPT_FILENAME = re.compile(r"[1-9]\d*-[1-9]\d*[.]json")
REPLAY_ID = "H021-P016-ORIGINAL-PARTIAL-AND-FULL-ATTEMPT-REPLAY-v1"
SOURCE_KINDS = ("udiff", "index")


def _source_from_receipt(
    receipt: dict[str, Any],
    *,
    kind: str,
    source_root: Path,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise TypeError("original NSE exchange source receipt must be object")
    if kind not in SOURCE_KINDS:
        raise ValueError("unsupported NSE source kind")
    extension = ".zip" if kind == "udiff" else ".csv"
    if receipt.get("raw_filename_extension") != extension:
        raise ValueError("original NSE raw file extension changed")
    state = receipt.get("status")
    raw = None
    if state == "OK":
        sha = receipt.get("raw_sha256")
        count = receipt.get("raw_byte_count")
        if (
            not isinstance(sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", sha) is None
            or type(count) is not int
            or count <= 0
        ):
            raise ValueError("NSE original raw source content hash/count missing")
        path = source_root / "raw" / "sha256" / f"{sha}{extension}"
        raw = path.read_bytes()
        if not raw or len(raw) != count or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("original NSE raw report byte count or SHA-256 mismatch")
    elif state in {"NOT_PUBLISHED", "ACCESS_BLOCKED", "FETCH_FAILED"}:
        if receipt.get("raw_sha256") is not None or receipt.get("raw_byte_count") is not None:
            raise ValueError("missing NSE source cannot falsely claim original raw bytes")
    else:
        raise ValueError("unrecognized official original source state")
    return {
        "status": state,
        "url": receipt.get("official_source_url"),
        "captured_at_utc": receipt.get("captured_at_utc"),
        "http_status": receipt.get("http_status"),
        "raw": raw,
        "error": receipt.get("error"),
    }


def replay_original_entry_attempt(
    *,
    frozen_intent: dict[str, Any],
    frozen_universe: dict[str, Any],
    attempt: dict[str, Any],
    source_root: Path,
) -> dict[str, Any]:
    if not isinstance(attempt, dict):
        raise TypeError("H021 source-attempt receipt must be object")
    if (
        attempt.get("schema_version") != 1
        or attempt.get("intent_id") != INTENT_ID
        or attempt.get("session_date_ist") != ENTRY_DAY
        or attempt.get("portfolio_eligibility_allowed") is not False
        or attempt.get("live_capital_allowed") is not False
    ):
        raise ValueError("original first H021 source-attempt identity or no-capital guard failed")
    sources = attempt.get("source_receipts")
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_KINDS):
        raise ValueError("exact original NSE stock and Nifty 500 receipts required")
    reconstructed_source = {
        kind: _source_from_receipt(sources[kind], kind=kind, source_root=source_root)
        for kind in SOURCE_KINDS
    }
    retained = [
        {
            "kind": kind,
            "path": (
                "raw/sha256/" + sources[kind]["raw_sha256"]
                + (".zip" if kind == "udiff" else ".csv")
            ),
            "sha256": sources[kind]["raw_sha256"],
        }
        for kind in SOURCE_KINDS
        if sources[kind]["status"] == "OK"
    ]
    if attempt.get("raw_sources_retained") != retained:
        raise ValueError("NSE attempt source bytes retained list altered")
    packet = build_entry_observation(
        frozen_intent,
        frozen_universe,
        udiff_source=reconstructed_source["udiff"],
        index_source=reconstructed_source["index"],
        recorded_at_utc=attempt.get("recorded_at_utc"),
    )
    validate_entry_observation(packet)
    if (
        packet["packet_sha256"] != attempt.get("packet_sha256")
        or packet["source_receipts"] != sources
        or packet["observed_official_stock_open_count"]
        != attempt.get("observed_official_stock_open_count")
        or packet["source_observation_status"]
        != attempt.get("source_observation_status")
    ):
        raise ValueError("independent original-source replay differs from Git-sealed attempt")
    return packet


def materialize_original_entry_attempts(
    *,
    frozen_intent: dict[str, Any],
    frozen_universe: dict[str, Any],
    source_root: Path,
    out_root: Path,
    verify_existing: bool = False,
) -> dict[str, Any]:
    raw_attempts = sorted((source_root / "attempts").glob("*.json"))
    existing_count = 0
    new_count = 0
    complete_count = 0
    partial_count = 0
    for path in raw_attempts:
        if ATTEMPT_FILENAME.fullmatch(path.name) is None:
            raise ValueError("unexpected original H021 source-attempt filename")
        attempt = json.loads(path.read_text(encoding="utf-8"))
        reconstructed = replay_original_entry_attempt(
            frozen_intent=frozen_intent,
            frozen_universe=frozen_universe,
            attempt=attempt,
            source_root=source_root,
        )
        if reconstructed["source_observation_status"] == (
            "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED"
        ):
            complete_count += 1
        else:
            partial_count += 1
        serialized = json.dumps(
            reconstructed, indent=2, sort_keys=True, allow_nan=False
        ) + "\n"
        target = out_root / path.name
        if target.exists():
            if target.read_text(encoding="utf-8") != serialized:
                raise ValueError("original source attempt replay was modified")
            existing_count += 1
        elif verify_existing:
            raise FileNotFoundError("missing previously replayed original NSE source attempt")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
            new_count += 1
    return {
        "schema_version": 1,
        "replay_id": REPLAY_ID,
        "frozen_original_entry_intent_id": INTENT_ID,
        "session_date_ist": ENTRY_DAY,
        "attempt_count_verified": len(raw_attempts),
        "new_original_source_attempt_packets": new_count,
        "existing_packets_reverified": existing_count,
        "full_source_attempt_count": complete_count,
        "partial_source_attempt_count": partial_count,
        "future_holding_returns_opened": False,
        "actual_trades_executed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
