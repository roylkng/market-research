"""Capture official UK subsidiary scanned annual report with true retrieval clock."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError
from marketlab.l001_p021_srl_uk import SOURCE_URL
from marketlab.l001_p022_srl_pdf import PDF_DIR, capture_pdf


def _fetch(url: str) -> tuple[int | None, bytes | None]:
    if url != SOURCE_URL:
        raise AlphaContractError("L001 P022 fetch can only access original issuer URL")
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NSE-DiligenceAudit/1.0)",
        "Accept": "application/pdf",
    }
    response = requests.get(
        url, headers=headers, timeout=50, allow_redirects=False
    )
    return response.status_code, (
        response.content if response.status_code == 200 else None
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--run-id", required=True)
    args = p.parse_args()
    receipt = capture_pdf(
        fetch=_fetch,
        root=args.repo_root,
        actual_capture_utc=datetime.now(UTC),
    )
    path = args.repo_root / PDF_DIR / "attempts" / f"{args.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise AlphaContractError("L001 P022 attempted to overwrite source-capture history")
    path.write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "state": receipt["source_state"],
        "http_status": receipt["http_status"],
        "original_pdf_sha256": receipt["original_full_pdf_sha256"],
        "full_original_bytes_archived": receipt["original_bytes_archived"],
        "source_period_cashflow_machine_verified": False,
        "source_receipt_sha256": receipt["receipt_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
