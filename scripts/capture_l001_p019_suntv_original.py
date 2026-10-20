"""Fetch actual first-party Sun TV FY26 annual-report proof, never backdate.

Retain full original if <=8MB. Otherwise retain signed selected original pages
plus the full-retrieval SHA and mark full-original archival incomplete.
HTTP or PDF parsing failure yields an immutable non-promotable source receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p019_suntv_original import archive_pdf_receipt
from marketlab.l001_p019_suntv_rights import ANNUAL_REPORT_URL


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    directory = root / "research/l001/originals/suntv_fy26/attempts"
    directory.mkdir(parents=True, exist_ok=True)
    receipt_path = directory / f"{args.run_id}.json"
    if receipt_path.exists():
        raise AlphaContractError("P019 original retrieval observation ID reused")
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; original-issuer-document-audit)",
        "Accept": "application/pdf,application/octet-stream",
    }
    response = None
    failure = None
    body = None
    try:
        response = requests.get(
            ANNUAL_REPORT_URL,
            headers=headers,
            timeout=45,
            allow_redirects=False,
        )
        if response.status_code == 200:
            body = response.content
    except requests.RequestException as exc:
        failure = type(exc).__name__
    # Actual evidence clock is AFTER completion of the download attempt.
    captured = datetime.now(UTC)
    if response is not None and response.status_code == 200 and body is not None:
        try:
            report = archive_pdf_receipt(
                body, captured_at_utc=captured, root=root
            )
        except (AlphaContractError, ValueError, OSError) as exc:
            report = {
                "source_receipt_state": "BLOCKED_ORIGINAL_ISSUER_PDF_VALIDATION",
                "failure_class": type(exc).__name__,
                "raw_sha256_if_observed": hashlib.sha256(body).hexdigest(),
                "actual_retrieval_at_utc": captured.isoformat(),
                "original_full_raw_archived": False,
                "company_equity_value_authorized": False,
                "live_capital_allowed": False,
            }
        else:
            report["source_receipt_state"] = "ORIGINAL_PDF_EVIDENCE_CAPTURED"
    else:
        report = {
            "source_receipt_state": "BLOCKED_ORIGINAL_ISSUER_HTTP",
            "failure_class": failure,
            "http_status": None if response is None else response.status_code,
            "raw_sha256_if_observed": None,
            "actual_retrieval_at_utc": captured.isoformat(),
            "original_full_raw_archived": False,
            "company_equity_value_authorized": False,
            "live_capital_allowed": False,
        }
    report["actual_document_url"] = ANNUAL_REPORT_URL
    report["capture_run_id"] = args.run_id
    report["receipt_sha256"] = digest({
        k: v for k, v in report.items() if k != "receipt_sha256"
    })
    receipt_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "receipt_path": str(receipt_path.relative_to(root)),
        "state": report["source_receipt_state"],
        "source_sha256": report.get("full_original_pdf_sha256"),
        "full_original_archived": report.get("full_original_pdf_archived", False),
        "no_normalized_owner_cash": True,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
