"""Capture original INOXGREEN NSE shareholding master and selected Reg31 XBRL.

This independent 2,319-company-universe issuer probe deliberately DOES NOT
read U001/H023 source ledgers. It records original bytes or honest blockers.
It does not certify current fully diluted shares or any stock's return.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h023_acquisition import (
    H023AcquisitionError,
    fetch_master,
    fetch_xbrl,
    master_session,
    xbrl_session,
)
from marketlab.hg007_shp_source import (
    MASTER_URL,
    review_original_xbrl,
    select_latest_official_filing,
)

COLLECTOR_ID = "HG007-P010-INOXGREEN-ORIGINAL-SHP-SOURCE-ACQUISITION-v1"


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def attempt_official_shareholding_acquisition() -> tuple[dict[str, Any], dict[str, bytes]]:
    now = _utcnow()
    report: dict[str, Any] = {
        "schema_version": 1,
        "collector_id": COLLECTOR_ID,
        "issuer": "INOXGREEN",
        "source_master_url": MASTER_URL,
        "attempt_started_at_utc": now,
        "status": "MASTER_NOT_RETRIEVED",
        "master_source": None,
        "official_xbrl_review": None,
        "blocking_reason": None,
        "reported_pledge_change_verified": False,
        "current_esop_reconciled": False,
        "current_fd_shares_verified": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    files: dict[str, bytes] = {}
    try:
        session = master_session(timeout=16)
        response = fetch_master(session, symbol="INOXGREEN", timeout=22, attempts=1)
        raw = response.content
        observed = select_latest_official_filing(raw, captured_at_utc=_utcnow())
        files["master"] = raw
        report["master_source"] = observed
        report["status"] = "MASTER_CAPTURED"
    except (H023AcquisitionError, ValueError, TypeError) as exc:
        report["status"] = "MASTER_UNAVAILABLE_OR_MALFORMED"
        report["blocking_reason"] = f"{type(exc).__name__}: {exc}"[:360]
        return report, files

    source = observed.get("original_latest_visible_standard_quarter")
    if not isinstance(source, dict):
        report["status"] = "NO_CURRENT_STANDARD_QUARTER_SOURCE"
        report["blocking_reason"] = "Official NSE master yielded no valid published standard quarter"
        return report, files
    try:
        response = fetch_xbrl(
            xbrl_session(),
            url=source["xbrl_url"],
            timeout=22,
            attempts=1,
        )
        files["xbrl"] = response.content
        parsed = review_original_xbrl(
            observed,
            response.content,
            retrieved_at_utc=_utcnow(),
        )
        report["official_xbrl_review"] = parsed
        report["status"] = (
            "SEPTEMBER_30_ORIGINAL_XBRL_SOURCE_CONFLICT"
            if parsed["issuer_basic_qip_xbrl_conflict"]
            else "SEPTEMBER_30_ORIGINAL_REG31_OBSERVATION_NO_LATER_SHARES_CONFIRMED"
            if parsed["report_date"] == "2026-09-30"
            else "OLDER_QUARTER_SOURCE_ONLY_CURRENT_POST_QIP_NOT_RESOLVED"
        )
    except (H023AcquisitionError, ValueError, TypeError) as exc:
        report["status"] = "XBRL_SOURCE_UNAVAILABLE_OR_PARSER_BLOCKED"
        report["blocking_reason"] = f"{type(exc).__name__}: {exc}"[:360]
    report["completed_at_utc"] = _utcnow()
    return report, files


def retain_acquisition(
    out_dir: Path,
    report: dict[str, Any],
    original: dict[str, bytes],
) -> None:
    if report.get("collector_id") != COLLECTOR_ID:
        raise ValueError("unrecognized original shareholding source capture")
    if report.get("current_fd_shares_verified") is not False:
        raise ValueError("issuer-only capture cannot certify October fully diluted shares")
    if report.get("live_capital_allowed") is not False:
        raise ValueError("source acquisition must not enable capital")
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for key, raw in sorted(original.items()):
        if key not in {"master", "xbrl"} or not isinstance(raw, bytes) or not raw:
            raise ValueError("original NSE raw source kind/bytes invalid")
        sha = hashlib.sha256(raw).hexdigest()
        ext = "json" if key == "master" else "xml"
        filename = f"{key}-{sha}.{ext}"
        path = out_dir / "source" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("original NSE shareholding bytes hash collision")
        path.write_bytes(raw)
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("original source retention SHA mismatch")
        metadata[key] = {
            "sha256": sha,
            "bytes": len(raw),
            "original_file": f"source/{filename}",
        }
    source = report.get("master_source")
    if "master" in metadata and (
        not isinstance(source, dict)
        or source.get("original_master_sha256") != metadata["master"]["sha256"]
    ):
        raise ValueError("raw NSE shareholding master SHA does not match parsed manifest")
    xbrl = report.get("official_xbrl_review")
    if "xbrl" in metadata and xbrl is not None and (
        not isinstance(xbrl, dict)
        or xbrl.get("original_xbrl_sha256") != metadata["xbrl"]["sha256"]
    ):
        raise ValueError("original XBRL SHA differs from parsed source")
    report = {**report, "original_content_addressed_sources": metadata}
    out_file = out_dir / "receipt-v1.json"
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if out_file.exists() and out_file.read_text(encoding="utf-8") != text:
        raise ValueError("original source receipt cannot be overwritten")
    out_file.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    receipt, original = attempt_official_shareholding_acquisition()
    retain_acquisition(args.out_dir, receipt, original)
    print(json.dumps(
        {
            "collector_id": COLLECTOR_ID,
            "state": receipt["status"],
            "as_of_utc": receipt["attempt_started_at_utc"],
            "latest_quarter": (
                receipt["master_source"]["original_latest_visible_standard_quarter"][
                    "report_date"
                ]
                if receipt["master_source"]
                and receipt["master_source"]["original_latest_visible_standard_quarter"]
                else None
            ),
            "xbrl_observed": receipt["official_xbrl_review"] is not None,
            "current_fd_verified": False,
            "live_capital_allowed": False,
        },
        sort_keys=True, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
