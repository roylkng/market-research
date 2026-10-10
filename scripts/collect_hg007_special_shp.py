"""Retrieve exact NSE 29 September INOXGREEN post-QIP special shareholding XBRL.

Original source master was captured 11 Oct, but the filing was broadcast
8 Oct. No third-party data, inferred pledge quantity, or trade target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h023_acquisition import H023AcquisitionError, fetch_xbrl, xbrl_session
from marketlab.hg007_special_shp import (
    AUDIT_ID,
    SPECIAL_URL,
    interpret_special_xbrl,
    verify_original_special_master,
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def collect_source(repo_root: Path) -> tuple[dict[str, Any], bytes | None]:
    original = verify_original_special_master(repo_root)
    record: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "original_master": original,
        "source_xbrl_url": SPECIAL_URL,
        "retrieved_at_utc": _now(),
        "status": "XBRL_SOURCE_UNAVAILABLE",
        "reason": None,
        "original_xbrl_sha256": None,
        "parsed_special_facts": None,
        "oct11_current_shares_certified": False,
        "pledge_quantity_4_9m_certified": False,
        "stock_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    try:
        response = fetch_xbrl(
            xbrl_session(), url=SPECIAL_URL, timeout=25.0, attempts=1
        )
    except (H023AcquisitionError, ValueError) as exc:
        record["reason"] = f"{type(exc).__name__}: {exc}"[:340]
        return record, None
    raw = response.content
    record["original_xbrl_sha256"] = hashlib.sha256(raw).hexdigest()
    record["original_xbrl_bytes"] = len(raw)
    try:
        facts = interpret_special_xbrl(
            original, raw, retrieved_at_utc=_now()
        )
    except (ValueError, TypeError) as exc:
        record["status"] = "ORIGINAL_XBRL_BYTES_CAPTURED_SEMANTICS_BLOCKED"
        record["reason"] = f"{type(exc).__name__}: {exc}"[:340]
    else:
        record["status"] = "ORIGINAL_QIP_SPECIAL_XBRL_SHARE_COUNTS_PARSED"
        record["parsed_special_facts"] = facts
    return record, raw


def save_source(out_dir: Path, report: dict[str, Any], raw: bytes | None) -> None:
    if (
        report.get("audit_id") != AUDIT_ID
        or report.get("live_capital_allowed") is not False
        or report.get("oct11_current_shares_certified") is not False
    ):
        raise ValueError("unrecognized or improperly promoted original source")
    out_dir.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        sha = hashlib.sha256(raw).hexdigest()
        if sha != report.get("original_xbrl_sha256"):
            raise ValueError("retained original XBRL SHA mismatch")
        dest = out_dir / "raw" / f"{sha}.xml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_bytes() != raw:
            raise ValueError("content-addressed original NSE XBRL mismatch")
        dest.write_bytes(raw)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            raise ValueError("failed original XBRL sha verification")
    elif report.get("original_xbrl_sha256") is not None:
        raise ValueError("no-source state cannot certify raw XBRL SHA")
    receipt_path = out_dir / "original-receipt-v1.json"
    serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if receipt_path.exists() and receipt_path.read_text(encoding="utf-8") != serialized:
        raise ValueError("immutable source receipt cannot be overwritten")
    receipt_path.write_text(serialized, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    report, raw = collect_source(args.repo_root)
    save_source(args.out_dir, report, raw)
    print(json.dumps({
        "audit_id": report["audit_id"],
        "status": report["status"],
        "original_xbrl_sha256": report["original_xbrl_sha256"],
        "reported_issued_basic_shares_as_of_sep29": (
            report["parsed_special_facts"]["reported_issued_basic_shares_as_of_sep29"]
            if report["parsed_special_facts"] else None
        ),
        "reported_fully_diluted_shares_as_of_sep29": (
            report["parsed_special_facts"]["reported_fully_diluted_shares_as_of_sep29"]
            if report["parsed_special_facts"] else None
        ),
        "promoter_pledge_boolean_as_of_report": (
            report["parsed_special_facts"]["promoter_pledge_boolean_as_of_report"]
            if report["parsed_special_facts"] else None
        ),
        "pledge_quantity_4_9m_certified": False,
        "current_oct11_fd_certified": False,
        "live_capital_allowed": False,
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
