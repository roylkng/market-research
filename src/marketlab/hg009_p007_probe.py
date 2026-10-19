"""HG009 P007 P2: immutable original NSE corporate-action source attempts.

NSE's public corporate-action JSON is an incomplete discovery screen.
Original bytes and *actual observed* capture times are retained, but even a
valid empty HTTP 200 response never establishes source-complete return basis.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p007_actions import (
    build_action_hazard_audit,
    load_original_hg009_sources,
    validate_action_hazard_audit,
)

PROTOCOL = "HG009-P007-P2-ORIGINAL-NSE-ACTION-SOURCE-PROBES-v1"
FIRST = "2026-10-15"
H5_EXIT = "2026-10-22"
LAST_CAPTURE = "2026-10-26"
MAX_SOURCE_BYTES = 8_000_000
ACTION_URL = "https://www.nseindia.com/api/corporates-corporateActions"
BASE = Path("research/hg009/p007-originals")
ATTEMPTS = BASE / "attempts"
RAW = BASE / "raw" / "sha256"


def _time(value: str) -> datetime:
    if not isinstance(value, str):
        raise AlphaContractError("P007 P2 missing source observation timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError("P007 P2 invalid source observation timestamp") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("P007 P2 capture clock needs offset")
    return parsed.astimezone(UTC)


def _attempt_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value):
        raise AlphaContractError("P007 P2 attempt ID must be safe and stable")
    return value


def _source_path(raw: bytes) -> Path:
    return RAW / f"{hashlib.sha256(raw).hexdigest()}.json"


def build_p007_probe(
    *,
    repo_root: Path,
    attempt_id: str,
    observed_at_utc: str,
    prepared_at_utc: str,
    fetcher: Callable[[], tuple[Any, bytes]],
) -> tuple[dict[str, Any], bytes | None]:
    """Fetch once; stamp AFTER network acquisition, retain failed attempts."""
    attempt_id = _attempt_id(attempt_id)
    observed = _time(observed_at_utc)
    prepared = _time(prepared_at_utc)
    today = observed.date().isoformat()
    if not (FIRST <= today <= LAST_CAPTURE) or prepared < observed:
        raise AlphaContractError("P007 P2 probe outside frozen capture window/clock")
    status, data, error = "FETCH_FAILED", None, None
    try:
        _unused_payload, candidate = fetcher()
        if not isinstance(candidate, bytes) or not candidate:
            error = "EMPTY_OR_NONBYTES_ORIGINAL_NSE_RESPONSE"
        elif len(candidate) > MAX_SOURCE_BYTES:
            error = "SOURCE_EXCEEDS_FROZEN_BYTES_LIMIT"
        else:
            data = candidate
            status = "OK"
    except Exception as exc:
        error = type(exc).__name__
    sha = hashlib.sha256(data).hexdigest() if data is not None else None
    receipt = {
        "url": ACTION_URL,
        "captured_at_utc": observed.isoformat(),
        "status": status,
        "http_status": 200 if status == "OK" else None,
        "raw_sha256": sha,
    }
    if status != "OK":
        receipt["error"] = error or "SOURCE_FETCH_FAILED"
    original, selected, controls = load_original_hg009_sources(repo_root)
    screened = build_action_hazard_audit(
        original=original,
        selected=selected,
        controls=controls,
        start_session=FIRST,
        end_session=H5_EXIT,
        original_action_raw=data,
        action_receipt=receipt,
        prepared_at_utc=prepared.isoformat(),
    )
    validate_action_hazard_audit(screened)
    envelope: dict[str, Any] = {
        "schema_version": 1,
        "probe_id": PROTOCOL,
        "attempt_id": attempt_id,
        "capture_observed_at_utc": observed.isoformat(),
        "prepared_at_utc": prepared.isoformat(),
        "source_receipt": receipt,
        "source_raw_repo_path": str(_source_path(data)) if data is not None else None,
        "source_bytes": len(data) if data is not None else None,
        "screen": screened,
        "original_300_identity_count": 300,
        "original_h5_exit": H5_EXIT,
        "screen_is_not_exhaustive_action_coverage": True,
        "issuer_dividends_total_return_cleared_count": 0,
        "market_price_return_promoted_to_economic_return": False,
        "live_capital_allowed": False,
    }
    envelope["envelope_sha256"] = digest(envelope)
    return envelope, data


def validate_p007_probe(
    value: dict[str, Any],
    *,
    repo_root: Path,
    source_raw: bytes | None,
) -> None:
    unsigned = copy.deepcopy(value)
    sealed = unsigned.pop("envelope_sha256", None)
    if sealed != digest(unsigned) or value.get("probe_id") != PROTOCOL:
        raise AlphaContractError("P007 P2 source-envelope signature mismatch")
    if (
        value.get("live_capital_allowed") is not False
        or value.get("issuer_dividends_total_return_cleared_count") != 0
        or value.get("screen_is_not_exhaustive_action_coverage") is not True
        or value.get("market_price_return_promoted_to_economic_return") is not False
        or value.get("original_300_identity_count") != 300
        or value.get("original_h5_exit") != H5_EXIT
    ):
        raise AlphaContractError("P007 P2 source probe incorrectly promotes investor returns")
    _attempt_id(value["attempt_id"])
    source = value["source_receipt"]
    if source.get("status") == "OK":
        if (
            not isinstance(source_raw, bytes)
            or not source_raw
            or len(source_raw) > MAX_SOURCE_BYTES
            or source.get("raw_sha256") != hashlib.sha256(source_raw).hexdigest()
            or value.get("source_raw_repo_path") != str(_source_path(source_raw))
            or value.get("source_bytes") != len(source_raw)
        ):
            raise AlphaContractError("P007 P2 original NSE source bytes modified")
    elif (
        source.get("status") != "FETCH_FAILED"
        or source_raw is not None
        or value.get("source_raw_repo_path") is not None
        or value.get("source_bytes") is not None
        or source.get("raw_sha256") is not None
    ):
        raise AlphaContractError("P007 P2 invalid failure-source evidence")
    original, selected, controls = load_original_hg009_sources(repo_root)
    again = build_action_hazard_audit(
        original=original,
        selected=selected,
        controls=controls,
        start_session=FIRST,
        end_session=H5_EXIT,
        original_action_raw=source_raw,
        action_receipt=source,
        prepared_at_utc=value["prepared_at_utc"],
    )
    validate_action_hazard_audit(again)
    if again != value["screen"]:
        raise AlphaContractError("P007 P2 source screen cannot replay original bytes")


def commit_probe(
    *,
    repo_root: Path,
    envelope: dict[str, Any],
    source_raw: bytes | None,
) -> Path:
    """Publish only unseen content-addressed raw and append-only attempt receipt."""
    validate_p007_probe(envelope, repo_root=repo_root, source_raw=source_raw)
    path = repo_root / ATTEMPTS / f"{envelope['attempt_id']}.json"
    if path.exists():
        raise AlphaContractError("P007 P2 immutable attempt ID already exists")
    if source_raw is not None:
        original = repo_root / _source_path(source_raw)
        original.parent.mkdir(parents=True, exist_ok=True)
        if original.exists() and original.read_bytes() != source_raw:
            raise AlphaContractError("P007 P2 content-addressed source collision")
        if not original.exists():
            original.write_bytes(source_raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(envelope, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def replay_all_probes(repo_root: Path) -> dict[str, Any]:
    attempts = repo_root / ATTEMPTS
    original_records = []
    if attempts.exists():
        for path in sorted(attempts.glob("*.json")):
            item = json.loads(path.read_text(encoding="utf-8"))
            if path.stem != item.get("attempt_id"):
                raise AlphaContractError("P007 P2 source attempt path or ID differs")
            raw_path = item.get("source_raw_repo_path")
            source = (repo_root / raw_path).read_bytes() if raw_path else None
            validate_p007_probe(item, repo_root=repo_root, source_raw=source)
            original_records.append({
                "attempt_id": item["attempt_id"],
                "status": item["source_receipt"]["status"],
                "source_state": item["screen"]["source_state"],
                "source_sha256": item["source_receipt"]["raw_sha256"],
                "envelope_sha256": item["envelope_sha256"],
                "hazards_observed_not_exhaustive": item["screen"]["observed_hazard_count"],
            })
    return {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "verified_attempt_count": len(original_records),
        "attempts": original_records,
        "economic_return_clearance_count": 0,
        "original_300_identity_count": 300,
        "live_capital_allowed": False,
    }
