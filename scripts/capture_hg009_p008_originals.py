"""Archive NSE FY26 original HTML, or retain an explicit failed-source receipt."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p008_capture import capture_issuer
from marketlab.hg009_p008_underwriting import load_sources

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; FinancialResearchAudit/1.0)",
    "Accept": "text/html,application/xhtml+xml",
})


def _fetch(url: str) -> tuple[int, bytes | None]:
    if not url.startswith(
        "https://nsearchives.nseindia.com/corporate/ixbrl/"
    ):
        raise AlphaContractError("P008 NSE source URL allowlist violation")
    response = SESSION.get(url, timeout=25, allow_redirects=False)
    data = response.content if response.status_code == 200 else None
    return response.status_code, data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--run-id", required=True)
    args = p.parse_args()
    facts = load_sources(args.repo_root)[0]["new_fy26"]["numeric_facts"]
    if len(facts) != 3:
        raise AlphaContractError("P008 pinned three issuer-FY26 fact table changed")
    root = args.repo_root
    receipt_dir = root / "research/hg009/p008-originals/attempts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for facts_row in facts:
        timestamp = datetime.now(UTC)
        receipt = capture_issuer(
            facts_row,
            fetch=_fetch,
            now_utc=timestamp,
            root=root,
        )
        path = receipt_dir / (
            f"{args.run_id}-{facts_row['symbol']}.json"
        )
        if path.exists():
            raise AlphaContractError("P008 receipt already exists: no clock overwrite")
        path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        reports.append({
            "symbol": facts_row["symbol"],
            "state": receipt["state"],
            "captured_at_utc": receipt["captured_at_utc"],
            "sha256": receipt.get("raw_sha256"),
        })
    print(json.dumps({
        "run": args.run_id,
        "original_source_receipts": reports,
        "fully_underwritten_equity_valuations_created": 0,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
