"""Capture the five remaining original NSE annual/quarterly issuer files.

A success means original bytes are archived, not that the financial facts or
issuer equity model are cleared. HTTP failures remain signed attempt records.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p009_originals import (
    ARCHIVE_ROOT,
    original_source_receipt,
    source_specifications,
    validate_original_receipt,
)

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; NSE-Filing-Custody-Research/1.0)",
    "Accept": "text/html,application/pdf,*/*",
})


def _fetch(url: str) -> tuple[int, bytes | None]:
    # Source URL is separately pinned and validated by source_specifications.
    response = _SESSION.get(url, timeout=28, allow_redirects=False)
    return response.status_code, (
        response.content if response.status_code == 200 else None
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--run-id", required=True)
    p.add_argument("--symbol")
    args = p.parse_args()
    root = args.repo_root
    docs = source_specifications(root)
    if args.symbol:
        docs = [row for row in docs if row["symbol"] == args.symbol]
        if not docs:
            raise AlphaContractError("P009 non-predeclared issuer not permitted")
    statuses = []
    for spec in docs:
        attempt_time = datetime.now(UTC)
        receipt = original_source_receipt(
            spec=spec,
            fetch=_fetch,
            recorded_at_utc=attempt_time,
            repo_root=root,
        )
        validate_original_receipt(receipt, root=root)
        target = root / ARCHIVE_ROOT / "attempts" / (
            f"{args.run_id}-{spec['document_id']}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise AlphaContractError("P009 attempt already sealed, no timestamp rewrite")
        target.write_text(
            json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        statuses.append({
            "document_id": spec["document_id"],
            "state": receipt["state"],
            "sha256": receipt["raw_sha256"],
            "actual_retrieved_at_utc": receipt["actual_retrieved_at_utc"],
        })
    print(json.dumps({
        "state": "SOURCE_ATTEMPTS_RECORDED",
        "files_attempted": len(statuses),
        "result": statuses,
        "issuer_cash_valuation_complete_count": 0,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
