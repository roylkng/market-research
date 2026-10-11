"""Acquire exact NSE 9 October 2026 EQ bhavcopy for five HG007 cases.

The whole original ZIP MUST match the previously independent SS002-P007
SHA-256. If NSE is unavailable or changed, no snapshot, stock price,
market cap, return outcome, or brokerage-fill is fabricated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.hg007_five_case_market_oct9 import (
    PINNED_ORIGINAL_NSE_SHA256,
    SOURCE_URL,
    build_five_case_price_context,
    load_frozen_five_sources,
    validate_five_case_price_context,
)

MAX_SOURCE_BYTES = 20_000_000


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def acquire(*, timeout: int = 30) -> tuple[dict, bytes | None]:
    if not 5 <= timeout <= 50:
        raise ValueError("official NSE timeout must be between 5 and 50 seconds")
    captured = _now()
    result = {
        "schema_version": 1,
        "source_url": SOURCE_URL,
        "captured_at_utc": captured,
        "status": "FETCH_FAILED",
        "http_status": None,
        "source_sha256": None,
        "original_source_byte_count": None,
        "error": None,
        "research_price_context_published": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    try:
        response = requests.get(
            SOURCE_URL,
            timeout=timeout,
            headers={
                "User-Agent": "marketlab-hg007-original-nse-evidence/1.0",
                "Accept": "application/zip,application/octet-stream",
            },
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        result["error"] = f"REQUEST_{type(exc).__name__}"
        return result, None
    result["captured_at_utc"] = _now()
    result["http_status"] = response.status_code
    if (
        getattr(response, "url", SOURCE_URL) != SOURCE_URL
        or 300 <= response.status_code < 400
    ):
        result["status"] = "UNFOLLOWED_REDIRECT"
        result["error"] = "NSE_SOURCE_REDIRECT_NOT_FOLLOWED"
        return result, None
    if response.status_code in (401, 403, 429):
        result["status"] = "ACCESS_BLOCKED"
        result["error"] = f"HTTP_{response.status_code}_NO_BYPASS"
        return result, None
    if response.status_code == 404:
        result["status"] = "SOURCE_NOT_PUBLISHED"
        result["error"] = "OFFICIAL_OCT9_BHAVCOPY_MISSING"
        return result, None
    if response.status_code != 200:
        result["status"] = "FETCH_FAILED"
        result["error"] = f"HTTP_{response.status_code}"
        return result, None
    raw = response.content
    if not isinstance(raw, bytes) or not 1000 <= len(raw) <= MAX_SOURCE_BYTES:
        result["status"] = "INVALID_SOURCE"
        result["error"] = "EMPTY_OVERSIZED_OR_NONBINARY_OFFICIAL_REPORT"
        return result, None
    actual = hashlib.sha256(raw).hexdigest()
    if actual != PINNED_ORIGINAL_NSE_SHA256:
        result["status"] = "SOURCE_DIGEST_MISMATCH"
        result["source_sha256"] = actual
        result["error"] = "NSE_SOURCE_BYTES_DIFFER_FROM_FROZEN_SS002_P007"
        return result, None
    result["status"] = "ORIGINAL_OCT9_UDIFF_BYTES_VERIFIED"
    result["source_sha256"] = actual
    result["original_source_byte_count"] = len(raw)
    return result, raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    hg005, p007, p033, receipts = load_frozen_five_sources(Path("."))
    receipt, raw = acquire(timeout=args.timeout)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        result = build_five_case_price_context(
            hg005, p007, p033,
            udiff_raw=raw,
            captured_at_utc=receipt["captured_at_utc"],
            provenance=receipts,
        )
        validate_five_case_price_context(result)
        destination = out / "original" / f"{receipt['source_sha256']}.zip"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError("original NSE ZIP SHA collision")
        destination.write_bytes(raw)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != PINNED_ORIGINAL_NSE_SHA256:
            raise ValueError("retained NSE original UDiFF bytes differ from SS002-P007")
        (out / "five-case-oct09-market-context-v1.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        receipt["research_price_context_published"] = True
        receipt["matched_frozen_case_count"] = len(result["price_context_rows"])
    (out / "acquisition-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
