"""One original NSE listed-security-master feasibility probe, source-only.

A 403 or unavailable NSE file remains an explicit failed receipt. Do not
circumvent origin access rules or substitute another date for Oct 21.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p034_mii_security import (
    SOURCE_URL,
    archive,
    replay_originals,
)


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--attempt-id", required=True)
    p.add_argument("--check", action="store_true")
    return p.parse_args()


def _fetch() -> tuple[int | None, bytes | None, str | None]:
    try:
        response = requests.get(
            SOURCE_URL,
            headers={
                "User-Agent": "market-research/1.0 (NSE public research source)",
                "Accept": "application/gzip,application/octet-stream",
            },
            timeout=25,
            allow_redirects=False,
        )
        status = response.status_code
        raw = response.content if status == 200 else None
        return status, raw, None
    except requests.RequestException as exc:
        return None, None, type(exc).__name__


def main() -> int:
    args = _args()
    if args.check:
        print(json.dumps(replay_originals(args.repo_root), sort_keys=True))
        return 0
    if (
        not args.attempt_id
        or len(args.attempt_id) > 80
        or not all(c.isalnum() or c in "_-" for c in args.attempt_id)
    ):
        raise AlphaContractError("P034 source attempt id is unsafe")
    observed = datetime.now(UTC).isoformat()
    status, raw, error = _fetch()
    if status != 200 or raw is None:
        report = {
            "protocol": "HG009-P034-20261021-NSE-CM-MII-SECURITY-MASTER-SCHEMA-v1",
            "original_url": SOURCE_URL,
            "first_observed_at_utc": observed,
            "state": "BLOCKED_ORIGINAL_NSE_ACCESS",
            "http_status": status,
            "error_class": error,
            "original_sha256": None,
            "company_sector_coverage_added": 0,
            "live_capital_allowed": False,
        }
    else:
        try:
            report = archive(
                root=args.repo_root,
                original_gzip=raw,
                first_observed_at_utc=observed,
            )
            report["state"] = "ORIGINAL_NSE_MII_SCHEMA_INSPECTED_NOT_ALPHA"
        except (AlphaContractError, UnicodeError, ValueError) as exc:
            report = {
                "protocol": "HG009-P034-20261021-NSE-CM-MII-SECURITY-MASTER-SCHEMA-v1",
                "original_url": SOURCE_URL,
                "first_observed_at_utc": observed,
                "state": "BLOCKED_SOURCE_SCHEMA_NOT_ASSUMED",
                "http_status": status,
                "error_class": type(exc).__name__,
                "original_sha256": hashlib.sha256(raw).hexdigest(),
                "original_byte_count": len(raw),
                "company_sector_coverage_added": 0,
                "live_capital_allowed": False,
            }
    receipt_dir = args.repo_root / "research/hg009/p034-mii-security/attempts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"attempt-{args.attempt_id}.json"
    report["attempt_receipt_sha256"] = digest(report)
    if path.exists():
        raise AlphaContractError("P034 attempt receipt already exists, no rewrite")
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "state": report["state"],
        "observed_at_utc": observed,
        "original_url": SOURCE_URL,
        "original_rows": report.get("original_instrument_row_count"),
        "exact_300_matches": report.get("exact_symbol_isin_count"),
        "sector_fields": report.get("published_column_names_that_look_like_sector"),
        "float_fields": report.get("published_column_names_that_look_like_float"),
        "sector_coverage_admitted_for_legacy_HG009": 0,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
