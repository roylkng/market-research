"""Capture original BSE all-active-equity ISIN/industry evidence, once per run.

Accept only the public BSE original endpoint without redirect/circumvention.
Retain actual UTC, raw bytes if valid, or an immutable failure receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p035_bse_industry import (
    AUDIT_ID,
    CUSTODY,
    SOURCE_URL,
    archive,
    replay_originals,
)


def _fetch() -> tuple[int | None, bytes | None, str | None]:
    try:
        response = requests.get(
            SOURCE_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.bseindia.com/",
            },
            timeout=30,
            allow_redirects=False,
        )
        status = response.status_code
        raw = response.content if status == 200 else None
        return status, raw, None
    except requests.RequestException as exc:
        return None, None, type(exc).__name__


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--attempt-id")
    p.add_argument("--check", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        print(json.dumps(replay_originals(args.repo_root), sort_keys=True))
        return 0
    attempt_id = args.attempt_id
    if (
        not isinstance(attempt_id, str)
        or not 1 <= len(attempt_id) <= 80
        or not all(c.isascii() and (c.isalnum() or c in "-_") for c in attempt_id)
    ):
        raise AlphaContractError("P035 safe immutable source attempt id required")
    observed = datetime.now(UTC).isoformat()
    status, raw, error = _fetch()
    if status != 200 or raw is None:
        outcome = {
            "schema_version": 1,
            "audit_id": AUDIT_ID,
            "source_url": SOURCE_URL,
            "actual_first_observed_at_utc": observed,
            "state": "BLOCKED_BSE_ORIGINAL_ACCESS",
            "http_status": status,
            "error_class": error,
            "raw_sha256": None,
            "new_issuer_industries_source_verified": 0,
            "live_capital_allowed": False,
        }
    else:
        try:
            outcome = archive(
                root=args.repo_root,
                raw=raw,
                first_observed_at_utc=observed,
            )
            outcome["state"] = "BSE_ORIGINAL_EQUITY_SCHEMA_OBSERVED_NOT_NSE_FACTOR"
        except (AlphaContractError, ValueError, UnicodeError, KeyError) as exc:
            outcome = {
                "schema_version": 1,
                "audit_id": AUDIT_ID,
                "source_url": SOURCE_URL,
                "actual_first_observed_at_utc": observed,
                "state": "BLOCKED_BSE_ORIGINAL_SCHEMA",
                "http_status": status,
                "error_class": type(exc).__name__,
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_byte_count": len(raw),
                "new_issuer_industries_source_verified": 0,
                "live_capital_allowed": False,
            }
    outcome["attempt_receipt_sha256"] = digest(outcome)
    location = args.repo_root / CUSTODY / "attempts"
    location.mkdir(parents=True, exist_ok=True)
    target = location / f"attempt-{attempt_id}.json"
    if target.exists():
        raise AlphaContractError("P035 immutable attempt already exists")
    target.write_text(
        json.dumps(outcome, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "state": outcome["state"],
        "source_url": SOURCE_URL,
        "observed_at_utc": observed,
        "source_row_count": outcome.get("original_source_row_count"),
        "source_industry_field": outcome.get("source_industry_field"),
        "exact_isin_matches": (
            sum(x["matched"] for x in outcome["exact_frozen_nse_isin_by_arm"].values())
            if "exact_frozen_nse_isin_by_arm" in outcome else 0
        ),
        "original_industry_cells": (
            sum(x["source_labeled"] for x in
                outcome["nonempty_original_bse_industry_by_arm"].values())
            if "nonempty_original_bse_industry_by_arm" in outcome else 0
        ),
        "historic_Oct15_NSE_industry_alpha_admissible": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
