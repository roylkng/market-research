"""Capture first actual FY25 ACE NSE consolidated issuer source by real UTC clock.

No inferred historic retrieval timestamp. A failed original source remains a
failed receipt, and cannot be quietly replaced by a current-year NSE source.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p017_ace_cash import (
    FIRST_RECEIPT,
    FY25_URL,
    capture_fy25_ace,
    extract_ace_fy25_original,
)

USER_AGENT = "Mozilla/5.0 (compatible; marketlab-source-verification/1.0)"


def _fetch(url: str) -> tuple[int, bytes | None]:
    if url != FY25_URL:
        raise AlphaContractError("P017 not the frozen FY25 original NSE filing")
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=30,
        allow_redirects=False,
    )
    return response.status_code, (
        response.content if response.status_code == 200 else None
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = args.repo_root
    attempts = root / "research/hg009/p017-originals/attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    result = capture_fy25_ace(
        fetch=_fetch,
        observed_at=datetime.now(UTC),
        root=root,
    )
    attempt = attempts / f"{args.run_id}-ACE-FY25.json"
    if attempt.exists():
        raise AlphaContractError("P017 immutable original source attempt collision")
    attempt.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if result["state"] == "ORIGINAL_NSE_FY25_CONSOLIDATED_CASHFLOW_REPLAYED":
        first = root / FIRST_RECEIPT
        if not first.exists():
            first.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        else:
            before = json.loads(first.read_text(encoding="utf-8"))
            signature = before.get("receipt_sha256")
            unsigned = dict(before)
            unsigned.pop("receipt_sha256", None)
            if signature != digest(unsigned):
                raise AlphaContractError("P017 first FY25 receipt was rewritten")
            if (
                before["source_sha256"] != result["source_sha256"]
                or before["state"] != result["state"]
            ):
                raise AlphaContractError("P017 different original FY25 source after first")
    print(json.dumps({
        "source_url": FY25_URL,
        "state": result["state"],
        "observed_at_utc": (
            result["observed_at_utc"]
            if "observed_at_utc" in result else result["captured_at_utc"]
        ),
        "source_sha256": result.get("source_sha256"),
        "issuer_FY25_FY26_cash_bridge_completed": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
